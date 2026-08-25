"""executor 抽象接口测试（#19）。

验证：数据结构字段语义（TaskStats/RunResult）与 Executor 协议形状。
纯协议层，无 I/O。
"""

import pytest

from cognicode.executor import RunResult, TaskStats


class TestTaskStats:
    def test_defaults_zero(self):
        s = TaskStats()
        assert s.num_turns == 0
        assert s.wall_time_ms == 0
        assert s.input_tokens == 0
        assert s.total_tokens == 0
        assert s.tool_calls == 0
        assert s.settled is False

    def test_frozen(self):
        s = TaskStats(num_turns=3)
        with pytest.raises(Exception):
            s.num_turns = 4  # type: ignore[misc]


class TestRunResult:
    def test_defaults(self):
        r = RunResult(ok=True, exit_code=0)
        assert r.ok is True
        assert r.exit_code == 0
        assert r.trace_file is None
        assert r.diff == ""
        assert r.stats == TaskStats()
        assert r.outcome_note == ""

    def test_frozen(self):
        r = RunResult(ok=True, exit_code=0)
        with pytest.raises(Exception):
            r.ok = False  # type: ignore[misc]

    def test_stats_passthrough(self):
        s = TaskStats(num_turns=5, total_tokens=9100)
        r = RunResult(ok=True, exit_code=0, stats=s)
        assert r.stats.num_turns == 5
        assert r.stats.total_tokens == 9100
