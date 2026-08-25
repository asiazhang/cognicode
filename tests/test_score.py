"""六维加权聚合单元测试。

期望值全部用独立手算的字面值（防 tautological）：
- 等权 1/6、六维点值 [0.6,0.5,0.4,0.7,0.3,0.5] → 总分 (0.6+0.5+0.4+0.7+0.3+0.5)/6
- 半宽传播 sqrt(Σ wᵢ²·hwᵢ²)
"""

import math

import pytest

from cognicode.score import (
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    DimensionScore,
    WEIGHT_VERSION,
    renormalize,
    validate_weights,
    weighted_total,
)


def _dims(points, half_widths=None):
    hw = half_widths or [0.0] * 6
    return {
        d: DimensionScore(point=p, half_width=h)
        for d, p, h in zip(DIMENSIONS, points, hw)
    }


class TestValidateWeights:
    def test_equal_weights_valid(self):
        validate_weights(DEFAULT_WEIGHTS)  # 不抛

    def test_missing_dimension_rejected(self):
        with pytest.raises(ValueError):
            validate_weights({"solvability": 1.0})

    def test_zero_weight_rejected(self):
        bad = dict(DEFAULT_WEIGHTS)
        bad["safety"] = 0.0
        bad["solvability"] = 1.0 / 6.0 + 1.0 / 6.0  # 和仍为 1
        with pytest.raises(ValueError, match="零权重"):
            validate_weights(bad)

    def test_negative_weight_rejected(self):
        bad = dict(DEFAULT_WEIGHTS)
        bad["safety"] = -0.1
        bad["solvability"] = 1.0 / 6.0 + 0.1
        with pytest.raises(ValueError, match="不得为负"):
            validate_weights(bad)

    def test_sum_not_one_rejected(self):
        bad = {d: 0.2 for d in DIMENSIONS}  # 和 = 1.2
        with pytest.raises(ValueError, match="之和必须为 1"):
            validate_weights(bad)


class TestWeightedTotal:
    def test_equal_weight_arithmetic_mean(self):
        dims = _dims([0.6, 0.5, 0.4, 0.7, 0.3, 0.5])
        total = weighted_total(dims)
        assert total.point == pytest.approx(0.5)  # (0.6+0.5+0.4+0.7+0.3+0.5)/6
        assert total.half_width == pytest.approx(0.0)

    def test_point_half_width_propagation(self):
        dims = _dims(
            [0.6, 0.5, 0.4, 0.7, 0.3, 0.5],
            half_widths=[0.1, 0.0, 0.0, 0.05, 0.08, 0.0],
        )
        total = weighted_total(dims)
        # 半宽 = sqrt((0.1² + 0.05² + 0.08²)/36)
        expected = math.sqrt((0.1**2 + 0.05**2 + 0.08**2) / 36.0)
        assert total.half_width == pytest.approx(expected)

    def test_static_dimension_zero_half_width(self):
        # 静态维只贡献点值：半宽 0 的维不放大总分区间
        dims = _dims([0.5] * 6, half_widths=[0.0] * 6)
        total = weighted_total(dims)
        assert total.half_width == pytest.approx(0.0)

    def test_missing_dimension_treated_as_zero(self):
        # 缺维按 0 处理（未测维）
        dims = _dims([0.6, 0.5, 0.4, 0.7, 0.3, 0.5])
        del dims["buildability"]
        total = weighted_total(dims)
        # 等权下缺一维（按 0）= (0.6+0.5+0.4+0.7+0.5)/6
        assert total.point == pytest.approx(2.7 / 6.0)

    def test_weighted_override(self):
        # 加权：可解性 0.5，其余均分 0.1
        w = {"solvability": 0.5}
        for d in DIMENSIONS:
            w.setdefault(d, 0.1)
        dims = _dims([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        total = weighted_total(dims, weights=w)
        assert total.point == pytest.approx(0.5)

    def test_zero_weights_rejected_in_total(self):
        dims = _dims([0.5] * 6)
        with pytest.raises(ValueError):
            weighted_total(dims, weights={"solvability": 1.0})


class TestRenormalize:
    def test_renormalize_sums_to_one(self):
        w = {d: (2.0 if i % 2 == 0 else 1.0) for i, d in enumerate(DIMENSIONS)}
        norm = renormalize(w)
        assert sum(norm.values()) == pytest.approx(1.0)
        # 相对比例保持
        assert norm["solvability"] / norm["safety"] == pytest.approx(2.0)

    def test_equal_weights_idempotent(self):
        assert renormalize(DEFAULT_WEIGHTS) == pytest.approx(DEFAULT_WEIGHTS)


class TestConstants:
    def test_default_weights_equal_1of6(self):
        for d in DIMENSIONS:
            assert DEFAULT_WEIGHTS[d] == pytest.approx(1.0 / 6.0)

    def test_weight_version_pinned(self):
        assert WEIGHT_VERSION == "equal-1of6-v1"
