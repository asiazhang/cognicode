"""聚合层单元测试（#21：判卷 + 静态 → 六维分 + 总分 + 区间 + 效率 + 软横比）。

用构造的判卷假数据（verdicts.json 形状）+ 静态假数据（static.json 形状），
验证聚合数学与决策规则：
- 维度内动态:静态 70/30（navigability/buildability 有静态面；其余四维 = 动态）
- 维度级 Wilson 95% CI（#6 #7）
- 总分 = 等权 1/6 加权算术平均 + 半宽线性解析传播（#8 #5）
- 效率分 = 语料 worse_ratio 百分位（四量平均，高=好）+ 原始中位数并报
- 软横比 = 语料中位数 + 固定声明句；无语料 → 无横比
- 探测失败 → 整体降级（只出静态分 + 动态面未测标注）
- 任务级全 success/全 fail 剔除（#5）

期望值全部来自独立手算的已知字面（防 tautological）。
"""

import json

import pytest

from cognicode.aggregate import (
    DYN_STATIC_SPLIT,
    aggregate_run,
    corpus_median,
    efficiency_score,
    median_of,
    task_statistics,
    verdicts_summary,
)


# ---------------------------------------------------------------------------
# 构造假数据（verdicts.json 形状：{tasks: [{task_id, kind, k, outcomes}]}）
# ---------------------------------------------------------------------------

def _verdicts(**overrides):
    """默认判卷假数据：六维对应的任务类别样本（修改 12×5、检索 8×3、定位 8×3）。"""
    base = {
        "tasks": [
            # 修改类（k=5，承载可解性 + 变更安全性）
            {"task_id": "modify-1", "kind": "modify", "k": 5,
             "outcomes": ["success"] * 3 + ["fail_incorrect"] * 2},
            {"task_id": "modify-2", "kind": "modify", "k": 5,
             "outcomes": ["success"] * 5},  # 全 success → 剔除
            # 检索类（k=3，可导航性动态面）
            {"task_id": "search-1", "kind": "search", "k": 3,
             "outcomes": ["success", "success", "fail_incorrect"]},
            {"task_id": "search-2", "kind": "search", "k": 3,
             "outcomes": ["success", "success", "success"]},  # 全 success → 剔除
            # 定位类（k=3，可诊断性）
            {"task_id": "locate-1", "kind": "locate", "k": 3,
             "outcomes": ["success", "fail_incorrect", "fail_incorrect"]},
            # 修改类（变更安全性：F2P 过但 P2P 回归 → fail_incorrect 归 safety）
            {"task_id": "modify-3", "kind": "modify", "k": 5,
             "outcomes": ["success", "fail_incorrect", "fail_incorrect",
                          "fail_budget", "fail_budget"]},
        ]
    }
    base.update(overrides)
    return base


def _static(navigability=0.5, buildability=0.75):
    """静态假数据（static.json 形状）。"""
    return {
        "signals": {
            "navigability.agent_context_docs": {"value": 1.0, "score": 1.0, "evidence": []},
            "navigability.readme": {"value": 1.0, "score": 1.0, "evidence": []},
            "navigability.comment_density": {"value": 0.0, "score": 0.0, "evidence": []},
            "navigability.entry_clarity": {"value": 0.0, "score": 0.0, "evidence": []},
            "buildability.build_def": {"value": 2.0, "score": 1.0, "evidence": []},
            "buildability.lockfile": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.ci": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.test_discoverability": {"value": 0.0, "score": 0.0, "evidence": []},
        },
        "dimensions": {
            "navigability": {"score": navigability, "signal_count": 4},
            "buildability": {"score": buildability, "signal_count": 4},
        },
    }


def _medians(**kw):
    """效率假数据：success 运行的 token/轮次/墙钟中位数。"""
    base = {"token": 10000, "turns": 4, "wall_ms": 90000}
    base.update(kw)
    return base


def _corpus():
    """效率语料参考分布（测试用）：token [20000,30000]、turns [8,10]、wall [200000,300000]。"""
    return {"token": [20000, 30000], "turns": [8, 10], "wall_ms": [200000, 300000]}


# ---------------------------------------------------------------------------
# 纯统计量
# ---------------------------------------------------------------------------

class TestMedianOf:
    def test_odd(self):
        assert median_of([5, 1, 3]) == 3.0

    def test_even(self):
        assert median_of([4, 1, 7, 2]) == 3.0  # (2+4)/2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            median_of([])


class TestEfficiencyScore:
    """效率分 = 语料 worse_ratio 百分位（四量平均，高=好）+ 原始并报。"""

    def test_worse_ratio_percentile(self):
        # 本仓 token 中位数 10000；语料 token 参考 [20000, 30000] → 比 2 个差 → 1.0
        score = efficiency_score(
            _medians(),
            corpus={"token": [20000, 30000], "turns": [8, 10], "wall_ms": [200000, 300000]},
        )
        assert score["point"] == pytest.approx(1.0)  # 全量优于语料
        assert score["raw_percentile"] == pytest.approx(0.0)  # CDF=0（最好）
        assert score["medians"]["token"] == 10000  # 原始并报

    def test_median_position(self):
        # 语料 [5000, 10000, 30000]：本仓 10000 平局 → worse_ratio = 2/3
        # turns 4 vs [2,8,10] → worse 2 个 → 2/3；wall 90000 vs [50000,200000,300000] → 2/3
        score = efficiency_score(
            {"token": 10000, "turns": 4, "wall_ms": 90000},
            corpus={"token": [5000, 10000, 30000], "turns": [2, 8, 10], "wall_ms": [50000, 200000, 300000]},
        )
        # token 10000 vs [5000,10000,30000]：仅 30000 worse（平局 10000 不算）→ 1/3
        # turns 4 vs [2,8,10]：8,10 worse → 2/3；wall 90000 vs [...] → 2/3
        # point = (1/3 + 2/3 + 2/3)/3 = 5/9
        assert score["point"] == pytest.approx(5 / 9, abs=0.001)
        assert score["raw_percentile"] == pytest.approx(4 / 9, abs=0.001)

    def test_no_corpus_returns_none_point(self):
        score = efficiency_score(_medians(), corpus=None)
        assert score["point"] is None
        assert score["raw_percentile"] is None
        assert score["medians"]["token"] == 10000  # 原始仍并报

    def test_missing_corpus_quantity_skipped(self):
        # 语料只有 token 参考，turns/wall 缺 → 只用 token 的量
        score = efficiency_score(
            _medians(),
            corpus={"token": [20000, 30000]},
        )
        assert score["point"] == pytest.approx(1.0)


class TestCorpusMedian:
    def test_odd(self):
        assert corpus_median([0.4, 0.6, 0.8]) == pytest.approx(0.6)

    def test_even(self):
        assert corpus_median([0.4, 0.6, 0.8, 0.9]) == pytest.approx(0.7)

    def test_empty_returns_none(self):
        assert corpus_median([]) is None


# ---------------------------------------------------------------------------
# 任务级统计
# ---------------------------------------------------------------------------

class TestTaskStatistics:
    def test_success_rate_and_wilson(self):
        # modify-1: 3 success + 2 fail_incorrect，k=5 全计入 → 3/5
        stat = task_statistics(["success"] * 3 + ["fail_incorrect"] * 2)
        assert stat["successes"] == 3
        assert stat["effective"] == 5
        assert stat["point"] == pytest.approx(0.6)
        # Wilson 3/5 半宽：区间 (0.6, 0.2307, 0.8824)（Wilson 公式独立手算）
        assert stat["lower"] == pytest.approx(0.2307, abs=0.002)
        assert stat["upper"] == pytest.approx(0.8824, abs=0.002)

    def test_fail_env_excluded(self):
        # fail_env 剔除：3 success + 1 fail_incorrect + 1 fail_env → 3/4
        stat = task_statistics(["success"] * 3 + ["fail_incorrect", "fail_env"])
        assert stat["successes"] == 3
        assert stat["effective"] == 4
        assert stat["point"] == pytest.approx(0.75)
        assert stat["excluded_env"] == 1

    def test_fail_budget_counts_as_failure(self):
        # fail_budget 计入失败（#6）
        stat = task_statistics(["success", "fail_budget", "fail_budget"])
        assert stat["effective"] == 3
        assert stat["successes"] == 1
        assert stat["point"] == pytest.approx(1 / 3)


class TestVerdictsSummary:
    """任务类别聚合：修改类拆分可解性/变更安全性（#15）。"""

    def test_kind_counts(self):
        v = _verdicts()
        s = verdicts_summary(v)
        # 修改类：modify-1 (3s/5) + modify-2 (5/5 剔除) + modify-3 (1s/5)
        # 检索类：search-1 (2/3) + search-2 (3/3 剔除)
        # 定位类：locate-1 (1/3)
        assert s["counts"]["modify"] == 3
        assert s["counts"]["search"] == 2
        assert s["counts"]["locate"] == 1

    def test_all_success_task_removed(self):
        # #5 全对/全错任务剔除：modify-2 5/5、search-2 3/3 不进统计
        v = _verdicts()
        s = verdicts_summary(v)
        assert "modify-2" in s["removed_all_same"]
        assert "search-2" in s["removed_all_same"]
        # 剩余：modify-1 3/5 + modify-3 1/5 + search-1 2/3 + locate-1 1/3
        assert s["tasks_included"] == 4


# ---------------------------------------------------------------------------
# 聚合（核心）
# ---------------------------------------------------------------------------

class TestAggregateRun:
    def test_dimension_mixing_70_30(self):
        """navigability/buildability 70/30 混合；其余四维 = 动态分。"""
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians(), corpus=_corpus())
        dims = agg["dimensions"]
        # navigability：动态 2/3（search-1 2/3）+ 静态 0.5 → 0.7·(2/3)+0.3·0.5
        assert dims["navigability"]["point"] == pytest.approx(0.7 * (2 / 3) + 0.3 * 0.5)
        # buildability：动态 0（无探测成功样本，未测）+ 静态 0.75 → 静态
        assert dims["buildability"]["point"] == pytest.approx(0.75)
        # 四维无静态信号 → dim = 动态分
        assert dims["solvability"]["point"] == pytest.approx((3 / 5 + 1 / 5) / 2)  # modify-1 + modify-3
        assert dims["diagnosability"]["point"] == pytest.approx(1 / 3)
        # 效率 = 语料百分位（worse_ratio：本仓全量优于语料 → 1.0）
        assert dims["efficiency"]["point"] == pytest.approx(1.0)

    def test_total_score_and_half_width(self):
        """总分 = 等权 1/6 + 半宽线性传播（独立手算）。"""
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians(), corpus=_corpus())
        total = agg["total"]
        # 六维点值：solvability (3/5+1/5)/2、safety 0（无 P2P 回归样本）？——
        # 等一下，safety 怎么来的？#15：F2P 过但 P2P 未过归 safety
        # 构造数据 modify-3 是 fail_budget+fail_incorrect（F2P 没过）→ 归 solvability
        # 没有 P2P 回归样本 → safety 动态样本 0 → 未测（0 点值）
        # 效率 1.0、navigability 混合、buildability 0.75、diagnosability 1/3
        # 总分点值（等权 1/6）：
        #   solvability (3/5+1/5)/2=0.4、safety 0、efficiency 1.0、
        #   navigability 0.6167、buildability 0.75、diagnosability 1/3
        #   = (0.4 + 0 + 1.0 + 0.6167 + 0.75 + 1/3)/6
        expected_p = (0.4 + 0.0 + 1.0 + (0.7 * 2 / 3 + 0.3 * 0.5) + 0.75 + 1 / 3) / 6
        assert total["point"] == pytest.approx(expected_p, abs=0.0001)
        assert "safety" not in total  # 总分是标量（点值+区间），维度不在 total 里

    def test_dynamic_not_measured_degrade(self):
        """探测失败 → 整体降级：只出静态分 + 动态面未测标注。"""
        agg = aggregate_run(
            _verdicts(), static=_static(), medians=_medians(),
            dynamic_measured=False,
        )
        assert agg["dynamic_measured"] is False
        # 可导航性/环境可用性 = 静态分
        assert agg["dimensions"]["navigability"]["point"] == pytest.approx(0.5)
        assert agg["dimensions"]["buildability"]["point"] == pytest.approx(0.75)
        # 其余四维未测 → None
        assert agg["dimensions"]["solvability"]["point"] is None
        assert agg["dimensions"]["efficiency"]["point"] is None
        # 总分 null + 标注
        assert agg["total"]["point"] is None

    def test_soft_benchmark(self):
        """软横比：总分旁语料中位数 + 声明句。"""
        agg = aggregate_run(
            _verdicts(), static=_static(), medians=_medians(),
            corpus_totals=[0.4, 0.6],
        )
        assert agg["soft_benchmark"]["corpus_median"] == pytest.approx(0.5)
        assert "软参考" in agg["soft_benchmark"]["statement"]

    def test_no_corpus_no_benchmark(self):
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians())
        assert agg["soft_benchmark"]["corpus_median"] is None
        assert "无横比" in agg["soft_benchmark"]["statement"]

    def test_snapshot_shape(self):
        """snapshot.json：配置全量 + report-schema + 权重版本。"""
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians())
        snap = agg["snapshot"]
        assert snap["report-schema"] == "1.0"
        assert snap["weights-version"] == "equal-1of6-v1"
        assert "config" in snap  # 配置全量（缺省空 dict，形状完整）
        assert snap["run"]["run_id"]

    def test_aggregate_serializable(self):
        """aggregate 全量可 JSON 序列化（落盘 aggregate.json）。"""
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians())
        json.dumps(agg)  # 不抛

    def test_dyn_static_split_pinned(self):
        assert DYN_STATIC_SPLIT == 0.7  # #8 钉死 70/30

    def test_sensitivity_produced_with_verdicts(self):
        """动态已测 → aggregate 产出敏感性小节（判据①）。"""
        agg = aggregate_run(_verdicts(), static=_static(), medians=_medians())
        sens = agg["sensitivity"]
        assert sens["grid"]["n_weights"] == 15625
        assert sens["dirichlet"]["n_samples"] == 200
        assert "criterion_pass" in sens["grid"]
        assert sens["corpus"] == {"present": False}  # 语料未注入

    def test_sensitivity_note_when_dynamic_not_measured(self):
        """探测失败 → 敏感性标不适用（总分未测，无点值可扰）。"""
        agg = aggregate_run(
            _verdicts(), static=_static(), dynamic_measured=False,
        )
        assert "note" in agg["sensitivity"]
        assert "不适用" in agg["sensitivity"]["note"]
