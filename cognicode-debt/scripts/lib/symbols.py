"""tree-sitter 符号提取（债检测确定性提取层，提取器名 `symbols`）。

从 `src/cognicode/symbols.py`（#20 任务生成资产）收缩搬迁（#58，
asset-inventory 资产 #1）：提取函数/方法/类命名符号，语言无关、确定性、
无 LLM。债检测语义下，符号面是多数族共享的中间层：

- A 族（naming-debt / duplicate-code）：符号名与位置锚；
- B 族（test-gap）：测试文件符号做分子（所以**要扫测试**，见下）；
- G 族（module-graph）：模块清单、公开/私有符号数（criteria/G 判据 §1）。

目录排除口径已按债检测语义修正（#58 验收项，旧口径为任务生成服务）：
- **移除** test/tests/spec/__tests__ 排除——债检测要扫测试，test-gap 检测
  需要测试文件符号；
- **保留** vendor/node_modules/dist/build 等依赖与产物目录排除，docs/doc
  排除保留（非源码）。

tree-sitter 生命周期与段错误规避沿袭原实现（start_byte 数行号，真仓实测）。
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
    ".css": "css",  # css 无符号提取（无符号节点映射），仅供 big-file/
                   # duplicate-exact 的文件域判定（样例仓 styles_v3.css 实锤簇）
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
# class = 类（class_declaration / class_definition；Swift 的 struct/enum/
# protocol/extension/actor 也都落 class_declaration——类型面统一记 class）
_SYMBOL_NODE_TYPES: dict[str, str] = {
    "function_definition": "function",   # python/go/rust/... 顶层函数
    "function_declaration": "function",  # js/ts 顶层函数 + swift 函数与方法
    "method_declaration": "method",      # php 类内方法
    "method_definition": "method",       # js/ts 类内方法
    "class_declaration": "class",        # js/ts/php 类 + swift 全类型声明
    "class_definition": "class",         # python 类
}

# 符号名称所在的子节点类型（语言相关，实测）
# simple_identifier：swift 的函数/方法名节点（#59 实测补——样例仓是
# Swift 仓，缺它则整个 Swift 符号面为空）
_NAME_NODE_TYPES: frozenset[str] = frozenset(
    {"identifier", "name", "property_identifier", "simple_identifier",
     "type_identifier"},
)



@dataclass(frozen=True)
class Symbol:
    """一个命名符号（语言无关的稳定键）。"""

    kind: str      # "function" | "method" | "class"
    name: str      # 符号名（类内方法只记方法名，锚点描述会带类前缀）
    file: str      # 相对仓库根的文件路径（posix 形式）
    line: int      # 符号起始行号（1-based）

    def to_dict(self) -> dict:
        """工件载荷形态（symbols.json data.symbols 条目）。"""
        return {"kind": self.kind, "name": self.name, "file": self.file,
                "line": self.line}


def file_language(relpath: str | Path) -> str | None:
    """按扩展名判定 tree-sitter 语言名；未知扩展返回 None。"""
    return _EXT_TO_LANG.get(Path(relpath).suffix.lower())


def symbol_display_name(kind: str, name: str) -> str:
    """符号的人类可读名（任务描述/报告用，中文 + 术语）。"""
    return {"function": "函数", "method": "方法", "class": "类"}.get(kind, kind) + f" {name}"


# ---------------------------------------------------------------------------
# 文件遍历（债检测口径：依赖/产物/文档目录排除，测试目录**不**排除）
# ---------------------------------------------------------------------------

# 与旧口径（任务生成，src/cognicode/symbols.py）的差异：
# 移除 "test", "tests", "spec", "__tests__"——债检测要扫测试（#58）。
_EXCLUDE_DIR_TOKENS = frozenset(
    {
        "vendor", "node_modules", "dist", "build", "docs", "doc",
        "public", "static", "assets", "template",
        "templates", "view", "views", "example", "examples", "sample", "data",
    }
)


def _iter_source_files(root: Path) -> list[Path]:
    """仓库内可解析源码文件（相对路径），跳过隐藏与排除目录。

    注意：test/tests/spec/__tests__ **不**在排除集——债检测要扫测试。
    """
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
    # 注意：不因 has_error 弃整个文件（#59 实测修正——样例仓 Swift 6 的
    # `isolated deinit` 语法 tree-sitter 尚不支持，has_error=True 时文件
    # 里其余符号仍完整可提取；ERROR 节点本身不匹配符号类型，walk 自然跳过）
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


def symbols_payload(repo: str | Path) -> dict:
    """`symbols.json` 的 data 载荷（symbols 提取器产出）。"""
    return {
        "symbols": [s.to_dict() for s in extract_symbols(repo)],
    }
