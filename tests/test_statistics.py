"""Wilson 置信区间单元测试。

验证用独立计算的已知字面值（不重算公式，防 tautological）：
- 6/8 的 95% Wilson 区间参考值：已知 (0.75, 0.407, 0.933)（R prop.test 同值）
- 边界行为：全对 / 全错 / 单样本
"""

import pytest

from cognicode.statistics import wilson_ci, wilson_half_width


class TestWilsonCI:
    def test_6_of_8_known_value(self):
        # 6/8 的 Wilson 95% 区间，R binom.confint(wilson) 已知值
        point, lower, upper = wilson_ci(6, 8)
        assert point == pytest.approx(0.75)
        assert lower == pytest.approx(0.409_3, abs=0.000_5)
        assert upper == pytest.approx(0.928_6, abs=0.000_5)

    def test_all_success(self):
        point, lower, upper = wilson_ci(5, 5)
        assert point == pytest.approx(1.0)
        assert lower > 0.5  # 全对也给出非零下限（Wilson 不塌到 0）
        assert upper == pytest.approx(1.0)

    def test_all_fail(self):
        point, lower, upper = wilson_ci(0, 5)
        assert point == pytest.approx(0.0)
        assert lower == pytest.approx(0.0)
        assert upper < 0.5  # 全错也给出非满上限

    def test_single_trial_success(self):
        point, lower, upper = wilson_ci(1, 1)
        assert point == pytest.approx(1.0)
        assert 0.0 <= lower <= upper <= 1.0

    def test_interval_contains_point(self):
        for s, t in [(1, 3), (2, 4), (3, 9), (7, 10)]:
            point, lower, upper = wilson_ci(s, t)
            assert lower <= point <= upper

    def test_zero_trials_rejected(self):
        with pytest.raises(ValueError):
            wilson_ci(0, 0)

    def test_successes_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            wilson_ci(4, 3)

    def test_monotonic_in_successes(self):
        # 样本数固定时，成功数越多点估计越高
        p1, _, _ = wilson_ci(2, 10)
        p2, _, _ = wilson_ci(5, 10)
        assert p2 > p1


class TestWilsonHalfWidth:
    def test_half_width_consistent_with_ci(self):
        _, lower, upper = wilson_ci(6, 8)
        assert wilson_half_width(6, 8) == pytest.approx((upper - lower) / 2)
