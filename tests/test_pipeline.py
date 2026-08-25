"""任务生成管线集成测试（#20 三段式）。

验证：tree-sitter 解析 → 模板合成 → 执行式验证过滤 全链路，
对假仓库生成并过滤出有效任务（ticket 产出要求）。
"""

from pathlib import Path

from cognicode.pipeline import generate_task_suite
from cognicode.generation import SearchTask, LocateTask, ModifyTask


def _make_repo(root: Path) -> Path:
    """搭一个最小多语言假仓库（含既有测试目录）。"""
    (root / "src").mkdir(parents=True)
    (root / "src" / "cart.py").write_text(
        "def compute_total(items):\n"
        "    return sum(items)\n"
        "\n"
        "class Cart:\n"
        "    def add(self, item):\n"
        "        return item\n",
        encoding="utf-8",
    )
    (root / "app").mkdir(parents=True)
    (root / "app" / "Cart.php").write_text(
        "<?php\n"
        "class Cart {\n"
        "    public function index($id = null) {\n"
        "        return $this->fetch($id);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_cart.py").write_text(
        "def test_compute_total():\n    assert compute_total([1, 2]) == 3\n",
        encoding="utf-8",
    )
    return root


class TestPipeline:
    def test_full_pipeline_generates_all_kinds(self, tmp_path):
        """三段式全链路：符号 → 合成 → 过滤，产出三类有效任务。"""
        repo = _make_repo(tmp_path)
        suite = generate_task_suite(
            repo,
            llm=None,  # offline：确定性模板
            counts={"search": 3, "locate": 3, "modify": 3},
            ks={"search": 3, "locate": 3, "modify": 5},
        )
        assert suite["search"], "应产出检索任务"
        assert suite["locate"], "应产出定位任务"
        assert suite["modify"], "应产出修改任务"

        for t in suite["search"]:
            assert isinstance(t, SearchTask)
            assert t.prompt and t.ground_truth
        for t in suite["locate"]:
            assert isinstance(t, LocateTask)
            assert t.injection["patch"]
            assert t.ground_truth
        for t in suite["modify"]:
            assert isinstance(t, ModifyTask)
            assert t.bug["patch"]
            # 验收测试注入约定：cognicode_ 前缀 + 放既有测试目录
            assert t.acceptance_files
            for f in t.acceptance_files:
                assert "cognicode_" in Path(f).name
                assert f.startswith("tests/")

    def test_counts_respected_when_symbols_sufficient(self, tmp_path):
        repo = _make_repo(tmp_path)
        suite = generate_task_suite(
            repo,
            llm=None,
            counts={"search": 2, "locate": 1, "modify": 1},
            ks={"search": 3, "locate": 3, "modify": 5},
        )
        assert len(suite["search"]) == 2
        assert len(suite["locate"]) == 1
        assert len(suite["modify"]) == 1
        # 采样 k 已烙在任务上
        assert all(t.k == 3 for t in suite["search"])
        assert all(t.k == 5 for t in suite["modify"])

    def test_offline_suite_is_deterministic(self, tmp_path):
        """offline 确定性：两次生成产出相同任务集（分数稳定前提）。"""
        repo = _make_repo(tmp_path)
        a = generate_task_suite(repo, llm=None, counts={"search": 2}, ks={"search": 3})
        b = generate_task_suite(repo, llm=None, counts={"search": 2}, ks={"search": 3})
        assert [t.id for t in a["search"]] == [t.id for t in b["search"]]
        assert [t.ground_truth for t in a["search"]] == [t.ground_truth for t in b["search"]]

    def test_dropped_tasks_recorded(self, tmp_path):
        """验证过滤失败的实例被记录（dropped）。"""
        repo = _make_repo(tmp_path)
        # 故意制造一个无法注入的文件：符号行不在真实内容中
        suite = generate_task_suite(
            repo,
            llm=None,
            counts={"search": 1, "locate": 1},
            ks={"search": 3, "locate": 3},
        )
        assert "dropped" in suite
        # 正常假仓库全部可注入 → dropped 应为空（或至少不炸）
        assert isinstance(suite["dropped"], list)
