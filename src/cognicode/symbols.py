"""tree-sitter 符号提取（#20）：任务生成管线的第一段。

从仓库源码提取函数/方法/类符号——语言无关的根基（#5 三段式第一段：
结构解析）。供三类任务的生成与验收对照：
- 检索类：选符号做 needle（RepoQA SNF 式），验收 = 符号级匹配（file+名称）；
- 定位类：选符号做注入点（bug 注入），验收 = 对照注入点；
- 修改类：选函数/方法做 bug 注入对象，验收 = 测试红绿。

只提取「命名符号」（函数/方法/类），不做语义评分；跳过测试文件与依赖/
文档目录（vendor/node_modules/docs 等），这些不是「被测代码」。
tree-sitter-language-pack 统一解析（prior-art.md：RepoQA 已验证的语言无关底座）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - 导入路径探测
    from tree_sitter_language_pack import get_parser
except ImportError:  # pragma: no cover
    get_parser = None

# ---------------------------------------------------------------------------
# 语言与扩展名映射（与 static_signals 共享口径；新增语言需回归）
# ---------------------------------------------------------------------------

# 扩展名 → tree-sitter 语言名（tree-sitter-language-pack 命名）
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".php": "php",
    ".rb": "ruby",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".rs": "rust",
    ".lua": "lua",
    ".ex": "elixir",
    ".exs": "elixir",
    ".kt": "kotlin",
    ".swift": "swift",
    ".sh": "bash",
}

# 符号节点类型 → 符号类别（tree-sitter AST 节点名，实测）
# method = 类内方法（php method_declaration / js method_definition）
# function = 顶层函数（python/js/go/... 的 function_definition/function_declaration）
# class = 类（class_declaration / class_definition）
_SYMBOL_NODE_TYPES: dict[str, str] = {
    "function_definition": "function",   # python/go/rust/... 顶层函数
    "function_declaration": "function",  # js/ts 顶层函数
    "method_declaration": "method",      # php 类内方法
    "method_definition": "method",       # js/ts 类内方法
    "class_declaration": "class",        # js/ts/php 类
    "class_definition": "class",         # python 类
}

# 符号名称所在的子节点类型（语言相关，实测）
_NAME_NODE_TYPES: frozenset[str] = frozenset(
    {"identifier", "name", "property_identifier"}
)


@dataclass(frozen=True)
class Symbol:
    """一个命名符号（语言无关的稳定键）。"""

    kind: str      # "function" | "method" | "class"
    name: str      # 符号名（类内方法只记方法名，检索描述会带类前缀）
    file: str      # 相对仓库根的文件路径（posix 形式）
    line: int      # 符号起始行号（1-based）
    root: str = ""  # 仓库根目录（可选；注入补丁读取源码时用）

    def __str__(self) -> str:
        return f"{symbol_display_name(self.kind, self.name)} @ {self.file}:{self.line}"


def file_language(relpath: str | Path) -> str | None:
    """按扩展名判定 tree-sitter 语言名；未知扩展返回 None。"""
    return _EXT_TO_LANG.get(Path(relpath).suffix.lower())


def symbol_display_name(kind: str, name: str) -> str:
    """符号的人类可读名（任务描述/报告用，中文 + 术语）。"""
    return {"function": "函数", "method": "方法", "class": "类"}.get(kind, kind) + f" {name}"


# ---------------------------------------------------------------------------
# 文件遍历（与 static_signals 排除口径一致：隐藏/依赖/文档目录不进符号面）
# ---------------------------------------------------------------------------

_EXCLUDE_DIR_TOKENS = frozenset(
    {
        "vendor", "node_modules", "dist", "build", "docs", "doc", "test",
        "tests", "spec", "__tests__", "public", "static", "assets", "template",
        "templates", "view", "views", "example", "examples", "sample", "data",
    }
)


def _iter_source_files(root: Path) -> list[Path]:
    """仓库内可解析源码文件（相对路径），跳过隐藏与排除目录。"""
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if any(part in _EXCLUDE_DIR_TOKENS for part in rel.parts):
            continue
        if file_language(rel) is None:
            continue
        files.append(rel)
    return files


def _symbol_name(node) -> str | None:
    """取符号节点的名称子节点文本；匿名/语法异常返回 None。"""
    for child in node.children:
        if child.type in _NAME_NODE_TYPES:
            try:
                return child.text.decode("utf-8", errors="replace")
            except Exception:
                return None
    return None


# ---------------------------------------------------------------------------
# 提取
# ---------------------------------------------------------------------------


def _symbols_in_file(root: Path, rel: Path, lang: str) -> list[Symbol]:
    """解析单个文件并提取符号（独立函数：tree-sitter 生命周期隔离）。

    真仓实测（nbnbk）：tree-sitter-language-pack 0.26 的 `Node.start_point`
    （Point 对象）访问在特定 PHP 节点上段错误（本环境）；改用
    `start_byte` + 源码计数行号（确定性、实测稳定）。
    """
    with open(root / rel, "rb") as f:
        src = f.read()
    tree = get_parser(lang).parse(src)
    if tree.root_node.has_error:
        return []
    found: list[Symbol] = []
    current: list = [tree.root_node]
    while current:
        nxt: list = []
        for node in current:
            kind = _SYMBOL_NODE_TYPES.get(node.type)
            if kind is not None:
                name = _symbol_name(node)
                if name:
                    # start_byte 安全；行号 = 源码中该偏移前的换行数 + 1
                    line = src[: node.start_byte].count(b"\n") + 1
                    found.append(
                        Symbol(
                            kind=kind,
                            name=name,
                            file=rel.as_posix(),
                            line=line,
                        )
                    )
            nxt.extend(node.children)
        current = nxt
    return found


def extract_symbols(root: str | Path) -> list[Symbol]:
    """提取仓库内全部命名符号（函数/方法/类），确定性、语言无关。

    Args:
        root: 仓库根目录。

    Returns:
        按 (file, line) 排序的符号清单。tree-sitter 不可用或某文件
        解析失败时跳过该文件（不炸管线，与 static_signals 同策略）。
    """
    root_path = Path(root)
    if get_parser is None:  # pragma: no cover - 依赖缺失降级
        return []

    symbols: list[Symbol] = []
    for rel in _iter_source_files(root_path):
        lang = file_language(rel)
        if lang is None:
            continue
        try:
            symbols.extend(_symbols_in_file(root_path, rel, lang))
        except Exception:
            continue  # 读/解析失败跳过（确定性：文件级跳过，不污染全局）

    symbols.sort(key=lambda s: (s.file, s.line))
    return symbols
