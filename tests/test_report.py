"""报告生成单元测试（#21/#12：报告结构、建议清单、软横比、schema 标识）。

验证 render_report / render_terminal_summary 的文本形状：
- 单页三层（总览 / 维度明细 / 建议清单）+ 敏感性小节独立后半 + 附录
- 纯文本无 ANSI、中文术语括英、报告头 schema 号
- 建议清单确定性排序（维度分最低优先，#8 #8）
- 软横比声明 / 无横比声明
- 效率维行显示语料百分位 + 原始四量中位数
"""

import pytest

from cognicode.report import (
    _build_suggestions,
    _priority_key,
    render_report,
    render_terminal_summary,
)


def _agg(**overrides):
    """最小 aggregate（供报告测试）。"""
    base = {
        "run_id": "run-1",
        "dynamic_measured": True,
        "dimensions": {
            "solvability": {"point": 0.4, "lower": 0.2, "upper": 0.6, "half_width": 0.2,
                            "source": "dynamic", "details": {}},
            "safety": {"point": 0.8, "lower": 0.6, "upper": 1.0, "half_width": 0.2,
                       "source": "dynamic", "details": {}},
            "efficiency": {"point": 0.9, "lower": None, "upper": None, "half_width": 0.0,
                           "source": "corpus_percentile",
                           "details": {"point": 0.9, "raw_percentile": 0.1,
                                       "medians": {"token": 10000, "turns": 4, "wall_ms": 90000}}},
            "navigability": {"point": 0.62, "lower": None, "upper": None, "half_width": 0.26,
                             "source": "dyn70_static30",
                             "details": {"dynamic": 0.67, "static": 0.5,
                                         "dynamic_ci": [0.21, 0.94]}},
            "buildability": {"point": 0.75, "lower": None, "upper": None, "half_width": 0.0,
                             "source": "static_only", "details": {"static": 0.75}},
            "diagnosability": {"point": 0.33, "lower": 0.06, "upper": 0.79, "half_width": 0.36,
                               "source": "dynamic", "details": {}},
        },
        "total": {"point": 0.52, "lower": 0.43, "upper": 0.60, "half_width": 0.085},
        "efficiency": {"point": 0.9, "raw_percentile": 0.1,
                       "medians": {"token": 10000, "turns": 4, "wall_ms": 90000}},
        "soft_benchmark": {
            "corpus_median": 0.5,
            "statement": "语料中位数 0.500（仅软参考）——跨仓库排序仅软参考，不做硬承诺（软横比，soft cross-repo comparison）",
        },
        "snapshot": {
            "report-schema": "1.0",
            "weights-version": "equal-1of6-v1",
            "config": {"weights": {"solvability": 1 / 6}},
            "run": {"run_id": "run-1", "dynamic_measured": True},
        },
        "sensitivity": {
            "grid": {"bandwidth": 0.03125, "criterion_pass": True,
                      "n_weights": 15625,
                      "sweep": {
                          "solvability": {"effect": 0.016, "low_tier_avg": 0.49, "high_tier_avg": 0.51},
                          "navigability": {"effect": 0.034, "low_tier_avg": 0.48, "high_tier_avg": 0.52},
                      }},
            "dirichlet": {"bandwidth": 0.029, "criterion_pass": True,
                           "n_samples": 200, "alpha": 12.0, "seed": None},
            "corpus": {"present": False},
        },
        "verdicts": {"counts": {"modify": 3, "search": 2, "locate": 1}, "removed_all_same": [], "tasks_included": 4},
        "removed": [],
    }
    base.update(overrides)
    return base


def _signals():
    """静态信号假数据（含低分信号触发模板建议）。"""
    return {
        "navigability.agent_context_docs": {"value": 1.0, "score": 1.0, "evidence": ["AGENTS.md"]},
        "navigability.readme": {"value": 1.0, "score": 1.0, "evidence": ["README.md"]},
        "navigability.comment_density": {"value": 0.02, "score": 0.0, "evidence": ["注释/代码比 0.020"]},
        "navigability.entry_clarity": {"value": 0.0, "score": 0.0, "evidence": []},
        "buildability.build_def": {"value": 2.0, "score": 1.0, "evidence": ["pyproject.toml"]},
        "buildability.lockfile": {"value": 1.0, "score": 1.0, "evidence": ["uv.lock"]},
        "buildability.ci": {"value": 1.0, "score": 1.0, "evidence": [".github/workflows"]},
        "buildability.test_discoverability": {"value": 0.0, "score": 0.0, "evidence": []},
    }


class TestReportStructure:
    def test_three_layers_and_schema_header(self):
        r = render_report(_agg(), static_signals=_signals(), repo_name="nbnbk")
        assert "# CogniCode 评估报告（report）" in r
        assert "report-schema: 1.0" in r  # 报告头显示 schema 号（#12 #5）
        assert "## 总览（overview）" in r
        assert "## 维度明细（dimension details）" in r
        assert "## 建议清单（suggestions）" in r
        # 敏感性小节独立放后半（在建议清单之后、附录之前）
        assert r.index("## 建议清单") < r.index("## 权重敏感性分析") < r.index("## 附录")

    def test_total_and_interval(self):
        r = render_report(_agg(), static_signals=_signals())
        assert "总分: 0.52 [0.43, 0.60]" in r

    def test_soft_benchmark_statement(self):
        r = render_report(_agg(), static_signals=_signals())
        assert "语料中位数 0.500" in r
        assert "仅软参考" in r

    def test_no_corpus_no_benchmark(self):
        agg = _agg()
        agg["soft_benchmark"] = {"corpus_median": None, "statement": "无横比（语料未提供，本仓为单点评估）"}
        r = render_report(agg, static_signals=_signals())
        assert "无横比" in r

    def test_efficiency_row_shows_percentile_and_medians(self):
        r = render_report(_agg(), static_signals=_signals())
        # 效率维行显示语料百分位 + 原始四量中位数并报（#12）
        assert "语料百分位 0.10" in r
        assert "token 10000 / turns 4 / wall 90000ms" in r

    def test_navigability_shows_decomposition(self):
        r = render_report(_agg(), static_signals=_signals())
        assert "动态 0.67 + 静态 0.50，70/30" in r

    def test_no_ansi_control_chars(self):
        r = render_report(_agg(), static_signals=_signals())
        assert "\x1b[" not in r  # 无 ANSI 色块（#12 #1）


class TestSuggestions:
    def test_deterministic_order_by_lowest_dim(self):
        """排序键：维度分最低优先（#8 #8）。"""
        sugg = _build_suggestions(_agg(), _signals())
        priorities = [s["priority"] for s in sugg]
        assert priorities == sorted(priorities)
        # 最低分维度（diagnosability 0.33）排第一
        assert sugg[0]["anchor"] == "diagnosability"

    def test_signal_template_for_low_score(self):
        """产分信号缺失/低档 → 确定性模板建议条（#7 #6）。"""
        sugg = _build_suggestions(_agg(), _signals())
        anchors = [s["anchor"] for s in sugg]
        assert "navigability.comment_density" in anchors  # score 0.0
        assert "navigability.agent_context_docs" not in anchors  # score 1.0 不触发

    def test_suggestion_has_anchor_direction_remeasurable(self):
        """每条建议含锚定 + 预期方向 + 可重测声明（#8 #7/#12）。"""
        sugg = _build_suggestions(_agg(), _signals())
        for s in sugg:
            assert s["anchor"]
            assert s["direction"]
            assert "可重测" in s["remeasurable"] or "重跑" in s["remeasurable"]

    def test_no_low_scores_no_suggestions(self):
        agg = _agg()
        for d in agg["dimensions"].values():
            d["point"] = 0.9
        signals = {k: {"value": 1.0, "score": 1.0, "evidence": []} for k in _signals()}
        assert _build_suggestions(agg, signals) == []


class TestPriorityKey:
    def test_lowest_dim_first(self):
        lo = _priority_key({"point": 0.3}, None)
        hi = _priority_key({"point": 0.8}, None)
        assert lo < hi

    def test_signal_tier_secondary(self):
        # 同维度分时信号档位低优先
        a = _priority_key({"point": 0.5}, 0.0)
        b = _priority_key({"point": 0.5}, 0.5)
        assert a < b

    def test_unmeasured_after_measured(self):
        a = _priority_key({"point": 0.1}, None)
        b = _priority_key(None, None)
        assert a < b


class TestTerminalSummary:
    def test_terminal_has_three_layers(self):
        r = render_terminal_summary(_agg(), static_signals=_signals())
        assert "## 总览" in r
        assert "## 维度明细" in r
        assert "## 建议清单" in r

    def test_terminal_no_ansi(self):
        r = render_terminal_summary(_agg(), static_signals=_signals())
        assert "\x1b[" not in r


class TestSensitivitySection:
    def test_render_sensitivity_judgement(self):
        """敏感性小节渲染带宽与判据①通过/失败（#22）。"""
        r = render_report(_agg(), static_signals=_signals())
        assert "## 权重敏感性分析（weight sensitivity analysis）" in r
        assert "网格 15625 组 带宽 0.031" in r
        assert "≤0.05 ✓" in r
        assert "总分对权重选择 稳健（pass）" in r

    def test_render_failed_bandwidth(self):
        """带宽超限 → 标注不稳健（判据① fail）。"""
        agg = _agg()
        agg["sensitivity"] = {
            "grid": {"bandwidth": 0.12, "criterion_pass": False,
                      "n_weights": 15625, "sweep": {}},
            "dirichlet": {"bandwidth": 0.09, "criterion_pass": False,
                           "n_samples": 200, "alpha": 12.0, "seed": None},
            "corpus": {"present": False},
        }
        r = render_report(agg, static_signals=_signals())
        assert ">0.05 ✗" in r
        assert "不稳健（fail）" in r

    def test_render_missing_sensitivity_note(self):
        """动态面未测 → 敏感性标注不适用。"""
        agg = _agg()
        agg["sensitivity"] = {"note": "动态面未测（总分未测），权重敏感性不适用"}
        r = render_report(agg, static_signals=_signals())
        assert "动态面未测（总分未测）" in r

    def test_terminal_summary_has_sensitivity_line(self):
        r = render_terminal_summary(_agg(), static_signals=_signals())
        assert "## 权重敏感性分析" in r
        assert "带宽 0.031" in r

    def test_corpus_direction_rendered_when_present(self):
        """判据②：语料各仓方向注入后渲染排序稳定性。"""
        agg = _agg()
        agg["sensitivity"]["corpus"] = {
            "present": True,
            "repos": ["nbnbk", "Melissa-Core"],
            "stable": True,
            "unstable_pairs": [],
        }
        r = render_report(agg, static_signals=_signals())
        assert "判据②（语料方向排序稳定）" in r
        assert "nbnbk > Melissa-Core" in r
        assert "✓ 稳定" in r

    def test_corpus_absent_shows_pending(self):
        r = render_report(_agg(), static_signals=_signals())
        assert "判据②（语料方向排序稳定）: 待语料" in r


# ---------------------------------------------------------------------------
# #23：归因管线并入（失败任务引用）+ 模块深度小节
# ---------------------------------------------------------------------------

class TestAttributionIntegration:
    def test_attribution_suggestions_consumed(self):
        """agg['attribution'] 存在 → 建议清单直接用归因管线产出（含失败引用）。"""
        agg = _agg()
        agg["attribution"] = {
            "suggestions": [{
                "anchor": "navigability.agent_context_docs",
                "anchor_kind": "signal",
                "text": "补充代理上下文文档（agent context document）",
                "direction": "up",
                "remeasurable": "重跑同一套任务与静态提取，用维度分区间判定方向移动",
                "evidence": "信号 navigability.agent_context_docs 当前 0.0",
                "failure_ref": "检索 2/3 失败（解出失败）",
                "source": "template",
                "priority": (0.25, 0.0, 0),
            }],
            "llm_groups": [],
        }
        r = render_report(agg, static_signals=_signals())
        assert "失败任务引用（failed task reference）: 检索 2/3 失败（解出失败）" in r
        assert "来源: 确定性模板（deterministic template）" in r

    def test_llm_suggestion_source_label(self):
        agg = _agg()
        agg["attribution"] = {
            "suggestions": [{
                "anchor": "solvability",
                "anchor_kind": "dimension",
                "text": "LLM 建议",
                "direction": "up",
                "remeasurable": "重跑对应任务类，用维度分区间判定方向移动",
                "evidence": "LLM 综合归因",
                "failure_ref": "修改 2/5 失败（解出失败）",
                "source": "llm",
                "llm_rank": 0,
                "priority": (0.4, 0.0, 0),
            }],
            "llm_groups": [],
        }
        r = render_report(agg, static_signals=_signals())
        assert "来源: LLM 综合归因（LLM synthesis）" in r

    def test_module_depth_section_rendered_when_enabled(self):
        """模块深度开启 → 报告后半有模块深度小节（重构参考，不进产分）。"""
        agg = _agg()
        agg["module_depth"] = {
            "enabled": True,
            "modules": [{"module": "src/core.py", "label": "shallow"}],
            "distribution": {"deep": 1, "shallow": 1, "unjudged": 0},
            "suggestions": ["模块 src/core.py 判定为 shallow：建议合并小模块或加深接口"],
        }
        r = render_report(agg, static_signals=_signals())
        assert "## 模块深度（module depth，重构参考）" in r
        assert "deep 1 / shallow 1 / 未判定 0" in r
        assert "src/core.py" in r

    def test_module_depth_hidden_when_offline(self):
        """模块深度关闭（--offline）→ 报告不渲染该小节。"""
        r = render_report(_agg(), static_signals=_signals())
        assert "## 模块深度" not in r
