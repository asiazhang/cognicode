"""归因管线单元测试（#23，attribution.py）。

验证（#15 三档「确定性优先、LLM 兜底」）：
- failure_sources：(维度 × 失败模式) 聚合；fail_budget 归可解性；修改类
  有 runs 明细时按 F2P/P2P 拆可解性/变更安全性；fail_env 剔除。
- build_deterministic_suggestions：产分信号命中 → 确定性模板（锚定该信号，
  失败样本作为实证佐证并入）；专属归因信号（测试覆盖缺口 / 单文件规模）
  命中即模板；无信号维度 → 无确定性建议（LLM 兜底）。
- slice_trace：轨迹确定性切片（工具名 + 目标文件 + 末 N 步 + 轮次），
  不含任务原文（消息内容不进入切片）。
- LLM 归因：结构化 JSON 合法才保留（#8 非法结构整条丢弃）；锚定维度
  必须合法；证据包不含任务原文。
- run_attribution：offline（llm=None）→ 确定性档；LLM 档按 (维度×失败模式)
  聚合一次归因；效率走独立低分驱动路径（单文件规模，#15 §8）。

期望值全部来自独立手算的已知字面（防 tautological）。
"""

import json

import pytest

from cognicode.attribution import (
    build_deterministic_suggestions,
    build_failure_ref,
    failure_sources,
    run_attribution,
    slice_trace,
)


# ---------------------------------------------------------------------------
# 构造假数据（verdicts.json 形状 + 静态信号 + 专属归因信号）
# ---------------------------------------------------------------------------

def _verdicts(**overrides):
    """默认判卷假数据：含各类失败样本（fail_env 剔除）。"""
    base = {
        "tasks": [
            # 检索（可导航性）：2/3 解出失败 + 1 超时
            {"task_id": "search-1", "kind": "search", "k": 3,
             "outcomes": ["fail_incorrect", "fail_incorrect", "success"]},
            {"task_id": "search-2", "kind": "search", "k": 3,
             "outcomes": ["fail_budget", "fail_budget", "fail_budget"]},
            {"task_id": "search-3", "kind": "search", "k": 3,
             "outcomes": ["success", "success", "fail_env"]},  # 全 success 但 1 个 env → 有效
            # 定位（可诊断性）：1 超时
            {"task_id": "locate-1", "kind": "locate", "k": 3,
             "outcomes": ["fail_budget", "success", "success"]},
            # 修改（可解性，无 runs 明细 → fail_incorrect 归可解性）：2 解出失败
            {"task_id": "modify-1", "kind": "modify", "k": 5,
             "outcomes": ["fail_incorrect", "fail_incorrect", "success", "success", "success"]},
            # 修改（有 runs 明细：P2P 回归 → 变更安全性）
            {"task_id": "modify-2", "kind": "modify", "k": 5,
             "outcomes": ["fail_incorrect", "success", "success", "success", "success"],
             "runs": [
                 {"outcome": "fail_incorrect", "f2p": [True, True], "p2p": [True, False]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
             ]},
            # 修改（有 runs 明细：F2P 未过 → 可解性）
            {"task_id": "modify-3", "kind": "modify", "k": 5,
             "outcomes": ["fail_incorrect", "success", "success", "success", "success"],
             "runs": [
                 {"outcome": "fail_incorrect", "f2p": [True, False], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
                 {"outcome": "success", "f2p": [True, True], "p2p": [True, True]},
             ]},
        ]
    }
    base.update(overrides)
    return base


def _static(navigability=0.5, buildability=0.75):
    """静态假数据（static.json 形状）。"""
    return {
        "signals": {
            "navigability.agent_context_docs": {"value": 0.0, "score": 0.0, "evidence": []},
            "navigability.readme": {"value": 1.0, "score": 1.0, "evidence": ["README.md"]},
            "navigability.comment_density": {"value": 0.0, "score": 0.0, "evidence": []},
            "navigability.entry_clarity": {"value": 0.0, "score": 0.0, "evidence": []},
            "buildability.build_def": {"value": 2.0, "score": 1.0, "evidence": []},
            "buildability.lockfile": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.ci": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.test_discoverability": {"value": 1.0, "score": 1.0, "evidence": []},
        },
        "dimensions": {
            "navigability": {"score": navigability, "signal_count": 4},
            "buildability": {"score": buildability, "signal_count": 4},
        },
    }



def _signals_map(**overrides):
    """静态信号映射形态 {signal_name: {score, value, evidence}}（report 同源）。"""
    base = {
        "navigability.agent_context_docs": {"value": 0.0, "score": 0.0, "evidence": []},
        "navigability.readme": {"value": 1.0, "score": 1.0, "evidence": ["README.md"]},
        "navigability.comment_density": {"value": 0.0, "score": 0.0, "evidence": []},
        "navigability.entry_clarity": {"value": 0.0, "score": 0.0, "evidence": []},
        "buildability.build_def": {"value": 2.0, "score": 1.0, "evidence": []},
        "buildability.lockfile": {"value": 1.0, "score": 1.0, "evidence": []},
        "buildability.ci": {"value": 1.0, "score": 1.0, "evidence": []},
        "buildability.test_discoverability": {"value": 1.0, "score": 1.0, "evidence": []},
    }
    base.update(overrides)
    return base


def _attr_signals(**kw):
    """专属归因信号假数据（测试覆盖缺口 + 单文件规模）。"""
    base = {
        "test_gap": {"value": 0.5, "score": 0.0, "evidence": ["gap 0.5"]},
        "big_file": {"value": 2000, "score": 0.0, "evidence": ["最大文件 2000 行"]},
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# failure_sources：(维度 × 失败模式) 聚合
# ---------------------------------------------------------------------------

class TestFailureSources:
    def test_groups_by_dimension_and_mode(self):
        f = failure_sources(_verdicts())
        groups = f["groups"]
        # 检索 → 可导航性：search-1 解出失败 2、search-2 超时 3
        assert groups["navigability"]["incorrect"][0]["task_id"] == "search-1"
        assert groups["navigability"]["incorrect"][0]["m"] == 2
        assert groups["navigability"]["budget"][0]["task_id"] == "search-2"
        assert groups["navigability"]["budget"][0]["m"] == 3
        # 定位 → 可诊断性：locate-1 超时 1
        assert groups["diagnosability"]["budget"][0]["task_id"] == "locate-1"
        # 修改无 runs → fail_incorrect 归可解性
        assert groups["solvability"]["incorrect"][0]["task_id"] == "modify-1"
        # 修改有 runs：P2P 回归 → 变更安全性；F2P 未过 → 可解性
        safety = groups["safety"]["incorrect"]
        assert any(e["task_id"] == "modify-2" and e["m"] == 1 for e in safety)
        solv = [e for e in groups["solvability"]["incorrect"] if e["task_id"] == "modify-3"]
        assert solv and solv[0]["m"] == 1
        # fail_env 剔除：search-3 不进组
        nav = groups["navigability"]
        assert all(e["task_id"] != "search-3" for e in nav["incorrect"] + nav["budget"])

    def test_budget_goes_to_solvability(self):
        """fail_budget 归可解性（#15：超时是解不出的真实信号）。"""
        f = failure_sources({"tasks": [
            {"task_id": "modify-x", "kind": "modify", "k": 5,
             "outcomes": ["fail_budget"] * 3 + ["success"] * 2},
        ]})
        assert f["groups"]["solvability"]["budget"][0]["m"] == 3

    def test_kind_totals(self):
        f = failure_sources(_verdicts())
        assert f["kind_totals"] == {"search": 3, "locate": 1, "modify": 3}

    def test_no_failures_empty(self):
        f = failure_sources({"tasks": [
            {"task_id": "s", "kind": "search", "k": 3,
             "outcomes": ["success", "success", "success"]},
        ]})
        assert f["groups"] == {}


# ---------------------------------------------------------------------------
# 确定性模板档
# ---------------------------------------------------------------------------

class TestDeterministicSuggestions:
    def test_signal_hit_template_with_failure_ref(self):
        """产分信号缺失 + 该维度有失败 → 模板建议，失败样本作为实证佐证并入。"""
        f = failure_sources(_verdicts())
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        # navigability 有两个低分信号 → 各出一条
        anchors = [s["anchor"] for s in sugg]
        assert "navigability.agent_context_docs" in anchors
        assert "navigability.comment_density" in anchors
        # 失败任务引用并入（锚定仍是信号，#15 §7）
        sd = next(s for s in sugg if s["anchor"] == "navigability.agent_context_docs")
        assert sd["failure_ref"]
        assert "检索" in sd["failure_ref"]

    def test_signal_hit_without_failure_still_suggested(self):
        """产分信号低分但无失败 → 仍出模板建议（改进轴独立于失败）。"""
        f = failure_sources({"tasks": []})
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        anchors = [s["anchor"] for s in sugg]
        assert "navigability.agent_context_docs" in anchors
        # 无失败 → 无失败引用
        assert all(not s["failure_ref"] for s in sugg)

    def test_no_deterministic_for_signal_less_dims(self):
        """可解性/可诊断性无静态信号 → 无确定性建议（LLM 兜底）。"""
        f = failure_sources(_verdicts())
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        anchors = [s["anchor"] for s in sugg]
        assert "solvability" not in anchors
        assert "diagnosability" not in anchors

    def test_test_gap_template_for_safety(self):
        """变更安全性失败 + 测试覆盖缺口命中 → 确定性模板（锚定归因信号）。"""
        f = failure_sources({"tasks": [
            {"task_id": "modify-r", "kind": "modify", "k": 5,
             "outcomes": ["fail_incorrect", "success", "success", "success", "success"],
             "runs": [
                 {"outcome": "fail_incorrect", "f2p": [True, True], "p2p": [True, False]},
             ]},
        ]})
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        gap = [s for s in sugg if s["anchor"] == "safety.test_gap"]
        assert gap
        assert gap[0]["failure_ref"] and "修改" in gap[0]["failure_ref"]

    def test_big_file_template_for_efficiency(self):
        """效率低分 + 单文件规模命中 → 确定性模板（#15 §8 独立低分驱动路径）。"""
        f = failure_sources({"tasks": []})
        sugg = build_deterministic_suggestions(
            f, _signals_map(), _attr_signals(),
            efficiency={"point": 0.3, "raw_percentile": 0.7},
        )
        bf = [s for s in sugg if s["anchor"] == "efficiency.big_file"]
        assert bf

    def test_efficiency_high_no_suggestion(self):
        """效率不低 → 单文件规模模板不触发。"""
        f = failure_sources({"tasks": []})
        sugg = build_deterministic_suggestions(
            f, _signals_map(), _attr_signals(),
            efficiency={"point": 0.9},
        )
        assert all(s["anchor"] != "efficiency.big_file" for s in sugg)

    def test_priority_key_impact(self):
        """排序键：维度分最低优先 → 信号档位最低优先 → 影响面（失败数多优先）。"""
        f = failure_sources(_verdicts())
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        prios = [s["priority"] for s in sugg]
        assert prios == sorted(prios)

    def test_suggestion_fields_complete(self):
        """每条建议含锚定 + 预期方向 + 可重测声明（#8 #7）。"""
        f = failure_sources(_verdicts())
        sugg = build_deterministic_suggestions(f, _signals_map(), _attr_signals())
        for s in sugg:
            assert s["anchor"]
            assert s["direction"]
            assert "可重测" in s["remeasurable"] or "重跑" in s["remeasurable"]


# ---------------------------------------------------------------------------
# 失败任务引用（#12/#15：`<类别> <m>/<k>（失败模式）`）
# ---------------------------------------------------------------------------

class TestFailureRef:
    def test_ref_format(self):
        f = failure_sources(_verdicts())
        # 检索：search-1 失败（2 解出失败）+ search-2 失败（3 超时）= 2/3 失败
        ref = build_failure_ref(f, "navigability")
        assert ref
        assert "检索" in ref
        assert "2/3" in ref
        assert "超时" in ref

    def test_no_failures_none(self):
        f = failure_sources({"tasks": []})
        assert build_failure_ref(f, "navigability") is None


# ---------------------------------------------------------------------------
# 轨迹确定性切片（LLM 证据包，不含任务原文）
# ---------------------------------------------------------------------------

class TestSliceTrace:
    def _trace(self, *events):
        return "\n".join(json.dumps(e) for e in events)

    def test_tool_names_and_files(self):
        trace = self._trace(
            {"type": "turn_start"},
            {"type": "tool_execution_start", "toolName": "grep", "input": {"pattern": "foo"}},
            {"type": "tool_execution_start", "toolName": "read", "input": {"file_path": "src/cart.js"}},
            {"type": "tool_execution_start", "toolName": "write", "input": {"file_path": "src/cart.js"}},
            {"type": "turn_start"},
            {"type": "agent_settled"},
        )
        s = slice_trace(trace)
        assert s["turns"] == 2
        names = [t["tool"] for t in s["tool_calls"]]
        assert names == ["grep", "read", "write"]
        # 目标文件（从输入提取）
        files = [t.get("file") for t in s["tool_calls"]]
        assert files[1] == "src/cart.js"

    def test_excludes_message_content(self):
        """任务原文（user 消息）不得进入切片（#15 §5 不含任务原文）。"""
        trace = self._trace(
            {"type": "message_start", "message": {"role": "user",
             "content": [{"type": "text", "text": "任务描述秘密原文"}]}},
            {"type": "tool_execution_start", "toolName": "read", "input": {"file_path": "a.py"}},
        )
        s = slice_trace(trace)
        blob = json.dumps(s, ensure_ascii=False)
        assert "任务描述秘密原文" not in blob

    def test_last_steps(self):
        trace = self._trace(*[
            {"type": "tool_execution_start", "toolName": f"tool{i}", "input": {}}
            for i in range(6)
        ])
        s = slice_trace(trace)
        assert len(s["last_steps"]) == 5  # 末 5 步
        assert s["last_steps"][-1]["tool"] == "tool5"


# ---------------------------------------------------------------------------
# LLM 兜底档（结构化 JSON，非法丢弃）
# ---------------------------------------------------------------------------

class _FakeLLM:
    """测试替身 LLM：按 prompt 返回预设输出。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, prompt, *, model=None):
        self.calls.append((prompt, model))
        if not self.outputs:
            return None
        return self.outputs.pop(0)


class TestRunAttribution:
    def test_offline_deterministic_only(self):
        """offline（llm=None）：只出确定性档，不出 LLM 建议。"""
        f = failure_sources(_verdicts())
        r = run_attribution(f, _signals_map(), llm=None, attribution_signals=_attr_signals())
        assert all(s["source"] != "llm" for s in r["suggestions"])
        assert r["llm_groups"] == []  # 未被归因的组记录在案（供报告说明）

    def test_llm_fills_signal_less_dims(self):
        """可解性/可诊断性失败 → LLM 锚定维度综合归因（结构化 JSON 合法才保留）。"""
        f = failure_sources(_verdicts())
        # 两条合法 LLM 输出（solvability / diagnosability 各一组，按组触发一次）
        fake = _FakeLLM([
            json.dumps({"dimension": "solvability", "text": "修改任务解出率低：建议补充单元测试与更清晰的失败输出", "direction": "up"}, ensure_ascii=False),
            json.dumps({"dimension": "diagnosability", "text": "定位任务超时：建议补充错误日志与可诊断信息", "direction": "up"}, ensure_ascii=False),
        ])
        r = run_attribution(f, _signals_map(), llm=fake, attribution_signals=_attr_signals())
        llm_sugg = [s for s in r["suggestions"] if s["source"] == "llm"]
        assert any(s["anchor"] == "solvability" for s in llm_sugg)
        assert any(s["anchor"] == "diagnosability" for s in llm_sugg)
        assert fake.calls  # 确实调了 LLM

    def test_llm_invalid_json_dropped(self):
        """非法结构（非 JSON / 缺字段 / 锚定维度非法）→ 整条丢弃（#8 约束 c）。"""
        f = failure_sources(_verdicts())
        fake = _FakeLLM([
            "这不是 JSON",
            json.dumps({"text": "缺 dimension 字段"}, ensure_ascii=False),
            json.dumps({"dimension": "bogus_dim", "text": "非法维度", "direction": "up"}, ensure_ascii=False),
        ])
        r = run_attribution(f, _signals_map(), llm=fake, attribution_signals=_attr_signals())
        llm_sugg = [s for s in r["suggestions"] if s["source"] == "llm"]
        assert llm_sugg == []  # 全部丢弃

    def test_llm_failure_returns_none_skips(self):
        """LLM 调用失败（None）→ 该组跳过，不炸管线。"""
        f = failure_sources(_verdicts())
        fake = _FakeLLM([None])
        r = run_attribution(f, _signals_map(), llm=fake, attribution_signals=_attr_signals())
        assert all(s["source"] != "llm" for s in r["suggestions"])

    def test_evidence_pack_excludes_task_prompts(self):
        """LLM 证据包 = 判卷 + 轨迹切片 + 静态快照，不含任务原文。"""
        f = failure_sources(_verdicts())
        trace = json.dumps({"type": "message_start", "message": {"role": "user",
                           "content": [{"type": "text", "text": "TOP_SECRET_TASK"}]}})
        fake = _FakeLLM([
            json.dumps({"dimension": "solvability", "text": "建议补充测试", "direction": "up"}, ensure_ascii=False),
        ])
        r = run_attribution(
            f, _signals_map(), llm=fake, attribution_signals=_attr_signals(),
            traces={"modify-1": trace},
        )
        prompt = fake.calls[0][0]
        assert "TOP_SECRET_TASK" not in prompt
        assert "modify" in prompt  # 判卷信息在

    def test_llm_rank_tiebreak(self):
        """LLM 建议带 llm_rank；排序键 = (确定性键, llm_rank)。"""
        f = failure_sources(_verdicts())
        fake = _FakeLLM([
            json.dumps({"dimension": "solvability", "text": "A", "direction": "up"}, ensure_ascii=False),
            json.dumps({"dimension": "diagnosability", "text": "B", "direction": "up"}, ensure_ascii=False),
        ])
        r = run_attribution(f, _signals_map(), llm=fake, attribution_signals=_attr_signals())
        llm_sugg = [s for s in r["suggestions"] if s["source"] == "llm"]
        keys = [(s["priority"], s.get("llm_rank", 999)) for s in llm_sugg]
        assert keys == sorted(keys)


