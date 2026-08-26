"""聚合层（#21）：判卷结果 + 静态信号 → 六维分 + 总分 + 区间 + 效率 + 软横比。

决策锚点（#6/#8/#10/#12/#15 + 地图 Standing preferences）：
- **维度内动态:静态 = 70/30**（#8 #2 钉死）：navigability/buildability 两维有
  静态产分信号（#18）→ `dim = 0.7·动态 + 0.3·静态`；其余四维（可解性/变更
  安全性/效率/可诊断性）无静态信号 → `dim = 动态分`。
- **维度级必须带区间**（#6 #7）：成功率类 = success/有效次数（fail_env 剔除），
  Wilson 95% CI（statistics.wilson_ci）。
- **总分 = 六维加权算术平均**（#8 #1/#10 等权 1/6），半宽 = sqrt(Σ wᵢ²·hwᵢ²)
  独立线性解析传播（#8 #5）；静态项只贡献点值（半宽=0，静态是确定性事实）。
- **效率维**（#8 #4）：success 运行的 token/轮次/墙钟中位数（成本恒 0 不采），
  效率分 = 本仓中位数在语料中的经验百分位（worse_ratio 反转，高=好）；
  原始四量中位数永远并报；语料参考缺 → 百分位 null（只报原始）。
- **软横比**（#8 #3/#12 #4）：总分旁语料中位数 + 固定声明句；无语料 → 无横比。
- **探测失败 → 整体降级**（地图 Standing）：只出静态分 + 标注动态面未测；
  无动态时维度 = 静态分（0.3 不适用），总分 null。
- **任务级全 success/全 fail 剔除**（#5）：无信息量任务不进统计（记入报告）。

输出（#21）：aggregate.json（聚合全量，含敏感性小节）+ snapshot.json（配置全量 +
report-schema 版本 + 权重版本，schema.report_schema_marker()）。

敏感性（#22/#10）：判据 ① 网格 5⁶ + Dirichlet 200 带宽 ≤0.05（本仓点值，随报告附）；
判据 ② 语料方向排序稳定性由报告层/调用方以各仓六维点值驱动（见 report/sensitivity）。

本模块纯函数、无 I/O；verdicts.json 形状 = {tasks: [{task_id, kind, k,
outcomes: [五类]}]}。
"""

from __future__ import annotations

from statistics import median

from cognicode.schema import REPORT_SCHEMA_VERSION, report_schema_marker
from cognicode.score import DEFAULT_WEIGHTS, DimensionScore, weighted_total
from cognicode.statistics import wilson_ci
from cognicode.verdict import OUTCOME_CATEGORIES, classify_verdict, is_counted

# 维度内动态:静态比例（#8 钉死 70/30；可被 #10 校准推翻，但本票不重开）
DYN_STATIC_SPLIT = 0.7

# 有静态产分信号的维度（#18：可导航性 + 环境可用性）
_STATIC_DIMS = frozenset({"navigability", "buildability"})

# 效率四量：量名 → (语料参考键, 中位数键)
_EFF_QUANTITIES = {
    "token": "token",
    "turns": "turns",
    "wall_ms": "wall_ms",
}


# ---------------------------------------------------------------------------
# 基础统计
# ---------------------------------------------------------------------------


def median_of(values: list[float]) -> float:
    """列表的中位数；空列表抛 ValueError。"""
    if not values:
        raise ValueError("median_of 需要非空列表")
    return float(median(values))


def task_statistics(outcomes: list[str]) -> dict:
    """单个任务的多轮判定统计（fail_env 剔除）。

    Returns:
        {successes, effective, excluded_env, point, lower, upper}：
        effective = 计入类别数（success/fail_incorrect/fail_budget），
        point/lower/upper = Wilson 95% CI（0 样本 → point=None）。
    """
    successes = 0
    effective = 0
    excluded_env = 0
    for cat in outcomes:
        classify_verdict(cat)
        if cat == "success":
            successes += 1
            effective += 1
        elif cat == "fail_env":
            excluded_env += 1
        else:
            effective += 1

    if effective == 0:
        return {
            "successes": 0, "effective": 0, "excluded_env": excluded_env,
            "point": None, "lower": None, "upper": None,
        }
    p, lower, upper = wilson_ci(successes, effective)
    return {
        "successes": successes, "effective": effective,
        "excluded_env": excluded_env,
        "point": p, "lower": lower, "upper": upper,
    }


def verdicts_summary(verdicts: dict) -> dict:
    """判卷数据 → 任务类别计数 + 剔除记录（#5 全 success/全 fail 剔除）。

    修改类任务会拆可解性/变更安全性（#15），但任务级统计仍按 kind 计。

    Returns:
        {counts: {kind: n}, removed_all_same: [task_id], tasks_included: n}
    """
    counts: dict[str, int] = {}
    removed: list[str] = []
    included = 0
    for task in verdicts.get("tasks", []):
        kind = task.get("kind")
        counts[kind] = counts.get(kind, 0) + 1
        outcomes = task.get("outcomes", [])
        counted = [c for c in outcomes if is_counted(c)]
        if counted and (all(c == "success" for c in counted)
                        or all(c != "success" for c in counted)):
            removed.append(task.get("task_id", "?"))
            continue
        included += 1
    return {
        "counts": counts,
        "removed_all_same": removed,
        "tasks_included": included,
    }


# ---------------------------------------------------------------------------
# 效率分（#8 #4：语料百分位）
# ---------------------------------------------------------------------------


def efficiency_score(
    medians: dict,
    corpus: dict | None = None,
) -> dict:
    """效率分：success 运行四量中位数在语料中的经验百分位（worse_ratio 反转）。

    Args:
        medians: {token, turns, wall_ms}（success 运行中位数）。
        corpus: {token: [...], turns: [...], wall_ms: [...]} 语料各仓参考值；
            None 或某量缺 → 该量跳过。

    Returns:
        {
          "point": 0-1（高=好；语料缺 → None），
          "raw_percentile": 1 - point（CDF，显示用；语料缺 → None），
          "medians": {token, turns, wall_ms}（原始并报，不隐藏）
        }
    """
    ratios: list[float] = []
    for q in _EFF_QUANTITIES:
        refs = (corpus or {}).get(q)
        value = medians.get(q)
        if not refs or value is None:
            continue
        sorted_refs = sorted(refs)
        worse = sum(1 for r in sorted_refs if r > value)
        ratios.append(worse / len(sorted_refs))

    if not ratios:
        point = None
        raw = None
    else:
        point = sum(ratios) / len(ratios)
        raw = 1.0 - point

    return {
        "point": point,
        "raw_percentile": raw,
        "medians": {
            "token": medians.get("token"),
            "turns": medians.get("turns"),
            "wall_ms": medians.get("wall_ms"),
        },
    }


def corpus_median(scores: list[float] | None) -> float | None:
    """语料各仓总分的简单中位数（软横比参考）；空 → None。"""
    if not scores:
        return None
    return float(median(sorted(scores)))


# ---------------------------------------------------------------------------
# 维度动态统计（按任务类别路由，#15）
# ---------------------------------------------------------------------------


def _dimension_dynamic(verdicts: dict) -> dict[str, dict]:
    """把判卷数据按维度路由聚合（任务类别即维度，#15）。

    - 检索 → 可导航性（动态面）
    - 定位 → 可诊断性
    - 修改 → 可解性（F2P 未过 / fail_budget）；变更安全性需要 F2P 过但
      P2P 未过的子类——本层按任务级 outcomes 聚合到可解性，
      P2P 回归的细分依赖判卷层标注（judge_modify 输出 fail_incorrect 时
      判卷驱动标记 safety；本票按任务级统计，P2P 细分归 #23 归因消费）。

    Returns:
        {dimension: {successes, effective, point, lower, upper}}
    """
    kind_to_dim = {
        "search": "navigability",
        "locate": "diagnosability",
        "modify": "solvability",
    }
    per_dim: dict[str, list[str]] = {d: [] for d in kind_to_dim.values()}
    for task in verdicts.get("tasks", []):
        kind = task.get("kind")
        dim = kind_to_dim.get(kind)
        if dim is None:
            continue
        outcomes = task.get("outcomes", [])
        counted = [c for c in outcomes if is_counted(c)]
        # #5 剔除全 success/全 fail（无信息量）
        if counted and (all(c == "success" for c in counted)
                        or all(c != "success" for c in counted)):
            continue
        per_dim[dim].extend(counted)

    result: dict[str, dict] = {}
    for dim, cats in per_dim.items():
        result[dim] = task_statistics(cats)
    return result


# ---------------------------------------------------------------------------
# 主聚合
# ---------------------------------------------------------------------------


def aggregate_run(
    verdicts: dict,
    *,
    static: dict,
    medians: dict | None = None,
    corpus: dict | None = None,
    corpus_totals: list[float] | None = None,
    dynamic_measured: bool = True,
    run_id: str = "run",
    config: dict | None = None,
    weights: dict[str, float] | None = None,
    repo_dims: dict[str, dict[str, float]] | None = None,
) -> dict:
    """聚合一次评估运行 → aggregate 全量数据（可落盘 aggregate.json）。

    Args:
        verdicts: 判卷数据 {tasks: [{task_id, kind, k, outcomes}]}。
        static: static.json（#18 形状：{signals, dimensions}）。
        medians: 效率 success 运行中位数 {token, turns, wall_ms}；
            None = 未采集（探测失败等）。
        corpus: 效率语料参考分布（可选，缺 → 效率百分位 null）。
        corpus_totals: 语料各仓总分（软横比中位数参考；缺 → 无横比）。
        dynamic_measured: 动态面是否已测（探测全灭 → False，整体降级）。
        run_id: 运行 id（进 snapshot）。
        config: 配置全量（进 snapshot；缺 → 空 dict）。
        weights: 评分权重（默认等权 1/6）；供测试/对比复算总分，
            可空（缺省即等权）。
        repo_dims: 语料各仓六维点值 {repo: {dim: 点值}}（敏感性判据②
            方向排序稳定性；缺 → 报告标「待语料」）。

    Returns:
        aggregate 全量：{run_id, dynamic_measured, verdicts_summary,
        dimensions, total, efficiency, soft_benchmark, snapshot, removed}
    """
    summary = verdicts_summary(verdicts)
    static_dims = static.get("dimensions", {})
    w = weights or DEFAULT_WEIGHTS

    dims: dict[str, dict] = {}
    if dynamic_measured:
        dyn = _dimension_dynamic(verdicts)
        eff = efficiency_score(medians or {}, corpus=corpus)
        for dim in [
            "solvability", "safety", "efficiency",
            "navigability", "buildability", "diagnosability",
        ]:
            if dim == "efficiency":
                dims[dim] = {
                    "point": eff["point"],
                    "lower": None, "upper": None,  # 语料百分位非采样量，无区间
                    "half_width": 0.0,
                    "source": "corpus_percentile",
                    "details": eff,
                }
            elif dim == "safety":
                # 变更安全性：P2P 回归样本（#15）；无则未测（0 点值，半宽 0）
                # 本票任务级聚合不细分 P2P——safety 动态样本来自判卷层标记
                # （构造数据无 P2P 回归 → 未测）
                dims[dim] = {"point": 0.0, "lower": None, "upper": None,
                             "half_width": 0.0, "source": "dynamic",
                             "details": {"note": "无 P2P 回归样本（未测）"}}
            elif dim in _STATIC_DIMS:
                # 有静态面的维度：动态有样本 → 70/30 混合；无动态样本 → 静态分
                # （动态未测时 0.3 不适用，等同该维降级，#16 只出静态分语义）
                st = static_dims.get(dim, {}).get("score", 0.0)
                if dim in dyn and dyn[dim]["point"] is not None:
                    dy = dyn[dim]
                    p = DYN_STATIC_SPLIT * dy["point"] + (1 - DYN_STATIC_SPLIT) * st
                    hw = DYN_STATIC_SPLIT * ((dy["upper"] - dy["lower"]) / 2)
                    dims[dim] = {
                        "point": p,
                        "lower": None, "upper": None,
                        "half_width": hw,
                        "source": "dyn70_static30",
                        "details": {
                            "dynamic": dy["point"], "static": st,
                            "dynamic_ci": [dy["lower"], dy["upper"]],
                        },
                    }
                else:
                    dims[dim] = {"point": st, "lower": None, "upper": None,
                                 "half_width": 0.0, "source": "static_only",
                                 "details": {"static": st, "note": "动态未测"}}
            elif dim in dyn:
                dy = dyn[dim]
                if dy["point"] is None:
                    # 动态样本 0（判卷无该维度数据）→ 未测
                    dims[dim] = {"point": None, "lower": None, "upper": None,
                                 "half_width": 0.0, "source": "unmeasured",
                                 "details": {}}
                else:
                    dims[dim] = {
                        "point": dy["point"],
                        "lower": dy["lower"], "upper": dy["upper"],
                        "half_width": (dy["upper"] - dy["lower"]) / 2,
                        "source": "dynamic",
                        "details": {"successes": dy["successes"],
                                    "effective": dy["effective"]},
                    }
            else:
                # 无动态样本且非静态维 → 未测
                dims[dim] = {"point": None, "lower": None, "upper": None,
                             "half_width": 0.0, "source": "unmeasured",
                             "details": {}}
    else:
        # 探测失败 → 整体降级：只出静态分（可导航性/环境可用性），其余未测
        for dim in [
            "solvability", "safety", "efficiency",
            "navigability", "buildability", "diagnosability",
        ]:
            if dim in _STATIC_DIMS:
                st = static_dims.get(dim, {}).get("score", 0.0)
                dims[dim] = {"point": st, "lower": None, "upper": None,
                             "half_width": 0.0, "source": "static_only",
                             "details": {"static": st}}
            else:
                dims[dim] = {"point": None, "lower": None, "upper": None,
                             "half_width": 0.0, "source": "unmeasured",
                             "details": {}}

    # 总分：等权 1/6 加权算术平均（#8 #1/#10）；缺维按 0 点值、0 半宽（未测维）
    measured = [d for d, v in dims.items() if v["point"] is not None]
    total = {"point": None, "lower": None, "upper": None, "half_width": None}
    if measured and dynamic_measured:
        dim_scores = {
            d: DimensionScore(
                point=dims[d]["point"] or 0.0,
                half_width=dims[d]["half_width"] or 0.0,
            )
            for d in dims
        }
        t = weighted_total(dim_scores, weights=w)
        total = {
            "point": t.point,
            "lower": max(0.0, t.point - t.half_width),
            "upper": min(1.0, t.point + t.half_width),
            "half_width": t.half_width,
        }

    # 软横比（#8 #3/#12 #4）
    cm = corpus_median(corpus_totals)
    if cm is not None:
        soft = {
            "corpus_median": cm,
            "statement": (
                f"语料中位数 {cm:.3f}（仅软参考）——跨仓库排序仅软参考，"
                "不做硬承诺（软横比，soft cross-repo comparison）"
            ),
        }
    else:
        soft = {
            "corpus_median": None,
            "statement": "无横比（语料未提供，本仓为单点评估）",
        }

    # 敏感性分析（#22/#10：纯解析，输入六维点值）：
    # 判据①（本仓带宽 ≤0.05）+ 判据②（语料方向排序稳定，随校准验证输出）。
    # 静态面确定性：非动态时也判据①（静态分确定性事实仍可看权重稳健性），
    # 但动态未测时总分未测 → 敏感性主体无意义，跳过并标注。
    sensitivity = None
    if dynamic_measured and total.get("point") is not None:
        from cognicode.sensitivity import sensitivity_analysis

        dim_points = {
            d: (dims[d].get("point") or 0.0) for d in dims
        }
        sensitivity = sensitivity_analysis(
            dim_points,
            repo_dims=repo_dims,
        )
    else:
        sensitivity = {
            "note": "动态面未测（总分未测），权重敏感性不适用",
        }

    snapshot = {
        **report_schema_marker(),
        "report-schema": REPORT_SCHEMA_VERSION,
        "weights-version": DEFAULT_WEIGHTS and report_schema_marker()["weights-version"],
        "config": config or {},
        "run": {
            "run_id": run_id,
            "dynamic_measured": dynamic_measured,
        },
    }

    return {
        "run_id": run_id,
        "dynamic_measured": dynamic_measured,
        "verdicts": summary,
        "dimensions": dims,
        "total": total,
        "efficiency": dims["efficiency"]["details"],
        "soft_benchmark": soft,
        "sensitivity": sensitivity,
        "snapshot": snapshot,
        "removed": summary["removed_all_same"],
    }
