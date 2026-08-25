"""任务模板合成单元测试（#20，第二段：LLM 模板合成）。

验证：
- 检索类：符号 → 不带名的自然语言描述（LLM 生成/确定性兜底），
  验收 = 符号级匹配 ground truth（file + 名称，非行号，#5 锁定）。
- 定位类：注入 bug 后 → 失败症状描述（执行式，非语义描述，#5 锁定），
  验收 = 对照注入点。
- 修改类：bug 注入 → 任务描述（描述→改动），验收 = F2P/P2P 双闸。

llm 接口可注入（fake LLM），offline 走确定性模板。期望值全部
来自已知字面规则（防 tautological）。
"""

import pytest
from pathlib import Path

from cognicode.generation import (
    GenerationConfig,
    SearchTask,
    LocateTask,
    ModifyTask,
    generate_tasks,
    DEFAULT_COUNTS,
)
from cognicode.symbols import Symbol


class TestGenerationConfig:
    def test_defaults_lock_task_counts(self):
        """默认任务量 = #6 锁定：检索 8 / 定位 8 / 修改 12。"""
        assert DEFAULT_COUNTS["search"] == 8
        assert DEFAULT_COUNTS["locate"] == 8
        assert DEFAULT_COUNTS["modify"] == 12

    def test_defaults_lock_ks(self):
        cfg = GenerationConfig()
        assert cfg.k_search == 3
        assert cfg.k_locate == 3
        assert cfg.k_modify == 5


class TestSearchTask:
    def test_search_task_has_symbol_target_and_prompt(self):
        sym = Symbol(kind="method", name="index", file="app/controller/Cart.php", line=3)
        t = SearchTask(id="search-1", symbol=sym, prompt="找到处理购物车列表的方法")
        assert t.symbol == sym
        assert "index" not in t.prompt  # 题面不带名（#5：检索 = 语义→位置）
        assert t.ground_truth == "app/controller/Cart.php::index"
        assert t.target_file == "app/controller/Cart.php"
        assert t.target_name == "index"


class TestLocateTask:
    def test_locate_task_carries_injection(self):
        sym = Symbol(kind="function", name="compute_total", file="src/cart.js", line=3)
        t = LocateTask(
            id="locate-1",
            symbol=sym,
            injection={"file": "src/cart.js", "line": 3, "patch": "-  return items.length;\n+  return 0;"},
            prompt="购物车总价计算异常，请定位根因",
        )
        assert t.injection["file"] == "src/cart.js"
        assert t.ground_truth == "src/cart.js::compute_total"
        assert t.prompt


class TestModifyTask:
    def test_modify_task_carries_bug_and_acceptance(self):
        sym = Symbol(kind="function", name="compute_total", file="src/cart.js", line=3)
        t = ModifyTask(
            id="modify-1",
            symbol=sym,
            bug={"file": "src/cart.js", "line": 3, "patch": "-  return items.length;\n+  return 0;"},
            prompt="修复购物车总价计算错误",
            acceptance_files=["tests/cognicode_test_cart.py"],
            guard_files=["tests/cognicode_guard_cart.py"],
        )
        assert t.bug["file"] == "src/cart.js"
        # 验收测试命名约定（地图 Notes：cognicode_ 前缀，放既有测试目录）
        assert all(f.startswith("tests/") for f in t.acceptance_files)
        assert all("cognicode_" in Path(f).name for f in t.acceptance_files)


def _syms(root: Path | None = None):
    return [
        Symbol(kind="function", name="compute_total", file="src/cart.js", line=3, root=root),
        Symbol(kind="method", name="index", file="app/controller/Cart.php", line=3, root=root),
        Symbol(kind="function", name="fetch_by_id", file="src/cart.py", line=3, root=root),
        Symbol(kind="class", name="Cart", file="src/cart.py", line=6, root=root),
    ]


def _write_fixture_files(root: Path):
    """搭 offline 测试的真实文件（符号行号与 _syms 一致）。"""
    (root / "src").mkdir(parents=True)
    (root / "src" / "cart.js").write_text(
        "export function computeTotal(items) {\n  return items.length;\n}\n",
        encoding="utf-8",
    )
    (root / "src" / "cart.py").write_text(
        "\n\ndef fetch_by_id(cart_id):\n    return cart_id\n\nclass Cart:\n    pass\n",
        encoding="utf-8",
    )
    (root / "app").mkdir(parents=True)
    (root / "app" / "controller").mkdir(parents=True)
    (root / "app" / "controller" / "Cart.php").write_text(
        "<?php\nclass Cart {\n    public function index($id = null) {\n        return $this->fetch($id);\n    }\n}\n",
        encoding="utf-8",
    )


class FakeLLM:
    """假 LLM：返回预设文本，记录调用。"""

    def __init__(self, responses: dict | None = None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def complete(self, prompt: str, *, model: str | None = None) -> str | None:
        self.calls.append(prompt)
        # 测试兜底：默认返回一个合理描述
        return self.responses.get(prompt, "该函数根据参数返回对应的业务数据")


class TestGenerateTasks:
    def test_generate_search_tasks_uses_symbols_and_llm(self):
        """检索任务：从符号里选 needle，LLM 生成不带名描述。"""
        llm = FakeLLM()
        tasks = generate_tasks(
            _syms(),
            llm=llm,
            kinds=("search",),
            config=GenerationConfig(search_count=2, k_search=3),
        )
        assert len(tasks) == 2
        assert all(isinstance(t, SearchTask) for t in tasks)
        # LLM 被调用（为每个 needle 生成描述）
        assert len(llm.calls) == 2
        # ground truth 符号级匹配（file::name）
        for t in tasks:
            assert t.ground_truth == f"{t.symbol.file}::{t.symbol.name}"
            assert t.k == 3

    def test_offline_no_llm_uses_deterministic_template(self, tmp_path):
        """offline（llm=None）：确定性模板兜底，仍产出有效任务。"""
        _write_fixture_files(tmp_path)
        syms = _syms(root=tmp_path)
        tasks = generate_tasks(
            syms,
            llm=None,
            kinds=("search", "locate"),
            config=GenerationConfig(search_count=2, locate_count=2, k_search=3, k_locate=3),
        )
        assert len(tasks) == 4
        search = [t for t in tasks if isinstance(t, SearchTask)]
        locate = [t for t in tasks if isinstance(t, LocateTask)]
        assert len(search) == 2 and len(locate) == 2
        for t in search:
            # 确定性模板：含符号所在文件（可读提示），但不含符号名
            assert t.symbol.file in t.prompt
            assert t.symbol.name not in t.prompt
        for t in locate:
            assert t.injection["patch"]  # 注入补丁存在
            assert t.symbol.name not in t.prompt  # 症状不给答案

    def test_fewer_symbols_than_requested(self, tmp_path):
        """符号不足时按实际数量产出（不硬凑）。"""
        _write_fixture_files(tmp_path)
        syms = _syms(root=tmp_path)
        tasks = generate_tasks(
            syms,
            llm=None,
            kinds=("search",),
            config=GenerationConfig(search_count=10, k_search=3),
        )
        assert len(tasks) == 4  # 只有 4 个符号

    def test_no_symbols_yields_no_tasks(self):
        tasks = generate_tasks(
            [], llm=None, kinds=("search", "locate", "modify"),
            config=GenerationConfig(search_count=8, locate_count=8, modify_count=12),
        )
        assert tasks == []

    def test_llm_failure_falls_back_to_template(self, tmp_path):
        """LLM 返回 None（超时/拒答）→ 确定性模板兜底（不炸管线）。"""
        class BrokenLLM:
            def complete(self, prompt, *, model=None):
                return None

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text(
            "export function computeTotal(items) {\n  return items.length;\n}\n",
            encoding="utf-8",
        )
        syms = _syms(root=tmp_path)
        tasks = generate_tasks(
            syms, llm=BrokenLLM(), kinds=("search",),
            config=GenerationConfig(search_count=2, k_search=3),
        )
        assert len(tasks) == 2
        assert all(t.prompt for t in tasks)
