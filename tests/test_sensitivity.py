"""权重敏感性分析单元测试（#22/#10）。

覆盖：
- 网格全枚举 5⁶ = 15625、档位与重归一化性质（护栏禁零权重）
- 带宽与判据①（手算基准：单维极值 0.5→1.0 带宽 0.15625；全等点值 0）
- Dirichlet 采样：可复现、和=1、禁零、分布均值 ≈ 等权
- 判据②语料方向：翻转检出 + 稳健通过 + 不足两仓
- sensitivity_analysis 集成：缺语料 → corpus.present=False
"""

import pytest

from cognicode.score import DIMENSIONS, renormalize
from cognicode.sensitivity import (
    BANDWIDTH_LIMIT,
    DIRICHLET_ALPHA,
    DIRICHLET_SAMPLES,
    GRID_FACTORS,
    corpus_direction,
    dirichlet_analysis,
    dirichlet_weights,
    grid_analysis,
    grid_weights,
    sensitivity_analysis,
    total_bandwidth,
    total_point,
)


def _dims(**overrides):
    """六维点值：默认全 0.5，可用 kwargs 覆盖。"""
    d = {dim: 0.5 for dim in DIMENSIONS}
    d.update(overrides)
    return d


class TestGridWeights:
    def test_full_enumeration_count(self):
        ws = grid_weights()
        assert len(ws) == 5**6  # 15625（#10 全枚举）

    def test_all_weights_renormalized_to_one(self):
        for w in grid_weights():
            assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
            assert set(w) == set(DIMENSIONS)

    def test_no_zero_weight_guardrail(self):
        # 护栏（#10）：任何扰动权重不得塌 0
        for w in grid_weights():
            assert all(v > 0 for v in w.values())

    def test_grid_covers_factor_tiers(self):
        # 每维在重归一化前的原始档位 = {0.5..1.5} × 1/6
        base = 1.0 / 6.0
        seen = {d: set() for d in DIMENSIONS}
        for idx in range(5**6):
            n = idx
            for d in DIMENSIONS:
                seen[d].add(GRID_FACTORS[n % 5] * base)
                n //= 5
        for d, tiers in seen.items():
            assert tiers == {f * base for f in GRID_FACTORS}

    def test_equal_weights_in_grid(self):
        # 全档位 1.0 → 重归一化后 = 等权
        base = 1.0 / 6.0
        assert renormalize({d: base for d in DIMENSIONS}) == pytest.approx(
            {d: base for d in DIMENSIONS}
        )


class TestTotalPoint:
    def test_equal_weight_mean(self):
        dims = _dims(solvability=0.6, safety=0.5, efficiency=0.4,
                     navigability=0.7, buildability=0.3, diagnosability=0.5)
        from cognicode.score import DEFAULT_WEIGHTS
        assert total_point(dims, DEFAULT_WEIGHTS) == pytest.approx(0.5)

    def test_missing_dimension_as_zero(self):
        dims = {d: 0.5 for d in DIMENSIONS}
        del dims["buildability"]
        from cognicode.score import DEFAULT_WEIGHTS
        assert total_point(dims, DEFAULT_WEIGHTS) == pytest.approx(0.5 * 5 / 6)


class TestBandwidth:
    def test_all_equal_points_zero_bandwidth(self):
        assert grid_analysis(_dims())["bandwidth"] == pytest.approx(0.0)

    def test_single_dim_extreme_hand_derived(self):
        # 手算基准：nav=1.0、其余 0.5。总分 = 1/6·(0.5·5 + 1.0·w_nav')，
        # 扰动权重中 nav 档位 0.5→1.5 ×1/6 重归一化后 w_nav ∈ [0.0625, 0.375]
        # → 总分范围 = (5·0.5 + 1·0.0625)/6 … (5·0.5 + 1·0.375)/6
        # 带宽 = (0.375 − 0.0625)·1.0/6 = 0.3125/6 = 0.15625
        dims = _dims(navigability=1.0)
        assert grid_analysis(dims)["bandwidth"] == pytest.approx(0.15625)

    def test_bandwidth_ratio_to_point_deviation(self):
        # 单维扰动带宽 = (hi−lo)·|p−0.5|·1/6：nav=0.6 → 0.3125·0.1/6 ≈ 0.03125
        dims = _dims(navigability=0.6)
        assert grid_analysis(dims)["bandwidth"] == pytest.approx(0.03125, abs=1e-6)

    def test_criterion_pass_under_limit(self):
        dims = _dims(navigability=0.6)
        g = grid_analysis(dims)
        assert g["bandwidth"] <= BANDWIDTH_LIMIT
        assert g["criterion_pass"] is True

    def test_criterion_fail_above_limit(self):
        dims = _dims(navigability=1.0)
        g = grid_analysis(dims)
        assert g["bandwidth"] > BANDWIDTH_LIMIT
        assert g["criterion_pass"] is False

    def test_total_bandwidth_empty_weights_zero(self):
        assert total_bandwidth(_dims(), []) == 0.0


class TestDirichlet:
    def test_seed_reproducible(self):
        a = dirichlet_weights(5, seed=7)
        b = dirichlet_weights(5, seed=7)
        assert a == b

    def test_weights_sum_to_one_and_positive(self):
        for w in dirichlet_weights(50, seed=1):
            assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
            assert all(v > 0 for v in w.values())  # 护栏禁零

    def test_mean_close_to_equal_weights(self):
        # α=12 → Dirichlet 均值 = 12/(12·6) = 1/6 = 等权（大样本近似）
        ws = dirichlet_weights(4000, seed=2)
        means = {d: sum(w[d] for w in ws) / len(ws) for d in DIMENSIONS}
        for d in DIMENSIONS:
            assert means[d] == pytest.approx(1.0 / 6.0, abs=0.005)

    def test_analysis_reports_samples_alpha_seed(self):
        r = dirichlet_analysis(_dims(), n=10, seed=3)
        assert r["n_samples"] == 10
        assert r["alpha"] == DIRICHLET_ALPHA
        assert r["seed"] == 3
        assert "bandwidth" in r and "criterion_pass" in r

    def test_all_equal_points_zero_bandwidth(self):
        r = dirichlet_analysis(_dims(), n=50, seed=4)
        assert r["bandwidth"] == pytest.approx(0.0)


class TestCorpusDirection:
    def _A_B(self):
        A = _dims()
        B = _dims(solvability=1.0, navigability=0.2)
        return {"A": A, "B": B}

    def test_order_by_equal_weight_total(self):
        # 等权：A = 0.5，B = (1.0+0.2+0.5·4)/6 = 0.5333 → B 在前
        c = corpus_direction(self._A_B())
        assert c["repos"] == ["B", "A"]

    def test_flip_detected(self):
        # B 带宽 (1.0−0.2)·0.3125/6 = 0.04167；序位差 0.0333 < 2×0.04167
        c = corpus_direction(self._A_B())
        assert c["stable"] is False
        assert len(c["unstable_pairs"]) == 1
        a, b, diff = c["unstable_pairs"][0]
        assert (a, b) == ("B", "A")
        assert diff == pytest.approx(1 / 30, abs=1e-4)

    def test_robust_order_pass(self):
        # A 全 0.9、B 全 0.4：序位差 0.5 ≫ 2×带宽 0
        c = corpus_direction({"A": _dims(**(dict.fromkeys(DIMENSIONS, 0.9))),
                              "B": _dims(**(dict.fromkeys(DIMENSIONS, 0.4)))})
        assert c["stable"] is True
        assert c["unstable_pairs"] == []

    def test_orders_counts_cover_all_weights(self):
        c = corpus_direction(self._A_B())
        total = sum(v for cnt in c["orders"]["B"].values() for v in [cnt])
        assert total == 5**6  # 每个扰动权重都贡献一个名次

    def test_single_repo_not_judgeable(self):
        c = corpus_direction({"A": _dims()})
        assert c["stable"] is False
        assert "不足两仓" in c["note"]


class TestSensitivityAnalysis:
    def test_missing_corpus_present_false(self):
        r = sensitivity_analysis(_dims(navigability=0.6), seed=1)
        assert r["corpus"] == {"present": False}
        assert r["grid"]["criterion_pass"] is True
        assert r["dirichlet"]["n_samples"] == DIRICHLET_SAMPLES

    def test_repo_dims_drives_corpus(self):
        r = sensitivity_analysis(
            _dims(),
            seed=1,
            repo_dims={"A": _dims(), "B": _dims(solvability=1.0, navigability=0.2)},
        )
        assert "repos" in r["corpus"]
        assert r["corpus"]["repos"] == ["B", "A"]

    def test_dimensions_echo(self):
        dims = _dims(navigability=0.6)
        r = sensitivity_analysis(dims, seed=1)
        assert r["dimensions"] == {
            d: (0.6 if d == "navigability" else 0.5) for d in DIMENSIONS
        }

    def test_unmeasured_dim_zero_point(self):
        # 未测维（None）按 0 点值参与扰动（#21 语义）→ 与显式 0.0 等价
        dims = _dims(navigability=0.9)
        dims["safety"] = None
        dims0 = _dims(navigability=0.9)
        dims0["safety"] = 0.0
        r = sensitivity_analysis(dims, seed=1)
        r0 = sensitivity_analysis(dims0, seed=1)
        assert r["grid"]["bandwidth"] == pytest.approx(
            r0["grid"]["bandwidth"]
        )


class TestGamma:
    def test_gamma_shape_gt1_matches_gauss_approx(self):
        # 大 shape 时 gamma 近似正态：均值 ≈ shape，方差 ≈ shape
        from cognicode.sensitivity import _gamma
        import random

        rng = random.Random(11)
        n = 20000
        vals = [_gamma(50.0, 1.0, rng) for _ in range(n)]
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        assert mean == pytest.approx(50.0, abs=0.3)
        assert var == pytest.approx(50.0, abs=4.0)

    def test_gamma_shape_lt1_positive(self):
        from cognicode.sensitivity import _gamma
        import random

        rng = random.Random(12)
        for _ in range(2000):
            assert _gamma(0.5, 1.0, rng) > 0
