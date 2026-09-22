"""CLI harness 接入测试（#19）：scan 触发探测 + 单任务执行，落盘产物。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cognicode.cli import main

FAKE_PI = str(Path(__file__).parent / "fake_pi.py")


@pytest.fixture
def git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "Makefile").write_text(
        "build:\n\ttrue\n"
        "test:\n\ttrue\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


class TestScanWithHarness:
    def test_scan_probe_uses_fake_pi(self, git_repo: Path, tmp_path, monkeypatch, capsys):
        """scan 在 offline 模式触发探测（假 pi），落盘探测结果。"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "cognicode.pi_executor.PiExecutor",
            _FakePiExecutor,
        )
        assert main(["scan", "--offline", str(git_repo)]) == 0
        run_dir = tmp_path / ".cognicode"
        probe_file = next(run_dir.glob("*/probe.json"))
        data = json.loads(probe_file.read_text(encoding="utf-8"))
        assert "success" in data
        assert "exit_codes" in data

    def test_scan_probe_success_generates_tasks(self, git_repo: Path, tmp_path, monkeypatch, capsys):
        """探测成功 → 任务生成落盘 tasks.json（#20 接入 CLI）。"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "cognicode.pi_executor.PiExecutor",
            _FakePiExecutor,
        )
        assert main(["scan", "--offline", str(git_repo)]) == 0
        run_dir = tmp_path / ".cognicode"
        tasks_file = next(run_dir.glob("*/tasks.json"))
        data = json.loads(tasks_file.read_text(encoding="utf-8"))
        # 假仓库（composer.json 无源码符号）→ 任务可能为空，但结构完整
        assert "counts" in data
        assert "tasks" in data
        assert set(data["counts"].keys()) == {"search", "locate", "modify"}


class _FakePiExecutor:
    """替代 PiExecutor：不真跑 pi，探测命令直接成功。"""

    def __init__(self, *args, **kwargs):
        pass

    def run(self, prompt, worktree, *, timeout_s=900, trace_file=None):
        from cognicode.executor import RunResult
        if trace_file:
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            trace_file.write_text(
                json.dumps({"type": "agent_settled", "fake": True}) + "\n",
                encoding="utf-8")
        return RunResult(ok=True, exit_code=0)
