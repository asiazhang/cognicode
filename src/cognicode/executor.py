"""executor 抽象接口（#19 实现）。

ADR-0005 决策：执行者 = 仅 pi（本机 0.84.3，dogfooding），pi 是唯一实现；
CodeBuddy 路径保留于接口后（可回退）。harness 采集字段由 executor 自算：
pi 无 CodeBuddy 的 result.subtype / duration_ms / num_turns（pi-schema.md §3），
轮次 = turn_start 计数、时长 = 事件时间戳差、token = get_session_stats、
结局 = 是否等到 agent_settled + 验收测试（判卷归 #20/#21，本层只采集）。

本模块只定义接口与数据结构（纯协议，无 I/O）；实现见 pi_executor.py。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TaskStats:
    """一次任务运行的采集统计（executor 自算，pi-schema.md §7 归一化口径）。

    字段对齐 #6 测量协议第 4 项：效率类（token/轮次/墙钟）取 success 运行
    中位数；cost 本机恒 0 不可用（pi-schema.md §TL;DR#2），不采。
    """

    # 轮次 = turn_start 计数（与 assistantMessages 一致，即模型调用次数）
    num_turns: int = 0
    # 墙钟 = 事件时间戳差（首 message_start → agent_settled，毫秒）
    wall_time_ms: int = 0
    # token（会话级聚合，get_session_stats.tokens）
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    # 推理 token（pi 独有，CodeBuddy 无对应）
    reasoning_tokens: int = 0
    # 工具调用计数（tool_execution_start 事件数）
    tool_calls: int = 0
    # 是否等到 agent_settled（终局信号，pi-schema.md §TL;DR#4）
    settled: bool = False


@dataclass(frozen=True)
class RunResult:
    """一次任务执行的结果（executor 返回给 harness 消费）。

    判卷（五类 outcome）归 #20/#21；本层只保证采集字段完整可审计。
    """

    # 执行是否成功（进程级）：exit 0 且等到 agent_settled。
    # 注意：不等于任务判卷通过——成功率由 harness 的验收测试判定（ADR-0002）。
    ok: bool
    # 退出码（pi 0.84.3 仅 0/1/124 三态；124 = 外层 timeout 杀）
    exit_code: int
    # 事件轨迹落盘路径（.cognicode/<run-id>/traces/<task>.jsonl），harness 侧写入
    trace_file: Path | None = None
    # 产物 diff（fresh worktree 上 git diff 的输出），harness 侧写入
    diff: str = ""
    # 采集统计（agent_settled 后 get_session_stats 的值）
    stats: TaskStats = field(default_factory=TaskStats)
    # stderr 尾部（参数错误等诊断用）
    stderr_tail: str = ""
    # 结局说明：settled / timeout / aborted / error
    outcome_note: str = ""


class Executor(Protocol):
    """执行者抽象：把「一个合成任务」跑成一个 RunResult。

    唯一实现 = PiExecutor（ADR-0005）；接口留缝给未来其他 agent 回退。
    """

    def run(
        self,
        prompt: str,
        worktree: Path,
        *,
        timeout_s: int = 900,
        trace_file: Path | None = None,
    ) -> RunResult: ...
