"""报告生成（#21/#12 锁定）：终端摘要 + 全量落盘 `cognicode-report.md`。

决策锚点（#12 + #8 + #7）：
- **单页三层**：总览（总分+区间、软横比、快照摘要一行、六维 mini）→
  维度明细（每维点估计+区间+条形；可导航性/环境可用性显示动静分解；
  效率行显示语料百分位+原始四量中位数）→ 建议清单。
- **敏感性小节独立放后半**（#12 #3-4）：内容由 #22 敏感性分析产出，
  本票落结构占位（标注待 #22）。
- **附录**：运行环境快照全量、信号原始值（#12 #3-5）。
- **纯文本无 ANSI**、中文正文术语括英、报告头摘要行显示 schema 号（#12 #5）。
- **建议清单**：确定性排序键（维度分最低优先 → 信号档位最低优先，
  #8 #8）；产分信号缺失/低档 → 确定性模板建议条（#7 #6/#15），
  每条含锚定信号 + 预期方向 + 可重测声明 + 失败任务引用（#12 #3-3）。
  LLM 综合归因档归 #23。

本模块纯函数、无 I/O；输入是 aggregate_run 的输出 + 静态信号原始值。
"""

from __future__ import annotations

from datetime import datetime, timezone

from cognicode.score import DIMENSIONS, DIMENSION_LABELS_ZH

# 建议模板：产分信号名 → (中文建议文本, 预期方向)。
# #7 #6/#15 #2-1：产分信号缺失/低档 → 确定性模板，锚定该信号。
_SIGNAL_SUGGESTIONS: dict[str, tuple[str, str]] = {
    "navigability.agent_context_docs": (
        "补充代理上下文文档（agent context document，如 AGENTS.md / CONTEXT.md），"
        "让编程 agent 无需通读代码即可定位关键模块",
        "升（up）",
    ),
    "navigability.readme": (
        "在仓库根添加 README 入口文档，说明项目用途与结构",
        "升（up）",
    ),
    "navigability.comment_density": (
        "提升注释/docstring 密度（当前低于 5% 阈值），降低 agent 理解代码的成本",
        "升（up）",
    ),
    "navigability.entry_clarity": (
        "补充/明确代码入口（如 main.py / cli.py / src/ 约定），让 agent 找到启动路径",
        "升（up）",
    ),
    "buildability.build_def": (
        "补充构建定义文件（如 pyproject.toml / package.json / Makefile），"
        "让 agent 从冷启动跑起构建",
        "升（up）",
    ),
    "buildability.lockfile": (
        "引入并提交依赖锁文件（lockfile），保证可复现安装",
        "升（up）",
    ),
    "buildability.ci": (
        "配置 CI（如 .github/workflows），让验证回路自动化",
        "升（up）",
    ),
    "buildability.test_discoverability": (
        "补充测试目录与测试文件（tests/ 等），让 agent 发现并运行验证回路",
        "升（up）",
    ),
}

# 维度级建议（无静态信号维度，锚定维度；#15 #3-3 归因归 #23，本票只落低分提示）
_DIM_SUGGESTIONS: dict[str, tuple[str, str]] = {
    "solvability": (
        "可解性（solvability）动态分偏低：修改/修复任务解出率低",
        "升（up）",
    ),
    "safety": (
        "变更安全性（safety）动态分偏低：修改类任务存在 P2P 回归",
        "升（up）",
    ),
    "diagnosability": (
        "可诊断性（diagnosability）动态分偏低：定位类任务成功率低",
        "升（up）",
    ),
    "efficiency": (
        "效率（efficiency）百分位偏低：success 运行的成本高于语料中位",
        "升（up）",
    ),
}


def _fmt_score(value: float | None, ndigits: int = 2) -> str:
    if value is None:
        return "未测"
    return f"{value:.{ndigits}f}"


def _bar(value: float | None, width: int = 10) -> str:
    """ASCII 条形（#12：维度分以数字为准 + ASCII 条形辅助）。"""
    if value is None:
        return " " * width + "（未测）"
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "█" * filled + "░" * (width - filled)


def _interval(dim: dict) -> str:
    """维度区间文本（[lower, upper] 或 半宽 ± 或 未测）。"""
    if dim.get("lower") is not None and dim.get("upper") is not None:
        return f"[{_fmt_score(dim['lower'])}, {_fmt_score(dim['upper'])}]"
    if dim.get("half_width"):
        return f"±{_fmt_score(dim['half_width'])}"
    return ""


def _decompose(dim: dict) -> str:
    """动静分解文本（仅可导航性/环境可用性，#12 #3-2）。"""
    src = dim.get("source")
    details = dim.get("details") or {}
    if src == "dyn70_static30":
        return f"（动态 {_fmt_score(details.get('dynamic'))} + 静态 {_fmt_score(details.get('static'))}，70/30）"
    if src == "static_only":
        return f"（静态 {_fmt_score(details.get('static'))}，动态未测）"
    if src == "corpus_percentile":
        m = details.get("medians") or {}
        raw = details.get("raw_percentile")
        # 原始中位数并报（#8 #4：永远并报，不隐藏）；未采集时中位数全 None → 不显示
        if raw is None and not any(v is not None for v in m.values()):
            return ""
        raw_s = _fmt_score(raw) if raw is not None else "无"
        tok = m.get("token")
        turn = m.get("turns")
        wall = m.get("wall_ms")
        med_s = (f"token {tok}" if tok is not None else "token -")
        med_s += f" / turns {turn}" if turn is not None else " / turns -"
        med_s += f" / wall {wall}ms" if wall is not None else " / wall -"
        return f"（语料百分位 {raw_s}，原始中位数 {med_s}）"
    return ""


def _build_suggestions(agg: dict, static_signals: dict | None) -> list[dict]:
    """确定性建议清单（#7 模板 + #8 排序键）。

    排序（#8 #8）：维度分最低优先 → 信号档位最低优先。
    LLM 综合/重排归 #23；本票只出确定性模板条。
    """
    suggestions: list[dict] = []
    dims = agg.get("dimensions", {})

    # 1) 静态信号缺失/低档 → 模板建议（锚定信号）
    for name, (text, direction) in _SIGNAL_SUGGESTIONS.items():
        sig = (static_signals or {}).get(name)
        score = (sig or {}).get("score")
        if score is not None and score < 1.0:
            dim = name.split(".")[0]
            suggestions.append({
                "anchor": name,
                "anchor_kind": "signal",
                "text": text,
                "direction": direction,
                "remeasurable": (
                    "重跑同一套任务与静态提取（static extraction），"
                    "用维度分区间判定是否向预期方向移动"
                ),
                "evidence": f"信号 {name} 当前 {_fmt_score(score)}",
                "priority": _priority_key(dims.get(dim), score),
            })

    # 2) 无静态信号维度的低分提示（锚定维度；LLM 归因归 #23）
    for dim, (text, direction) in _DIM_SUGGESTIONS.items():
        d = dims.get(dim) or {}
        point = d.get("point")
        if point is not None and point < 0.5:
            suggestions.append({
                "anchor": dim,
                "anchor_kind": "dimension",
                "text": text,
                "direction": direction,
                "remeasurable": (
                    f"重跑对应任务类（{dim}），用维度分区间判定方向移动"
                ),
                "evidence": f"维度 {DIMENSION_LABELS_ZH.get(dim, dim)} 当前 {_fmt_score(point)}",
                "priority": _priority_key(d, None),
            })

    # 排序：维度分最低优先（#8 #8 主键）
    suggestions.sort(key=lambda s: s["priority"])
    return suggestions


def _priority_key(dim: dict | None, signal_score: float | None) -> tuple:
    """确定性排序键：#8 #8 主键 = 维度分最低优先 → 信号档位最低优先。"""
    point = (dim or {}).get("point")
    if point is None:
        dim_key = 1.0  # 未测维度排后（无分可比较）
    else:
        dim_key = round(point, 6)
    sig_key = 0.0 if signal_score is None else round(signal_score, 6)
    return (dim_key, sig_key)


def render_terminal_summary(agg: dict, static_signals: dict | None = None) -> str:
    """终端一屏纯文本摘要（#12 #1：总览 → 维度明细 → 建议清单）。"""
    return render_report(agg, static_signals=static_signals, terminal=True)


def render_report(
    agg: dict,
    *,
    static_signals: dict | None = None,
    repo_name: str = "",
    commit_pin: str = "",
    terminal: bool = False,
) -> str:
    """渲染全量报告文本（cognicode-report.md；terminal=True 时截断为摘要）。

    纯文本无 ANSI；中文正文术语括英；报告头显示 schema 号（#12 #5）。
    """
    dims = agg.get("dimensions", {})
    total = agg.get("total", {})
    soft = agg.get("soft_benchmark", {})
    snapshot = agg.get("snapshot", {})
    schema_v = snapshot.get("report-schema", "1.0")
    weight_v = snapshot.get("weights-version", "")
    run_id = agg.get("run_id", "")
    dynamic_measured = agg.get("dynamic_measured", True)

    lines: list[str] = []
    lines.append("# CogniCode 评估报告（report）")
    lines.append("")
    lines.append(f"report-schema: {schema_v} · 权重版本: {weight_v} · 运行: {run_id}")
    lines.append("")

    # ---- 总览 ----
    lines.append("## 总览（overview）")
    lines.append("")
    who = repo_name or "（未提供仓库名）"
    if commit_pin:
        who += f"（commit {commit_pin}）"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"- 仓库: {who} · 评估日期: {now}")
    if total.get("point") is not None:
        lines.append(
            f"- 总分: {_fmt_score(total['point'])} "
            f"[{_fmt_score(total.get('lower'))}, {_fmt_score(total.get('upper'))}]（95% 区间）"
        )
    else:
        lines.append("- 总分: 未测（动态面未测，仅静态分可用）")
    lines.append(f"- 软横比（soft cross-repo comparison）: {soft.get('statement', '')}")
    if not dynamic_measured:
        lines.append("- 动态面未测（探测失败降级，仅静态分可用）")
    # 六维 mini 表（#12 #3-1）
    mini = " · ".join(
        f"{DIMENSION_LABELS_ZH.get(d, d)} {_fmt_score(dims.get(d, {}).get('point'))}"
        for d in DIMENSIONS
    )
    lines.append(f"- 六维: {mini}")
    lines.append("")

    # ---- 维度明细 ----
    lines.append("## 维度明细（dimension details）")
    lines.append("")
    for d in DIMENSIONS:
        dim = dims.get(d, {})
        label = DIMENSION_LABELS_ZH.get(d, d)
        lines.append(
            f"- {label}（{d}）: {_fmt_score(dim.get('point'))} "
            f"{_interval(dim)} {_bar(dim.get('point'))}{_decompose(dim)}"
        )
    lines.append("")

    # ---- 建议清单 ----
    suggestions = _build_suggestions(agg, static_signals)
    lines.append("## 建议清单（suggestions）")
    lines.append("")
    if not suggestions:
        lines.append("- 无（当前无低分产分信号与低分维度）")
    else:
        for i, s in enumerate(suggestions[:8], 1):
            lines.append(
                f"{i}. **{s['text']}**  "
                f"[锚定: {s['anchor']} · 预期方向: {s['direction']}]"
            )
            lines.append(f"   - 可重测声明（re-measurability claim）: {s['remeasurable']}")
            lines.append(f"   - 证据: {s['evidence']}")
    lines.append("")

    if terminal:
        # 终端摘要：三层 + 敏感性一行 + 快照摘要一行
        lines.append("## 权重敏感性分析（weight sensitivity）")
        lines.append("")
        lines.extend(_render_sensitivity_lines(agg, terminal=True))
        lines.append("")
        lines.append("## 附录（appendix）")
        lines.append("")
        lines.append(f"- 运行环境快照: {json_dumps(snapshot)}")
        return "\n".join(lines)

    # ---- 敏感性小节（独立放后半，#12 #3-4，内容由 #22 产出）----
    lines.append("## 权重敏感性分析（weight sensitivity analysis）")
    lines.append("")
    lines.extend(_render_sensitivity_lines(agg))
    lines.append("")

    # ---- 附录 ----
    lines.append("## 附录（appendix）")
    lines.append("")
    lines.append("### 运行环境快照（run snapshot）")
    lines.append("")
    lines.append(f"```json\n{json_dumps(snapshot)}\n```")
    lines.append("")
    lines.append("### 信号原始值（signal values）")
    lines.append("")
    if static_signals:
        for name, sig in static_signals.items():
            lines.append(
                f"- {name}: score {_fmt_score(sig.get('score'))} "
                f"value {_fmt_score(sig.get('value'), 4)}"
                f"{('（证据: ' + '；'.join(sig.get('evidence', [])) + '）') if sig.get('evidence') else ''}"
            )
    else:
        lines.append("- （无静态信号数据）")
    lines.append("")
    return "\n".join(lines)


def _render_sensitivity_lines(agg: dict, terminal: bool = False) -> list[str]:
    """敏感性小节文本（#22 产出；内容见 agg['sensitivity']）。

    判据①：网格 5⁶ + Dirichlet 200 的总分点值带宽 ≤0.05（#10），附每维
    档位净影响（提高该维权重对总分的拉动方向）。判据②（语料方向排序
    稳定）需语料各仓六维点值——由调用方经 agg['sensitivity']['corpus']
    注入；缺 → 标注「待语料」。
    """
    sens = agg.get("sensitivity") or {}
    lines: list[str] = []
    if sens.get("note"):
        lines.append(f"- {sens['note']}")
        return lines

    grid = sens.get("grid") or {}
    dirl = sens.get("dirichlet") or {}
    bw = grid.get("bandwidth")
    if bw is None:
        lines.append("- 敏感性数据缺失（aggregate 未产出）")
        return lines

    g_pass = grid.get("criterion_pass", False)
    d_pass = dirl.get("criterion_pass", False)
    verdict = "稳健（pass）" if (g_pass and d_pass) else "不稳健（fail）"
    lines.append(
        f"- 判据①（带宽 ≤0.05）: 网格 {grid.get('n_weights', '?')} 组 "
        f"带宽 {bw:.3f}（{'≤0.05 ✓' if g_pass else '>0.05 ✗'}）；"
        f"Dirichlet {dirl.get('n_samples', '?')} 次带宽 "
        f"{(dirl.get('bandwidth') or 0.0):.3f}"
        f"（{'≤0.05 ✓' if d_pass else '>0.05 ✗'}）→ 总分对权重选择 {verdict}"
    )
    if terminal:
        return lines

    # 每维净影响（提高该维权重对总分的拉动方向；0.5 = 中性）
    sweep = grid.get("sweep") or {}
    parts = []
    for d in DIMENSIONS:
        s = sweep.get(d) or {}
        eff = s.get("effect")
        if eff is None:
            continue
        mark = "↑" if eff > 0.0005 else ("↓" if eff < -0.0005 else "·")
        parts.append(f"{DIMENSION_LABELS_ZH.get(d, d)} {mark}{eff:+.3f}")
    lines.append(
        "- 每维权重从最低档拉到最高档对总分点值的净影响（0–1 标尺）: "
        + "，".join(parts)
    )

    # 判据②（语料方向排序稳定；需各仓六维点值）
    corpus = sens.get("corpus") or {}
    if corpus.get("present") is False or not corpus.get("repos"):
        lines.append(
            "- 判据②（语料方向排序稳定）: 待语料——需各仓六维点值注入"
            "（校准验证阶段输出，MVP done 前以判据①为准）"
        )
    else:
        order = " > ".join(corpus.get("repos", []))
        pairs = corpus.get("unstable_pairs", [])
        if corpus.get("stable"):
            st = "✓ 稳定（相邻序位差 ≥ 2×带宽）"
        else:
            st = "✗ 不稳定（相邻序位差 < 2×带宽）"
        lines.append(f"- 判据②（语料方向排序稳定）: {order} —— {st}")
        if pairs:
            lines.append(
                "  - 敏感序位对（点值差 < 2×带宽）: "
                + "，".join(
                    f"{a}/{b}（差 {d:.3f}）" for a, b, d in pairs
                )
            )
    return lines


def json_dumps(obj) -> str:
    """快照等 JSON 落盘的统一序列化（中文不转义、缩进 2）。"""
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)
