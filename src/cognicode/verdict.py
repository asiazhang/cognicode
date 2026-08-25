"""判卷结果分类：一次任务运行的判卷归类（五类互斥）。

五类（#6 锁定）：
- success: 判卷通过（F2P 通过且 P2P 无回归 / 位置匹配 / 探测回路跑通）
- fail_incorrect: 正常跑完但判卷不过（含破坏 P2P 的「解出但炸了别处」）
- fail_budget: 触及 max-turns 或墙钟超时
- fail_env: harness 侧环境故障（worktree 损坏、agent 进程崩溃、网络故障）

前三类计入统计；fail_env 剔除并重跑（最多重跑 2 次，>50% 标 harness-unstable）。
"""

from __future__ import annotations

# 五类互斥，顺序即文档；fail_env 恒为末位（剔除类）。
OUTCOME_CATEGORIES: list[str] = [
    "success",
    "fail_incorrect",
    "fail_budget",
    "fail_env",
]

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
