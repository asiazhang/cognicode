"""权重敏感性分析（#22，决策锚点 #10 + 地图 Standing preferences）。

对六维权重做确定性网格扰动 + Dirichlet 采样补网，判定总分对权重选择的
稳健性。纯解析：输入是六维**点值**（聚合层已算好的量），不重跑任务、
不调 LLM；Dirichlet 采样用纯 Python 手写 gamma 实现（无 numpy/scipy 依赖）。

- **网格**：每维权重在 {0.5, 0.75, 1, 1.25, 1.5} × (1/6) 上独立取值，
  再重归一化，全枚举 5⁶ = 15625 组（#10；ticket 定为 5 档）。
- **Dirichlet 补网**：200 次采样（ticket + 地图 standing preference 锁定；
  #10 决议原案为 2000，本图 standing preference 以 200 为准），α = 12
  （#10，每个 αᵢ = 2 × 六维数，均值 = 等权 1/6），覆盖网格外区域。
- **判据**（#10）：
  ① 扰动下总分点值**带宽 ≤ 0.05**（0–1 标尺）——每次打分必跑，随报告附
     「权重敏感性带宽」；
  ② 语料方向排序不翻转——多仓总分**排序**在扰动下稳定（同序位点值差
     ≥ 2×带宽 ⇒ 序位稳健；低于 2×带宽的序位标为「敏感」待补数据）。
- **护栏**（#10）：禁任何维度权重塌 0（塌 0 = 忽略一种独立失败模式，
  与 #4 矛盾）；网格档位 ×1/6 恒 > 0，Dirichlet 采样也钳制下限。

输出：{grid: {bandwidth, criterion_pass, sweep}, dirichlet: {...},
corpus: {...}}（见 sensitivity_analysis docstring）。
"""

from __future__ import annotations

import math
import random

from cognicode.score import DEFAULT_WEIGHTS, DIMENSIONS, renormalize, weighted_total

# 网格档位：每维 {0.5, 0.75, 1, 1.25, 1.5} × (1/6)（#10）
GRID_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5)

# Dirichlet 补网采样数（ticket + 地图 standing preference；#10 原案 2000 被覆盖）
DIRICHLET_SAMPLES = 200

# Dirichlet 浓度参数 α（#10）：每维 12，均值 = 12/72 = 1/6 = 等权
DIRICHLET_ALPHA = 12.0

# 权重下限钳制（防采样极端接近 0；护栏「禁零权重」的工程化）
_WEIGHT_MIN = 1e-6

# 判据 ①：总分点值带宽阈值（#10 钉死 ≤0.05，0–1 标尺）
BANDWIDTH_LIMIT = 0.05

# 判据 ② 的序位稳健阈值：同序位点值差 ≥ 2×带宽 ⇒ 排序稳健（#10 语义）
# 带宽为 0（退化）时该比值为 0，序位差 > 0 即视为稳健。
_ORDER_RATIO = 2.0


# ---------------------------------------------------------------------------
# 权重扰动生成
# ---------------------------------------------------------------------------


def _grid_combos() -> list[tuple[dict[str, float], dict[str, float]]]:
    """网格全枚举：返回 [(重归一化权重, 原始档位因子)]，顺序固定。"""
    base = 1.0 / 6.0
    combos: list[tuple[dict[str, float], dict[str, float]]] = []
    for idx in range(len(GRID_FACTORS) ** len(DIMENSIONS)):
        raw: dict[str, float] = {}
        factors: dict[str, float] = {}
        n = idx
        for d in DIMENSIONS:
            factors[d] = GRID_FACTORS[n % len(GRID_FACTORS)]
            raw[d] = factors[d] * base
            n //= len(GRID_FACTORS)
        combos.append((renormalize(raw), factors))
    return combos


def grid_weights() -> list[dict[str, float]]:
    """确定性网格全枚举：5⁶ = 15625 组重归一化权重（#10）。

    Returns:
        权重映射列表，每维 ∈ {0.5,0.75,1,1.25,1.5}×(1/6) 重归一化到和=1。
    """
    return [w for w, _ in _grid_combos()]


def grid_factors() -> list[dict[str, float]]:
    """网格全枚举的原始档位因子（与 grid_weights 同序一一对应）。"""
    return [f for _, f in _grid_combos()]


def _gamma(shape: float, scale: float, rng: random.Random) -> float:
    """标准 gamma(shape, scale) 采样：Ahrens–Dieter 整数 + Marsaglia–Tsang。

    shape < 1 用 Ahrens–Dieter 算法（接受-拒绝）补足，shape ≥ 1 用
    Marsaglia–Tsang 直接采样。纯 Python 实现，无 numpy/scipy 依赖。
    """
    if shape < 1.0:
        while True:
            u = rng.random()
            x = -math.log(1.0 - u) if u < 1.0 else 0.0
            if rng.random() <= (x ** (shape - 1.0)) * math.exp(-x):
                return x * scale
        # 该分支不可达（循环内 return）
    # shape >= 1：Marsaglia–Tsang（d = shape - 1/3, c = 1/sqrt(9d)）
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        while True:
            x = rng.gauss(0.0, 1.0)
            v = 1.0 + c * x
            if v > 0.0:
                break
        v3 = v * v * v
        u = rng.random()
        if u < 1.0 - 0.0331 * (x * x) ** 2:
            return d * v3 * scale
        if math.log(u) < 0.5 * x * x + d * (1.0 - v3 + math.log(v3)):
            return d * v3 * scale


def dirichlet_weights(
    n: int = DIRICHLET_SAMPLES,
    alpha: float = DIRICHLET_ALPHA,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> list[dict[str, float]]:
    """Dirichlet(α) 采样权重（补网格覆盖外的区域，#10）。

    Args:
        n: 采样数（默认 200）。
        alpha: 每维浓度 α（默认 12；均值 = 1/6 = 等权）。
        seed: 可选随机种子（可复现）。
        rng: 可选现成 Random 实例（与 seed 二选一）。

    Returns:
        n 组和=1 的权重映射（每维钳制 ≥ 1e-6 后重归一化，护栏禁零权重）。
    """
    if seed is not None and rng is None:
        rng = random.Random(seed)
    if rng is None:
        rng = random
    samples: list[dict[str, float]] = []
    for _ in range(n):
        draws = [max(_gamma(alpha, 1.0, rng), _WEIGHT_MIN) for _ in DIMENSIONS]
        samples.append(renormalize({d: v for d, v in zip(DIMENSIONS, draws)}))
    return samples


# ---------------------------------------------------------------------------
# 扰动评估
# ---------------------------------------------------------------------------


def total_bandwidth(
    dims: dict[str, float],
    weights: list[dict[str, float]],
) -> float:
    """一组权重下总分点值的带宽（max − min，#10 判据 ①）。

    Args:
        dims: 六维点值 {dimension: float}（未测维点值 None → 按 0）。
        weights: 扰动权重列表。

    Returns:
        带宽（0–1 标尺）。weights 为空 → 0.0。
    """
    pts = [total_point(dims, w) for w in weights]
    return (max(pts) - min(pts)) if pts else 0.0


def total_point(dims: dict[str, float], weights: dict[str, float]) -> float:
    """单组权重下的总分点值（未测维按 0 点值，#21 语义）。"""
    from cognicode.score import DimensionScore

    dd = {
        d: DimensionScore(point=dims.get(d) or 0.0, half_width=0.0)
        for d in DIMENSIONS
    }
    return weighted_total(dd, weights=weights).point


def _clamp_bandwidth(value: float) -> float:
    return max(0.0, min(1.0, value))


def grid_analysis(dims: dict[str, float]) -> dict:
    """网格全枚举 + 带宽判定（#10 判据 ①）。

    Returns:
        {
          "bandwidth": 带宽（0–1 标尺，裁剪到 [0,1]），
          "criterion_pass": bandwidth ≤ 0.05,
          "n_weights": 15625,
          "sweep": {dimension: {effect, low_tier_avg, high_tier_avg}} 每维
                   权重从最低档拉到最高档对总分点值的净影响（effect 正 =
                   提高该维权重拉高总分；单位 0–1 标尺）
        }
    """
    weights = grid_weights()
    factors = grid_factors()
    points = [total_point(dims, w) for w in weights]
    bandwidth = _clamp_bandwidth(max(points) - min(points))

    sweep: dict[str, dict] = {}
    for d in DIMENSIONS:
        # 按该维**原始档位因子**分组（每档恰含其余维全扫过的 5⁵ 个点值）
        per_tier: dict[float, list[float]] = {}
        for f, p in zip(factors, points):
            per_tier.setdefault(f[d], []).append(p)
        tiers = sorted(per_tier)
        lo_avg = sum(per_tier[tiers[0]]) / len(per_tier[tiers[0]])
        hi_avg = sum(per_tier[tiers[-1]]) / len(per_tier[tiers[-1]])
        sweep[d] = {
            "effect": round(hi_avg - lo_avg, 6),
            "low_tier_avg": round(lo_avg, 6),
            "high_tier_avg": round(hi_avg, 6),
        }

    return {
        "bandwidth": bandwidth,
        "criterion_pass": bandwidth <= BANDWIDTH_LIMIT,
        "n_weights": len(weights),
        "sweep": sweep,
    }


def dirichlet_analysis(
    dims: dict[str, float],
    n: int = DIRICHLET_SAMPLES,
    alpha: float = DIRICHLET_ALPHA,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Dirichlet 采样补网 + 带宽判定（#10 判据 ① 在网格外区域）。

    Returns:
        {
          "n_samples": n,
          "alpha": alpha,
          "seed": seed,
          "bandwidth": 采样集总分点值带宽（裁剪到 [0,1]），
          "criterion_pass": bandwidth ≤ 0.05
        }
    """
    weights = dirichlet_weights(n=n, alpha=alpha, seed=seed, rng=rng)
    points = [total_point(dims, w) for w in weights]
    bandwidth = _clamp_bandwidth(max(points) - min(points))
    return {
        "n_samples": n,
        "alpha": alpha,
        "seed": seed,
        "bandwidth": bandwidth,
        "criterion_pass": bandwidth <= BANDWIDTH_LIMIT,
    }


def corpus_direction(
    repo_dims: dict[str, dict[str, float]],
    weights: list[dict[str, float]] | None = None,
) -> dict:
    """语料方向排序稳定性（#10 判据 ②，实现后校准验证随报告输出）。

    方向翻转必须用**各仓六维点值**在扰动下重算总分再排序；只给总分是
    tautological（总分不随权重变，排序恒稳，无意义）。

    Args:
        repo_dims: {repo_name: {dimension: 点值}}（≥2 仓才有排序语义）。
        weights: 扰动权重列表；缺省 = 网格全枚举。

    Returns:
        {
          "repos": [repo_name]，按（等权）总分降序,
          "orders": {repo_name: {rank: 出现次数}} 每仓在扰动下每个名次的
                    出现次数（名次 1 = 最高分）,
          "stable": bool 全部相邻序位稳健（判据 ②）,
          "unstable_pairs": [[a, b, diff], ...] 序位差 < 2×带宽的相邻仓对
                            （diff = 等权总分差；这些对排序不稳健）
        }
    """
    if weights is None:
        weights = grid_weights()
    names = list(repo_dims)
    if len(names) < 2:
        return {
            "repos": names,
            "orders": {},
            "stable": False,
            "unstable_pairs": [],
            "note": "语料不足两仓，无法判方向排序稳定性（判据②需 ≥2 仓）",
        }

    def repo_point(repo: str, w: dict[str, float]) -> float:
        return total_point(repo_dims[repo], w)

    base_order = sorted(
        names, key=lambda n: repo_point(n, DEFAULT_WEIGHTS), reverse=True
    )

    # 每个扰动权重下的名次
    order_counts: dict[str, dict[int, int]] = {n: {} for n in names}
    for w in weights:
        ranked = sorted(names, key=lambda n: repo_point(n, w), reverse=True)
        for rank, n in enumerate(ranked, 1):
            order_counts[n][rank] = order_counts[n].get(rank, 0) + 1

    # 相邻序位对：等权总分差 vs 2×带宽
    base_points = {n: repo_point(n, DEFAULT_WEIGHTS) for n in names}
    bw = total_bandwidth_from_repos(repo_dims, weights)
    unstable: list[list] = []
    stable = True
    for a, b in zip(base_order, base_order[1:]):
        diff = base_points[a] - base_points[b]
        ok = diff > 0 if bw == 0 else diff >= _ORDER_RATIO * bw
        if not ok:
            stable = False
            unstable.append([a, b, round(diff, 6)])

    return {
        "repos": base_order,
        "orders": order_counts,
        "stable": stable,
        "unstable_pairs": unstable,
    }


def total_bandwidth_from_repos(
    repo_dims: dict[str, dict[str, float]],
    weights: list[dict[str, float]] | None = None,
) -> float:
    """语料各仓在扰动下总分带宽的上界（判据②的稳健参考量）。

    取各仓带宽的最大值：任一仓总分在扰动下漂移超过该值，跨仓排序的
    可信度才受威胁。空权重列表 → 0.0。
    """
    if weights is None:
        weights = grid_weights()
    if not weights:
        return 0.0
    return max(total_bandwidth(dims, weights) for dims in repo_dims.values())


def sensitivity_analysis(
    dims: dict[str, float],
    *,
    n_dirichlet: int = DIRICHLET_SAMPLES,
    seed: int | None = None,
    repo_dims: dict[str, dict[str, float]] | None = None,
) -> dict:
    """完整敏感性分析（#10 判据 ① + ②），纯解析、无 I/O。

    Args:
        dims: 六维点值 {dimension: float}（未测维 None → 按 0）。
        n_dirichlet: Dirichlet 补网采样数（默认 200）。
        seed: 随机种子（可复现；None → 系统熵）。
        repo_dims: 语料各仓六维点值 {repo: {dim: 点值}}；提供且 ≥2 仓 →
            判方向排序稳定性（判据 ②）；缺 → 不判（报告标「待语料」）。

    Returns:
        {
          "dimensions": dims（回显输入）,
          "grid": grid_analysis 结果,
          "dirichlet": dirichlet_analysis 结果,
          "corpus": corpus_direction 结果（或缺 → {"present": False}）
        }
    """
    g = grid_analysis(dims)
    d = dirichlet_analysis(dims, n=n_dirichlet, seed=seed)
    if repo_dims and len(repo_dims) >= 2:
        c = corpus_direction(repo_dims, weights=grid_weights())
    else:
        c = {"present": False}
    return {
        "dimensions": {d: dims.get(d) for d in DIMENSIONS},
        "grid": g,
        "dirichlet": d,
        "corpus": c,
    }
