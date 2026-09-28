"""test-gap 提取器（#59 新写）：两层漏斗，产 per-符号 gap 候选清单。

判据权威来源：criteria/B-testing.md §1 + criteria/rules/test-gap.md——
两层漏斗从便宜到贵：文件级漏斗筛「无测试触达的文件」，符号级精判抓
「有触达文件里的裸露符号」。

「测试触达」口径 = **符号触达**（判据文件原话）：被测符号名在测试文件
**文本中出现**即可，不验证调用图。保守口径，语言无关、确定可提取；
误报方向可控（偏宽只漏报 rot，不冤枉 gap）。

产物（test_gap.json data 载荷）：
- `files`：文件级结论（每源文件一行：主符号名列表、是否零触达、
  gap/total 符号数、gap 符号名采样）——B 族子代理上卷到模块级的原料；
- `gap_symbols`：per-符号 gap 明细（每未触达符号一条，判据的实例粒度）。

「主符号名」（文件级触达判定键）= 文件定义的类型符号（class/struct/
enum/protocol/actor/extension/typealias 名）∪ 文件名词干。对 open-vibe-island
实测：这口径复现手工样例的 35 个零触达文件（文件名零出现，含
WatchHTTPEndpoint / 安装管理器群 / coordinator 层）。类型符号兜底文件名：
`Foo.swift` 未定义任何类型时按文件名判（Swift 文件名惯例 = 主类型名）。

符号级精判的**类型/函数不对称**（实测校准，见 testgap 的样例验证）：
- **类型符号**（kind=class 等）：符号名出现即触达——类型名撞通用词
  （Entry/CodingKeys）罕见且有正测语义；
- **函数符号**（kind=function/method）：`start/stop/title/disconnect`
  等通用词在测试文本中大量出现，逐词判触达会把整片裸露文件判成
  「有触达」。口径：**文件任一主符号（类型名）触达才进符号级精判**，
  文件级零触达的文件整文件计 gap（漏斗语义：便宜的先筛）。
  有触达文件内，函数符号仍逐符号判（gap 函数如实裸露，主类型被
  测到不代表其方法被测到）。

目录口径：复用 symbols.py 的 `_iter_source_files`（要扫测试——测试
文件是触达判定的**分子**，本身不产 gap）；文件域不排除 design/ 等
设计资产目录（duplicate-code 的 exact 档在那边有簇，test-gap 只对
有测试文件的仓库有意义，无测试文件时全部源文件即全部 gap——如实
报告，由 B 族子代理结合模块语义上卷）。

tree-sitter 不可用时：符号级精判降级为纯文件名口径（文件名零出现 =
零触达），`degraded` 字段标注，不炸管线（与 #58 容错纪律一致）。
"""

from __future__ import annotations

from pathlib import Path

from lib.symbols import Symbol, extract_symbols, file_language

# 测试文件判定（触达判定的分子；口径与 probe/static_signals 的常识一致）
_TEST_DIR_TOKENS = frozenset({"test", "tests", "__tests__", "spec", "specs"})

# gap 符号名采样上限（文件级行的 symbols 字段；全量在 gap_symbols）
_SAMPLE_LIMIT = 12


def _is_test_file(relpath: str) -> bool:
    """测试文件判定：路径任一层是 test/tests/__tests__/spec(s)（大小写不
    敏感——Swift 惯例的 Tests/ 与 JS 的 __tests__/__tests__/都入面）；或
    文件名 test_/test-/spec_/spec- 前缀。"""
    parts = Path(relpath).parts
    if any(part.lower() in _TEST_DIR_TOKENS for part in parts[:-1]):
        return True
    name = parts[-1].lower() if parts else ""
    return name.startswith(("test_", "test-", "spec_", "spec-"))


def _is_type_symbol(sym: Symbol) -> bool:
    """类型符号（class/struct/enum/protocol/actor/extension/typealias 等）。

    symbols 提取器的 kind 里 "class" 类 + extension（若有）都算类型面；
    "function"/"method" 不算。
    """
    return sym.kind == "class"


def test_gap_payload(repo: str | Path) -> dict:
    """`test_gap.json` 的 data 载荷（test-gap 提取器产出）。"""
    root = Path(repo)
    all_symbols = extract_symbols(root)
    if not all_symbols:  # 无符号面（tree-sitter 缺失或空仓）：纯文件名口径
        return _filename_only_payload(root)

    src_symbols = [s for s in all_symbols if not _is_test_file(s.file)]
    test_files = sorted({s.file for s in all_symbols if _is_test_file(s.file)})
    if not test_files:
        # 无测试文件符号面：测试面按测试文件文本兜底（文件名口径）；
        # 连测试文件都没有 → 全部源文件零触达（如实报告）
        test_text = _read_test_text_by_walk(root)
    else:
        test_text = _read_test_files(root, test_files)

    files_by_path: dict[str, list[Symbol]] = {}
    for s in src_symbols:
        files_by_path.setdefault(s.file, []).append(s)

    files_out: list[dict] = []
    gap_symbols: list[dict] = []
    for rel in sorted(files_by_path):
        syms = files_by_path[rel]
        types = [s for s in syms if _is_type_symbol(s)]
        # 主符号名 = 类型符号名 ∪ 文件名词干（去扩展名）
        primary = {s.name for s in types}
        primary.add(Path(rel).stem)
        touched = any(n in test_text for n in primary)

        gaps = [] if touched else list(syms)
        if not touched:
            # 文件级漏斗命中：整文件 gap
            pass
        else:
            # 符号级精判：类型符号触达即文件触达；函数符号逐个判
            gaps = [s for s in syms if not _is_type_symbol(s)
                    and s.name not in test_text]

        files_out.append({
            "file": rel,
            "primary_symbols": sorted(primary),
            "zero_touch": not touched,
            "symbols_total": len(syms),
            "symbols_gap": len(gaps),
            "gap_symbol_names": [s.name for s in gaps[:_SAMPLE_LIMIT]],
        })
        for s in gaps:
            gap_symbols.append(s.to_dict())

    return {
        "test_files": test_files,
        "source_files": len(files_out),
        "files": files_out,
        "gap_symbols": gap_symbols,
    }


def _read_test_files(root: Path, test_files: list[str]) -> str:
    """读测试文件文本（触达判定分子；读失败跳过，不炸）。"""
    parts: list[str] = []
    for rel in test_files:
        try:
            parts.append((root / rel).read_text(errors="replace"))
        except Exception:
            continue
    return "\n".join(parts)


def _read_test_text_by_walk(root: Path) -> str:
    """无符号面时按目录走查找测试文件（文件名口径）。"""
    parts: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if file_language(rel) is None:
            continue
        if not _is_test_file(rel.as_posix()):
            continue
        try:
            parts.append(p.read_text(errors="replace"))
        except Exception:
            continue
    return "\n".join(parts)


def _filename_only_payload(root: Path) -> dict:
    """降级口径：无符号面时按文件名判触达（degraded 标注）。"""
    test_files: list[str] = []
    src_files: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if file_language(rel) is None:
            continue
        rel_str = rel.as_posix()
        (test_files if _is_test_file(rel_str) else src_files).append(rel_str)

    test_text = "\n".join(
        _safe_read(root / f) for f in test_files
    )
    files_out = []
    gap_symbols = []
    for rel in src_files:
        stem = Path(rel).stem
        zero = stem not in test_text
        files_out.append({
            "file": rel,
            "primary_symbols": [stem],
            "zero_touch": zero,
            "symbols_total": 1,
            "symbols_gap": 1 if zero else 0,
            "gap_symbol_names": [stem] if zero else [],
        })
        if zero:
            gap_symbols.append({"kind": "file", "name": stem,
                                "file": rel, "line": 1})
    return {
        "degraded": "filename-only (no symbol surface)",
        "test_files": test_files,
        "source_files": len(files_out),
        "files": files_out,
        "gap_symbols": gap_symbols,
    }


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except Exception:
        return ""
