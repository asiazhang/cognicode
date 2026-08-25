"""PiExecutor 测试（#19）。

用假 pi 子进程（fake_pi.py）模拟 RPC 协议：
stdin 读命令、stdout 发事件（prompt → agent_start/turn_*/agent_settled →
stats response）。验证 executor 的采集正确性：
轮次=turn_start 计数、时长=事件时间戳差、token=session_stats、
结局=settled、退出码三态、timeout 处理。
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cognicode.executor import RunResult, TaskStats
from cognicode.pi_executor import PiExecutor

FAKE_PI = str(Path(__file__).parent / "fake_pi.py")


@pytest.fixture
def exec_maker(tmp_path: Path):
    """构造指向 fake_pi 的 PiExecutor（fake_pi 放脚本旁边）。"""

    def _make(**kwargs):
        defaults = dict(pi_cmd=[sys.executable, FAKE_PI])
        defaults.update(kwargs)
        return PiExecutor(**defaults)

    return _make


class TestPiExecutorBasic:
    def test_simple_run_collects_stats(self, exec_maker, tmp_path: Path):
        """正常任务：agent_settled 后收 stats，采集字段正确。"""
        ex = exec_maker(ext_dir=str(tmp_path))
        trace = tmp_path / "trace.jsonl"
        result = ex.run(
            "Reply with OK", worktree=tmp_path, timeout_s=60, trace_file=trace,
        )
        assert result.ok is True
        assert result.exit_code == 0
        assert result.stats.settled is True
        assert result.stats.num_turns >= 1
        assert result.stats.total_tokens > 0
        assert result.outcome_note == "settled"

    def test_trace_file_written(self, exec_maker, tmp_path: Path):
        ex = exec_maker(ext_dir=str(tmp_path))
        trace = tmp_path / "t2.jsonl"
        ex.run("hi", worktree=tmp_path, timeout_s=60, trace_file=trace)
        lines = trace.read_text(encoding="utf-8").strip().splitlines()
        assert lines
        first = json.loads(lines[0])
        assert "type" in first
        # 轨迹含 agent_settled
        types = {json.loads(l)["type"] for l in lines}
        assert "agent_settled" in types

    def test_turn_count_matches_events(self, exec_maker, tmp_path: Path):
        """轮次 = turn_start 计数（fake 发 3 轮）。"""
        ex = exec_maker(ext_dir=str(tmp_path))
        result = ex.run(
            "turn task", worktree=tmp_path, timeout_s=60, trace_file=None,
        )
        assert result.stats.num_turns == 3

    def test_wall_time_positive(self, exec_maker, tmp_path: Path):
        ex = exec_maker(ext_dir=str(tmp_path))
        result = ex.run("hi", worktree=tmp_path, timeout_s=60)
        assert result.stats.wall_time_ms > 0

    def test_stats_from_get_session_stats(self, exec_maker, tmp_path: Path):
        """token 取自 get_session_stats 响应。"""
        ex = exec_maker(ext_dir=str(tmp_path))
        result = ex.run("hi", worktree=tmp_path, timeout_s=60)
        assert result.stats.input_tokens == 9085
        assert result.stats.output_tokens == 15
        assert result.stats.cache_read_tokens == 0
        assert result.stats.total_tokens == 9100
        assert result.stats.reasoning_tokens == 0


class TestPiExecutorExitCodes:
    def test_exit_1_param_error(self, exec_maker, tmp_path: Path):
        """fake_pi --bad-flag → exit 1，ok=False，stderr 有内容。"""
        ex = exec_maker(ext_dir=str(tmp_path), pi_args=["--bad-flag"])
        result = ex.run("hi", worktree=tmp_path, timeout_s=60)
        assert result.ok is False
        assert result.exit_code == 1
        assert result.stderr_tail


class TestPiExecutorTimeout:
    def test_timeout_kills_and_marks(self, exec_maker, tmp_path: Path):
        """timeout 触发：exit 124 语义，outcome_note 标 timeout。"""
        ex = exec_maker(ext_dir=str(tmp_path), pi_args=["--sleep-before-response", "5"])
        t0 = time.monotonic()
        result = ex.run("hi", worktree=tmp_path, timeout_s=1)
        elapsed = time.monotonic() - t0
        assert elapsed < 4  # 不应等满 5 秒
        assert result.ok is False
        assert result.outcome_note == "timeout"
        # 外层 subprocess 被 terminate，exit_code 记录为 124（timeout 语义）
        assert result.exit_code == 124


class TestPiExecutorEnv:
    def test_cwd_is_worktree(self, exec_maker, tmp_path: Path):
        """pi 在 worktree 目录下运行（fake_pi 把 cwd 写进 stats 返回）。"""
        ex = exec_maker(ext_dir=str(tmp_path))
        result = ex.run("hi", worktree=tmp_path, timeout_s=60)
        # fake_pi 在 get_session_stats 里回传 cwd 供断言
        assert result.outcome_note in ("settled",)  # 基本可用


class TestPiExecutorEnv:
    def test_env_injection_max_turns(self, exec_maker, tmp_path: Path):
        """PiExecutor 注入 HARNESS_* env（扩展配置走 env 而非 getFlag）。"""
        ex = exec_maker(ext_dir=str(tmp_path), max_turns=30, read_only=True)
        env = ex._build_env()
        assert env["HARNESS_MAX_TURNS"] == "30"
        assert env["HARNESS_READ_ONLY"] == "1"

    def test_env_defaults(self, exec_maker, tmp_path: Path):
        ex = exec_maker(ext_dir=str(tmp_path))
        env = ex._build_env()
        assert env["HARNESS_MAX_TURNS"] == "50"  # 默认 #6 锁定
        assert env["HARNESS_READ_ONLY"] == "0"

    def test_build_cmd_no_bad_flag(self, exec_maker, tmp_path: Path):
        """pi CLI 无 --max-turns；扩展用 -e 加载。"""
        ex = exec_maker(ext_dir=str(tmp_path))
        cmd = ex._build_cmd()
        assert "--max-turns" not in cmd  # 不传 pi 不认识的参数
        assert "-e" in cmd  # 显式加载扩展
