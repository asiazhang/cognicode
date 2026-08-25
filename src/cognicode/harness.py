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

import json
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cognicode.executor import Executor, RunResult
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
        wt_dir = self.worktrees_dir / f"wt-{int(time.time() * 1000)}"
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
              "exit_codes": {name: code},
              "durations": {name: ms},
              "notes": [...],
            }
        """
        commands, notes = locate_probe_commands(repo)
        exit_codes: dict[str, int] = {}
        durations: dict[str, int] = {}
        mgr = WorktreeManager(source_repo=repo, worktrees_dir=repo.parent / ".cognicode-wts")

        for cmd in commands:
            t0 = time.time()
            try:
                with mgr.worktree() as wt:
                    # 探测 = 让 agent 在 fresh worktree 里跑构建/测试
                    result = self.executor.run(
                        " ".join(cmd.command),
                        worktree=wt,
                        timeout_s=PROBE_TIMEOUT_S,
                    )
                    code = result.exit_code if result.ok else (result.exit_code or 1)
            except WorktreeError as e:
                notes.append(f"{cmd.name}: worktree 失败（{e}）")
                code = -1
            exit_codes[cmd.name] = code
            durations[cmd.name] = int((time.time() - t0) * 1000)

        success, reason = probe_success(exit_codes)
        notes.append(reason)
        return {
            "success": success,
            "degrade": not success,
            "exit_codes": exit_codes,
            "durations": durations,
            "notes": notes,
        }


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
            result = executor.run(
                prompt, worktree=wt, timeout_s=timeout_s, trace_file=trace_file,
            )
            # 收产物：harness 侧 git diff（fresh worktree 的改动）
            try:
                diff = subprocess.run(
                    ["git", "-C", str(wt), "diff", "HEAD"],
                    capture_output=True, text=True, timeout=30,
                )
                result = RunResult(
                    ok=result.ok, exit_code=result.exit_code,
                    trace_file=result.trace_file, diff=diff.stdout,
                    stats=result.stats, stderr_tail=result.stderr_tail,
                    outcome_note=result.outcome_note,
                )
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(diff.stdout, encoding="utf-8")
            except Exception:
                pass
            return result
    except WorktreeError as e:
        return None
