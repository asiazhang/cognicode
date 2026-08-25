"""任务模板合成 + 执行式验证过滤（#20 第二、三段）。

三段式生成管线（#5 锁定）：
1. **结构解析**（`symbols.py`）：tree-sitter 抽取符号；
2. **LLM 模板合成**（本模块）：符号 → 任务描述（检索不带名 / 定位给症状 /
   修改给描述），走 `llm` 接口（配置独立固定，#5）；offline（llm=None）
   或 LLM 失败时确定性模板兜底（Q17：--offline 时管线降级而非终止）；
3. **执行式验证过滤**（`verify.py`）：生成的任务须过 harness 客观判定
   （位置匹配/测试红绿/退出码，ADR-0002），过不了的实例当场砍掉。

任务量/配比/采样 k 按 #6 锁定：探测 2 + 检索 8 + 定位 8 + 修改 12；
修改 k=5 / 检索定位 k=3 / 探测 k=3（本模块只管合成任务，探测归 probe.py）。

三类任务（CONTEXT.md「合成任务」）：
- 检索（语义→位置）：验收 = 符号级匹配 ground truth（file::name，非行号）；
- 定位（症状→根因）：验收 = 对照注入点（bug 注入位置）；
- 修改（描述→改动）：bug 注入 + F2P/P2P 双闸验收。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cognicode.symbols import Symbol

# ---------------------------------------------------------------------------
# 生成配置（独立固定，#5/#6 锁定；改动需回 #5/#6）
# ---------------------------------------------------------------------------

# 默认任务量（#6：初版锚点）
DEFAULT_COUNTS: dict[str, int] = {
    "search": 8,
    "locate": 8,
    "modify": 12,
}


@dataclass(frozen=True)
class GenerationConfig:
    """生成配置：任务量 + 采样 k，独立固定（版本进可复现性元数据）。"""

    search_count: int = DEFAULT_COUNTS["search"]
    locate_count: int = DEFAULT_COUNTS["locate"]
    modify_count: int = DEFAULT_COUNTS["modify"]
    # 采样次数 k（#6 锁定：修改 5 / 检索定位 3；探测 k=3 归 probe 层）
    k_search: int = 3
    k_locate: int = 3
    k_modify: int = 5
    # LLM 合成模型（独立固定；实际模型串由 llm 层解析，这里是默认 pin）
    llm_model: str = "tencent-copilot/deepseek-v4-flash-ioa"


# ---------------------------------------------------------------------------
# 任务数据结构（判卷消费：ground_truth / injection / acceptance）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchTask:
    """检索类任务：语义 → 位置。验收 = 符号级匹配 ground truth。"""

    id: str
    symbol: Symbol
    prompt: str  # 自然语言描述（不带符号名）
    k: int = 3

    @property
    def kind(self) -> str:
        return "search"

    @property
    def ground_truth(self) -> str:
        return f"{self.symbol.file}::{self.symbol.name}"

    @property
    def target_file(self) -> str:
        return self.symbol.file

    @property
    def target_name(self) -> str:
        return self.symbol.name


@dataclass(frozen=True)
class LocateTask:
    """定位类任务：症状 → 根因。验收 = 对照注入点。"""

    id: str
    symbol: Symbol
    injection: dict  # {"file", "line", "patch"}: 注入 bug 的落点与改动
    prompt: str  # 失败症状描述（注入后测试失败输出，非语义描述）
    k: int = 3

    @property
    def kind(self) -> str:
        return "locate"

    @property
    def ground_truth(self) -> str:
        return f"{self.symbol.file}::{self.symbol.name}"


@dataclass(frozen=True)
class ModifyTask:
    """修改/修复类任务：描述 → 改动。验收 = F2P/P2P 双闸。"""

    id: str
    symbol: Symbol
    bug: dict  # {"file", "line", "patch"}: 注入 bug
    prompt: str  # 任务描述
    acceptance_files: list[str] = field(default_factory=list)  # F2P 验收测试（cognicode_ 前缀）
    guard_files: list[str] = field(default_factory=list)  # P2P 守护测试（改动前已绿基线）
    k: int = 5

    @property
    def kind(self) -> str:
        return "modify"

    @property
    def ground_truth(self) -> str:
        return f"{self.symbol.file}::{self.symbol.name}"


# ---------------------------------------------------------------------------
# LLM 接口（配置独立固定；offline/失败走确定性模板）
# ---------------------------------------------------------------------------


def _search_prompt_deterministic(sym: Symbol) -> str:
    """检索类确定性兜底模板：语义→位置，不给符号名（#5 防泄题）。"""
    return (
        f"在仓库中定位与以下功能描述相关的代码位置："
        f"位于 {sym.file} 中、负责业务核心逻辑的代码单元（{sym.kind}）。"
        f"请输出其文件路径与符号名称。"
    )


def _locate_prompt_deterministic(sym: Symbol) -> str:
    """定位类确定性兜底模板：症状→根因，不给符号名（#5 防泄题）。"""
    return (
        f"仓库中位于 {sym.file} 的某个代码单元（{sym.kind}）行为异常，"
        f"产生了错误的输出。请定位导致该错误的根因位置，并说明问题所在。"
    )


def _modify_prompt_deterministic(sym: Symbol) -> str:
    """修改类确定性兜底模板：描述→改动。"""
    return (
        f"仓库中位于 {sym.file} 的某个代码单元（{sym.kind}）存在逻辑缺陷，"
        f"产生错误的计算结果。请修复该缺陷，使其行为符合预期，"
        f"且不破坏仓库既有功能。"
    )


# 确定性模板注册表（offline / LLM 失败兜底）
_DETERMINISTIC_PROMPTS = {
    "search": _search_prompt_deterministic,
    "locate": _locate_prompt_deterministic,
    "modify": _modify_prompt_deterministic,
}


# ---------------------------------------------------------------------------
# 注入补丁（bug 注入，SWE-smith 式：tree-sitter 层可泛化）
# ---------------------------------------------------------------------------


def _inject_patch(line: str, mutated: str) -> str:
    """把一行代码替换为缺陷版本，生成统一 diff 风格补丁（相对文件）。

    diff 行 = `-`/`+` + 原行内容（含全部缩进），无多余前导空格
    （与 verify._PATCH_HUNK 的解析约定一致）。
    """
    return f"-{line}\n+{mutated}"


# 各类语言「一行表达式变常量」的注入形态（确定性，语言无关）
# key = 语言；value = 替换规则（把函数/方法体第一个 return 表达式改为常量）
# 本版实现最小通用注入：把行内表达式整体替换为常量 0 / null / ""（按语言）。
_MUTATION_CONSTANTS = {
    "python": "0",
    "javascript": "0",
    "typescript": "0",
    "php": "0",
    "go": "0",
    "rust": "0",
    "java": "0",
    "c": "0",
    "cpp": "0",
    "csharp": "0",
    "ruby": "0",
    "lua": "0",
    "bash": "0",
}


def _mutate_line(line: str, lang: str) -> str | None:
    """把一行代码突变为缺陷版（确定性）；不适用返回 None。"""
    stripped = line.strip()
    # 找 return/表达式语句
    if stripped.startswith("return "):
        body = stripped[len("return "):].rstrip()
        if body and "=" not in body and not body.endswith(("{", "}")):
            const = _MUTATION_CONSTANTS.get(lang, "0")
            indent = line[: len(line) - len(line.lstrip())]
            return f"{indent}return {const}\n"
    return None


# ---------------------------------------------------------------------------
# 合成
# ---------------------------------------------------------------------------


def _build_search_task(idx: int, sym: Symbol, prompt: str, cfg: GenerationConfig) -> SearchTask:
    return SearchTask(id=f"search-{idx}", symbol=sym, prompt=prompt, k=cfg.k_search)


def _build_locate_task(idx: int, sym: Symbol, patch: str, prompt: str, cfg: GenerationConfig) -> LocateTask:
    return LocateTask(
        id=f"locate-{idx}",
        symbol=sym,
        injection={"file": sym.file, "line": sym.line, "patch": patch},
        prompt=prompt,
        k=cfg.k_locate,
    )


def _build_modify_task(idx: int, sym: Symbol, patch: str, prompt: str, cfg: GenerationConfig) -> ModifyTask:
    return ModifyTask(
        id=f"modify-{idx}",
        symbol=sym,
        bug={"file": sym.file, "line": sym.line, "patch": patch},
        prompt=prompt,
        acceptance_files=[],  # 由验证过滤阶段注入验收测试文件（verify.py）
        guard_files=[],
        k=cfg.k_modify,
    )


def _llm_prompt(prompt: str, model: str, llm) -> str | None:
    """调 LLM 生成描述；失败返回 None（调用方兜底）。"""
    try:
        result = llm.complete(prompt, model=model)
        if isinstance(result, str) and result.strip():
            return result.strip()
    except Exception:
        pass
    return None


def generate_tasks(
    symbols: list[Symbol],
    *,
    llm=None,
    kinds: tuple[str, ...] = ("search", "locate", "modify"),
    config: GenerationConfig | None = None,
) -> list:
    """合成三类任务（第二段）。

    Args:
        symbols: tree-sitter 符号清单（第一段产出）。
        llm: 可选；提供则用 LLM 生成描述（走 llm 接口，模型由 config pin），
            None（offline）或调用失败时用确定性模板兜底。
        kinds: 要合成的任务类别子集。
        config: 生成配置（默认值按 #6 锁定）。

    Returns:
        按类别顺序（search → locate → modify）的任务清单；
        符号不足时不硬凑（按实际数量）。注入补丁只对能确定性突变
        的行生成；不适用则跳过该符号。
    """
    cfg = config or GenerationConfig()
    counts = {
        "search": cfg.search_count,
        "locate": cfg.locate_count,
        "modify": cfg.modify_count,
    }
    tasks: list = []
    idx = {"search": 0, "locate": 0, "modify": 0}

    for kind in kinds:
        limit = counts.get(kind, 0)
        for sym in symbols:
            if idx[kind] >= limit:
                break
            lang = Path(sym.file).suffix.lstrip(".").lower()
            if kind == "search":
                if llm is not None:
                    base = _search_prompt_deterministic(sym)
                    prompt = _llm_prompt(base, cfg.llm_model, llm) or base
                else:
                    prompt = _search_prompt_deterministic(sym)
                tasks.append(_build_search_task(idx[kind] + 1, sym, prompt, cfg))
                idx[kind] += 1
            elif kind == "locate":
                mutated = _mutate_line_for_symbol(sym, lang)
                if mutated is None:
                    continue  # 无法确定性突变 → 跳过（不硬凑）
                if llm is not None:
                    base = _locate_prompt_deterministic(sym)
                    prompt = _llm_prompt(base, cfg.llm_model, llm) or base
                else:
                    prompt = _locate_prompt_deterministic(sym)
                tasks.append(_build_locate_task(idx[kind] + 1, sym, mutated, prompt, cfg))
                idx[kind] += 1
            elif kind == "modify":
                mutated = _mutate_line_for_symbol(sym, lang)
                if mutated is None:
                    continue
                if llm is not None:
                    base = _modify_prompt_deterministic(sym)
                    prompt = _llm_prompt(base, cfg.llm_model, llm) or base
                else:
                    prompt = _modify_prompt_deterministic(sym)
                tasks.append(_build_modify_task(idx[kind] + 1, sym, mutated, prompt, cfg))
                idx[kind] += 1
    return tasks


def _mutate_line_for_symbol(sym: Symbol, lang: str) -> str | None:
    """为符号生成注入补丁：读取源码，在符号体内找第一个 return 表达式行做突变。

    搜索范围：从符号起始行向下，到下一个同缩进/更浅缩进的结构行（函数/类/顶层
    代码）或文件尾。当前实现：只对「return <表达式>」形态的行做替换为常量。
    读不到/不适用返回 None（生成时跳过该符号）。
    """
    root = Path(sym.root) if sym.root else Path.cwd()
    try:
        src_path = root / sym.file
        lines = src_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    sym_indent = _line_indent(lines[sym.line - 1]) if sym.line - 1 < len(lines) else 0
    for i in range(sym.line - 1, len(lines)):
        line = lines[i]
        indent = _line_indent(line)
        # 越出符号体：遇到更浅缩进的非空行（下一个顶层结构）即停
        if indent < sym_indent and line.strip():
            break
        mutated = _mutate_line(line, lang)
        if mutated is not None:
            return _inject_patch(line, mutated)
    return None


def _line_indent(line: str) -> int:
    """行前导空白字符数（制表符按 4 计，粗略）。"""
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4
        else:
            break
    return n
