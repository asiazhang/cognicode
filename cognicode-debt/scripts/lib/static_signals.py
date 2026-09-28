"""静态信号提取（#18）：8 个产分信号。

两维静态面（#7 锁定，语言无关、确定性提取，不做语义评分）：
- 可导航性 4：代理上下文文档、README、注释密度（tree-sitter，唯一需解析的信号）、入口清晰度
- 环境可用性 4：构建定义、锁文件、CI、测试可发现性

每信号产出 (value, score, evidence)：score 取离散刻度 {0, 0.5, 1}；
维度分 = 产分信号算术均值（#7 锁定）；全部确定性，无 LLM。

输出 `static.json`（信号级取值 + 每信号刻度 + 维度算术均值），
消费方是聚合/报告票（#21）。tree-sitter 依赖仅在计算注释密度时触碰。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# 注释密度是唯一需要 tree-sitter 的信号，延迟导入（其余 7 信号不依赖它）
try:  # pragma: no cover - 导入路径探测
    from tree_sitter_language_pack import get_parser
except ImportError:  # pragma: no cover
    get_parser = None

# ---------------------------------------------------------------------------
# 可导航性 4 信号的阈值常量（确定性规则，改动需回 #7/#18）
# ---------------------------------------------------------------------------

# 代理上下文文档：专为编程 agent 准备的仓库上下文说明文件
AGENT_CONTEXT_DOCS = ("AGENTS.md", "CLAUDE.md", "CONTEXT.md", ".cursorrules")

# README：仓库根/一层的入口文档（不递归，深层文档不是入口）
# 大小写不敏感匹配（README/Readme/readme 均算）
README_NAMES = ("README", "README.md", "README.rst", "README.txt")
_README_NAMES_LOWER = frozenset(n.lower() for n in README_NAMES)

# 入口清晰度：仓库根/一层源码里的常见入口文件名（纯命名规则）
ENTRY_NAMES = (
    "main.py",
    "cli.py",
    "app.py",
    "manage.py",
    "index.js",
    "index.ts",
    "main.js",
    "main.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "main.go",
    "main.rs",
    "index.html",
)

# ---------------------------------------------------------------------------
# 环境可用性 4 信号的阈值常量
# ---------------------------------------------------------------------------

# 构建定义：任一定义文件（=1 类 → 0.5；≥2 类 → 1）
BUILD_DEF_NAMES = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "build.gradle",
    "pom.xml",
    "Gemfile",
    "composer.json",
    "Makefile",
    "CMakeLists.txt",
    "Dockerfile",
    "mix.exs",
    "mix.lock",  # 排除（归锁文件）
    "package-lock.json",  # 排除（归锁文件）
)

# 锁文件：依赖解析锁定
LOCKFILE_NAMES = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "composer.lock",
    "mix.lock",
)

# CI 配置
CI_PATHS = (
    ".github/workflows",  # 目录：其下任意文件即命中
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
)

# 测试可发现性：测试文件/目录（`_` 前缀是验收测试注入约定，不算）
# 排除目录：依赖、文档、静态资产、模板、语言无关的通用目录名
TEST_PATH_TOKENS = ("test", "tests", "spec")
TEST_SUFFIXES = (".test.js", ".test.ts", ".spec.js", ".spec.ts")
_TEST_EXCLUDE_DIRS = frozenset(
    {
        "docs",
        "doc",
        "vendor",
        "node_modules",
        "public",
        "static",
        "assets",
        "dist",
        "build",
        "template",
        "templates",
        "view",
        "views",
        "example",
        "examples",
        "sample",
        "samples",
        "resource",
        "resources",
        "data",
        "config",
        "conf",
        "cache",
        "log",
        "logs",
        "tmp",
        "images",
        "img",
        "css",
        "js",
    }
)
# 语言无关的通用代码目录：测试在其中才算可发现
_GENERIC_CODE_DIRS = frozenset({"src", "lib", "app"})

# ---------------------------------------------------------------------------
# 信号注册表
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalSpec:
    """一个产分信号的元信息：名称、维度、刻度、证据类型。"""

    name: str
    dimension: str  # navigability | buildability
    scale: tuple[float, ...] = (0.0, 0.5, 1.0)


# 名称 = <dimension>.<signal>，锁定为 static.json 的稳定键
SIGNALS: list[SignalSpec] = [
    SignalSpec("navigability.agent_context_docs", "navigability"),
    SignalSpec("navigability.readme", "navigability"),
    SignalSpec("navigability.comment_density", "navigability"),
    SignalSpec("navigability.entry_clarity", "navigability"),
    SignalSpec("buildability.build_def", "buildability"),
    SignalSpec("buildability.lockfile", "buildability"),
    SignalSpec("buildability.ci", "buildability"),
    SignalSpec("buildability.test_discoverability", "buildability"),
]

SIGNAL_NAMES: list[str] = [s.name for s in SIGNALS]


@dataclass
class SignalResult:
    """一个信号的提取结果：取值 + 离散刻度 + 证据。"""

    value: float
    score: float
    evidence: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 文件收集
# ---------------------------------------------------------------------------


# 隐藏但参与信号提取的路径（CI 配置、cursor 规则等），不视为隐藏
_ALLOWED_HIDDEN = frozenset(
    {".github", ".gitlab-ci.yml", ".circleci", ".travis.yml", ".cursor", ".cursorrules"}
)


def _is_hidden(path: Path) -> bool:
    """是否隐藏路径（.git/.venv/node_modules 等；信号相关隐藏文件除外）。"""
    parts = path.parts
    for part in parts:
        if part in (".git", ".venv", "node_modules", "__pycache__", ".tox", ".nox"):
            return True
        if part.startswith(".") and part not in _ALLOWED_HIDDEN:
            return True
    return False


def _iter_files(root: Path, max_depth: int | None = None) -> list[Path]:
    """遍历仓库文件（相对路径），跳过隐藏路径；max_depth=None 表示不限制。"""
    files: list[Path] = []
    root_parts_len = len(root.parts)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_hidden(rel):
            continue
        if max_depth is not None and len(rel.parts) > max_depth:
            continue
        files.append(rel)
    return files


# ---------------------------------------------------------------------------
# 信号提取器
# ---------------------------------------------------------------------------


def _extract_agent_context_docs(files: list[Path], root: Path) -> SignalResult:
    found = [str(p) for p in files if p.name in AGENT_CONTEXT_DOCS]
    return SignalResult(
        value=1.0 if found else 0.0,
        score=1.0 if found else 0.0,
        evidence=found,
    )


def _extract_readme(files: list[Path], root: Path) -> SignalResult:
    found = [
        str(p)
        for p in files
        if p.name.lower() in _README_NAMES_LOWER and len(p.parts) <= 1
    ]
    return SignalResult(
        value=1.0 if found else 0.0,
        score=1.0 if found else 0.0,
        evidence=found,
    )


def _extract_entry_clarity(files: list[Path], root: Path) -> SignalResult:
    found = [
        str(p)
        for p in files
        if p.name in ENTRY_NAMES and len(p.parts) <= 2 and p.parts[0] != "docs"
    ]
    score = 1.0 if len(found) >= 2 else (0.5 if len(found) == 1 else 0.0)
    return SignalResult(value=float(len(found)), score=score, evidence=found)


def _extract_build_def(files: list[Path], root: Path) -> SignalResult:
    found = [
        str(p)
        for p in files
        if p.name in BUILD_DEF_NAMES and len(p.parts) <= 2
    ]
    # 一个定义文件 → 0.5（能定位构建入口但未构成清晰定义面）；≥2 类 → 1
    score = 1.0 if len(found) >= 2 else (0.5 if len(found) == 1 else 0.0)
    return SignalResult(value=float(len(found)), score=score, evidence=found)


def _extract_lockfile(files: list[Path], root: Path) -> SignalResult:
    found = [str(p) for p in files if p.name in LOCKFILE_NAMES]
    return SignalResult(
        value=1.0 if found else 0.0,
        score=1.0 if found else 0.0,
        evidence=found,
    )


def _extract_ci(files: list[Path], root: Path) -> SignalResult:
    found = [
        str(p)
        for p in files
        if any(str(p) == c or str(p).startswith(c + "/") for c in CI_PATHS)
    ]
    return SignalResult(
        value=1.0 if found else 0.0,
        score=1.0 if found else 0.0,
        evidence=found,
    )


def _extract_test_discoverability(files: list[Path], root: Path) -> SignalResult:
    found: list[str] = []
    for p in files:
        is_test = False
        if any(tok in p.parts for tok in TEST_PATH_TOKENS):
            is_test = True
        elif p.suffix == ".py" and (
            p.name.startswith("test_") or p.name.endswith("_test.py")
        ):
            is_test = True
        elif p.suffix in (".js", ".ts") and any(
            p.name.endswith(s) for s in TEST_SUFFIXES
        ):
            is_test = True

        # 排除依赖/文档/静态资产等非代码目录；src/lib/app 下的测试才算可发现
        if not is_test:
            continue
        dirs = set(p.parts[:-1])
        if dirs & _TEST_EXCLUDE_DIRS:
            continue
        if dirs & _GENERIC_CODE_DIRS:
            found.append(str(p))
            continue
        # 其余位置（根目录/普通包目录）的测试文件也计入
        found.append(str(p))
    return SignalResult(
        value=1.0 if found else 0.0,
        score=1.0 if found else 0.0,
        evidence=found,
    )


# ---------------------------------------------------------------------------
# 注释密度（tree-sitter，唯一需解析的信号）
# ---------------------------------------------------------------------------

# 注释密度 = 注释字节 / 代码总字节（只统计可解析的源码文件）；
# 刻度：<0.05 → 0；0.05~0.15 → 0.5；≥0.15 → 1
COMMENT_RATIO_MIN_HALF = 0.05
COMMENT_RATIO_MIN_FULL = 0.15

# 语言名 → 注释节点类型集合（tree-sitter-language-pack 实测；加语言需回归）
_COMMENT_NODE_TYPES: dict[str, frozenset[str]] = {
    "python": frozenset({"comment"}),
    "javascript": frozenset({"comment"}),
    "typescript": frozenset({"comment"}),
    "php": frozenset({"comment"}),
    "ruby": frozenset({"comment"}),
    "bash": frozenset({"comment"}),
    "go": frozenset({"comment"}),
    "c": frozenset({"comment"}),
    "cpp": frozenset({"comment"}),
    "csharp": frozenset({"comment"}),
    "java": frozenset({"comment", "line_comment"}),
    "rust": frozenset({"comment", "line_comment"}),
    "lua": frozenset({"comment"}),
    "elixir": frozenset({"comment"}),
    "kotlin": frozenset({"comment"}),
    "swift": frozenset({"comment"}),
    "c_sharp": frozenset({"comment"}),
    "c_sharp_": frozenset({"comment"}),
}

# 扩展名 → tree-sitter 语言名（树语言与包命名可能不同，见 _lang_for_file）
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".php": "php",
    ".rb": "ruby",
    ".sh": "bash",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".java": "java",
    ".rs": "rust",
    ".lua": "lua",
    ".ex": "elixir",
    ".exs": "elixir",
    ".kt": "kotlin",
    ".swift": "swift",
}


def _lang_for_file(path: Path) -> str | None:
    return _EXT_TO_LANG.get(path.suffix.lower())


def _comment_bytes_for_file(path: Path, src: bytes, lang: str) -> int | None:
    """解析单个源码文件，返回注释字节数；解析失败（语法错误/不支持）返回 None。"""
    if get_parser is None:
        return None
    parser = get_parser(lang)
    tree = parser.parse(src)
    if tree.root_node.has_error:
        return None  # 语法错误文件不参与密度（确定性，不算噪声）
    comment_types = _COMMENT_NODE_TYPES.get(lang)
    if comment_types is None:
        return None
    total = 0
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in comment_types:
            total += node.end_byte - node.start_byte
        stack.extend(node.children)
    return total


def _extract_comment_density(files: list[Path], root: Path) -> SignalResult:
    if get_parser is None:  # tree-sitter 不可用：退化为 0 并标注（不炸管线）
        return SignalResult(value=0.0, score=0.0, evidence=["tree-sitter 不可用"])

    total_bytes = 0
    comment_bytes = 0
    parsed_files = 0
    unparsed: list[str] = []
    for rel in files:
        lang = _lang_for_file(rel)
        if lang is None:
            continue
        with open(root / rel, "rb") as f:
            src = f.read()
        total_bytes += len(src)
        comment = _comment_bytes_for_file(rel, src, lang)
        if comment is None:
            unparsed.append(str(rel))
            continue
        parsed_files += 1
        comment_bytes += comment

    if total_bytes == 0 or parsed_files == 0:
        ratio = 0.0
    else:
        ratio = comment_bytes / total_bytes

    if ratio >= COMMENT_RATIO_MIN_FULL:
        score = 1.0
    elif ratio >= COMMENT_RATIO_MIN_HALF:
        score = 0.5
    else:
        score = 0.0

    evidence = [f"注释/代码比 {ratio:.3f}（{parsed_files} 个可解析源码文件）"]
    if unparsed:
        evidence.append(f"未解析 {len(unparsed)} 个（语法错误，不计入）")
    return SignalResult(value=ratio, score=score, evidence=evidence)


# 提取器注册表：顺序即 static.json 信号顺序（与 SIGNALS 对齐）
_EXTRACTORS: dict[str, Callable[[list[Path], Path], SignalResult]] = {
    "navigability.agent_context_docs": _extract_agent_context_docs,
    "navigability.readme": _extract_readme,
    "navigability.comment_density": _extract_comment_density,
    "navigability.entry_clarity": _extract_entry_clarity,
    "buildability.build_def": _extract_build_def,
    "buildability.lockfile": _extract_lockfile,
    "buildability.ci": _extract_ci,
    "buildability.test_discoverability": _extract_test_discoverability,
}

# ---------------------------------------------------------------------------
# 维度聚合与 static.json
# ---------------------------------------------------------------------------


def dimension_scores(results: dict[str, SignalResult]) -> dict[str, float]:
    """维度分 = 产分信号算术均值（#7 锁定）。"""
    dims: dict[str, list[float]] = {}
    for name, res in results.items():
        dims.setdefault(name.split(".")[0], []).append(res.score)
    return {d: sum(scores) / len(scores) for d, scores in dims.items()}


def static_json(repo_path: str | Path) -> dict:
    """提取静态信号，输出 static.json 形状（信号级 + 维度均值）。

    Args:
        repo_path: 仓库根目录路径。

    Returns:
        dict: {"signals": {名称: {value, score, evidence}},
               "dimensions": {维度: {score, signal_count}}}
    """
    root = Path(repo_path)
    files = _iter_files(root)
    results: dict[str, SignalResult] = {}
    for spec in SIGNALS:
        results[spec.name] = _EXTRACTORS[spec.name](files, root)

    signals_out: dict[str, dict] = {}
    for spec in SIGNALS:
        r = results[spec.name]
        signals_out[spec.name] = {
            "value": r.value,
            "score": r.score,
            "evidence": r.evidence,
        }

    dims = dimension_scores(results)
    dimensions_out = {
        d: {
            "score": round(score, 6),
            "signal_count": sum(
                1 for s in SIGNALS if s.dimension == d
            ),
        }
        for d, score in sorted(dims.items())
    }
    return {"signals": signals_out, "dimensions": dimensions_out}
