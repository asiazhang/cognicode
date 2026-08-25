"""六维加权聚合与报告 schema 校验（#8 / #10 / #12 锁定）。

聚合：总分 = Σ wᵢ·dimᵢ（加权算术平均），六维 = 可解性/变更安全性/效率/
可导航性/环境可用性/可诊断性。首发权重 = 等权 1/6（#10），禁零权重
（塌 0 = 忽略一种独立失败模式）。

维度分可带区间（#8）：dimᵢ = (point, half_width)；总分点值 = Σ wᵢ·pᵢ，
半宽 = sqrt(Σ wᵢ²·(dimᵢ半宽)²)——概念正交的独立线性解析传播。
静态维只贡献点值（半宽=0）。
"""

from __future__ import annotations

from dataclasses import dataclass

# 六维概念维度（#4 锁定，顺序即文档）
DIMENSIONS: list[str] = [
    "solvability",       # 可解性
    "safety",            # 变更安全性
    "efficiency",        # 效率
    "navigability",      # 可导航性
    "buildability",      # 环境可用性
    "diagnosability",    # 可诊断性
]

# 维度名 → 中文（报告正文用，术语括注英文）
DIMENSION_LABELS_ZH: dict[str, str] = {
    "solvability": "可解性",
    "safety": "变更安全性",
    "efficiency": "效率",
    "navigability": "可导航性",
    "buildability": "环境可用性",
    "diagnosability": "可诊断性",
}

# 首发权重：等权 1/6（#10）
DEFAULT_WEIGHTS: dict[str, float] = {d: 1.0 / 6.0 for d in DIMENSIONS}

# 权重版本（#10 版本化，进运行环境快照）
WEIGHT_VERSION = "equal-1of6-v1"


@dataclass(frozen=True)
class DimensionScore:
    """一个维度的分数：点估计 + 半宽（0 = 静态确定性事实）。"""

    point: float
    half_width: float = 0.0


def validate_weights(weights: dict[str, float]) -> None:
    """校验权重：六维齐全、非负、和 = 1、每维 > 0（禁零权重）。

    Raises:
        ValueError: 任一约束不满足。
    """
    if set(weights) != set(DIMENSIONS):
        raise ValueError(
            f"权重必须恰好覆盖六维 {DIMENSIONS}，got {sorted(weights)}"
        )
    if any(w < 0 for w in weights.values()):
        raise ValueError("权重不得为负")
    if any(w == 0 for w in weights.values()):
        raise ValueError("禁止零权重：塌 0 = 忽略一种独立失败模式")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"权重之和必须为 1，got {total}")


def weighted_total(
    dims: dict[str, DimensionScore],
    weights: dict[str, float] | None = None,
) -> DimensionScore:
    """六维加权聚合：总分点值 + 区间半宽（线性解析传播）。

    Args:
        dims: 六维维度分；缺省维按 0 点值、0 半宽处理（静态缺失/未测维）。
        weights: 六维权重重归一化后的映射；缺省 = 等权 1/6。

    Returns:
        总分 DimensionScore（半宽 = sqrt(Σ wᵢ²·hwᵢ²)）。
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(w)

    point = 0.0
    var = 0.0
    for d in DIMENSIONS:
        wi = w[d]
        dim = dims.get(d, DimensionScore(0.0, 0.0))
        point += wi * dim.point
        var += wi * wi * dim.half_width * dim.half_width
    return DimensionScore(point=point, half_width=var**0.5)


def renormalize(weights: dict[str, float]) -> dict[str, float]:
    """把任意六维权重重归一化为和 = 1（供敏感性分析扰动用）。

    只校验六维齐全、非负、非零；不要求原和 = 1（这正是要归一化的量）。
    """
    if set(weights) != set(DIMENSIONS):
        raise ValueError(
            f"权重必须恰好覆盖六维 {DIMENSIONS}，got {sorted(weights)}"
        )
    if any(w <= 0 for w in weights.values()):
        raise ValueError("权重必须非负且非零")
    total = sum(weights.values())
    return {d: w / total for d, w in weights.items()}
