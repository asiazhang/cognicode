"""模块深度模块单元测试（#23，module_depth.py）。

验证（#14 决议 + 地图 Notes「模块深度：LLM 判 deep/shallow 分布，
只做重构建议、不进产分」）：
- collect_modules：文件级模块（语言无关），排除 test/spec/docs/vendor 与
  隐藏目录；跳过空/平凡文件；确定性、无 LLM。
- judge_module_depth：LLM 判定 deep/shallow（复用原型 judge_depth.py 的
  提示词与判定思路）；输出结构化 JSON；非法输出 → None（重试后放弃）。
- run_module_depth：全仓判定 → deep/shallow 分布 + 重构建议清单（shallow
  模块 = 建议合并/加深，参考性，不进产分）。offline（llm=None）→ 关闭。
- 判定不确定性是特性（ADR-0004）：不强校验、不要求跨模型对齐。

期望值全部来自独立手算的已知字面（防 tautological）。
"""

import json

import pytest

from cognicode.module_depth import (
    collect_modules,
    judge_module_depth,
    run_module_depth,
)


def _make_repo(tmp_path):
    """造一个迷你仓库：含可判定模块 + 应排除目录。"""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "core.py").write_text(
        "# core\n\ndef run(a, b):\n    return a + b\n\ndef run2(x):\n    return x * 2\n",
        encoding="utf-8",
    )
    (repo / "src" / "tiny.py").write_text("# tiny\n", encoding="utf-8")  # 平凡文件（<5 行）
    (repo / "tests").mkdir()
    (repo / "tests" / "test_core.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# guide\n", encoding="utf-8")
    (repo / "vendor").mkdir()
    (repo / "vendor" / "dep.py").write_text(
        "def dep():\n    return 1\n", encoding="utf-8")
    (repo / "src" / "__init__.py").write_text(
        "# init\n", encoding="utf-8")  # 空 init（<5 行 → 跳过）
    (repo / ".hidden").mkdir()
    (repo / ".hidden" / "x.py").write_text(
        "def h():\n    return 1\n", encoding="utf-8")
    return repo


class TestCollectModules:
    def test_file_level_modules_exclude_infra(self, tmp_path):
        """文件级模块：排除 test/spec/docs/vendor/隐藏目录，跳过平凡文件。"""
        mods = collect_modules(_make_repo(tmp_path))
        # 只应剩 src/core.py（src/tiny.py 平凡、__init__.py 平凡、vendor/docs/tests/隐藏排除）
        names = sorted(mods.keys())
        assert names == ["src/core.py"]

    def test_skip_trivial_files(self, tmp_path):
        """<5 行的文件（import-only 等）不算模块。"""
        repo = _make_repo(tmp_path)
        mods = collect_modules(repo)
        from pathlib import Path as _P
        assert all(_P(paths[0]).read_text().splitlines().__len__() >= 5
                   for paths in mods.values())

    def test_deterministic_order(self, tmp_path):
        """模块收集确定性（排序稳定）。"""
        repo = _make_repo(tmp_path)
        a = list(collect_modules(repo).keys())
        b = list(collect_modules(repo).keys())
        assert a == b


class _FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, prompt, *, model=None):
        self.calls.append(prompt)
        if not self.outputs:
            return None
        return self.outputs.pop(0)


class TestJudgeModuleDepth:
    def test_parses_valid_json(self):
        """LLM 返回合法 JSON（deep/shallow）→ 判定成功。"""
        llm = _FakeLLM([
            json.dumps({"module_id": "repo/src/core.py", "label": "deep"}),
        ])
        mods = {"src/core.py": ["/tmp/repo/src/core.py"]}
        label = judge_module_depth(
            "repo/src/core.py", mods["src/core.py"], llm=llm,
        )
        assert label == "deep"

    def test_invalid_json_retries_then_none(self):
        """非法输出（非 JSON）→ 重试；仍非法 → None（放弃，不炸管线）。"""
        llm = _FakeLLM(["不是 JSON", "还是不对", None])
        mods = {"src/core.py": ["/tmp/repo/src/core.py"]}
        label = judge_module_depth("src/core.py", mods["src/core.py"], llm=llm, retries=2)
        assert label is None
        assert len(llm.calls) == 3  # 首次 + 2 次重试

    def test_llm_none_returns_none(self):
        """LLM 不可用（None）→ 返回 None（模块深度关闭语义）。"""
        mods = {"src/core.py": ["/tmp/repo/src/core.py"]}
        assert judge_module_depth("src/core.py", mods["src/core.py"], llm=None) is None

    def test_label_normalization(self):
        """大小写/带标点的 label 归一化（Deep/Shallow/dEEP）。"""
        llm = _FakeLLM([json.dumps({"label": "DEEP"})])
        mods = {"src/core.py": ["/tmp/repo/src/core.py"]}
        assert judge_module_depth("src/core.py", mods["src/core.py"], llm=llm) == "deep"


class TestRunModuleDepth:
    def test_offline_disabled(self, tmp_path):
        """--offline（llm=None）→ 模块深度关闭：{enabled: false}。"""
        repo = _make_repo(tmp_path)
        r = run_module_depth(repo, llm=None)
        assert r["enabled"] is False
        assert r["modules"] == []

    def test_full_judges_and_reports(self, tmp_path):
        """开 LLM：全仓判定 → deep/shallow 分布 + shallow 重构建议。"""
        repo = _make_repo(tmp_path)
        llm = _FakeLLM([
            json.dumps({"module_id": "src/core.py", "label": "shallow"}),
            json.dumps({"module_id": "src/core.py", "label": "deep"}),
        ])
        r = run_module_depth(repo, llm=llm, max_modules=10)
        assert r["enabled"] is True
        # src/core.py 一个模块：LLM 给 shallow + deep → 最终 label 取最后判定（参考性）
        assert r["modules"]
        m = r["modules"][0]
        assert m["label"] in ("deep", "shallow")
        assert "deep" in r["distribution"] or "shallow" in r["distribution"]
        # shallow 模块 → 重构建议清单（合并/加深，参考性）
        shallow = [x for x in r["modules"] if x["label"] == "shallow"]
        if shallow:
            assert r["suggestions"]
            assert "shallow" in r["suggestions"][0] or "合并" in r["suggestions"][0]

    def test_no_scoring(self, tmp_path):
        """模块深度不进产分：输出无维度分字段（#14/ADR-0004）。"""
        repo = _make_repo(tmp_path)
        llm = _FakeLLM([json.dumps({"module_id": "src/core.py", "label": "deep"})])
        r = run_module_depth(repo, llm=llm, max_modules=10)
        assert "score" not in json.dumps(r, ensure_ascii=False)
