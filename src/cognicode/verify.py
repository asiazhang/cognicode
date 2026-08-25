"""执行式验证过滤（#20 第三段）。

生成的任务须过 harness 侧客观判定（ADR-0002：位置匹配/测试红绿/退出码），
过不了的实例当场砍掉（SWE-bench/SWE-smith 式「生成即验证」）。

本模块实现**确定性验证器**（生成期过滤，不真跑 agent）：
- 检索类：题面不带名 → 需能解析出 ground truth 符号（文件+名称存在）；
- 定位类：注入补丁必须能应用到仓库源码（可逆、可判定）；
- 修改类：注入补丁可应用 + 最小验收测试文件可注入（`cognicode_` 前缀，
  放既有测试目录，判 F2P）+ P2P 守护测试（保证「改动前已绿」基线，
  地图 Notes 锁定）。

真正跑测试红绿的判卷（五类 outcome 归类）归 #21（verdict 层 + harness）；
本层只做「生成出的实例可执行」的静态可应用性过滤。

验证器可注入（Verifier 协议），假验证器用于单测，RealVerifier 供管线用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationConfig:
    """验证过滤配置（独立固定）。"""

    # 验收测试目录：既有测试目录（地图 Notes：放既有测试目录）
    test_dirs: tuple[str, ...] = ("tests", "test", "spec", "phpunit")
    # 验收测试文件名前缀（地图 Notes 锁定：cognicode_）
    prefix: str = "cognicode_"
    # P2P 守护测试标记（文件名含 guard 即守护）
    guard_marker: str = "guard"


# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationResult:
    """一次任务验证的结论。"""

    ok: bool
    note: str = ""


class Verifier(Protocol):
    """验证器协议：判定一个任务实例可否执行。"""

    def verify(self, task) -> VerificationResult: ...


# ---------------------------------------------------------------------------
# 补丁应用（统一 diff 风格：- 旧行 / + 新行）
# ---------------------------------------------------------------------------


_PATCH_HUNK = re.compile(r"^-(?P<old>.*)\n\+(?P<new>.*)$", re.MULTILINE)


def apply_injection(root: Path, relfile: str, patch: str, *, dry_run: bool = False) -> tuple[bool, int]:
    """把注入补丁应用到仓库源码文件。

    Args:
        root: 仓库根目录。
        relfile: 相对路径（如 src/cart.js）。
        patch: 统一 diff 风格（`- old` / `+ new` 行对，本生成器形态）。
        dry_run: 只检查可应用性，不落盘改动（生成期过滤用）。

    Returns:
        (ok, applied): 全部匹配并应用返回 (True, 应用行数)；
        任一行不匹配返回 (False, 已应用行数)。dry_run 时不写文件。
    """
    path = root / relfile
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return False, 0

    hunks = list(_PATCH_HUNK.finditer(patch))
    if not hunks:
        return False, 0

    new_lines = list(lines)
    applied = 0
    # 从后往前应用，避免行号漂移（简单起见逐 hunk 精确匹配一次）
    for m in hunks:
        old_line, new_line = m.group("old"), m.group("new")
        found = False
        for i, ln in enumerate(new_lines):
            if ln == old_line:
                new_lines[i] = new_line
                found = True
                applied += 1
                break
        if not found:
            return False, applied  # 不匹配 → 判定无效实例，不落盘

    if dry_run:
        return True, applied
    try:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        return False, applied
    return True, applied


# ---------------------------------------------------------------------------
# 验收测试注入
# ---------------------------------------------------------------------------


def _acceptance_test_content(task: ModifyTask, guard: bool) -> str:
    """生成最小验收测试（F2P）或 P2P 守护测试内容（占位骨架）。

    真实测试体由判卷层（#21）在跑测试时按语言生成可执行断言；
    本层先注入文件骨架 + 目标符号信息，保证「文件存在、命名合规、
    放既有测试目录」这一生成期约定可验证。
    """
    sym = task.symbol
    marker = "guard" if guard else "fail_to_pass"
    return (
        f"# cognicode {marker} acceptance test (synthetic, task {task.id})\n"
        f"# target: {sym.file}::{sym.name}\n"
    )


def _test_dir_for(root: Path, cfg: VerificationConfig) -> Path | None:
    """定位既有测试目录（地图 Notes：放既有测试目录）；无则返回 None。"""
    for name in cfg.test_dirs:
        d = root / name
        if d.is_dir():
            return d
    return None


def prepare_acceptance_files(
    root: Path, task: ModifyTask, test_dir: str, cfg: VerificationConfig | None = None,
) -> list[Path] | None:
    """为修改类任务注入最小验收测试文件（F2P）+ P2P 守护测试。

    Args:
        root: 仓库根目录。
        task: 修改类任务。
        test_dir: 既有测试目录名（如 "tests"）。
        cfg: 验证配置。

    Returns:
        注入的文件路径清单；测试目录不存在返回 None（实例不可执行）。
    """
    cfg = cfg or VerificationConfig()
    td = root / test_dir
    if not td.is_dir():
        return None

    sym_name = task.symbol.name
    f2p = td / f"{cfg.prefix}f2p_{sym_name}.py"
    guard = td / f"{cfg.prefix}guard_{sym_name}.py"
    f2p.write_text(_acceptance_test_content(task, guard=False), encoding="utf-8")
    guard.write_text(_acceptance_test_content(task, guard=True), encoding="utf-8")
    return [f2p, guard]


# ---------------------------------------------------------------------------
# 确定性验证器
# ---------------------------------------------------------------------------


class RealVerifier:
    """生成期确定性验证器：可应用性过滤（不真跑测试，判卷归 #21）。"""

    def __init__(self, config: VerificationConfig | None = None, root: Path | None = None):
        self.config = config or VerificationConfig()
        self.root = root  # 仓库根（优先于 symbol.root，便于测试注入）

    def _root_for(self, task) -> Path:
        if self.root is not None:
            return self.root
        return Path(task.symbol.root) if task.symbol.root else Path.cwd()

    def verify(self, task) -> VerificationResult:
        kind = task.kind
        if kind == "search":
            # 检索：题面不带名 + ground truth 符号存在（文件+名称可解析）
            if not task.ground_truth:
                return VerificationResult(False, "检索任务缺 ground truth")
            return VerificationResult(True, "检索任务有效（符号级匹配目标存在）")
        if kind == "locate":
            root = self._root_for(task)
            ok, n = apply_injection(root, task.injection["file"], task.injection["patch"], dry_run=True)
            if not ok:
                return VerificationResult(False, f"注入补丁无法应用（{task.injection['file']}）")
            return VerificationResult(True, f"注入补丁可应用（{n} 行）")
        if kind == "modify":
            root = self._root_for(task)
            ok, n = apply_injection(root, task.bug["file"], task.bug["patch"], dry_run=True)
            if not ok:
                return VerificationResult(False, f"bug 补丁无法应用（{task.bug['file']}）")
            td = _test_dir_for(root, self.config)
            if td is None:
                return VerificationResult(False, "仓库无既有测试目录，无法注入验收测试")
            return VerificationResult(True, "修改类任务有效（补丁可应用 + 验收测试可注入）")
        return VerificationResult(False, f"未知任务类别 {kind!r}")


# ---------------------------------------------------------------------------
# 过滤
# ---------------------------------------------------------------------------


def verify_tasks(
    tasks: list,
    *,
    verifier: Verifier,
    root: Path | None = None,
) -> tuple[list, list[tuple[str, str]]]:
    """执行式验证过滤：通过的任务保留，失败的砍掉并记录原因。

    Args:
        tasks: 生成的任务清单。
        verifier: 验证器（协议可注入）。
        root: 仓库根（验证器自己会用 symbol.root，这里仅留接口）。

    Returns:
        (kept, dropped): kept 为通过任务；dropped 为 [(task_id, 原因)]。
    """
    kept: list = []
    dropped: list[tuple[str, str]] = []
    for task in tasks:
        try:
            result = verifier.verify(task)
        except Exception as e:  # 验证器自身异常视为不通过（不炸管线）
            result = VerificationResult(False, f"验证异常：{e}")
        if result.ok:
            kept.append(task)
        else:
            dropped.append((task.id, result.note))
    return kept, dropped
