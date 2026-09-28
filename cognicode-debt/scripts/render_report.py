"""JSON→HTML 确定性渲染器（#61 tracer bullet 落地）。

读 `.cognicode/debt-scan/debt.json`（LLM 写手产出的债项清单）出 HTML
报告，零 LLM 参与。渲染产物落**临时目录**即开即看，不写被扫仓库
（#66 决议）。

确定性要求（SKILL.md 渲染器调用协议）：同 JSON 两次渲染**逐字节一致**
——渲染器不引入时钟、随机数或 dict 迭代序依赖；所有排序显式给定。

报告形态（#66 评审决议，R2/R3）：
- 证据呈现器：无「推荐先修」/Top recommendation 式行动指令；
- 严重度带分组：高带展开，中/低带默认折叠（<details>）；
- SVG 散点全景（严重度 × 近 90 天改动频率）；
- 类型分区：本场景重点类型（#65 强证据带 ∩ AI 迭代场景相关性）置顶
  展开，其余类型随后；
- 严重度/成本档判据写进图例（R2 裁决外化）。

外部资源（Tailwind CDN）沿 improve-codebase-architecture HTML 报告先例：
渲染期不拉取网络（纯 HTML 生成），浏览器打开时加载。

输入：`render_report.py <被扫仓库根目录>`
退出码：0 成功；2 debt.json 缺失或非法（不产生降级输出）。
"""

from __future__ import annotations

import html
import json
import sys
import tempfile
from pathlib import Path

# 本场景重点类型（地图 #63 种子决策 9：#65 强证据带 ∩ AI 迭代场景相关性，
# 于 #61 落地为渲染器常量——「新增 agent 高频迭代踩到的类型」优先呈现）。
# 强证据带（#65）：doc-rot、agent-doc-missing、build-entry-unclear、
# monolith-file、test-gap、implicit-contract、naming-debt；其中与
# 「AI 快速迭代累积债」场景直接相关的前六类置顶。
SCENARIO_FOCUS_SLUGS = frozenset({
    "doc-rot", "agent-doc-missing", "build-entry-unclear",
    "monolith-file", "test-gap", "implicit-contract",
})

_SLUG_ZH = {
    "doc-rot": "文档腐烂", "agent-doc-missing": "代理文档缺失/撒谎",
    "build-entry-unclear": "构建入口不明", "monolith-file": "巨石文件",
    "test-gap": "测试缺口", "implicit-contract": "隐式契约",
    "duplicate-code": "重复代码", "test-rot": "测试腐烂",
    "flaky-test": "脆弱测试", "test-shape": "测试形状债",
    "fidelity-debt": "保真度债", "config-drift": "配置漂移",
    "oral-tradition": "口头传统", "naming-debt": "命名债",
    "shallow-module": "浅模块债", "misplaced-seam": "错位 seam 债",
    "hypothetical-seam": "伪 seam 债",
}

_BAND_ORDER = {"high": 0, "medium": 1, "low": 2}
_BAND_ZH = {"high": "高", "medium": "中", "low": "低"}
_COST_ZH = {
    "very-low": "极低", "low": "低", "medium": "中", "high": "高",
}
_EVIDENCE_ZH = {"confirmed": "确证", "risk": "风险"}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def load_debt_json(repo: Path) -> dict:
    """读 debt.json 并做清单级机械校验（SKILL.md §3.5 的复用）。"""
    debt_path = repo / ".cognicode" / "debt-scan" / "debt.json"
    if not debt_path.is_file():
        print(f"[render] 缺少 {debt_path}（先跑管线前三段）", file=sys.stderr)
        raise SystemExit(2)
    try:
        doc = json.loads(debt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[render] debt.json 解析失败：{e}", file=sys.stderr)
        raise SystemExit(2)
    for field in ("schema", "repo", "base_commit", "scanned_at", "items"):
        if field not in doc:
            print(f"[render] debt.json 顶层缺字段：{field}", file=sys.stderr)
            raise SystemExit(2)
    ids: set[str] = set()
    for i, item in enumerate(doc["items"]):
        for field in (
            "id", "slug", "slugs", "location", "severity_band",
            "evidence_class", "confidence", "rationale", "evidence",
            "fix_suggestion", "fix_cost_band", "hotspot_90d",
        ):
            if field not in item:
                print(f"[render] items[{i}] 缺字段：{field}", file=sys.stderr)
                raise SystemExit(2)
        if item["severity_band"] not in _BAND_ORDER:
            raise SystemExit(2)
        if item["id"] in ids:
            print(f"[render] id 重复：{item['id']}", file=sys.stderr)
            raise SystemExit(2)
        ids.add(item["id"])
    # 排序纪律假设校验（§3.3）：乱序告警但不重排（渲染器是消费方不是写手）
    key = lambda it: (
        _BAND_ORDER[it["severity_band"]], it["slugs"][0], it["location"]
    )
    if [key(it) for it in doc["items"]] != sorted(key(it) for it in doc["items"]):
        print("[render] 警告：items 未按 §3.3 全序排列", file=sys.stderr)
    return doc


# ── SVG 散点全景（确定性：输入仅 items 的 band/hotspot/slug） ──────────

def _scatter_svg(items: list[dict]) -> str:
    pts: list[tuple[int, int, int, str, str]] = []
    # x 轴：近 90 天改动次数（无热点数据的沉睡债聚在左缘）
    # y 轴：严重度带（带内按 slug 稳定微移防重叠）
    lane = {"high": 0, "medium": 1, "low": 2}
    seen: dict[tuple[int, int], int] = {}
    for it in items:
        h = it.get("hotspot_90d") or 0
        x = 90 + min(h, 34) * (760 - 90) / 34.0
        y = {0: 60.0, 1: 205.0, 2: 340.0}[lane[it["severity_band"]]]
        k = (int(x), lane[it["severity_band"]])
        seen[k] = seen.get(k, 0) + 1
        y += (seen[k] - 1) * 16
        r = 8 + min(h, 24) * 0.25
        label = it["slugs"][0] + " · " + (str(h) + " 次改动" if h else "沉睡")
        pts.append((x, y, r, label, it["severity_band"]))
    fill = {"high": "#b45309", "medium": "#78716c", "low": "#a8a29e"}
    circles = "".join(
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{fill[b]}">'
        f'<title>{_esc(t)}</title></circle>'
        for x, y, r, t, b in pts
    )
    return (
        '<svg viewBox="0 0 860 420" class="w-full min-w-[680px] h-auto" role="img" '
        'aria-label="债项全景：严重度 × 近 90 天改动频率">'
        '<rect x="70" y="10" width="390" height="185" fill="#fef3c7" opacity="0.55"/>'
        '<text x="455" y="30" text-anchor="end" fill="#b45309" font-size="11" '
        'class="mono">高严重度带</text>'
        '<line x1="70" y1="10" x2="70" y2="400" stroke="#d6d3d1" stroke-width="1.5"/>'
        '<line x1="70" y1="400" x2="850" y2="400" stroke="#d6d3d1" stroke-width="1.5"/>'
        '<text x="30" y="205" transform="rotate(-90 30 205)" text-anchor="middle" '
        'fill="#78716c" font-size="12">严重度</text>'
        '<text x="460" y="420" text-anchor="middle" fill="#78716c" font-size="12">'
        '近 90 天被改次数 →</text>'
        '<text x="26" y="60" fill="#b45309" font-size="11">高</text>'
        '<text x="26" y="205" fill="#57534e" font-size="11">中</text>'
        '<text x="26" y="340" fill="#a8a29e" font-size="11">低</text>'
        + circles + "</svg>"
    )


# ── 卡片 ─────────────────────────────────────────────────────────────

def _card(it: dict) -> str:
    slugs = " + ".join(
        f"{_SLUG_ZH.get(s, s)} <span class=\"mono\">{s}</span>" for s in it["slugs"]
    )
    hotspot = it.get("hotspot_90d")
    hotspot_html = (
        f'近 90 天改动 {hotspot} 次' if hotspot else '近 90 天零改动（沉睡）'
    )
    cost = _COST_ZH.get(it["fix_cost_band"], it["fix_cost_band"])
    return f'''<article class="rounded-xl border border-stone-200 bg-white p-6 space-y-3">
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
    <h3 class="serif text-lg font-bold">{_esc(it['id'])}</h3>
    <span class="text-xs text-slate-500 mono">{slugs} · {_EVIDENCE_ZH.get(it['evidence_class'], it['evidence_class'])} · 置信度{it['confidence']}</span>
  </div>
  <div class="flex flex-wrap gap-1.5 text-[11px] mono">
    <span class="bg-stone-100 border border-stone-200 rounded px-2 py-0.5">{hotspot_html}</span>
    <span class="bg-stone-100 border border-stone-200 rounded px-2 py-0.5">修复成本 {cost}</span>
  </div>
  <div class="mono text-xs text-slate-500">{_esc(it['location'])}</div>
  <div class="text-sm leading-7 text-slate-700 space-y-2">
    <p><strong class="text-slate-900">为什么是债：</strong>{_esc(it['rationale'])}</p>
    <p><strong class="text-slate-900">证据：</strong><span class="mono text-xs">{_esc(it['evidence'])}</span></p>
    <p><strong class="text-slate-900">怎么修：</strong>{_esc(it['fix_suggestion'])}</p>
  </div>
</article>'''


def _band_section(band: str, items: list[dict], collapsed: bool) -> str:
    zh = _BAND_ZH[band]
    focus = [it for it in items if it["slugs"][0] in SCENARIO_FOCUS_SLUGS]
    rest = [it for it in items if it["slugs"][0] not in SCENARIO_FOCUS_SLUGS]
    inner_focus = "".join(_card(it) for it in focus)
    inner_rest = "".join(_card(it) for it in rest)
    head = (
        f'<h2 class="serif text-2xl font-bold border-b border-stone-200 pb-2">'
        f'{zh}严重度 <span class="text-sm font-normal text-slate-500 mono">'
        f'{len(items)} 项</span></h2>'
    )
    body = ""
    if focus:
        body += (
            '<div class="pt-2"><h3 class="text-sm font-bold uppercase '
            'tracking-wider text-slate-500">本场景重点类型 <span class="mono '
            'text-[11px] font-normal text-slate-400">强证据带 ∩ AI 迭代场景'
            '</span></h3></div><div class="space-y-4">' + inner_focus + "</div>"
        )
    if rest:
        label = "其余类型" if focus else "全部类型"
        body += (
            f'<div class="pt-2"><h3 class="text-sm font-bold uppercase '
            f'tracking-wider text-slate-500">{label}</h3></div>'
            f'<div class="space-y-4">{inner_rest}</div>'
        )
    details_attrs = ' open' if not collapsed else ''
    return (
        f'<section class="space-y-4"><details{details_attrs} class="group">'
        f'<summary class="flex items-center gap-2 cursor-pointer select-none '
        f'py-2">{head}</summary><div class="space-y-4 pt-2">{body}</div>'
        f"</details></section>"
    )


def render_html(doc: dict, repo_name: str) -> str:
    items = doc["items"]
    n_band = {
        b: sum(1 for it in items if it["severity_band"] == b)
        for b in ("high", "medium", "low")
    }
    skipped = doc.get("families_skipped") or []
    skipped_note = "、".join(skipped) if skipped else "无"
    sections = "".join(
        _band_section(b, [it for it in items if it["severity_band"] == b],
                      collapsed=(b != "high"))
        for b in ("high", "medium", "low") if n_band[b]
    )
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>技术债报告 · {repo_name}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  .serif {{ font-family: Georgia, "Noto Serif SC", serif; }}
  .mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; }}
  details > summary {{ list-style: none; cursor: pointer; }}
  details > summary::-webkit-details-marker {{ display: none; }}
</style>
</head>
<body class="bg-stone-50 text-slate-900 font-sans">
<main class="max-w-5xl mx-auto px-6 py-12 space-y-12">

  <header class="space-y-4">
    <div class="flex items-baseline justify-between flex-wrap gap-2">
      <h1 class="serif text-3xl font-bold">技术债报告 · <span class="mono text-2xl">{repo_name}</span></h1>
      <div class="text-sm text-slate-500">基准 <span class="mono">{_esc(doc['base_commit'][:7])}</span> · cognicode 扫描</div>
    </div>
    <div class="text-xs text-slate-500 border-y border-stone-200 py-2 leading-6">
      <strong class="text-slate-600">判据图例</strong> · 严重度 = 违反后果类型（静默错结果 ＞ 随机红绿 ＞ 摸索成本），结合证据等级与热点；
      修复成本 = 动作类型学（高 = 新模块边界/跨文件结构改动；中 = 单文件内重构；低 = 文件级小改；极低 = ≤3 行）。
      证据等级：确证 = 可复现静态实锤；风险 = 静态反模式/LLM 推断，未动态验证。
      未覆盖族：{skipped_note}。销账：修复后重跑扫描，条目按 ID 消失；git 历史 + diff 即审计轨迹。
    </div>
  </header>

  <section class="space-y-3">
    <div class="flex items-baseline gap-3">
      <h2 class="serif text-xl font-bold">债项全景：严重度 × 近 90 天改动频率</h2>
      <span class="text-xs text-slate-500">每个点是一项债；悬停查看改动次数；点的大小随热度增大</span>
    </div>
    <div class="rounded-lg border border-stone-200 bg-white p-4 overflow-x-auto">
      {_scatter_svg(items)}
      <div class="flex flex-wrap gap-4 mt-3 text-xs text-slate-500">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-[#b45309] inline-block"></span>高严重度（{n_band['high']} 项）</span>
        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#78716c] inline-block"></span>中严重度（{n_band['medium']} 项）</span>
        <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#a8a29e] inline-block"></span>低严重度（{n_band['low']} 项）</span>
      </div>
    </div>
  </section>

  {sections}

  <footer class="border-t border-stone-200 pt-6 text-xs leading-5 text-slate-400">
    <p>共 {len(items)} 项（高 {n_band['high']} · 中 {n_band['medium']} · 低 {n_band['low']}）。清单基准：仓库内 <span class="mono">.cognicode/debt-scan/debt.json</span>（销账与审计基准）；本 HTML 为其确定性渲染，不构成行动指令。</p>
  </footer>

</main>
</body>
</html>
'''


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("用法: render_report.py <被扫仓库根目录>", file=sys.stderr)
        return 2
    repo = Path(args[0]).resolve()
    doc = load_debt_json(repo)
    out_html = render_html(doc, repo.name)
    out_dir = Path(tempfile.mkdtemp(prefix="cognicode-debt-report-"))
    out_path = out_dir / f"{repo.name}-debt-report.html"
    out_path.write_text(out_html, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
