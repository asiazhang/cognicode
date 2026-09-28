"""test-gap 提取器测试（#59）：两层漏斗口径 + 降级 + 容错。"""

import json

from lib.test_gap import _is_test_file, test_gap_payload as build_test_gap_payload

def _make_repo(tmp_path, with_symbols=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Sources").mkdir()
    (repo / "Tests").mkdir()
    if with_symbols:
        # 有触达：AService 类型名与 touch_method 都出现在测试里
        (repo / "Sources" / "a_service.py").write_text(
            "class AService:\n"
            "    def touch_method(self):\n"
            "        pass\n"
            "    def bare_method(self):\n"      # 裸露：测试文本零出现
            "        pass\n",
            encoding="utf-8")
        # 零触达：类型名与文件名都零出现
        (repo / "Sources" / "orphan.py").write_text(
            "class OrphanThing:\n"
            "    def never_tested(self):\n"
            "        pass\n",
            encoding="utf-8")
        (repo / "Tests" / "test_a_service.py").write_text(
            "from Sources.a_service import AService\n"
            "def test_touch():\n"
            "    s = AService()\n"
            "    s.touch_method()\n",
            encoding="utf-8")
    else:
        # 无符号面：源文件无命名符号，测试文件也无（整仓符号面为空）；
        # 测试文本提到 mod（文件名词干）→ 降级口径下有触达
        (repo / "Sources" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "Tests" / "mod_tests.py").write_text(
            "# mod smoke\nassert True\n", encoding="utf-8")
    return repo


class TestIsTestFile:
    def test_dir_tokens(self):
        assert _is_test_file("tests/test_a.py")
        # Swift 惯例的大写 Tests/ 目录入面（大小写不敏感）
        assert _is_test_file("Tests/test_a.swift")
        assert _is_test_file("Tests/helper.swift")
        assert _is_test_file("src/__tests__/foo.js")
        assert _is_test_file("spec/helper.rb")
        assert not _is_test_file("src/app.py")

    def test_filename_prefix(self):
        assert _is_test_file("src/test_app.py")
        assert _is_test_file("src/spec_helper.rb")
        assert not _is_test_file("src/app_test.py")  # 后缀不算（Go/JS 惯例另裁）


class TestTwoLayerFunnel:
    def test_zero_touch_file_and_partial_file(self, tmp_path):
        """文件级漏斗（orphan 零触达）+ 符号级精判（bare_method 裸露）。"""
        repo = _make_repo(tmp_path)
        payload = build_test_gap_payload(repo)

        files = {f["file"]: f for f in payload["files"]}
        # 文件级：orphan 零触达（类型名+文件名词干都零出现）
        orphan = files["Sources/orphan.py"]
        assert orphan["zero_touch"] is True
        assert orphan["symbols_gap"] == orphan["symbols_total"] == 2
        # 文件级：a_service 有触达（AService 出现在测试里）
        a_service = files["Sources/a_service.py"]
        assert a_service["zero_touch"] is False
        # 符号级：bare_method 裸露、touch_method 触达
        assert a_service["symbols_gap"] == 1
        assert "bare_method" in a_service["gap_symbol_names"]

        # per-符号明细（判据实例粒度）
        gaps = {g["name"] for g in payload["gap_symbols"]}
        assert "OrphanThing" in gaps and "never_tested" in gaps
        assert "bare_method" in gaps
        assert "touch_method" not in gaps
        assert "AService" not in gaps

    def test_generic_function_names_do_not_rescue_untouched_file(self, tmp_path):
        """通用词函数名（start/stop）不把零触达文件救回来（口径校准点）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "Sources").mkdir()
        (repo / "Tests").mkdir()
        (repo / "Sources" / "endpoint.py").write_text(
            "class Endpoint:\n"
            "    def start(self):\n"
            "        pass\n"
            "    def stop(self):\n"
            "        pass\n",
            encoding="utf-8")
        # 测试只测别的类，但文本里有 start/stop 通用词
        (repo / "Tests" / "test_other.py").write_text(
            "class OtherTests:\n"
            "    def test_start_stop_flow(self):\n"
            "        start(); stop()\n",
            encoding="utf-8")
        payload = build_test_gap_payload(repo)
        f = payload["files"][0]
        assert f["zero_touch"] is True  # 主符号（类型名）零出现 → 整文件 gap
        assert f["symbols_gap"] == 3

    def test_no_test_files_all_gap(self, tmp_path):
        """无测试文件：全部源文件零触达（如实报告）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text(
            "def main():\n    pass\n", encoding="utf-8")
        payload = build_test_gap_payload(repo)
        assert payload["files"][0]["zero_touch"] is True
        assert payload["gap_symbols"]

    def test_payload_deterministic(self, tmp_path):
        """同 repo 两次提取字节一致（确定性纪律）。"""
        repo = _make_repo(tmp_path)
        a = json.dumps(build_test_gap_payload(repo), sort_keys=True)
        b = json.dumps(build_test_gap_payload(repo), sort_keys=True)
        assert a == b


class TestDegraded:
    def test_no_symbols_falls_back_to_filename(self, tmp_path, monkeypatch):
        """无符号面（空文件）：降级为文件名口径，degraded 标注。"""
        repo = _make_repo(tmp_path, with_symbols=False)
        # mod.py 无命名符号 → symbols 面为空 → 文件名口径
        payload = build_test_gap_payload(repo)
        assert payload.get("degraded") == "filename-only (no symbol surface)"
        f = payload["files"][0]
        assert f["zero_touch"] is False  # "mod"（文件名词干）出现在测试文本里
