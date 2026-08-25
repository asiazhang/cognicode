"""tree-sitter 符号提取单元测试（#20）。

验证：从仓库源码提取函数/方法/类符号（语言无关），输出稳定键
{kind, name, file, line}，供检索/定位/修改三类任务的生成与验收对照。
期望值全部来自已知字面规则（防 tautological）。
"""

import pytest

from cognicode.symbols import (
    extract_symbols,
    file_language,
    symbol_display_name,
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

    def test_skips_test_and_vendor_files(self, tmp_path):
        _write(tmp_path, "src/app.py", "def real_fn():\n    return 1\n")
        _write(tmp_path, "tests/test_app.py", "def test_real_fn():\n    pass\n")
        _write(tmp_path, "vendor/third.py", "def vendored():\n    return 2\n")
        syms = extract_symbols(tmp_path)
        names = {s.name for s in syms}
        assert "real_fn" in names
        assert "test_real_fn" not in names  # 测试文件不算符号
        assert "vendored" not in names  # vendor 不算


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
