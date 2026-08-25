"""Wilson 95% 置信区间（#6 锁定的成功率区间）。

点估计 = 成功次数 / 有效次数（fail_env 已剔除）；区间用 Wilson score
interval（对极端 p 比正态近似稳），z = 1.96 对应 95%。
"""

import math

# 95% 置信度的标准正态分位数
_Z_95 = 1.959963984540054


def wilson_ci(
    successes: int, trials: int, z: float = _Z_95
) -> tuple[float, float, float]:
    """计算 Wilson 区间。

    Args:
        successes: 成功次数（已剔除 fail_env 后的有效样本内）。
        trials: 有效次数（fail_env 剔除后的总数）。
        z: 标准正态分位数，默认 1.96（95%）。

    Returns:
        (point, lower, upper)：点估计与区间半开闭边界 [lower, upper]，
        均裁剪到 [0, 1]。

    Raises:
        ValueError: trials <= 0，或 successes 越界。
    """
    if trials <= 0:
        raise ValueError(f"trials 必须为正，got {trials}")
    if not 0 <= successes <= trials:
        raise ValueError(
            f"successes 必须在 [0, trials] 内，got {successes}/{trials}"
        )

    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = (p + z2 / (2.0 * trials)) / denom
    half_width = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
    half_width /= denom

    lower = max(0.0, centre - half_width)
    upper = min(1.0, centre + half_width)
    return (p, lower, upper)


def wilson_half_width(successes: int, trials: int, z: float = _Z_95) -> float:
    """Wilson 区间半宽（供聚合传播用，见 score 模块）。"""
    _, lower, upper = wilson_ci(successes, trials, z)
    return (upper - lower) / 2.0
