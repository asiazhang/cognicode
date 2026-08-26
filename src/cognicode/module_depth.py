"""模块深度模块（#23，归因信号；#14 决议 + ADR-0004 落地）。

「模块深度」是可导航性静态面的**归因信号（不进产分）**：用 LLM 判定模块
deep/shallow，产出「哪些模块是 pass-through、建议合并/加深」的重构参考清单，
供用户自行判断，不参与打分（#14：跨模型一致性不达标 → 降为归因信号）。

- 单元 = **文件级模块**（语言无关，最接近 #13 的「seam=代码里真实存在的
  接口」；Python 模块=文件、PHP 类=文件、Lua 模块=文件，复用原型
  `prototype/module-depth` 的判定脚本思路）。
- 排除 test/spec/docs/vendor 等基础设施目录与隐藏路径；跳过平凡文件
  （<5 行，import-only 等，与原型 collect 一致）。
- 判定 = LLM 结构化 JSON 输出（module_id + label deep/shallow），复用原型
  judge_depth.py 的提示词与判定协议（模块 id + 源码头 N 字符）；非法输出
  重试后放弃（None，Q17 兜底，不炸管线）。
- 判定不确定性是**特性**（ADR-0004）：不强校验、不要求跨模型对齐、不要求
  重跑稳定——只产出参考清单。
- offline（llm=None）→ 模块深度关闭（enabled: false，地图 Notes 锁定
  `--offline` 时模块深度关闭）。

本模块纯函数、无 I/O（读源码文件；LLM 调用经注入的 LLMClient）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 排除目录（复用原型 judge_depth.py 的 VENDOR_DIRS/INFRA_DIRS，语言无关）
_EXCLUDE_DIRS = frozenset({
    "vendor", "node_modules", "bower_components", "thinkphp", "lib", "libs",
    "third_party", "third-party", "3rdparty", "extern", "external", "ext",
    "extend", "assets", "static", "public", "dist", "build", "target",
    "site-packages", "framework",
    # 基础设施目录
    ".git", ".github", "docs", "doc", "test", "tests", "test_suite", "spec",
    "ci", ".ci", "tools", "scripts", "demo", "examples", "mock", "mocks",
    "fixtures", "__tests__",
})

# 参与判定的源码扩展名（语言无关；与 symbols/static_signals 口径一致）
_SOURCE_SUFFIXES = frozenset({
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".php", ".phtml",
    ".rb", ".go", ".rs", ".java", ".c", ".h", ".cc", ".cpp", ".cs", ".lua",
    ".ex", ".exs", ".kt", ".swift", ".sh",
})

# 平凡文件行数阈值（< 5 行：import-only / 空 init 等，不算模块；原型 collect）
_TRIVIAL_LINES = 5

# 单模块源码字符预算（LLM 提示词；原型 judge_depth 16K）
_CHAR_BUDGET = 16000

# LLM 重试次数（非法输出重试后放弃）
_RETRIES = 2

# 判定结果 label 归一化映射
_LABELS = frozenset({"deep", "shallow"})

_DEEP_PROMPT = """你是代码结构分析器。请判定下面这个代码模块是 DEEP 还是 SHALLOW。

定义（John Ousterhout《A Philosophy of Software Design》）：
- DEEP 模块：小而简单的接口隐藏大量行为/实现——调用者学一点、得到很多。
- SHALLOW 模块：接口很大但背后行为很少——大量 pass-through、getter/setter、
  薄包装、或每个琐碎步骤一个方法。调用者要理解很多才能得到一点。

以模块整体判定（不是单文件）。聚焦接口 vs 其隐藏的行为。语言无关。

只输出一个 JSON 对象，不要其他文字：
{{"module_id": "{module_id}", "label": "deep"}}
或
{{"module_id": "{module_id}", "label": "shallow"}}

模块 id：{module_id}

源码：
{code}"""


def _read_files(paths: list[str], char_budget: int = _CHAR_BUDGET) -> str:
    """拼接文件内容（带文件名头），截断到字符预算（整文件截断，不切半行）。

    与原型 judge_depth.py 的 read_files 一致：按文件名排序，超出预算的
    后续文件整文件舍弃。
    """
    out: list[str] = []
    used = 0
    for p in sorted(paths):
        try:
            c = Path(p).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        chunk = f"\n===== {Path(p).name} =====\n{c}\n"
        if used + len(chunk) > char_budget and out:
            break
        out.append(chunk)
        used += len(chunk)
    return "".join(out)


def collect_modules(repo: str | Path) -> dict[str, list[str]]:
    """收集仓库的文件级模块（语言无关，确定性，无 LLM）。

    排除：test/spec/docs/vendor 等基础设施目录、隐藏路径（点开头）、
    非源码扩展名文件、平凡文件（<5 行）。

    Args:
        repo: 仓库根目录。

    Returns:
        {相对路径: [绝对文件路径...]}（每个文件级模块单文件；排序稳定）。
    """
    root = Path(repo)
    mods: dict[str, list[str]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part.startswith(".") for part in parts):
            continue
        if any(part in _EXCLUDE_DIRS for part in parts[:-1]):
            continue
        if rel.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        try:
            if sum(1 for _ in p.open(encoding="utf-8", errors="ignore")) < _TRIVIAL_LINES:
                continue
        except OSError:
            continue
        mods[rel.as_posix()] = [str(p)]
    return mods


def judge_module_depth(
    module_id: str,
    file_paths: list[str],
    *,
    llm,
    retries: int = _RETRIES,
    char_budget: int = _CHAR_BUDGET,
) -> str | None:
    """LLM 判定一个模块 deep/shallow（复用原型 judge_depth.py 协议）。

    Args:
        module_id: 模块标识（相对仓库根路径）。
        file_paths: 该模块的文件路径清单（文件级 = 单文件）。
        llm: LLMClient（complete(prompt, model=None) -> str | None）。
        retries: 非法输出重试次数。
        char_budget: 源码字符预算。

    Returns:
        "deep" | "shallow"；LLM 不可用 / 重试后仍非法 → None（放弃）。
    """
    if llm is None:
        return None
    code = _read_files(file_paths, char_budget)
    prompt = _DEEP_PROMPT.format(module_id=module_id, code=code)
    for _ in range(retries + 1):
        try:
            text = llm.complete(prompt, model=None)
        except Exception:
            text = None
        label = _parse_label(text)
        if label is not None:
            return label
    return None


def _parse_label(text: str | None) -> str | None:
    """解析 LLM 输出 → deep/shallow；非法 → None。

    容忍 ```json 包裹；要求 JSON 含 label 字段且为 deep/shallow。
    """
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if m:
            text = m.group(1).strip()
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    label = obj.get("label")
    if not isinstance(label, str):
        return None
    norm = label.strip().lower()
    return norm if norm in _LABELS else None


def run_module_depth(
    repo: str | Path,
    *,
    llm=None,
    max_modules: int | None = None,
) -> dict:
    """全仓模块深度判定 → deep/shallow 分布 + 重构建议清单。

    Args:
        repo: 仓库根目录。
        llm: LLMClient | None。None（--offline）→ 关闭（enabled: false）。
        max_modules: 最多判定的模块数（None = 全部；冒烟/演示可限量）。

    Returns:
        {
          "enabled": bool,       # llm=None → False（--offline 关闭）
          "modules": [{module, label|None, files}],   # 判定失败 label=None
          "distribution": {"deep": n, "shallow": n, "unjudged": n},
          "suggestions": [shallow 模块的重构建议文本...],  # 参考性，不进产分
        }
    """
    if llm is None:
        return {
            "enabled": False,
            "modules": [],
            "distribution": {"deep": 0, "shallow": 0, "unjudged": 0},
            "suggestions": [],
        }

    mods = collect_modules(repo)
    module_ids = sorted(mods.keys())
    if max_modules is not None:
        module_ids = module_ids[:max_modules]

    judged: list[dict] = []
    dist = {"deep": 0, "shallow": 0, "unjudged": 0}
    for mid in module_ids:
        label = judge_module_depth(mid, mods[mid], llm=llm)
        judged.append({
            "module": mid,
            "label": label,
            "files": mods[mid],
        })
        if label is None:
            dist["unjudged"] += 1
        else:
            dist[label] += 1

    # 重构建议清单：shallow 模块 = 建议合并/加深（参考性，用户自行判断）
    suggestions = []
    for m in judged:
        if m["label"] == "shallow":
            suggestions.append(
                f"模块 {m['module']} 判定为 shallow（pass-through/薄包装）："
                "建议合并小模块或加深接口隐藏行为，降低 agent 导航与维护成本"
            )

    return {
        "enabled": True,
        "modules": judged,
        "distribution": dist,
        "suggestions": suggestions,
    }
