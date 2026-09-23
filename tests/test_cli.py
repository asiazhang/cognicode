"""CLI 壳的冒烟测试（不经网络、不经 pipeline）。"""

import pytest

from cognicode.cli import main


class TestCli:
    def test_version_includes_report_schema(self, capsys):
        with pytest.raises(SystemExit) as e:
            main(["--version"])
        assert e.value.code == 0
        out = capsys.readouterr().out
        assert "cognicode" in out
        assert "report-schema" in out

    def test_scan_accepts_repo_and_offline(self, capsys, tmp_path):
        repo = tmp_path / "some-repo"
        repo.mkdir()
        assert main(["scan", str(repo)]) == 0
        assert main(["scan", "--offline", str(repo)]) == 0
        out = capsys.readouterr().out
        assert "offline" in out

    def test_scan_missing_repo_dir_rejected(self, capsys):
        # 不存在的目录 → 报错退出码 1（不做空跑）
        assert main(["scan", "/tmp/definitely-not-a-repo-xyz"]) == 1

    def test_missing_subcommand_rejected(self):
        with pytest.raises(SystemExit):
            main([])

    def test_scan_writes_static_json(self, tmp_path, monkeypatch, capsys):
        # 端到端：scan 在 .cognicode/<run-id>/ 落盘合法 static.json
        monkeypatch.chdir(tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("# rules\n")
        (repo / "README.md").write_text("# hi\n")
        assert main(["scan", str(repo)]) == 0
        run_dir = tmp_path / ".cognicode"
        static_file = next(run_dir.glob("*/static.json"))
        import json

        data = json.loads(static_file.read_text(encoding="utf-8"))
        assert data["signals"]["navigability.agent_context_docs"]["score"] == 1.0
        assert data["dimensions"]["navigability"]["score"] == 0.5  # (1+1+0+0)/4
