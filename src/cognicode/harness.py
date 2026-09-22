"""harness 层（#19 实现）：执行编排。

三件事（#19 正文 + 地图 Notes 锁定）：
1. **WorktreeManager**：每次任务 = fresh git worktree（克隆被测仓库，
   用户确认），harness 侧 `git diff` 收产物（ADR-0003 爆炸半径隔离）。
2. **ProbeRunner**：环境探测——定位仓库声明的构建/测试命令（probe.py），
   逐一执行、记录 exit code 与耗时；「成功」= 至少一条构建 exit 0 且
   至少一条测试 exit 0；探测结果决定任务生成上限（fail_env 降级路径）。
3. **run_task**：单任务编排——fresh worktree → executor.run（外层
   timeout 包裹）→ git diff 收产物 → 轨迹落盘。

判卷（五类 outcome）归 #20/#21；本层保证采集字段完整可审计。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from cognicode.executor import Executor, RunResult, TaskStats
from cognicode.probe import locate_probe_commands, probe_success

# 探测超时（#6 锁定：探测 30 分钟）
PROBE_TIMEOUT_S = 1800
# 单任务超时（#6 锁定：任务 15 分钟）
TASK_TIMEOUT_S = 900


class WorktreeError(Exception):
    """worktree 创建/使用失败（fail_env 类）。"""


@dataclass
class WorktreeManager:
    """管理「克隆被测仓库 → fresh worktree」生命周期。

    每次任务一个独立 worktree（clone 源 → worktree 追加），任务结束清理。
    source_repo 是已被克隆到本地的被测仓库（含 .git）。
    """

    source_repo: Path
    worktrees_dir: Path

    @contextmanager
    def worktree(self):
        """产出一个 fresh worktree（Path），退出时清理。"""
        wt_dir = None
        try:
            wt_dir = self._create()
            yield wt_dir
        finally:
            if wt_dir and wt_dir.exists():
                shutil.rmtree(wt_dir, ignore_errors=True)

    def _create(self) -> Path:
        if not (self.source_repo / ".git").exists():
            raise WorktreeError(
                f"源仓库 {self.source_repo} 不是 git 仓库（无 .git）"
            )
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        # UUID 避免快速连续采样在同一毫秒复用目录。
        wt_dir = self.worktrees_dir / f"wt-{uuid.uuid4().hex}"
        try:
            subprocess.run(
                ["git", "clone", "-q", "--no-hardlinks", str(self.source_repo), str(wt_dir)],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"git clone 失败: {e.stderr.decode()[:500]}") from e
        return wt_dir


def _run_probe_command(command: list[str], worktree: Path) -> dict[str, str | int]:
    """在探测 worktree 中执行真实命令并保留可审计诊断。

    返回值使用 shell 命令的退出码，而不是 ``Executor`` 的 Agent 进程码。
    命令定位器产出 argv，因此不使用 shell=True，避免探测命令注入。
    """
    try:
        completed = subprocess.run(
            command,
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
        )
        return {
            "exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
            "error": "",
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "exit_code": 124,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
            "error": f"命令超时（>{PROBE_TIMEOUT_S}s）",
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": 127,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": str(exc),
        }
    except OSError as exc:
        return {
            "exit_code": 126,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": str(exc),
        }


class ProbeRunner:
    """环境探测执行器：定位命令 → worktree 内逐条执行 → 判定。"""

    def __init__(self, executor: Executor):
        self.executor = executor

    def run(self, repo: Path) -> dict:
        """在 repo（已克隆）上执行探测。

        Returns:
            {
              "success": bool,        # probe_success 判定
              "degrade": bool,        # 探测全灭 → 整体降级（fail_env 路径）
              "exit_codes": {name: code},  # 命令真实退出码（兼容字段）
              "command_exit_codes": {name: code},
              "agent_exit_codes": {name: code},
              "durations": {name: ms},  # 命令执行耗时
              "diagnostics": {name: {...}},
              "notes": [...],
            }
        """
        commands, notes = locate_probe_commands(repo)
        # ``exit_codes`` 的正式语义是命令退出码；不要把 Agent 的
        # RunResult.exit_code 写进这里。后者只表示 pi 进程本身是否收尾。
        command_exit_codes: dict[str, int] = {}
        agent_exit_codes: dict[str, int] = {}
        durations: dict[str, int] = {}
        diagnostics: dict[str, dict] = {}
        mgr = WorktreeManager(source_repo=repo, worktrees_dir=repo.parent / ".cognicode-wts")

        for cmd in commands:
            agent_code: int | None = None
            agent_note = ""
            try:
                # Agent 和真实命令各用一个 pristine worktree。否则 Agent 可能
                # 修改依赖/生成物，导致后面的命令码不再代表冷启动仓库。
                with mgr.worktree() as agent_wt:
                    # 先保留 Agent 的冷启动执行与进程级结果，作为诊断信息；
                    # 但它不能代表 build/test 命令是否成功。
                    try:
                        result = self.executor.run(
                            " ".join(cmd.command),
                            worktree=agent_wt,
                            timeout_s=PROBE_TIMEOUT_S,
                        )
                        agent_code = result.exit_code
                        agent_note = result.outcome_note
                    except Exception as exc:
                        agent_code = 1
                        agent_note = f"{type(exc).__name__}: {exc}"

                with mgr.worktree() as command_wt:
                    t0 = time.time()
                    command_result = _run_probe_command(cmd.command, command_wt)
                    duration_ms = int((time.time() - t0) * 1000)
                    code = command_result["exit_code"]
                    diagnostic = {
                        "command": cmd.command,
                        "exit_code": code,
                        "duration_ms": duration_ms,
                        "stdout_tail": command_result["stdout_tail"],
                        "stderr_tail": command_result["stderr_tail"],
                        "agent_exit_code": agent_code,
                    }
                    if command_result["error"]:
                        diagnostic["error"] = command_result["error"]
            except WorktreeError as e:
                notes.append(f"{cmd.name}: worktree 失败（{e}）")
                code = -1
                duration_ms = 0
                diagnostic = {
                    "command": cmd.command,
                    "exit_code": code,
                    "duration_ms": duration_ms,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "agent_exit_code": agent_code,
                    "error": str(e),
                }

            command_exit_codes[cmd.name] = code
            durations[cmd.name] = duration_ms
            if agent_code is not None:
                agent_exit_codes[cmd.name] = agent_code
            diagnostics[cmd.name] = diagnostic
            if agent_code != 0:
                notes.append(f"{cmd.name}: Agent 进程 exit {agent_code}（{agent_note or '未正常收尾'}）")
            if code != 0:
                notes.append(
                    f"{cmd.name}: 命令 exit {code}（{diagnostic.get('stderr_tail') or diagnostic.get('stdout_tail') or '无诊断输出'}）"
                )

        success, reason = probe_success(command_exit_codes)
        notes.append(reason)
        return {
            "success": success,
            "degrade": not success,
            # 保留旧键，修正其语义为真实命令退出码。
            "exit_codes": command_exit_codes,
            "command_exit_codes": command_exit_codes,
            "agent_exit_codes": agent_exit_codes,
            "durations": durations,
            "diagnostics": diagnostics,
            "notes": notes,
        }


@dataclass(frozen=True)
class SampleResult:
    """一次任务采样的可审计结果及其产物位置。

    ``sample_id`` 是全局运行目录内的定位键；所有路径都指向运行目录下的
    持久产物，worktree 本身不属于审计产物，采样结束后会被删除。
    """

    task_id: str
    sample_id: str
    result: RunResult | None
    trace_file: Path
    diff_file: Path
    result_file: Path


def run_task(
    executor: Executor,
    worktree_mgr: WorktreeManager,
    prompt: str,
    task_id: str,
    run_dir: Path,
    timeout_s: int = TASK_TIMEOUT_S,
) -> RunResult | None:
    """编排单任务执行。

    Args:
        executor: 执行者（PiExecutor 或假 executor）。
        worktree_mgr: worktree 管理器（每任务 fresh）。
        prompt: 任务描述。
        task_id: 任务标识（轨迹文件名）。
        run_dir: 运行目录（.cognicode/<run-id>/，落 traces/ 与 diff）。
        timeout_s: 外层超时（#6：任务 15 分钟）。

    Returns:
        RunResult；worktree 创建失败返回 None（fail_env 信号）。
    """
    trace_dir = run_dir / "traces"
    trace_file = trace_dir / f"{task_id}.jsonl"
    diff_file = run_dir / "diffs" / f"{task_id}.diff"

    try:
        with worktree_mgr.worktree() as wt:
            try:
                result = executor.run(
                    prompt, worktree=wt, timeout_s=timeout_s, trace_file=trace_file,
                )
            except Exception as exc:
                # 外部 executor 崩溃是一次可观测的任务结果，不应让整个采样
                # 中断；结果 JSON 会将其标记为 fail_env，避免计入有效样本。
                result = RunResult(
                    ok=False,
                    exit_code=1,
                    trace_file=trace_file,
                    stderr_tail=f"{type(exc).__name__}: {exc}",
                    outcome_note="crash",
                )
                trace_file.parent.mkdir(parents=True, exist_ok=True)
                _append_trace_event(trace_file, {
                    "type": "executor_crash",
                    "error": result.stderr_tail,
                })

            # 统一由 harness 决定产物路径，避免 executor 返回的路径破坏
            # task/sample 定位契约。
            if not trace_file.exists():
                trace_file.parent.mkdir(parents=True, exist_ok=True)
                trace_file.touch()

            # 收产物：harness 侧 git diff（fresh worktree 的改动）。即使
            # diff 命令失败，也保留空 diff 文件，保证目录契约稳定。
            diff_text, diff_error = _collect_diff(wt)
            diff_file.parent.mkdir(parents=True, exist_ok=True)
            diff_file.write_text(diff_text, encoding="utf-8")
            if diff_error:
                result = replace(
                    result,
                    stderr_tail=(result.stderr_tail + "\n" + diff_error).strip(),
                    outcome_note=result.outcome_note or "artifact_error",
                )
            return replace(
                result,
                trace_file=trace_file,
                diff=diff_text,
            )
    except WorktreeError:
        return None


def _append_trace_event(trace_file: Path, event: dict) -> None:
    """追加 harness 事件，不覆盖 executor 已经写入的 trace。"""
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    with trace_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def _collect_diff(worktree: Path) -> tuple[str, str | None]:
    """收集已跟踪与未跟踪改动，避免新建测试文件从 diff 中消失。"""
    try:
        tracked_result = subprocess.run(
            ["git", "-C", str(worktree), "diff", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        if tracked_result.returncode != 0:
            return "", f"diff collection failed: {tracked_result.stderr[-500:]}"
        untracked_result = subprocess.run(
            ["git", "-C", str(worktree), "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=30,
        )
        if untracked_result.returncode != 0:
            return "", f"untracked file listing failed: {untracked_result.stderr[-500:]}"
        parts = [tracked_result.stdout]
        for name in untracked_result.stdout.splitlines():
            path = worktree / name
            if path.is_file():
                extra = subprocess.run(
                    ["git", "diff", "--no-index", "--", "/dev/null", str(path)],
                    capture_output=True, text=True, timeout=30,
                )
                # git diff --no-index 用 1 表示「有差异」，这仍是成功收集。
                if extra.returncode not in (0, 1):
                    return "", f"untracked diff failed for {name}: {extra.stderr[-500:]}"
                if extra.stdout:
                    parts.append(extra.stdout)
        return "".join(parts), None
    except Exception as exc:
        return "", f"diff collection failed: {type(exc).__name__}: {exc}"


def _result_payload(task_id: str, sample_id: str, result: RunResult | None) -> dict:
    """把任务级结果编码成稳定、无 Path 对象的 JSON 审计记录。"""
    if result is None:
        return {
            "task_id": task_id,
            "sample_id": sample_id,
            "ok": False,
            "exit_code": None,
            "outcome_note": "worktree_error",
            "outcome_category": "fail_env",
            "trace_file": None,
            "diff_file": None,
            "result_file": None,
            "stats": asdict(result.stats) if result else asdict(TaskStats()),
        }
    payload = asdict(result)
    payload["trace_file"] = str(result.trace_file) if result.trace_file else None
    payload["stats"] = asdict(result.stats)
    payload["outcome_category"] = _execution_category(result)
    payload.update({"task_id": task_id, "sample_id": sample_id})
    return payload


def _execution_category(result: RunResult) -> str | None:
    """映射可观测的 executor 状态；最终判卷仍由 harness 负责。"""
    if result.outcome_note in {"crash", "artifact_error"}:
        return "fail_env"
    if result.outcome_note == "timeout" or result.exit_code == 124:
        return "fail_budget"
    return None


def _artifact_id(task_id: str, sample_number: int) -> str:
    """将任务标识编码为 run_dir 内安全且稳定的文件键。"""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id).strip("._") or "task"
    if safe != task_id or ".." in task_id:
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12]
        safe = f"{safe}-{digest}"
    return f"{safe}__sample-{sample_number}"


def run_samples(
    executor: Executor,
    worktree_mgr: WorktreeManager,
    prompt: str,
    task_id: str,
    sample_count: int,
    run_dir: Path,
    timeout_s: int = TASK_TIMEOUT_S,
) -> list[SampleResult]:
    """独立重复执行一个合成任务，并保留每个 sample 的运行产物。

    每次循环都创建新的 fresh worktree；``run_task`` 返回后 worktree 已清理，
    但 ``traces/``, ``diffs/`` 和 ``results/`` 下的审计文件继续保留。
    """
    if sample_count < 1:
        raise ValueError("sample_count 必须至少为 1")

    results: list[SampleResult] = []
    for index in range(1, sample_count + 1):
        sample_id = f"{task_id}/sample-{index}"
        artifact_id = _artifact_id(task_id, index)
        result = run_task(
            executor=executor,
            worktree_mgr=worktree_mgr,
            prompt=prompt,
            task_id=artifact_id,
            run_dir=run_dir,
            timeout_s=timeout_s,
        )
        trace_file = run_dir / "traces" / f"{artifact_id}.jsonl"
        diff_file = run_dir / "diffs" / f"{artifact_id}.diff"
        result_file = run_dir / "results" / f"{artifact_id}.json"
        # 即使 worktree 创建失败，也为该 sample 保留稳定的 trace/diff
        # 占位文件；结果 JSON 会明确记录 worktree_error。
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        diff_file.parent.mkdir(parents=True, exist_ok=True)
        trace_file.touch(exist_ok=True)
        diff_file.touch(exist_ok=True)
        result_file.parent.mkdir(parents=True, exist_ok=True)
        payload = _result_payload(task_id, sample_id, result)
        payload.update({
            "trace_file": str(trace_file),
            "diff_file": str(diff_file),
            "result_file": str(result_file),
        })
        result_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        results.append(SampleResult(
            task_id=task_id,
            sample_id=sample_id,
            result=result,
            trace_file=trace_file,
            diff_file=diff_file,
            result_file=result_file,
        ))
    return results
