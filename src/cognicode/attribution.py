"""归因管线（#23，三档「确定性优先、LLM 兜底」；#15 决议落地）。

失败样本（fail_incorrect / fail_budget）→ 改进建议的映射：

1. **失败样本 → (维度 × 失败模式) 聚合**（#15 §1/§5/§6）：
   - 检索 → 可导航性；定位 → 可诊断性；探测 → 环境可用性。
   - 修改按判卷拆分：F2P 未过 = 可解性；F2P 过但 P2P 未过 = 变更安全性
     （需要判卷层 runs 明细带 f2p/p2p 标记；无明细时 fail_incorrect 归可解性）。
   - fail_budget 归可解性（#15 §1：超时是「解不出」的真实信号）。
   - fail_env 剔除（#6），不产生归因候选。
   - m≥1 即产生候选（#15 §3：不设硬阈值），聚合单元 = (维度 × 失败模式)，
     同任务多次采样 / 不同任务同根因 → 合并计数（同根因去重，#15 §6）。

2. **确定性档（模板优先）**（#15 §2/§7）：
   - 产分信号命中（该维度有静态信号且低分）→ 模板建议，锚定该信号，
     失败样本作为「预期方向的实证佐证」并入（不单独出条）。
   - 专属归因信号命中（变更安全性 = 测试覆盖缺口；效率 = 单文件规模）
     → 模板建议，锚定归因信号。
   - 无静态信号的维度（可解性/可诊断性）→ 无确定性建议，留给 LLM 档。
   - 效率无失败样本：独立低分驱动路径（#15 §8），单文件规模命中即模板。

3. **LLM 兜底档**（#15 §5/§8；#8 约束）：
   - 触发粒度 = (维度 × 失败模式) 聚合一次归因，不逐样本。
   - 输入 = 结构化证据包：判卷输出（失败测试名/退出码/错误摘要、F2P/P2P 红绿）
     + 轨迹**确定性切片**（工具调用名与目标文件、失败前末 N 步、轮次/token）
     + 该维度静态信号快照。**不含合成任务原文与注入点细节**。
   - 输出 = 结构化 JSON（dimension/text/direction）；非法结构整条丢弃
     （#8 约束 c），LLM 失败返回 None 跳过（Q17 兜底，不炸管线）。
   - 锚定维度必须合法（六维之一，harness 校验，#8 约束 a）。

4. **排序**（#8 §8）：确定性键为主（维度分最低优先 → 信号档位最低优先
   → 影响面失败数多优先），LLM 建议在同档内按 llm_rank 重排。

本模块纯函数、无 I/O（轨迹切片读文本；LLM 调用经注入的 LLMClient）。
"""

from __future__ import annotations

import json
import re

from cognicode.static_signals import SIGNAL_NAMES

# 六维度失败模式语言（分类轴，原 score.py 常量随评分形态废弃，语言内联回归）
DIMENSIONS = (
    "solvability",
    "safety",
    "efficiency",
    "navigability",
    "buildability",
    "diagnosability",
)
DIMENSION_LABELS_ZH = {
    "solvability": "可解性",
    "safety": "变更安全性",
    "efficiency": "效率",
    "navigability": "可导航性",
    "buildability": "环境可用性",
    "diagnosability": "可诊断性",
}


def is_counted(category: str) -> bool:
    """该任务类别是否计入统计（前三类计，fail_env 剔除；原 verdict.py 内联）。"""
    return category in {"success", "fail_incorrect", "fail_budget"}

# 任务类别 → 维度（#15 §1：任务类型即维度）
_KIND_TO_DIM = {
    "search": "navigability",
    "locate": "diagnosability",
    "modify": "solvability",
}

# 任务类别 → 中文（失败任务引用）
_KIND_LABELS_ZH = {
    "search": "检索",
    "locate": "定位",
    "modify": "修改",
    "probe": "探测",
}

# 失败模式中文（失败任务引用）
_MODE_LABELS_ZH = {
    "incorrect": "解出失败",
    "budget": "超时",
}

# 有静态产分信号的维度（#18：可导航性 + 环境可用性）→ 静态信号缺失/低档
# 时出确定性模板（#15 §2 档 1）。
_STATIC_DIMS = frozenset({"navigability", "buildability"})

# 专属归因信号（#7：变更安全性 = 测试覆盖缺口；效率 = 单文件规模）
# 锚定名 = <dimension>.<signal>，命中即模板（#15 §2 档 2）。
_ATTRIBUTION_SIGNAL_NAMES = ("test_gap", "big_file")
_ATTRIBUTION_DIM_OF = {
    "test_gap": "safety",
    "big_file": "efficiency",
}

# 确定性排序键的维度分「未测/无分」占位（排最后）
_UNMEASURED_DIM_KEY = 1.0

# LLM 证据包：轨迹切片的末 N 步（#15 §5）
_TRACE_LAST_STEPS = 5

# LLM 输出结构化 JSON 字段（#8 §6：LLM 输出结构化 JSON，非法结构整条丢弃）
_LLM_JSON_FIELDS = ("dimension", "text", "direction")

# 维度分数点值注入（确定性排序键主键；未注入 → 全按未测处理）
# 由 run_attribution 从 aggregate 传入。


class FailureEvidence(dict):
    """一个失败样本条目（(维度 × 失败模式) 聚合单元的最小单位）。

    用 dict 而非 dataclass：全管线 JSON 可序列化，且测试/报告直接按键访问。
    """


# ---------------------------------------------------------------------------
# 失败样本 → (维度 × 失败模式) 聚合（#15 §1/§5/§6）
# ---------------------------------------------------------------------------


def _split_modify_runs(task: dict, outcomes: list[str]) -> dict[str, list[str]]:
    """修改类任务：按 runs 明细（f2p/p2p 标记）拆分失败样本到可解性/变更安全性。

    #15 §1：F2P 未过 = 可解性；F2P 过但 P2P 未过 = 变更安全性。
    有 runs 明细时，fail_incorrect 逐条按 f2p/p2p 归类；fail_budget 恒归可解性。
    无 runs 明细（判卷层未标注）→ fail_incorrect 归可解性（保守默认）。

    Returns:
        {"solvability": [失败模式...], "safety": [失败模式...]}
    """
    result: dict[str, list[str]] = {"solvability": [], "safety": []}
    runs = task.get("runs")
    for cat in outcomes:
        if cat == "fail_budget":
            result["solvability"].append("budget")
            continue
        if cat != "fail_incorrect":
            continue
        mode = "incorrect"
        if runs:
            # 取与本次失败对应的 runs 条目（按顺序对齐；无则默认可解性）
            run = runs[len(result["solvability"]) + len(result["safety"])] \
                if len(runs) > len(result["solvability"]) + len(result["safety"]) else {}
            f2p = run.get("f2p") or [True, True]
            p2p = run.get("p2p") or [True, True]
            if f2p[0] and f2p[1] and p2p[0] and not p2p[1]:
                result["safety"].append(mode)
                continue
        result["solvability"].append(mode)
    return result


def failure_sources(verdicts: dict) -> dict:
    """判卷数据 → (维度 × 失败模式) 聚合的失败样本清单。

    Args:
        verdicts: verdicts.json 形状 {tasks: [{task_id, kind, k, outcomes,
            runs?}]}。

    Returns:
        {
          "groups": {
            维度: {
              "incorrect": [FailureEvidence...],
              "budget": [FailureEvidence...],
            }
          },
          "kind_totals": {kind: 任务数},   # 失败任务引用 <m>/<k> 的分母
        }
        无失败样本 → groups 为空 dict。
    """
    groups: dict[str, dict[str, list]] = {}
    kind_totals: dict[str, int] = {}
    for task in verdicts.get("tasks", []):
        kind = task.get("kind")
        k_total = task.get("k", 1)
        kind_totals[kind] = kind_totals.get(kind, 0) + 1
        outcomes = [c for c in task.get("outcomes", []) if is_counted(c)]
        if kind == "modify":
            split = _split_modify_runs(task, outcomes)
            for dim, modes in split.items():
                _accumulate(groups, dim, modes, task, k_total)
        else:
            dim = _KIND_TO_DIM.get(kind)
            if dim is None:
                continue  # 未知任务类别不进归因
            modes = [
                "budget" if c == "fail_budget" else "incorrect"
                for c in outcomes if c != "success"
            ]
            _accumulate(groups, dim, modes, task, k_total)

    return {"groups": groups, "kind_totals": kind_totals}


def _accumulate(
    groups: dict,
    dim: str,
    modes: list[str],
    task: dict,
    k_total: int,
) -> None:
    """把一条任务的多轮失败按模式累进 (维度 × 失败模式) 聚合单元。

    同任务同模式多次失败 → 合并为一条（m = 失败次数，同根因去重，#15 §6）。
    """
    for mode in modes:
        bucket = groups.setdefault(dim, {}).setdefault(mode, [])
        # 同根因合并：同任务同模式只加计数（失败任务引用 <m>/<k> 合并计数）
        for ev in bucket:
            if ev["task_id"] == task.get("task_id"):
                ev["m"] = ev["m"] + 1
                break
        else:
            bucket.append(FailureEvidence(
                task_id=task.get("task_id", "?"),
                kind=task.get("kind", "?"),
                m=1,
                k=k_total,
                mode=mode,
                detail=_run_detail(task, mode),
            ))


def _run_detail(task: dict, mode: str) -> str:
    """判卷输出摘要（LLM 证据包用，不含任务原文）。

    从 runs 明细（f2p/p2p/测试名）或任务字段（kind/注入点行）提取
    确定性事实；无则空串。
    """
    parts: list[str] = []
    runs = task.get("runs")
    if runs:
        parts.append(f"runs={len(runs)}")
    if mode == "budget":
        parts.append("超时/轮次上限")
    return "；".join(parts)


# ---------------------------------------------------------------------------
# 失败任务引用（#12/#15：`<类别> <m>/<k>（失败模式）`）
# ---------------------------------------------------------------------------


def build_failure_ref(f: dict, dim: str) -> str | None:
    """该维度的失败任务引用（合并计数，跨任务同根因合并）。

    #15 §6：同根因合并 → 失败任务引用合并计数（如「检索 4/8、定位 2/8 失败」）。
    此处按维度聚合：`<类别> <m>/<k>（失败模式）`，多个任务按类别分组。

    Returns:
        引用文本；无失败 → None。
    """
    groups = f.get("groups", {}).get(dim, {})
    if not groups:
        return None
    kind_totals = f.get("kind_totals", {})
    parts: list[str] = []
    for kind in ("search", "locate", "modify", "probe"):
        evs = []
        for mode in ("incorrect", "budget"):
            evs.extend(groups.get(mode, []))
        evs = [e for e in evs if e["kind"] == kind]
        if not evs:
            continue
        # m = 失败任务数（同根因合并：#15 §6「检索 4/8」；任务至少一次失败即计），
        # k = 该类别任务总数。失败模式并报（#12「含 1 超时」）。
        m_total = len({e["task_id"] for e in evs})
        k_total = kind_totals.get(kind, 0)
        modes = sorted({_MODE_LABELS_ZH[e["mode"]] for e in evs})
        label = _KIND_LABELS_ZH.get(kind, kind)
        parts.append(f"{label} {m_total}/{k_total} 失败（{'；'.join(modes)}）")
    if not parts:
        return None
    return "，".join(parts)


# ---------------------------------------------------------------------------
# 轨迹确定性切片（#15 §5：LLM 证据包输入，不含任务原文）
# ---------------------------------------------------------------------------


def slice_trace(trace: str | None) -> dict:
    """轨迹 JSONL → 确定性切片（供 LLM 证据包）。

    #15 §5：只提取确定性事实——工具调用类型与目标文件、失败前末 N 步、
    轮次计数。**不含消息内容**（任务原文不进证据包）。

    Returns:
        {"turns": n, "tool_calls": [{tool, file?}...], "last_steps": [...末 5 步]}
    """
    turns = 0
    tool_calls: list[dict] = []
    if trace:
        for line in trace.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if not isinstance(ev, dict):
                continue
            etype = ev.get("type")
            if etype == "turn_start":
                turns += 1
            elif etype == "tool_execution_start":
                tool_name = ev.get("toolName") or ""
                inp = ev.get("input") or {}
                entry: dict = {"tool": tool_name}
                # 目标文件：只取输入里的确定性文件字段（read/write/edit 等）
                fpath = inp.get("file_path") or inp.get("filePath") or inp.get("path")
                if isinstance(fpath, str) and fpath.strip():
                    entry["file"] = fpath.strip()
                tool_calls.append(entry)

    return {
        "turns": turns,
        "tool_calls": tool_calls,
        "last_steps": tool_calls[-_TRACE_LAST_STEPS:],
    }


# ---------------------------------------------------------------------------
# 确定性档：模板建议
# ---------------------------------------------------------------------------


# 产分信号模板（与 report._SIGNAL_SUGGESTIONS 同源；#7 #6/#15 档 1）。
# 锚定该信号；文本 + 预期方向。
_SIGNAL_SUGGESTIONS: dict[str, tuple[str, str]] = {
    "navigability.agent_context_docs": (
        "补充代理上下文文档（agent context document，如 AGENTS.md / CONTEXT.md），"
        "让编程 agent 无需通读代码即可定位关键模块",
        "up",
    ),
    "navigability.readme": (
        "在仓库根添加 README 入口文档，说明项目用途与结构",
        "up",
    ),
    "navigability.comment_density": (
        "提升注释/docstring 密度（当前低于 5% 阈值），降低 agent 理解代码的成本",
        "up",
    ),
    "navigability.entry_clarity": (
        "补充/明确代码入口（如 main.py / cli.py / src/ 约定），让 agent 找到启动路径",
        "up",
    ),
    "buildability.build_def": (
        "补充构建定义文件（如 pyproject.toml / package.json / Makefile），"
        "让 agent 从冷启动跑起构建",
        "up",
    ),
    "buildability.lockfile": (
        "引入并提交依赖锁文件（lockfile），保证可复现安装",
        "up",
    ),
    "buildability.ci": (
        "配置 CI（如 .github/workflows），让验证回路自动化",
        "up",
    ),
    "buildability.test_discoverability": (
        "补充测试目录与测试文件（tests/ 等），让 agent 发现并运行验证回路",
        "up",
    ),
}

# 专属归因信号模板（#7：#15 档 2）
_ATTRIBUTION_SUGGESTIONS: dict[str, tuple[str, str]] = {
    "safety.test_gap": (
        "补充测试覆盖（测试覆盖缺口信号命中）：为变更安全性提供回归守护，"
        "减少「解出但炸了别处」",
        "up",
    ),
    "efficiency.big_file": (
        "拆分超大文件（单文件规模信号命中）：降低 agent 理解与修改单个文件的成本，"
        "减少 token 高耗",
        "up",
    ),
}

# 可重测声明模板（锚定信号/维度两类，#8 #7）
_REMEASURE_SIGNAL = (
    "重跑同一套任务与静态提取（static extraction），"
    "用维度分区间判定是否向预期方向移动"
)
_REMEASURE_DIM = (
    "重跑对应任务类，用维度分区间判定方向移动"
)


def _low_score(name: str, static_signals: dict) -> float | None:
    """静态信号 score（低分触发模板）；缺信号（未提取）返回 None。"""
    sig = (static_signals or {}).get(name)
    if sig is None:
        return None
    return float(sig.get("score", 1.0))


def build_deterministic_suggestions(
    f: dict,
    static_signals: dict | None,
    attribution_signals: dict | None,
    *,
    dim_points: dict[str, float | None] | None = None,
    efficiency: dict | None = None,
) -> list[dict]:
    """确定性档模板建议（#15 §2/§7/§8）。

    Args:
        f: failure_sources 输出。
        static_signals: static.json 的 signals（产分信号）。
        attribution_signals: 专属归因信号 {test_gap, big_file}（#18 附录
            未产出时可为 None——只走产分信号档）。
        dim_points: 维度点值 {dim: float|None}（排序键主键；缺 → 未测）。
        efficiency: 效率分 {point, raw_percentile}（#15 §8 独立低分驱动；
            缺 → 不触发单文件规模模板）。

    Returns:
        模板建议清单（含 failure_ref 实证佐证并入、priority 排序键）。
    """
    groups = f.get("groups", {})
    suggestions: list[dict] = []

    # 档 1：产分信号缺失/低档 → 模板（锚定信号）
    for name, (text, direction) in _SIGNAL_SUGGESTIONS.items():
        score = _low_score(name, static_signals)
        if score is None or score >= 1.0:
            continue
        dim = name.split(".")[0]
        ref = build_failure_ref(f, dim)
        suggestions.append({
            "anchor": name,
            "anchor_kind": "signal",
            "text": text,
            "direction": direction,
            "remeasurable": _REMEASURE_SIGNAL,
            "failure_ref": ref or "",
            "evidence": f"信号 {name} 当前 {score:.1f}" + (f"；{ref}" if ref else ""),
            "source": "template",
            "priority": _priority_key(dim_points, dim, score, f, dim),
        })

    # 档 2：专属归因信号命中 → 模板（锚定归因信号）
    for sig_name in _ATTRIBUTION_SIGNAL_NAMES:
        dim = _ATTRIBUTION_DIM_OF[sig_name]
        sig = (attribution_signals or {}).get(sig_name)
        if sig is None:
            continue
        score = float(sig.get("score", 1.0))
        if score >= 1.0:
            continue
        anchor = f"{dim}.{sig_name}"
        # 效率走独立路径（#15 §8）：低分才触发，与失败无关
        if dim == "efficiency":
            eff_point = (efficiency or {}).get("point")
            if eff_point is None or eff_point >= 0.5:
                continue
        text, direction = _ATTRIBUTION_SUGGESTIONS[anchor]
        ref = build_failure_ref(f, dim)
        suggestions.append({
            "anchor": anchor,
            "anchor_kind": "signal",
            "text": text,
            "direction": direction,
            "remeasurable": _REMEASURE_SIGNAL,
            "failure_ref": ref or "",
            "evidence": f"归因信号 {sig_name} 当前 {score:.1f}"
                       + (f"；{ref}" if ref else ""),
            "source": "template",
            "priority": _priority_key(dim_points, dim, score, f, dim),
        })

    suggestions.sort(key=lambda s: s["priority"])
    return suggestions


def _priority_key(
    dim_points: dict[str, float | None] | None,
    dim: str,
    signal_score: float,
    f: dict,
    dim_key: str,
) -> tuple:
    """确定性排序键（#8 §8）：维度分最低优先 → 信号档位最低优先 → 影响面。

    影响面 = 该维度失败样本数（根因共享度；#8 §8 第三键，多失败优先）。
    """
    point = (dim_points or {}).get(dim)
    dim_k = _UNMEASURED_DIM_KEY if point is None else round(float(point), 6)
    sig_k = round(signal_score, 6)
    impact = -sum(
        e["m"] for e in f.get("groups", {}).get(dim_key, {}).get("incorrect", [])
    ) - sum(
        e["m"] for e in f.get("groups", {}).get(dim_key, {}).get("budget", [])
    )
    return (dim_k, sig_k, impact)


# ---------------------------------------------------------------------------
# LLM 兜底档（结构化 JSON，非法丢弃）
# ---------------------------------------------------------------------------


def _evidence_pack(
    f: dict,
    dim: str,
    static_signals: dict | None,
    attribution_signals: dict | None,
    traces: dict | None,
) -> dict:
    """该维度 (维度 × 失败模式) 的结构化证据包（#15 §5）。

    三块：①判卷输出（失败任务/次数/F2P-P2P 红绿、退出码摘要）；
    ②轨迹确定性切片（工具调用与目标文件、末 N 步、轮次）——不含任务原文；
    ③该维度静态信号快照（供锚定与排除「信号已合格」）。

    不含合成任务原文与注入点细节（#15 §5）。
    """
    groups = f.get("groups", {}).get(dim, {})
    pack: dict = {
        "dimension": dim,
        "label": DIMENSION_LABELS_ZH.get(dim, dim),
        "failures": [],
        "traces": [],
        "static": {},
    }
    for mode in ("incorrect", "budget"):
        for ev in groups.get(mode, []):
            pack["failures"].append({
                "task_id": ev["task_id"],
                "kind": ev["kind"],
                "m": ev["m"],
                "k": ev["k"],
                "mode": _MODE_LABELS_ZH.get(ev["mode"], ev["mode"]),
                "detail": ev["detail"],
            })
            # 轨迹切片（若提供）
            tr = (traces or {}).get(ev["task_id"])
            if tr:
                pack["traces"].append({
                    "task_id": ev["task_id"],
                    "slice": slice_trace(tr),
                })

    # 该维度静态快照（产分 + 归因信号）
    if dim in _STATIC_DIMS:
        for sig in SIGNAL_NAMES:
            if sig.startswith(dim + "."):
                s = (static_signals or {}).get(sig)
                if s is not None:
                    pack["static"][sig] = {
                        "score": s.get("score"),
                        "value": s.get("value"),
                    }
    # 变更安全性/效率的专属归因信号
    for sig_name in _ATTRIBUTION_SIGNAL_NAMES:
        if _ATTRIBUTION_DIM_OF[sig_name] == dim:
            s = (attribution_signals or {}).get(sig_name)
            if s is not None:
                pack["static"][f"{dim}.{sig_name}"] = {
                    "score": s.get("score"),
                    "value": s.get("value"),
                }
    return pack


_LLM_PROMPT = """你是 CogniCode 的失败归因分析器。仓库评估中维度「{label}（{dim}）」存在失败样本，请综合证据给出**一条**改进建议。

证据包（结构化 JSON）：
{pack}

要求：
1. 只输出一个 JSON 对象（不要其他文字），字段：dimension（锚定维度，必须是 "{dim}"）、text（中文建议，锚定维度 + 预期方向，一句话）、direction（"up"）。
2. 建议必须可重测（改后重跑同一套任务用维度分区间判定方向移动）。
3. 不要提任务原文与注入点细节。"""


def _parse_llm_json(text: str | None) -> dict | None:
    """解析 LLM 结构化 JSON；非法（非 JSON / 缺字段 / 锚定非法）→ None。"""
    if not text:
        return None
    text = text.strip()
    # 容忍 ```json ... ``` 包裹
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
    for field in _LLM_JSON_FIELDS:
        if not isinstance(obj.get(field), str) or not obj[field].strip():
            return None
    dimension = obj["dimension"].strip()
    if dimension not in DIMENSIONS:
        return None  # 锚定维度必须合法（#8 约束 a）
    return {
        "dimension": dimension,
        "text": obj["text"].strip(),
        "direction": obj["direction"].strip(),
    }


def run_attribution(
    f: dict,
    static_signals: dict | None,
    *,
    llm=None,
    attribution_signals: dict | None = None,
    dim_points: dict[str, float | None] | None = None,
    efficiency: dict | None = None,
    traces: dict | None = None,
) -> dict:
    """归因管线主入口（三档「确定性优先、LLM 兜底」，#15）。

    Args:
        f: failure_sources 输出。
        static_signals: static.json 的 signals。
        llm: LLMClient | None。None（--offline）→ 只出确定性档。
        attribution_signals: 专属归因信号（测试覆盖缺口 / 单文件规模）。
        dim_points: 维度点值 {dim: float|None}（排序键）。
        efficiency: 效率分 {point, ...}（单文件规模触发判断）。
        traces: {task_id: 轨迹 JSONL 文本}（LLM 证据包轨迹切片；缺 → 空切片）。

    Returns:
        {
          "suggestions": [建议条...]（确定性 + LLM，已排序），
          "llm_groups": [未被 LLM 归因的 (维度, 失败模式, 失败数)]（报告说明），
          "llm_calls": 实际 LLM 调用次数（快照/审计）。
        }
    """
    suggestions = build_deterministic_suggestions(
        f, static_signals, attribution_signals,
        dim_points=dim_points, efficiency=efficiency,
    )

    llm_groups: list[dict] = []
    llm_calls = 0
    if llm is not None:
        # 需 LLM 归因的组：无静态信号维度（可解性/可诊断性）且该组有失败，
        # 或静态面合格（产分信号全高分）却动态失败（#15 §2 档 1 未命中）。
        for dim in ("solvability", "safety", "diagnosability", "navigability", "buildability"):
            groups = f.get("groups", {}).get(dim, {})
            for mode in ("incorrect", "budget"):
                evs = groups.get(mode, [])
                if not evs:
                    continue
                # 静态面合格却失败 → 归因留给 LLM（档 1 未命中兜底）
                if dim in _STATIC_DIMS and _static_dim_ok(dim, static_signals):
                    continue
                m_total = sum(e["m"] for e in evs)
                pack = _evidence_pack(f, dim, static_signals, attribution_signals, traces)
                prompt = _LLM_PROMPT.format(
                    label=DIMENSION_LABELS_ZH.get(dim, dim),
                    dim=dim,
                    pack=json.dumps(pack, ensure_ascii=False),
                )
                try:
                    text = llm.complete(prompt, model=None)
                except Exception:
                    text = None
                llm_calls += 1
                parsed = _parse_llm_json(text)
                if parsed is None:
                    llm_groups.append({
                        "dimension": dim,
                        "mode": mode,
                        "failures": m_total,
                        "note": "LLM 输出非法/失败，已丢弃（Q17 兜底）",
                    })
                    continue
                # 锚定维度（LLM 已校验合法）→ 建议条；排序键同档内按 llm_rank
                ref = build_failure_ref(f, parsed["dimension"]) or ""
                llm_rank = len([s for s in suggestions if s.get("source") == "llm"])
                suggestions.append({
                    "anchor": parsed["dimension"],
                    "anchor_kind": "dimension",
                    "text": parsed["text"],
                    "direction": parsed["direction"],
                    "remeasurable": _REMEASURE_DIM,
                    "failure_ref": ref,
                    "evidence": f"LLM 综合归因（锚定维度 {parsed['dimension']}）"
                               + (f"；{ref}" if ref else ""),
                    "priority": _priority_key(
                        dim_points, parsed["dimension"], 0.0, f, parsed["dimension"]
                    ),
                    "source": "llm",
                    "llm_rank": llm_rank,
                })

    # 排序：确定性键为主（(dim, sig, impact)），LLM 同档内按 llm_rank 重排（#8 §8）
    suggestions.sort(key=lambda s: (s["priority"], s.get("llm_rank", -1)))
    return {
        "suggestions": suggestions,
        "llm_groups": llm_groups,
        "llm_calls": llm_calls,
    }


def _static_dim_ok(dim: str, static_signals: dict | None) -> bool:
    """该维度静态面是否合格（产分信号全高分）。

    静态面合格却动态失败 → 确定性模板未命中 → LLM 兜底（#15 §2 档 1）。
    信号缺（未提取）→ 视为不合格（保守，走 LLM 兜底或仅失败提示）。
    """
    sigs = [n for n in SIGNAL_NAMES if n.startswith(dim + ".")]
    if not sigs:
        return False
    for name in sigs:
        s = (static_signals or {}).get(name)
        if s is None or float(s.get("score", 0.0)) < 1.0:
            return False
    return True
