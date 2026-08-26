"""判卷：结果分类 + 判定层（#6 五类，判定归 #21 实现）。

五类（#6 锁定）：
- success: 判卷通过（F2P 通过且 P2P 无回归 / 位置匹配 / 探测回路跑通）
- fail_incorrect: 正常跑完但判卷不过（含破坏 P2P 的「解出但炸了别处」）
- fail_budget: 触及 max-turns 或墙钟超时
- fail_env: harness 侧环境故障（worktree 损坏、agent 进程崩溃、网络故障）

前三类计入统计；fail_env 剔除并重跑（最多重跑 2 次，>50% 标 harness-unstable）。

## 判定层（#21）

judge_result 把一次任务运行（RunResult + 交卷/测试结果）归入五类之一，
纯函数、无 I/O，可用构造假数据单测（#24 done 标准 2）：
- 修改类：F2P/P2P 双闸（f2p_before=True 契约；F2P 红→绿且 P2P 保绿 = success）
- 检索类：符号级位置匹配（submit_result 交卷 verdict ↔ ground_truth）
- 定位类：对照注入点（verdict ↔ injection.file/line，行容差 ±2）
- fail_budget：exit 124 / timeout / max-turns 触顶（budget 标记）
- fail_env：worktree 失败（result=None）或进程崩溃（未 settled 且非 timeout 码）

交卷解析：parse_submit_verdict 从轨迹（JSONL）提取 submit_result 的
`tool_execution_end.result.details.verdict`（#29 实测 details 字段）。
"""

from __future__ import annotations

import json
import re
from typing import Iterable

# 五类互斥，顺序即文档；fail_env 恒为末位（剔除类）。
OUTCOME_CATEGORIES: list[str] = [
    "success",
    "fail_incorrect",
    "fail_budget",
    "fail_env",
]

# 定位类行号容差（注入点行附近都算命中；#5 符号级匹配精神）
_LINE_TOLERANCE = 2

# 计入统计的类别（前三类）；fail_env 剔除。
_COUNTED_CATEGORIES = frozenset(OUTCOME_CATEGORIES[:-1])


def classify_verdict(category: str) -> str:
    """校验判卷类别属于五类之一，原样返回。

    Raises:
        ValueError: 未知类别（例如 agent 自报告混入的非约定值）。
    """
    if category not in OUTCOME_CATEGORIES:
        raise ValueError(
            f"未知判卷类别 {category!r}；合法类别：{OUTCOME_CATEGORIES}"
        )
    return category


def is_counted(category: str) -> bool:
    """该类别是否计入统计（前三类计，fail_env 剔）。"""
    classify_verdict(category)  # 先校验
    return category in _COUNTED_CATEGORIES


# ---------------------------------------------------------------------------
# 判定层（#21）：位置匹配
# ---------------------------------------------------------------------------


def match_location(verdict: str | None, ground_truth: str) -> bool:
    """检索类符号级位置匹配：交卷 verdict 命中 ground_truth（file::name）。

    #5 锁定符号级匹配（file + 名称，非行号）。匹配规则：ground_truth 的
    文件名末段（Cart.php）与符号名（index）都出现在 verdict（大小写不敏感）
    即命中——容忍全路径差异与 #28 实测的 `::index()` 带括号形态。
    同名不同文件（Order.php::index vs Cart.php::index）不误报。
    """
    if not verdict or not ground_truth:
        return False
    file_part, sep, name = ground_truth.partition("::")
    if not sep:
        return False
    base = file_part.split("/")[-1].lower()
    v = verdict.lower()
    return name.lower() in v and base in v


def match_injection(verdict: str | None, injection: dict) -> bool:
    """定位类对照注入点：verdict 命中 injection.file（行号容差 ±2）。

    验收 = 对照注入点（#5）。文件末段必须出现在 verdict；若 verdict 带行号
    （如 `Cart.php:12`），与注入行差 ≤2 才算命中；无行号时只按文件判定。
    """
    if not verdict:
        return False
    file_part = injection.get("file", "")
    if not file_part:
        return False
    base = file_part.split("/")[-1].lower()
    v = verdict.lower()
    if base not in v:
        return False
    line = injection.get("line")
    if line is None:
        return True
    m = re.search(r":(\d+)", v)
    if m is not None:
        return abs(int(m.group(1)) - int(line)) <= _LINE_TOLERANCE
    return True  # 无行号只按文件


# ---------------------------------------------------------------------------
# 判定层：交卷解析
# ---------------------------------------------------------------------------


def parse_submit_verdict(trace: str | Iterable[str] | None) -> str | None:
    """从轨迹（JSONL）提取 submit_result 的结构化交卷 verdict。

    #29 实测：submit_result 工具执行完成事件
    `tool_execution_end.result.details = {verdict, evidence}`。
    返回最后一个 submit_result 的 verdict；无则 None。

    Args:
        trace: 轨迹 JSONL 全文（可含非 JSON 行）或行迭代器。
    """
    if trace is None:
        return None
    lines: Iterable[str]
    if isinstance(trace, str):
        lines = trace.splitlines()
    else:
        lines = trace
    found: str | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") != "tool_execution_end":
            continue
        if ev.get("toolName") != "submit_result":
            continue
        result = ev.get("result") or {}
        details = result.get("details") or {}
        verdict = details.get("verdict")
        if isinstance(verdict, str) and verdict.strip():
            found = verdict.strip()
    return found


# ---------------------------------------------------------------------------
# 判定层：五类归类
# ---------------------------------------------------------------------------


def judge_modify(
    *,
    f2p_before: bool,
    f2p_after: bool,
    p2p_before: bool,
    p2p_after: bool,
) -> str:
    """修改类 F2P/P2P 双闸 → success / fail_incorrect。

    契约：f2p_before 必须为 True（注入 bug 已被测试抓住，F2P 红基线）。
    f2p_before=False（测试本来就是绿的）→ 任务无效，抛 ValueError
    （调用方负责在判卷前剔除无效任务，#5 全对/全错剔除）。

    判定（#6）：F2P 通过且 P2P 无回归 = success；
    F2P 未过（解不出）或 P2P 回归（解出但炸了别处）= fail_incorrect。
    """
    if not f2p_before:
        raise ValueError(
            "F2P 基线必须为红（注入 bug 未被既有测试抓住 → 任务无效）"
        )
    if f2p_after and p2p_before and p2p_after:
        return "success"
    return "fail_incorrect"


def judge_result(
    kind: str,
    result=None,
    *,
    verdict: str | None = None,
    ground_truth: str | None = None,
    injection: dict | None = None,
    f2p: tuple[bool, bool] | None = None,
    p2p: tuple[bool, bool] | None = None,
    budget: bool = False,
) -> str:
    """一次任务运行 → 五类 outcome（纯函数，构造数据可测）。

    Args:
        kind: 任务类别（modify / search / locate）。探测类判定复用 probe.json
            （#19 probe_success），不走本函数。
        result: RunResult | None；None = worktree 失败（fail_env）。
        verdict: 检索/定位类交卷（submit_result.details.verdict）。
        ground_truth: 检索类验收（file::name，#5 符号级）。
        injection: 定位类注入点（{file, line, patch}）。
        f2p/p2p: 修改类测试结果 (before, after)。
        budget: max-turns 触顶标记（扩展早停，调用方按轨迹判定）。

    判定顺序：
    1. result=None → fail_env（worktree 失败）
    2. budget / exit 124 / timeout → fail_budget
    3. 进程崩溃（未 settled 且非 timeout 码）→ fail_env
    4. 按类别验收：修改 F2P/P2P；检索 match_location；定位 match_injection
    5. 无验收数据 → fail_incorrect（判定不了 = 没通过）
    """
    if result is None:
        return "fail_env"

    exit_code = getattr(result, "exit_code", 0)
    note = getattr(result, "outcome_note", "")
    settled = getattr(result.stats, "settled", False)

    if budget or exit_code == 124 or note == "timeout":
        return "fail_budget"
    if not settled and exit_code not in (0, 124):
        return "fail_env"  # 进程崩溃/参数错误（非 timeout 码）

    if kind == "modify":
        if f2p is None or p2p is None:
            return "fail_incorrect"  # 测试数据不全 = 没通过判定
        return judge_modify(
            f2p_before=f2p[0], f2p_after=f2p[1],
            p2p_before=p2p[0], p2p_after=p2p[1],
        )
    if kind == "search":
        if verdict and ground_truth and match_location(verdict, ground_truth):
            return "success"
        return "fail_incorrect"
    if kind == "locate":
        if verdict and injection and match_injection(verdict, injection):
            return "success"
        return "fail_incorrect"
    raise ValueError(f"未知任务类别 {kind!r}（仅支持 modify/search/locate）")
