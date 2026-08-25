"""静态信号提取单元测试（#18）。

构造假仓库验证提取正确：每个测试用 tmp_path 搭最小目录树，
断言信号取值（value）、离散刻度（score ∈ {0, 0.5, 1}）与证据（evidence）。
期望值全部来自已知字面规则（防 tautological）。
"""

import pytest

from cognicode.static_signals import (
    SIGNALS,
    static_json,
)


def _touch(root, relpath, content=""):
    """在假仓库里造一个文件。"""
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _scores(json_out):
    """static.json 里 信号名 → score 的便捷映射。"""
    return {k: v["score"] for k, v in json_out["signals"].items()}


class TestAgentContextDocs:
    def test_no_context_docs_scores_zero(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        out = static_json(tmp_path)
        assert _scores(out)["navigability.agent_context_docs"] == 0.0

    def test_agents_md_present_scores_one(self, tmp_path):
        _touch(tmp_path, "AGENTS.md", "# repo rules\n")
        out = static_json(tmp_path)
        r = out["signals"]["navigability.agent_context_docs"]
        assert r["score"] == 1.0
        assert "AGENTS.md" in r["evidence"]

    def test_any_context_doc_variant_counts(self, tmp_path):
        # CLAUDE.md 同样算命中（代理上下文文档 = AGENTS/CLAUDE/CONTEXT/.cursorrules）
        _touch(tmp_path, "CLAUDE.md", "# claude\n")
        out = static_json(tmp_path)
        assert _scores(out)["navigability.agent_context_docs"] == 1.0

    def test_context_md_counts(self, tmp_path):
        _touch(tmp_path, "CONTEXT.md", "# context\n")
        assert _scores(static_json(tmp_path))["navigability.agent_context_docs"] == 1.0

    def test_cursorrules_counts(self, tmp_path):
        _touch(tmp_path, ".cursorrules", "always use ts\n")
        assert _scores(static_json(tmp_path))["navigability.agent_context_docs"] == 1.0


class TestReadme:
    def test_no_readme_scores_zero(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        assert _scores(static_json(tmp_path))["navigability.readme"] == 0.0

    def test_readme_md_scores_one(self, tmp_path):
        _touch(tmp_path, "README.md", "# hi\n")
        out = static_json(tmp_path)
        assert _scores(out)["navigability.readme"] == 1.0
        assert "README.md" in out["signals"]["navigability.readme"]["evidence"]

    def test_readme_lowercase_scores_one(self, tmp_path):
        _touch(tmp_path, "readme", "hi\n")
        assert _scores(static_json(tmp_path))["navigability.readme"] == 1.0

    def test_readme_rst_scores_one(self, tmp_path):
        _touch(tmp_path, "README.rst", "hi\n")
        assert _scores(static_json(tmp_path))["navigability.readme"] == 1.0

    def test_nested_readme_not_counted(self, tmp_path):
        # 只有仓库根/一层的 README 才算入口文档，深层文档不算
        _touch(tmp_path, "docs/README.md", "hi\n")
        assert _scores(static_json(tmp_path))["navigability.readme"] == 0.0


class TestEntryClarity:
    def test_no_entry_scores_zero(self, tmp_path):
        _touch(tmp_path, "lib/util.py", "x = 1\n")
        assert _scores(static_json(tmp_path))["navigability.entry_clarity"] == 0.0

    def test_single_entry_scores_half(self, tmp_path):
        _touch(tmp_path, "main.py", "print('hi')\n")
        assert _scores(static_json(tmp_path))["navigability.entry_clarity"] == 0.5

    def test_entry_in_src_counts(self, tmp_path):
        _touch(tmp_path, "src/index.js", "console.log(1)\n")
        assert _scores(static_json(tmp_path))["navigability.entry_clarity"] == 0.5

    def test_multiple_entries_scores_one(self, tmp_path):
        _touch(tmp_path, "main.py", "print('a')\n")
        _touch(tmp_path, "cli.py", "print('b')\n")
        out = static_json(tmp_path)
        assert _scores(out)["navigability.entry_clarity"] == 1.0
        assert len(out["signals"]["navigability.entry_clarity"]["evidence"]) == 2


class TestBuildDef:
    def test_no_build_def_scores_zero(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        assert _scores(static_json(tmp_path))["buildability.build_def"] == 0.0

    def test_single_build_def_scores_half(self, tmp_path):
        _touch(tmp_path, "pyproject.toml", "[project]\n")
        assert _scores(static_json(tmp_path))["buildability.build_def"] == 0.5

    def test_multiple_build_defs_scores_one(self, tmp_path):
        _touch(tmp_path, "pyproject.toml", "[project]\n")
        _touch(tmp_path, "Makefile", "all:\n\techo hi\n")
        out = static_json(tmp_path)
        assert _scores(out)["buildability.build_def"] == 1.0
        assert len(out["signals"]["buildability.build_def"]["evidence"]) == 2


class TestLockfile:
    def test_no_lockfile_scores_zero(self, tmp_path):
        _touch(tmp_path, "pyproject.toml", "[project]\n")
        assert _scores(static_json(tmp_path))["buildability.lockfile"] == 0.0

    def test_lockfile_present_scores_one(self, tmp_path):
        _touch(tmp_path, "uv.lock", "version = 1\n")
        assert _scores(static_json(tmp_path))["buildability.lockfile"] == 1.0

    def test_package_lock_scores_one(self, tmp_path):
        _touch(tmp_path, "package-lock.json", "{}\n")
        assert _scores(static_json(tmp_path))["buildability.lockfile"] == 1.0


class TestCi:
    def test_no_ci_scores_zero(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        assert _scores(static_json(tmp_path))["buildability.ci"] == 0.0

    def test_github_workflow_scores_one(self, tmp_path):
        _touch(tmp_path, ".github/workflows/ci.yml", "name: ci\n")
        assert _scores(static_json(tmp_path))["buildability.ci"] == 1.0

    def test_gitlab_ci_scores_one(self, tmp_path):
        _touch(tmp_path, ".gitlab-ci.yml", "test:\n  script: pytest\n")
        assert _scores(static_json(tmp_path))["buildability.ci"] == 1.0


class TestTestDiscoverability:
    def test_no_tests_scores_zero(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        assert _scores(static_json(tmp_path))["buildability.test_discoverability"] == 0.0

    def test_tests_dir_scores_one(self, tmp_path):
        _touch(tmp_path, "tests/test_foo.py", "def test_x():\n    pass\n")
        out = static_json(tmp_path)
        assert _scores(out)["buildability.test_discoverability"] == 1.0
        assert out["signals"]["buildability.test_discoverability"]["evidence"]

    def test_test_file_scores_one(self, tmp_path):
        _touch(tmp_path, "test_foo.py", "def test_x():\n    pass\n")
        assert _scores(static_json(tmp_path))["buildability.test_discoverability"] == 1.0

    def test_spec_file_scores_one(self, tmp_path):
        _touch(tmp_path, "src/foo.test.js", "test('x', () => {});\n")
        assert _scores(static_json(tmp_path))["buildability.test_discoverability"] == 1.0


class TestStaticJsonShape:
    def test_exactly_eight_scoring_signals(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        out = static_json(tmp_path)
        assert len(out["signals"]) == 8

    def test_scores_all_on_discrete_scale(self, tmp_path):
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        for v in _scores(static_json(tmp_path)).values():
            assert v in (0.0, 0.5, 1.0)

    def test_dimension_scores_are_arithmetic_means(self, tmp_path):
        # 空仓库：可导航性 4 信号全 0 → 0；环境可用性 4 全 0 → 0
        out = static_json(tmp_path)
        assert out["dimensions"]["navigability"]["score"] == 0.0
        assert out["dimensions"]["buildability"]["score"] == 0.0

    def test_dimension_mean_with_mixed_scores(self, tmp_path):
        # navigability: 1,1,0,0.5 → 2.5/4 = 0.625
        _touch(tmp_path, "AGENTS.md", "# r\n")
        _touch(tmp_path, "README.md", "# r\n")
        _touch(tmp_path, "main.py", "print(1)\n")
        out = static_json(tmp_path)
        assert out["dimensions"]["navigability"]["score"] == pytest.approx(2.5 / 4)

    def test_static_json_is_serializable(self, tmp_path):
        import json

        _touch(tmp_path, "AGENTS.md", "# r\n")
        json.dumps(static_json(tmp_path))  # 不抛

    def test_signal_registry_is_stable(self):
        # 首发 8 产分信号名称锁定（#7/#18）
        assert [s.name for s in SIGNALS] == [
            "navigability.agent_context_docs",
            "navigability.readme",
            "navigability.comment_density",
            "navigability.entry_clarity",
            "buildability.build_def",
            "buildability.lockfile",
            "buildability.ci",
            "buildability.test_discoverability",
        ]


class TestCommentDensity:
    def test_no_source_files_scores_zero(self, tmp_path):
        _touch(tmp_path, "data.txt", "hello\n")
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 0.0

    def test_no_comments_scores_zero(self, tmp_path):
        # 只有代码没有注释
        _touch(tmp_path, "main.py", "x = 1\nprint(x)\n" * 20)
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 0.0

    def test_heavy_comments_scores_one(self, tmp_path):
        # 注释为主的文件 → 密度 ≥ 0.15
        src = "".join("# comment line\n" for _ in range(50)) + "x = 1\n"
        _touch(tmp_path, "main.py", src)
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 1.0

    def test_moderate_comments_scores_half(self, tmp_path):
        # 注释字节占比落在 0.05~0.15（实测 3 条短注释 + 12 行代码 → 0.1）
        code = "# a\n" * 3 + "x = 1\n" + "y = 2\n" * 12
        _touch(tmp_path, "main.py", code)
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 0.5

    def test_js_comments_counted(self, tmp_path):
        _touch(tmp_path, "index.js", "// comment one\n// comment two\nconst x = 1;\n" * 30)
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 1.0

    def test_evidence_reports_ratio(self, tmp_path):
        _touch(tmp_path, "main.py", "# c\nx = 1\n" * 40)
        out = static_json(tmp_path)
        ev = out["signals"]["navigability.comment_density"]["evidence"]
        assert any("比" in e for e in ev)


class TestRobustness:
    def test_hidden_and_vendor_dirs_excluded(self, tmp_path):
        # node_modules/.git 里的测试文件不算数（确定性：不扫描依赖/隐藏目录）
        _touch(tmp_path, "node_modules/pkg/test_x.js", "test('x', () => {});\n")
        _touch(tmp_path, ".git/hooks/test_x.py", "def test_x():\n    pass\n")
        _touch(tmp_path, "src/foo.py", "x = 1\n")
        out = static_json(tmp_path)
        assert _scores(out)["buildability.test_discoverability"] == 0.0
        # 隐藏目录也不产出任何信号
        assert len(out["signals"]["navigability.agent_context_docs"]["evidence"]) == 0

    def test_comment_density_skips_syntax_error_files(self, tmp_path):
        # 语法错误文件不参与密度（确定性，不算噪声）
        _touch(tmp_path, "broken.py", "def foo(:\n")
        assert _scores(static_json(tmp_path))["navigability.comment_density"] == 0.0
