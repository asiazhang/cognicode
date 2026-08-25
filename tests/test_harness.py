"""harness 层测试（#19）。

验证：worktree 创建、探测执行（ProbeRunner）、任务执行编排
（fresh worktree + timeout + git diff 收产物）、轨迹落盘。
用假 executor（不真跑 pi）隔离 harness 编排逻辑。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cognicode.executor import RunResult, TaskStats
from cognicode.harness import (
    ProbeRunner,
    WorktreeManager,
    run_task,
)


@pytest.fixture
def git_repo(tmp_path: Path):
    """造一个最小 git 仓库（含一个文件 + 一次提交），供 worktree 测试。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "hello.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


class TestWorktreeManager:
    def test_create_worktree_clones_repo(self, git_repo: Path, tmp_path: Path):
        wt_dir = tmp_path / "wts"
        mgr = WorktreeManager(source_repo=git_repo, worktrees_dir=wt_dir)
        with mgr.worktree() as wt:
            assert wt.is_dir()
            assert (wt / "hello.txt").exists()
            assert (wt / ".git").exists()
        # 退出后 worktree 被清理
        assert not wt.exists()

    def test_worktree_isolated_from_source(self, git_repo: Path, tmp_path: Path):
        """worktree 里改动不影响源仓库。"""
        wt_dir = tmp_path / "wts"
        mgr = WorktreeManager(source_repo=git_repo, worktrees_dir=wt_dir)
        with mgr.worktree() as wt:
            (wt / "hello.txt").write_text("changed\n", encoding="utf-8")
            src = (git_repo / "hello.txt").read_text(encoding="utf-8")
            assert src == "hello\n"


class FakeExecutor:
    """假 executor：不真跑 pi，返回预设 RunResult；按真实行为写 trace 文件。"""

    def __init__(self, results: list[RunResult] | None = None):
        self.results = list(results or [])
        self.calls: list[tuple[str, Path]] = []

    def run(self, prompt: str, worktree: Path, *, timeout_s: int = 900,
            trace_file: Path | None = None) -> RunResult:
        self.calls.append((prompt, worktree))
        r = self.results.pop(0) if self.results else RunResult(ok=True, exit_code=0)
        if trace_file:
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            trace_file.write_text(
                json.dumps({"type": "agent_settled", "fake": True}) + "\n",
                encoding="utf-8",
            )
        return r


class TestProbeRunner:
    def test_probe_runs_located_commands(self, tmp_path: Path):
        """ProbeRunner 对定位到的命令逐条执行，记录 exit code 与耗时。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
        (repo / "composer.json").write_text(
            '{"scripts": {"build": "true", "test": "true"}}', encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
        # 假 executor：每次 run 都 ok（探测就是让 agent 跑命令）
        ex = FakeExecutor([
            RunResult(ok=True, exit_code=0),  # build
            RunResult(ok=True, exit_code=0),  # test
        ])
        runner = ProbeRunner(executor=ex)
        result = runner.run(repo)
        assert result["success"] is True
        assert result["exit_codes"]["build.composer"] == 0

    def test_probe_fail_all_degrades(self, tmp_path: Path):
        repo = tmp_path / "repo2"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
        (repo / "composer.json").write_text(
            '{"scripts": {"build": "false", "test": "false"}}', encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
        ex = FakeExecutor([
            RunResult(ok=False, exit_code=1),
            RunResult(ok=False, exit_code=1),
        ])
        runner = ProbeRunner(executor=ex)
        result = runner.run(repo)
        assert result["success"] is False
        assert result["degrade"] is True  # 探测全灭 → 整体降级


class TestRunTask:
    def test_run_task_uses_worktree_and_collects_diff(self, git_repo: Path, tmp_path: Path):
        """run_task：fresh worktree + 假 executor + 收集 diff。"""
        wt_dir = tmp_path / "wts"
        mgr = WorktreeManager(source_repo=git_repo, worktrees_dir=wt_dir)
        ex = FakeExecutor()
        trace = tmp_path / "runs" / "t1" / "traces" / "task1.jsonl"
        result = run_task(
            executor=ex,
            worktree_mgr=mgr,
            prompt="do something",
            task_id="task1",
            run_dir=tmp_path / "runs" / "t1",
            timeout_s=60,
        )
        assert result is not None
        # 假 executor 被调用，worktree 目录在调用期间有效（退出后已清理）
        assert ex.calls, "executor 应被调用一次"
        assert (tmp_path / "runs" / "t1" / "traces" / "task1.jsonl").exists()

    def test_run_task_returns_none_on_worktree_failure(self, tmp_path: Path):
        """源仓库不是 git 仓库 → worktree 创建失败 → 返回 None（fail_env）。"""
        repo = tmp_path / "not-git"
        repo.mkdir()
        wt_dir = tmp_path / "wts"
        mgr = WorktreeManager(source_repo=repo, worktrees_dir=wt_dir)
        ex = FakeExecutor()
        result = run_task(
            executor=ex, worktree_mgr=mgr, prompt="x", task_id="t",
            run_dir=tmp_path / "runs", timeout_s=60,
        )
        assert result is None
