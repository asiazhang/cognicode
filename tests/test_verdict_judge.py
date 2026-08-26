"""判卷判定层单元测试（#21，verdict.py 扩展）。

验证判定纯函数（构造假数据驱动，符合 #24 done 标准 2「判卷五类结果分类
在构造假数据上单测全绿」）：
- judge_result：RunResult/交卷/测试结果 → 五类 outcome
- judge_modify：F2P/P2P 四态 → success / fail_incorrect
- match_location / match_injection：位置匹配（检索/定位）
- parse_submit_verdict：轨迹里 submit_result 的结构化交卷
- fail_budget / fail_env 判定

期望值全部来自独立手算的已知字面（防 tautological）。
"""

import json

import pytest

from cognicode.executor import RunResult, TaskStats
from cognicode.verdict import (
    judge_modify,
    judge_result,
    match_injection,
    match_location,
    parse_submit_verdict,
)

# 构造假 RunResult（#19 数据结构，纯协议）
def _result(ok=True, exit_code=0, note="settled", settled=True, turns=3):
    stats = TaskStats(num_turns=turns, wall_time_ms=1000, total_tokens=9100, settled=settled)
    return RunResult(ok=ok, exit_code=exit_code, outcome_note=note, stats=stats)


class TestJudgeModify:
    """修改类：F2P/P2P 双闸 → success / fail_incorrect。"""

    def test_f2p_pass_p2p_no_regression_success(self):
        # F2P 红→绿（True→True）+ P2P 前后都绿 → success
        assert judge_modify(f2p_before=True, f2p_after=True, p2p_before=True, p2p_after=True) == "success"

    def test_f2p_fail_is_incorrect(self):
        # F2P 没过（解不出）→ fail_incorrect
        assert judge_modify(f2p_before=True, f2p_after=False, p2p_before=True, p2p_after=True) == "fail_incorrect"

    def test_p2p_regression_is_incorrect(self):
        # F2P 过但 P2P 回归（解出但炸了别处，变更安全性失败）→ fail_incorrect
        assert judge_modify(f2p_before=True, f2p_after=True, p2p_before=True, p2p_after=False) == "fail_incorrect"

    def test_p2p_baseline_not_green_is_incorrect(self):
        # 守护测试改动前就不绿（基线已坏）→ 不算成功
        assert judge_modify(f2p_before=True, f2p_after=True, p2p_before=False, p2p_after=True) == "fail_incorrect"

    def test_f2p_not_red_rejected(self):
        # F2P 本来就是绿的（bug 没被测试抓住）→ 任务无效，判卷层拒绝
        with pytest.raises(ValueError):
            judge_modify(f2p_before=False, f2p_after=True, p2p_before=True, p2p_after=True)


class TestMatchLocation:
    """检索类：符号级位置匹配（file::name，非行号，#5 锁定）。"""

    GT = "application/api/controller/Cart.php::index"

    def test_exact_full_path(self):
        assert match_location("application/api/controller/Cart.php::index", self.GT) is True

    def test_verdict_with_parens(self):
        # #28 实测交卷形如 Cart.php::index()（带括号）
        assert match_location("application/api/controller/Cart.php::index()", self.GT) is True

    def test_verdict_without_dir_prefix(self):
        # 交卷只写文件名 + 符号名 → 命中
        assert match_location("Cart.php::index", self.GT) is True

    def test_wrong_symbol_not_match(self):
        assert match_location("Cart.php::list()", self.GT) is False

    def test_wrong_file_not_match(self):
        assert match_location("Order.php::index", self.GT) is False

    def test_empty_verdict_not_match(self):
        assert match_location("", self.GT) is False
        assert match_location(None, self.GT) is False


class TestMatchInjection:
    """定位类：对照注入点（file，行号容差 ±2）。"""

    INJ = {"file": "application/api/controller/Cart.php", "line": 12, "patch": "-old\n+new"}

    def test_file_only(self):
        assert match_injection("Cart.php", self.INJ) is True

    def test_file_with_close_line(self):
        assert match_injection("Cart.php:10", self.INJ) is True  # 12-2=10 容差内

    def test_file_with_far_line(self):
        assert match_injection("Cart.php:50", self.INJ) is False

    def test_wrong_file(self):
        assert match_injection("Order.php:12", self.INJ) is False


class TestParseSubmitVerdict:
    """轨迹里 submit_result 的结构化交卷解析（#29 实测 details.verdict）。"""

    def _trace(self, *events):
        return "\n".join(json.dumps(e) for e in events)

    def test_parses_details_verdict(self):
        trace = self._trace(
            {"type": "tool_execution_start", "toolName": "submit_result"},
            {"type": "tool_execution_end", "toolName": "submit_result",
             "result": {"content": [{"type": "text", "text": "submitted: x"}],
                        "details": {"verdict": "Cart.php::index", "evidence": ["Cart.php:12"]}}},
            {"type": "agent_settled"},
        )
        assert parse_submit_verdict(trace) == "Cart.php::index"

    def test_no_submit_returns_none(self):
        trace = self._trace({"type": "agent_start"}, {"type": "agent_settled"})
        assert parse_submit_verdict(trace) is None

    def test_other_tools_ignored(self):
        trace = self._trace(
            {"type": "tool_execution_end", "toolName": "bash",
             "result": {"content": [{"type": "text", "text": "ok"}]}},
            {"type": "agent_settled"},
        )
        assert parse_submit_verdict(trace) is None

    def test_malformed_lines_skipped(self):
        trace = "not json\n" + self._trace({"type": "agent_settled"})
        assert parse_submit_verdict(trace) is None


class TestJudgeResult:
    """judge_result：一次任务运行 → 五类 outcome（构造数据）。"""

    def test_worktree_failure_is_env(self):
        # run_task 返回 None（worktree 失败）→ fail_env
        assert judge_result("modify", result=None) == "fail_env"

    def test_timeout_is_budget(self):
        # exit 124 / timeout → fail_budget
        r = _result(ok=False, exit_code=124, note="timeout", settled=False)
        assert judge_result("search", result=r) == "fail_budget"

    def test_max_turns_budget_flag(self):
        # max-turns 触顶（扩展早停）→ fail_budget（调用方传 budget=True）
        r = _result(ok=True, exit_code=0, note="settled")
        assert judge_result("search", result=r, budget=True) == "fail_budget"

    def test_process_crash_is_env(self):
        # exit 非 0 非 124 且未 settled（进程崩溃）→ fail_env
        r = _result(ok=False, exit_code=1, note="进程提前退出 rc=1", settled=False)
        assert judge_result("modify", result=r) == "fail_env"

    def test_search_location_match_success(self):
        r = _result()
        assert judge_result(
            "search", result=r, ground_truth="application/api/controller/Cart.php::index",
            verdict="Cart.php::index",
        ) == "success"

    def test_search_location_miss_incorrect(self):
        r = _result()
        assert judge_result(
            "search", result=r, ground_truth="application/api/controller/Cart.php::index",
            verdict="Cart.php::list",
        ) == "fail_incorrect"

    def test_search_no_verdict_incorrect(self):
        # 没交卷（没定位到）→ fail_incorrect
        r = _result()
        assert judge_result("search", result=r, ground_truth="a.php::x", verdict=None) == "fail_incorrect"

    def test_locate_injection_match_success(self):
        r = _result()
        inj = {"file": "application/api/controller/Cart.php", "line": 12, "patch": ""}
        assert judge_result("locate", result=r, injection=inj, verdict="Cart.php:12") == "success"

    def test_locate_injection_miss_incorrect(self):
        r = _result()
        inj = {"file": "application/api/controller/Cart.php", "line": 12, "patch": ""}
        assert judge_result("locate", result=r, injection=inj, verdict="Order.php:12") == "fail_incorrect"

    def test_modify_f2p_p2p_success(self):
        r = _result()
        assert judge_result(
            "modify", result=r,
            f2p=(True, True), p2p=(True, True),
        ) == "success"

    def test_modify_f2p_fail_incorrect(self):
        r = _result()
        assert judge_result(
            "modify", result=r,
            f2p=(True, False), p2p=(True, True),
        ) == "fail_incorrect"

    def test_modify_missing_test_data_incorrect(self):
        # 判卷数据不全（没跑测试）→ fail_incorrect（判定不了 = 没通过）
        r = _result()
        assert judge_result("modify", result=r, f2p=None, p2p=None) == "fail_incorrect"

    def test_unknown_kind_rejected(self):
        r = _result()
        with pytest.raises(ValueError):
            judge_result("probe", result=r)
