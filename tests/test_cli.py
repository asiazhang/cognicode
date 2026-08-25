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

    def test_scan_accepts_repo_and_offline(self, capsys):
        assert main(["scan", "/tmp/some-repo"]) == 0
        assert main(["scan", "--offline", "/tmp/some-repo"]) == 0
        out = capsys.readouterr().out
        assert "offline" in out

    def test_report_accepts_run_id(self, capsys):
        assert main(["report", "run-123"]) == 0

    def test_missing_subcommand_rejected(self):
        with pytest.raises(SystemExit):
            main([])
