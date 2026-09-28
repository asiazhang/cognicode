"""scan 入口测试（#58）：工件目录协议 + per-extractor 容错 + 退出码。

验证 ARTIFACTS.md 的协议纪律：
- 工件落盘位置（被扫仓库根 .cognicode/debt-scan/）与信封形状（§3）；
- 单提取器失败只缩窄（该工件 status=failed + error），其余照常、退出码 0；
- 确定性：提取器工件与时间戳无关，同 repo 重跑 diff 稳定（scan.json 的
  元信息除外）。
"""

import json

import pytest

from scan import (
    EXTRACTORS,
    _probe_payload,
    _write_envelope,
    main,
    scan,
)


def _make_repo(tmp_path):
    """造一个可提取的最小仓库。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text(
        "def real_fn():\n    return 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text(
        "def test_real_fn():\n    pass\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    return repo


class TestScanArtifacts:
    def test_all_artifacts_written_with_envelope(self, tmp_path):
        """三类工件落盘 + 信封形状（ARTIFACTS.md §3）。"""
        repo = _make_repo(tmp_path)
        assert scan(repo, quiet=True) == 0
        out = repo / ".cognicode" / "debt-scan"
        for name in ("scan.json", "symbols.json", "static_signals.json",
                     "probe.json"):
            assert (out / name).is_file(), f"缺工件 {name}"

        sym = json.loads((out / "symbols.json").read_text(encoding="utf-8"))
        assert sym["schema"] == "debt-scan/symbols@1"
        assert sym["extractor"] == "symbols"
        assert sym["status"] == "ok"
        assert sym["repo"] == str(repo.resolve())
        # 债检测口径：测试符号入面（#58 验收项）
        names = {s["name"] for s in sym["data"]["symbols"]}
        assert "real_fn" in names
        assert "test_real_fn" in names

        stat = json.loads((out / "static_signals.json").read_text(encoding="utf-8"))
        assert stat["extractor"] == "static-signals"
        assert stat["status"] == "ok"
        assert len(stat["data"]["signals"]) == 8

        probe = json.loads((out / "probe.json").read_text(encoding="utf-8"))
        assert probe["extractor"] == "probe"
        assert probe["status"] == "ok"
        # pyproject + tests/ → pytest 测试命令定位
        assert any(c["kind"] == "test" and "pytest" in c["command"]
                   for c in probe["data"]["commands"])

        scan_meta = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        assert {r["status"] for r in scan_meta["extractors"]} == {"ok"}

    def test_extractor_subset(self, tmp_path):
        """--extractors 只跑指定提取器。"""
        repo = _make_repo(tmp_path)
        assert scan(repo, extractors=["probe"], quiet=True) == 0
        out = repo / ".cognicode" / "debt-scan"
        assert (out / "probe.json").is_file()
        assert not (out / "symbols.json").exists()

    def test_deterministic_artifacts_across_runs(self, tmp_path):
        """提取器工件与时间戳无关：重跑字节一致（scan.json 元信息除外）。"""
        repo = _make_repo(tmp_path)
        scan(repo, quiet=True)
        first = {
            f: (repo / ".cognicode" / "debt-scan" / f).read_text(encoding="utf-8")
            for f in ("symbols.json", "static_signals.json", "probe.json")
        }
        scan(repo, quiet=True)
        for f, content in first.items():
            assert (repo / ".cognicode" / "debt-scan" / f).read_text(
                encoding="utf-8") == content


class TestPerExtractorTolerance:
    def test_failed_extractor_recorded_not_fatal(self, tmp_path, monkeypatch, capsys):
        """单提取器失败：该工件 status=failed + error，其余照常，退出码 0。"""
        repo = _make_repo(tmp_path)

        def boom(_repo):
            raise RuntimeError("tree-sitter 炸了")

        monkeypatch.setitem(EXTRACTORS, "symbols", (boom, "symbols.json"))
        rc = scan(repo, quiet=True)
        assert rc == 0  # 缩窄不炸

        out = repo / ".cognicode" / "debt-scan"
        sym = json.loads((out / "symbols.json").read_text(encoding="utf-8"))
        assert sym["status"] == "failed"
        assert sym["data"] is None
        assert "RuntimeError" in sym["error"]
        # 其余提取器照常产出
        stat = json.loads((out / "static_signals.json").read_text(encoding="utf-8"))
        assert stat["status"] == "ok"

        scan_meta = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        by_name = {r["extractor"]: r["status"] for r in scan_meta["extractors"]}
        assert by_name == {"symbols": "failed", "static-signals": "ok",
                           "probe": "ok"}

    def test_all_failed_returns_one(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)

        def boom(_repo):
            raise RuntimeError("x")

        for name in list(EXTRACTORS):
            monkeypatch.setitem(EXTRACTORS, name, (boom, f"{name}.json"))
        assert scan(repo, quiet=True) == 1


class TestCli:
    def test_main_invalid_repo(self, capsys):
        assert main(["/nonexistent/repo/xyz"]) == 1

    def test_main_unknown_extractor(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert main([str(repo), "--extractors", "nope"]) == 1

    def test_main_ok(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        assert main([str(repo)]) == 0
        assert (repo / ".cognicode" / "debt-scan" / "scan.json").is_file()
