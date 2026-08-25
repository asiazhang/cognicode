"""执行式验证过滤单元测试（#20 第三段）。

验证：生成的任务须过 harness 侧客观判定（位置匹配/测试红绿/退出码，
ADR-0002），过不了当场砍掉。验证器是可注入的（假验证器 + 真验证器
骨架），本票实现确定性验证器（注入补丁可应用 + 验收测试可注入），
真正跑测试的判卷归 #21（verdict 层）。

期望值全部来自已知字面规则（防 tautological）。
"""

import pytest

from cognicode.generation import LocateTask, ModifyTask, SearchTask
from cognicode.symbols import Symbol
from cognicode.verify import (
    VerificationResult,
    VerificationConfig,
    verify_tasks,
    apply_injection,
    prepare_acceptance_files,
)


def _search_task() -> SearchTask:
    sym = Symbol(kind="function", name="compute_total", file="src/cart.js", line=3)
    return SearchTask(id="search-1", symbol=sym, prompt="找到计算总价的代码", k=3)


def _locate_task() -> LocateTask:
    sym = Symbol(kind="function", name="compute_total", file="src/cart.js", line=3)
    return LocateTask(
        id="locate-1",
        symbol=sym,
        injection={"file": "src/cart.js", "line": 3, "patch": "-  return items.length;\n+  return 0;"},
        prompt="总价计算异常",
        k=3,
    )


def _modify_task() -> ModifyTask:
    sym = Symbol(kind="function", name="compute_total", file="src/cart.js", line=3)
    return ModifyTask(
        id="modify-1",
        symbol=sym,
        bug={"file": "src/cart.js", "line": 3, "patch": "-  return items.length;\n+  return 0;"},
        prompt="修复总价计算",
        k=5,
    )


class TestApplyInjection:
    def test_apply_patch_to_file(self, tmp_path):
        """把注入补丁应用到真实文件（可逆、可验证）。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text(
            "export function computeTotal(items) {\n  return items.length;\n}\n",
            encoding="utf-8",
        )
        patch = "-  return items.length;\n+  return 0;"
        ok, applied = apply_injection(tmp_path, "src/cart.js", patch)
        assert ok is True
        content = (tmp_path / "src" / "cart.js").read_text(encoding="utf-8")
        assert "return 0;" in content
        assert "return items.length;" not in content
        assert applied == 1

    def test_patch_not_applicable_fails(self, tmp_path):
        """补丁与文件内容不匹配 → 验证失败（可判定为无效实例）。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text("// empty\n", encoding="utf-8")
        patch = "-  return items.length;\n+  return 0;"
        ok, applied = apply_injection(tmp_path, "src/cart.js", patch)
        assert ok is False


class TestPrepareAcceptance:
    def test_acceptance_file_naming_convention(self, tmp_path):
        """验收测试文件名带 cognicode_ 前缀、放既有测试目录（地图 Notes）。"""
        (tmp_path / "tests").mkdir()
        result = prepare_acceptance_files(tmp_path, _modify_task(), "tests")
        assert result is not None
        names = [p.name for p in result]
        assert any(n.startswith("cognicode_") for n in names)
        assert any("guard" in n for n in names)  # P2P 守护测试

    def test_acceptance_in_dir_without_tests(self, tmp_path):
        """仓库无 tests 目录 → 不可注入验收测试（返回 None）。"""
        result = prepare_acceptance_files(tmp_path, _modify_task(), "tests")
        assert result is None


class TestVerifyTasks:
    def test_all_pass_keeps_all(self, tmp_path):
        """验证全部通过 → 全部保留。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text(
            "export function computeTotal(items) {\n  return items.length;\n}\n",
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        # 假验证器：全部通过
        class PassVerifier:
            def verify(self, task):
                return VerificationResult(ok=True, note="pass")

        tasks = [_search_task(), _locate_task(), _modify_task()]
        kept, dropped = verify_tasks(tasks, verifier=PassVerifier(), root=tmp_path)
        assert len(kept) == 3
        assert dropped == []

    def test_drops_failed_and_records(self, tmp_path):
        """验证失败的任务被砍掉（记录原因）。"""
        class FailSome:
            def verify(self, task):
                if task.id == "locate-1":
                    return VerificationResult(ok=False, note="补丁无法应用")
                return VerificationResult(ok=True, note="pass")

        tasks = [_search_task(), _locate_task(), _modify_task()]
        kept, dropped = verify_tasks(tasks, verifier=FailSome(), root=tmp_path)
        assert [t.id for t in kept] == ["search-1", "modify-1"]
        assert dropped == [("locate-1", "补丁无法应用")]

    def test_real_verifier_applies_injection_and_acceptance(self, tmp_path):
        """真验证器：注入补丁可应用 + 验收测试可注入 → 判定。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text(
            "export function computeTotal(items) {\n  return items.length;\n}\n",
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        from cognicode.verify import RealVerifier

        verifier = RealVerifier(root=tmp_path)
        tasks = [_search_task(), _locate_task(), _modify_task()]
        kept, dropped = verify_tasks(tasks, verifier=verifier, root=tmp_path)
        # search 无需注入 → 通过；locate/modify 注入可应用 → 通过
        assert len(kept) == 3

    def test_real_verifier_drops_unapplicable(self, tmp_path):
        """注入补丁不可应用 → 实例被砍（SWE-bench 式执行式过滤）。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "cart.js").write_text("// no such line\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        from cognicode.verify import RealVerifier

        verifier = RealVerifier(root=tmp_path)
        tasks = [_locate_task()]
        kept, dropped = verify_tasks(tasks, verifier=verifier, root=tmp_path)
        assert kept == []
        assert len(dropped) == 1
