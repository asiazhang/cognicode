"""pi executor（#19 实现，ADR-0005：pi 是唯一执行者）。

用 pi 0.84.3 `--mode rpc` 长驻协议驱动合成任务：
stdin 发命令（prompt / get_session_stats），stdout 收 JSONL 事件流。

采集自算（pi-schema.md §7 归一化口径，pi 无 CodeBuddy 的
result.subtype/duration_ms/num_turns）：
- 轮次 = turn_start 计数
- 时长 = 首 message_start → agent_settled 的时间戳差（毫秒）
- token = get_session_stats.tokens（会话级聚合）
- 结局 = 是否等到 agent_settled
- 退出码三态：0 正常 / 1 参数错误 / 124 外层 timeout 杀

测量隔离固定清单（pi-schema.md §6 + ADR-0003）：
`-p --mode rpc --no-session --no-approve -nc --no-skills --no-prompt-templates
--no-themes` + 显式 `-e` 加载 provider 扩展与测量隔离扩展
（--no-* 禁发现但显式加载仍生效）。不显式 --provider（#28 §9 踩坑：
显式传会触发模型目录刷新时序 bug）。

5 个已实测坑内置规避（pi-schema.md §9）：
1. provider 目录刷新预热：首次跑前 pi --list-models
2. stdin 保持打开：子进程 stdin 一直 open，事件结束后才 close
3. 显式 -e 加载 provider 扩展（headless 不自动加载 settings packages）
4. stats 等 agent_settled：settled 后才发 get_session_stats
5. --no-* 全禁组合在带项目资源 cwd 触发 model: unknown：本机规避是
   不显式 --provider + 固定模型 + -e 扩展注册 provider

max-turns 50（#6 锁定）由测量隔离扩展实现（turn 计数 + tool_call
block+terminate 早停 + ctx.abort 兜底），见 ext/cognicode-harness-ext.ts。
"""

from __future__ import annotations

import json
import queue
import selectors
import shutil
import subprocess
import threading
import time
from pathlib import Path

from cognicode.executor import Executor, RunResult, TaskStats

# pi 0.84.3 固定模型（地图 Notes 锁定：tencent-copilot/deepseek-v4-flash-ioa）
DEFAULT_MODEL = "tencent-copilot/deepseek-v4-flash-ioa"

# 测量隔离固定清单（pi-schema.md §6，除 -e 外的 --no-* 全禁 + -p 单发）
# 注意：--no-extensions 与显式 -e 不冲突（禁发现，显式加载仍生效）
BASE_ISOLATION_ARGS = [
    "--no-session",
    "--no-approve",
    "-nc",  # --no-context-files
    "--no-skills",
    "--no-prompt-templates",
    "--no-themes",
]


class PiExecutor:
    """pi RPC executor：一次 run() = 一次 prompt + 事件采集 + stats。"""

    def __init__(
        self,
        *,
        pi_cmd: list[str] | None = None,
        pi_args: list[str] | None = None,
        ext_dir: str | Path | None = None,
        model: str = DEFAULT_MODEL,
        max_turns: int = 50,
        read_only: bool = False,
        list_models_prewarm: bool = True,
        provider_ext: str | Path | None = None,
    ) -> None:
        """Args:
            pi_cmd: pi 可执行（默认 ["pi"]；测试注入 fake）。
            pi_args: 附加参数（测试注入，如 --sleep-before-response）。
            ext_dir: 测量隔离扩展所在目录（src/cognicode/ext）。
                若提供，加载 harness 扩展（max-turns 早停）。
            model: 固定模型串（ADR-0003 版本精确钉死）。
            max_turns: 轮次上限（#6 锁定 50，传扩展 env）。
            read_only: 只读工具门（检索/定位类任务用；修改类关闭）。
            list_models_prewarm: 首次跑前 pi --list-models 预热
                （pi-schema.md §9 坑 1）。
            provider_ext: provider 扩展路径（headless 需显式 -e 加载，
                pi-schema.md §9 坑 3）。默认探测本机 kit。
        """
        self.pi_cmd = pi_cmd if pi_cmd is not None else ["pi"]
        self.pi_args = list(pi_args or [])
        self.model = model
        self.max_turns = max_turns
        self.read_only = read_only
        self.ext_dir = Path(ext_dir) if ext_dir else None
        self.provider_ext = Path(provider_ext) if provider_ext else None
        self._prewarmed = not list_models_prewarm

    # ------------------------------------------------------------------
    # 扩展定位
    # ------------------------------------------------------------------
    def _harness_ext(self) -> Path | None:
        """测量隔离扩展路径（包内 src/cognicode/ext/cognicode-harness-ext.ts）。"""
        if self.ext_dir:
            p = Path(self.ext_dir) / "cognicode-harness-ext.ts"
            return p.resolve() if p.exists() else None
        here = Path(__file__).resolve().parent
        p = here / "ext" / "cognicode-harness-ext.ts"
        return p if p.exists() else None

    def _resolve_provider_ext(self) -> Path | None:
        if self.provider_ext:
            return Path(self.provider_ext).resolve()
        # 默认：本机 pi-codebuddy-kit（#28 实测路径）
        kit = Path("/root/.pi/agent/git/github.com/asiazhang/pi-codebuddy-kit")
        return kit if kit.exists() else None

    def _build_cmd(self) -> list[str]:
        cmd = list(self.pi_cmd)
        # 附加参数（测试注入，如 --sleep-before-response）始终追加在 pi 后
        cmd += self.pi_args
        cmd += ["--mode", "rpc", "--model", self.model]
        cmd += BASE_ISOLATION_ARGS
        ext = self._harness_ext()
        if ext:
            cmd += ["-e", str(ext)]
        # 显式 -e 加载 provider 扩展（headless 不自动加载 settings packages）
        pext = self._resolve_provider_ext()
        if pext:
            cmd += ["-e", str(pext)]
        # 注意：pi CLI 无 --max-turns（实测 0.84.3 --help 无此参数），
        # 轮次上限由 harness 扩展 env 控制（见 _build_env）
        return cmd

    def _build_env(self) -> dict[str, str]:
        """子进程环境：注入 harness 扩展配置（env 方案，getFlag 在 RPC 不可用）。"""
        import os

        env = dict(os.environ)
        env["HARNESS_MAX_TURNS"] = str(self.max_turns)
        env["HARNESS_READ_ONLY"] = "1" if self.read_only else "0"
        env.setdefault("HARNESS_NO_SUBMIT", "0")
        return env

    # ------------------------------------------------------------------
    # 预热（坑 1）
    # ------------------------------------------------------------------
    def prewarm(self) -> None:
        """pi --list-models 预热模型目录（首次跑前调用一次）。"""
        if self._prewarmed:
            return
        try:
            subprocess.run(
                ["pi", "--list-models"],
                capture_output=True, timeout=120,
            )
        except Exception:
            pass
        self._prewarmed = True

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(
        self,
        prompt: str,
        worktree: Path,
        *,
        timeout_s: int = 900,
        trace_file: Path | None = None,
    ) -> RunResult:
        """执行一次合成任务。

        Args:
            prompt: 任务描述（prompt 消息）。
            worktree: 被测仓库 worktree（cwd = worktree）。
            timeout_s: 外层超时（#6：任务 15 分钟 / 探测 30 分钟）。
            trace_file: 轨迹落盘路径（JSONL 全量事件）。

        Returns:
            RunResult：采集字段完整；判卷（五类）归 #20/#21。
        """
        self.prewarm()
        cmd = self._build_cmd()
        env = self._build_env()
        t0 = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(worktree),
                env=env,
            )
        except FileNotFoundError:
            return RunResult(
                ok=False, exit_code=127, outcome_note="pi 可执行未找到",
                stderr_tail=f"命令 {cmd[0]!r} 不存在",
            )

        events: list[dict] = []
        stats: TaskStats | None = None
        stderr_tail = ""
        outcome_note = ""
        timed_out = False

        # 发 prompt（保持 stdin 打开，坑 2）
        try:
            proc.stdin.write(json.dumps({"type": "prompt", "message": prompt}) + "\n")
            proc.stdin.flush()
        except Exception:
            pass

        # 后台线程持续读 stdout 塞队列（避免 select+readline 竞态导致阻塞/漏读）
        evq: queue.Queue = queue.Queue()

        def _pump() -> None:
            try:
                for line in proc.stdout:
                    evq.put(line)
            except Exception:
                pass
            finally:
                evq.put(None)  # EOF 哨兵

        pump = threading.Thread(target=_pump, daemon=True)
        pump.start()

        def read_event(timeout: float) -> dict | None:
            """等 timeout 秒内取一个事件；超时/EOF 返回 None。"""
            try:
                line = evq.get(timeout=timeout)
            except queue.Empty:
                return None
            if line is None:
                return None
            try:
                return json.loads(line)
            except Exception:
                return None

        # 轮询 stdout，等 agent_settled
        deadline = time.time() + timeout_s
        seen_settled = False
        first_msg_ts: int | None = None
        settled_ts: int | None = None
        turn_count = 0

        while time.time() < deadline:
            if proc.poll() is not None:
                # 进程提前退出（exit 1 参数错误等）
                break
            ev = read_event(0.25)
            if ev is None:
                # 无新事件：检查进程是否退出；未退出则继续等（保留超时检测）
                if proc.poll() is not None:
                    break
                continue
            etype = ev.get("type")
            events.append(ev)

            if etype == "turn_start":
                turn_count += 1
            if etype == "message_start" and first_msg_ts is None:
                ts = ev.get("message", {}).get("timestamp")
                if ts is not None:
                    first_msg_ts = int(ts)
            if etype == "agent_settled":
                seen_settled = True
                ts = ev.get("timestamp")
                settled_ts = int(ts) if ts is not None else int(time.time() * 1000)
                # 等 stats：settled 后发 get_session_stats（坑 4）
                break

        if not seen_settled:
            # 没等到 settled：可能超时或进程异常退出
            if proc.poll() is None:
                # 还在跑 → 超时，kill
                timed_out = True
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
                outcome_note = "timeout"
                # 外层 timeout 语义：exit 124
                exit_code = 124
            else:
                # 进程自己退出（exit 1）
                exit_code = proc.returncode
                outcome_note = f"进程提前退出 rc={exit_code}"
        else:
            # settled 已到：发 get_session_stats 收尾
            try:
                proc.stdin.write(json.dumps({"type": "get_session_stats"}) + "\n")
                proc.stdin.flush()
            except Exception:
                pass
            # 短暂收 stats 响应（非阻塞，最多 5 秒）
            stats_deadline = time.time() + 5.0
            while time.time() < stats_deadline and proc.poll() is None:
                ev = read_event(0.25)
                if ev is None:
                    continue
                if ev.get("type") == "response" and ev.get("command") == "get_session_stats":
                    data = ev.get("data") or {}
                    stats = _stats_from_session(data, turn_count, first_msg_ts, settled_ts)
                    break

            # 正常收尾：close stdin 让 pi 优雅退出（RPC 长驻模式 stdin EOF 即退出），
            # 绝不 terminate（会留下 -15 退出码，且真实 pi 无收尾逻辑）
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            exit_code = proc.returncode if proc.returncode is not None else 0
            outcome_note = "settled" if seen_settled else outcome_note

        # stderr 尾部（诊断用）
        try:
            err = proc.stderr.read()
            stderr_tail = err[-2000:] if err else ""
        except Exception:
            pass

        # 轨迹落盘
        if trace_file:
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            with open(trace_file, "w", encoding="utf-8") as f:
                for ev in events:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")

        # 归一化统计
        if stats is None:
            stats = TaskStats(
                num_turns=turn_count,
                wall_time_ms=int((time.time() - t0) * 1000),
                settled=seen_settled,
            )

        # ok = exit 0 且等到 settled（进程级成功；任务成败由判卷定）
        ok = (exit_code == 0) and seen_settled

        return RunResult(
            ok=ok,
            exit_code=exit_code,
            trace_file=trace_file,
            diff="",  # diff 由 harness 侧 git diff 收（本层不执行 git）
            stats=stats,
            stderr_tail=stderr_tail,
            outcome_note=outcome_note if outcome_note else ("settled" if seen_settled else "unknown"),
        )


def _stats_from_session(
    data: dict, turn_count: int, first_msg_ts: int | None, settled_ts: int | None
) -> TaskStats:
    """从 get_session_stats 响应归一化 TaskStats（pi-schema.md §7）。"""
    tokens = data.get("tokens") or {}
    wall = 0
    if first_msg_ts is not None and settled_ts is not None:
        wall = max(0, settled_ts - first_msg_ts)
    return TaskStats(
        num_turns=turn_count,
        wall_time_ms=wall,
        input_tokens=int(tokens.get("input", 0)),
        output_tokens=int(tokens.get("output", 0)),
        cache_read_tokens=int(tokens.get("cacheRead", 0)),
        cache_write_tokens=int(tokens.get("cacheWrite", 0)),
        total_tokens=int(tokens.get("total", 0)),
        tool_calls=0,  # 工具调用由轨迹事件统计（harness 侧），此处留 0
        settled=True,
    )
