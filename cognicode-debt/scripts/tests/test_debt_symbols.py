"""symbols 提取器测试（#58，从 tests/test_symbols.py 随行迁移）。

迁移差异（债检测口径修正，#58 验收项）：
- 测试目录（tests/）与测试文件**不再排除**——test-gap 检测需要测试
  文件符号做分子，新增 TestDebtScanScope 断言之；
- vendor/docs 排除保留（依赖与非源码目录不进符号面）。

期望值全部来自已知字面规则（防 tautological）。
"""

import pytest

from lib.symbols import (
    extract_symbols,
    file_language,
    symbol_display_name,
    symbols_payload,
)


def _write(root, relpath, content):
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestFileLanguage:
    def test_python_extension(self):
        assert file_language("src/cart.py") == "python"

    def test_php_extension(self):
        assert file_language("application/api/controller/Cart.php") == "php"

    def test_js_ts(self):
        assert file_language("src/app.js") == "javascript"
        assert file_language("src/app.ts") == "typescript"

    def test_unknown_extension_none(self):
        assert file_language("README.md") is None
        assert file_language("data.sql") is None


class TestExtractPython:
    def test_functions_and_classes(self, tmp_path):
        _write(
            tmp_path,
            "src/cart.py",
            '"""Cart domain."""\n'
            "\n"
            "def fetch_by_id(cart_id):\n"
            "    return cart_id\n"
            "\n"
            "class Cart:\n"
            "    def index(self, request):\n"
            "        return request\n"
            "\n",
        )
        syms = extract_symbols(tmp_path)
        # 只统计 src/ 下的符号
        names = {(s.kind, s.name, s.file) for s in syms}
        assert ("function", "fetch_by_id", "src/cart.py") in names
        assert ("class", "Cart", "src/cart.py") in names
        # python 的 method 是 function_definition，落在 class 体内
        assert any(s.name == "index" and s.kind == "function" for s in syms)
        # 行号 1-based
        fetch = next(s for s in syms if s.name == "fetch_by_id")
        assert fetch.line == 3
        cart = next(s for s in syms if s.name == "Cart")
        assert cart.line == 6

    def test_skips_vendor_and_docs_files(self, tmp_path):
        # 债检测口径：vendor/docs 仍排除（依赖与非源码目录）
        _write(tmp_path, "src/app.py", "def real_fn():\n    return 1\n")
        _write(tmp_path, "vendor/third.py", "def vendored():\n    return 2\n")
        _write(tmp_path, "docs/guide.py", "def documented():\n    return 3\n")
        syms = extract_symbols(tmp_path)
        names = {s.name for s in syms}
        assert "real_fn" in names
        assert "vendored" not in names  # vendor 不算
        assert "documented" not in names  # docs 不算


class TestDebtScanScope:
    """债检测口径修正（#58）：测试目录/文件进符号面。"""

    def test_tests_dir_not_excluded(self, tmp_path):
        # 旧口径（任务生成）排除 tests/；债检测要扫测试（test-gap 分子）
        _write(tmp_path, "src/app.py", "def real_fn():\n    return 1\n")
        _write(tmp_path, "tests/test_app.py", "def test_real_fn():\n    pass\n")
        syms = extract_symbols(tmp_path)
        names = {s.name for s in syms}
        assert "real_fn" in names
        assert "test_real_fn" in names  # 测试符号照常入面

    def test_spec_and_underscore_tests_not_excluded(self, tmp_path):
        _write(tmp_path, "spec/helper_spec.js", "function specHelper() {}\n")
        _write(tmp_path, "__tests__/unit.js", "function unitCase() {}\n")
        _write(tmp_path, "test_foo.py", "def test_foo():\n    pass\n")
        syms = extract_symbols(tmp_path)
        names = {s.name for s in syms}
        assert "specHelper" in names
        assert "unitCase" in names
        assert "test_foo" in names

    def test_hidden_dirs_still_excluded(self, tmp_path):
        _write(tmp_path, ".venv/lib/x.py", "def hidden_fn():\n    return 1\n")
        syms = extract_symbols(tmp_path)
        assert all(s.name != "hidden_fn" for s in syms)


class TestExtractPhp:
    def test_php_class_methods(self, tmp_path):
        _write(
            tmp_path,
            "app/controller/Cart.php",
            "<?php\n"
            "class Cart {\n"
            "    public function index($id = null) {\n"
            "        return $this->fetch($id);\n"
            "    }\n"
            "    private function fetch($id) { return $id; }\n"
            "}\n"
            "function global_helper() {}\n",
        )
        syms = extract_symbols(tmp_path)
        kinds = {(s.kind, s.name) for s in syms}
        assert ("class", "Cart") in kinds
        assert ("method", "index") in kinds
        assert ("method", "fetch") in kinds
        assert ("function", "global_helper") in kinds


class TestExtractJavascript:
    def test_js_function_and_method(self, tmp_path):
        _write(
            tmp_path,
            "src/cart.js",
            "export function computeTotal(items) {\n"
            "  return items.length;\n"
            "}\n"
            "class Cart {\n"
            "  index(id) { return id; }\n"
            "}\n",
        )
        syms = extract_symbols(tmp_path)
        kinds = {(s.kind, s.name) for s in syms}
        assert ("function", "computeTotal") in kinds
        assert ("class", "Cart") in kinds
        assert ("method", "index") in kinds


class TestDisplayName:
    def test_display_name_wraps_kind(self):
        assert symbol_display_name("method", "index") == "方法 index"
        assert symbol_display_name("function", "compute_total") == "函数 compute_total"
        assert symbol_display_name("class", "Cart") == "类 Cart"


class TestPayload:
    def test_payload_shape(self, tmp_path):
        """symbols.json 载荷形状（ARTIFACTS.md §5）。"""
        _write(tmp_path, "src/cart.py", "def fetch_by_id(x):\n    return x\n")
        payload = symbols_payload(tmp_path)
        assert list(payload.keys()) == ["symbols"]
        entry = payload["symbols"][0]
        assert entry == {
            "kind": "function",
            "name": "fetch_by_id",
            "file": "src/cart.py",
            "line": 1,
        }
