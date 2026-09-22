"""环境探测命令定位与判定测试（#19，纯函数层）。

验证：确定性命令定位（无执行）、探测成功判定（#6 + 地图 Notes 锁定：
「成功」= 至少一条构建 exit 0 且至少一条测试 exit 0）。
"""

from pathlib import Path

import pytest

from cognicode.probe import (
    locate_probe_commands,
    probe_success,
)


class TestLocateComposer:
    def test_build_and_test_from_scripts(self, tmp_path: Path):
        (tmp_path / "composer.json").write_text(
            '{"scripts": {"build": "php build.php", "test": "phpunit"}}',
            encoding="utf-8",
        )
        commands, notes = locate_probe_commands(tmp_path)
        kinds = [(c.kind, c.name, c.command) for c in commands]
        assert ("build", "build.composer", ["composer", "run", "build"]) in kinds
        assert ("test", "test.composer", ["composer", "run", "test"]) in kinds

    def test_test_fallback_to_phpunit_config(self, tmp_path: Path):
        (tmp_path / "composer.json").write_text('{"scripts": {"build": "x"}}', encoding="utf-8")
        (tmp_path / "phpunit.xml").write_text("<phpunit/>", encoding="utf-8")
        commands, _ = locate_probe_commands(tmp_path)
        assert any(c.kind == "test" and c.command == ["phpunit"] for c in commands)

    def test_no_test_command_note(self, tmp_path: Path):
        (tmp_path / "composer.json").write_text('{"name": "x"}', encoding="utf-8")
        commands, notes = locate_probe_commands(tmp_path)
        assert not any(c.kind == "test" for c in commands)
        assert any("无 scripts.test" in n for n in notes)


class TestLocatePackageJson:
    def test_build_test(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            '{"scripts": {"build": "vite build", "test": "vitest run"}}',
            encoding="utf-8",
        )
        commands, _ = locate_probe_commands(tmp_path)
        kinds = [(c.kind, c.command) for c in commands]
        assert ("build", ["npm", "run", "build"]) in kinds
        assert ("test", ["npm", "run", "test"]) in kinds


class TestLocatePyproject:
    def test_pytest_when_tests_dir(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        commands, _ = locate_probe_commands(tmp_path)
        assert any(c.kind == "test" and "pytest" in c.command for c in commands)

    def test_no_pytest_note(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
        commands, notes = locate_probe_commands(tmp_path)
        assert not any(c.kind == "test" for c in commands)
        assert any("无 pytest" in n for n in notes)


class TestLocateMakefile:
    def test_build_test_targets(self, tmp_path: Path):
        (tmp_path / "Makefile").write_text("build:\n\techo hi\ntest:\n\techo hi\n", encoding="utf-8")
        commands, _ = locate_probe_commands(tmp_path)
        kinds = [(c.kind, c.command) for c in commands]
        assert ("build", ["make", "build"]) in kinds
        assert ("test", ["make", "test"]) in kinds


class TestProbeSuccess:
    def test_both_ok(self):
        ok, reason = probe_success({"build.composer": 0, "test.phpunit": 0})
        assert ok is True
        assert "exit 0" in reason

    def test_build_ok_test_fail(self):
        ok, _ = probe_success({"build.composer": 0, "test.phpunit": 1})
        assert ok is False

    def test_build_fail_test_ok(self):
        ok, _ = probe_success({"build.composer": 1, "test.phpunit": 0})
        assert ok is False

    def test_all_fail(self):
        ok, reason = probe_success({"build.composer": 1, "test.phpunit": 1})
        assert ok is False
        assert "构建全灭" in reason
        assert "测试全灭" in reason

    def test_missing_build(self):
        ok, reason = probe_success({"test.phpunit": 0})
        assert ok is False
        assert "无构建命令" in reason

    def test_missing_test(self):
        ok, reason = probe_success({"build.composer": 0})
        assert ok is False
        assert "无测试命令" in reason

    def test_missing_build_and_test(self):
        ok, reason = probe_success({})
        assert ok is False
        assert "无构建命令" in reason
        assert "无测试命令" in reason
