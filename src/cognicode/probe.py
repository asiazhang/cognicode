"""环境探测（#19 实现，探测判定已由地图 Notes 锁定）。

定位仓库声明的构建/测试命令，逐一执行、记录 exit code 与耗时；
「成功」= 至少一条构建 exit 0 且至少一条测试 exit 0（standing preference，
勿再开票）。探测结果决定任务生成上限（fail_env 降级路径，见 #6 与地图 Notes）。

探测是零合成基准任务（CONTEXT.md「环境探测」）：让 agent 从冷启动跑起
构建与测试，探测先行，其结果决定合成任务的生成上限——基建缺失导致的
任务降级是环境可用性的低分信号，不是评估失败。

本模块只做命令定位（确定性、无 I/O 执行）；执行由调用方驱动
（ProbeRunner 在 harness 内，见 harness.py）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# 探测命令来源清单（按优先级）：仓库声明的包管理/构建/测试定义文件。
# 每种来源给出「构建命令」「测试命令」定位规则（确定性，不做语义评分）。
# 排序即优先级：包定义 > 锁文件 > CI 配置 > Makefile。
# 探测会逐条尝试（exec 存在才执行）；「成功」判定见探测协议。
BUILD_DEF_FILES = (
    "composer.json",     # PHP（scripts: {build, ...}）
    "package.json",      # JS/TS（scripts: {build, ...}）
    "pyproject.toml",    # Python（[tool.uv] 或 build-system + pytest）
    "setup.py",          # Python 遗留
    "requirements.txt",  # Python 依赖（探测「能否安装」用）
    "Cargo.toml",        # Rust
    "go.mod",            # Go
    "pom.xml",           # Java
    "Makefile",          # 通用（make build / make test）
    "GNUmakefile",
    "build.gradle",
)

# 已知测试框架的测试目录（探测测试命令的后备：目录存在即认为有测试面）
TEST_DIRS = ("tests", "test", "spec", "__tests__", "phpunit")


@dataclass(frozen=True)
class ProbeCommand:
    """一条待探测命令：构建或测试。"""

    kind: str  # "build" | "test"
    name: str  # 判卷键名：build.<来源> / test.<来源>，如 "build.composer"（probe_success 消费）
    command: list[str]  # 可执行命令（argv），如 ["composer", "run", "build"]
    source_file: Path | None = None  # 定位来源（配置/CI 文件）


def _read_json(path: Path) -> dict | None:
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _scan_scripts(scripts: dict, keys: tuple[str, ...]) -> list[str]:
    """从 package.json/composer.json 的 scripts 里按键名取命令（确定性）。

    keys 按优先级：如 ("build", "compile", "dist") 取第一个命中的值；
    值若是字符串命令直接返回；若是 dict（npm run-script 嵌套）跳过。
    """
    for key in keys:
        val = scripts.get(key)
        if isinstance(val, str) and val.strip():
            return [val]
    return []


def locate_probe_commands(repo: Path) -> tuple[list[ProbeCommand], list[str]]:
    """定位仓库声明的构建/测试命令。

    Returns:
        (commands, notes): 命令清单（按来源优先级排好，探测按序执行）；
        notes 记录定位过程中的事实（如「composer.json 无 scripts.build」），
        供报告/诊断。

    纯确定性定位：只读文件、不执行任何命令。
    """
    commands: list[ProbeCommand] = []
    notes: list[str] = []

    # --- 1. composer.json（PHP） ---
    composer = repo / "composer.json"
    if composer.exists():
        data = _read_json(composer)
        if data:
            scripts = data.get("scripts") or {}
            for key in ("build", "compile"):
                vals = _scan_scripts(scripts, (key,))
                if vals:
                    commands.append(
                        ProbeCommand(
                            "build", "build.composer",
                            ["composer", "run", key], composer,
                        )
                    )
                    break
            else:
                notes.append("composer.json 无 scripts.build/compile")
            # 测试：scripts.test 或 phpunit 约定
            test_vals = _scan_scripts(scripts, ("test", "phpunit", "spec"))
            if test_vals:
                commands.append(
                    ProbeCommand("test", "test.composer",
                                 ["composer", "run", "test"], composer)
                )
            elif (repo / "phpunit.xml").exists() or (repo / "phpunit.xml.dist").exists():
                commands.append(
                    ProbeCommand("test", "test.phpunit", ["phpunit"], composer)
                )
            else:
                notes.append("composer.json 无 scripts.test 且无 phpunit.xml")

    # --- 2. package.json（JS/TS） ---
    pkg = repo / "package.json"
    if pkg.exists():
        data = _read_json(pkg)
        if data:
            scripts = data.get("scripts") or {}
            for key in ("build", "compile", "dist"):
                vals = _scan_scripts(scripts, (key,))
                if vals:
                    commands.append(
                        ProbeCommand(
                            "build", "build.package",
                            ["npm", "run", key], pkg,
                        )
                    )
                    break
            else:
                notes.append("package.json 无 scripts.build/compile/dist")
            test_vals = _scan_scripts(scripts, ("test", "spec", "jest"))
            if test_vals:
                commands.append(
                    ProbeCommand("test", "test.package",
                                 ["npm", "run", "test"], pkg)
                )
            else:
                notes.append("package.json 无 scripts.test")

    # --- 3. pyproject.toml（Python，uv/pytest） ---
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        notes.append("pyproject.toml：构建命令无通用形态，探测从 pytest 起")
        if (repo / "pytest.ini").exists() or (repo / "tox.ini").exists() \
                or (repo / "tests").is_dir():
            commands.append(
                ProbeCommand("test", "test.pytest",
                             ["python", "-m", "pytest", "-q"], pyproject)
            )
        else:
            notes.append("pyproject.toml 无 pytest 配置/测试目录")

    # --- 4. Makefile ---
    for mf in ("Makefile", "GNUmakefile"):
        if (repo / mf).exists():
            text = (repo / mf).read_text(encoding="utf-8", errors="replace")
            if "build:" in text:
                commands.append(
                    ProbeCommand("build", "build.makefile", ["make", "build"], repo / mf)
                )
            if "test:" in text:
                commands.append(
                    ProbeCommand("test", "test.makefile", ["make", "test"], repo / mf)
                )
            break

    # --- 5. 测试目录后备（无显式测试命令时，目录存在即给 phpunit/pytest 探测） ---
    if not any(c.kind == "test" for c in commands):
        for d in TEST_DIRS:
            if (repo / d).is_dir():
                # 探测「测试能否跑」由调用方决定执行；这里只记录存在性
                notes.append(f"测试目录 {d} 存在（无声明测试命令）")
                break

    return commands, notes


def probe_success(exit_codes: dict[str, int]) -> tuple[bool, str]:
    """探测判定：「成功」= 至少一条构建 exit 0 且至少一条测试 exit 0。

    Args:
        exit_codes: {命令名: exit code}，探测逐条执行后的结果。

    Returns:
        (success, reason)：success 决定任务生成上限（fail_env 降级路径）；
        reason 供报告（如「构建全灭：composer 依赖装不上」）。
    """
    builds = {k: v for k, v in exit_codes.items() if k.startswith("build.")}
    tests = {k: v for k, v in exit_codes.items() if k.startswith("test.")}

    build_ok = any(v == 0 for v in builds.values())
    test_ok = any(v == 0 for v in tests.values())

    if not builds:
        return False, "无构建命令可探测（仓库未声明构建）"
    if not tests:
        return False, "无测试命令可探测（仓库未声明测试）"
    if build_ok and test_ok:
        return True, "构建与测试均至少一条 exit 0"
    if not build_ok:
        return False, "构建全灭（无任何构建 exit 0）"
    return False, "测试全灭（无任何测试 exit 0）"
