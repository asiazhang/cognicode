"""CogniCode 薄 CLI 壳。

命令（地图 Notes 锁定的形态）：
- `cognicode scan <repo>`: 对仓库跑完整评估（内部调 pipeline 占位）
- `cognicode scan --offline <repo>`: 确定性链路，LLM 全关
- `cognicode report <run-id>`: 从运行目录 `.cognicode/<run-id>/` 出报告
- `cognicode --version`: 版本串，含 report-schema 版本

纯函数层已就位；scan 的 pipeline 本体在本图后续票（harness/生成/
静态提取）实现，这里先接壳并调用占位。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from cognicode import __version__
from cognicode.schema import REPORT_SCHEMA_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cognicode",
        description="AI-native code readiness assessment and scoring tool.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__} (report-schema {REPORT_SCHEMA_VERSION})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="评估一个仓库（完整管线）")
    scan.add_argument("repo", help="仓库路径或 git URL")
    scan.add_argument(
        "--offline",
        action="store_true",
        help="确定性链路：LLM 全关（仅静态 + 探测）",
    )

    report = sub.add_parser("report", help="从运行目录生成报告")
    report.add_argument("run_id", help="运行 id（对应 .cognicode/<run-id>/）")

    return parser


def _cmd_scan(args: argparse.Namespace) -> int:
    """扫描仓库：静态提取（#18）+ 探测（#19）+ 演示任务（#19）。"""
    mode = "offline" if args.offline else "full"
    repo_path = Path(args.repo)
    if not repo_path.is_dir():
        print(f"[cognicode] 错误：{args.repo!r} 不是目录", file=sys.stderr)
        return 1

    run_id = f"scan-{int(time.time())}"
    run_dir = Path.cwd() / ".cognicode" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # 记录被测仓库路径（report 的模块深度判定需要读仓库源码）
    (run_dir / "run.json").write_text(
        json.dumps({"repo": str(repo_path.resolve()), "mode": mode},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    from cognicode.static_signals import static_json

    data = static_json(repo_path)
    static_file = run_dir / "static.json"
    static_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    dims = data["dimensions"]
    summary = "  ".join(
        f"{d}={v['score']:.2f}" for d, v in sorted(dims.items())
    )
    print(
        f"[cognicode] scan（{mode}）已完成静态提取："
        f"{repo_path} → {static_file}\n  {summary}"
    )

    # ---- 环境探测（#19）：定位构建/测试命令，逐条执行，记录 exit code ----
    from cognicode.harness import ProbeRunner
    from cognicode.pi_executor import PiExecutor

    executor = PiExecutor(ext_dir=Path(__file__).resolve().parent / "ext")
    runner = ProbeRunner(executor=executor)
    probe = runner.run(repo_path)
    probe_file = run_dir / "probe.json"
    probe_file.write_text(
        json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    verdict = "成功" if probe["success"] else "失败"
    print(
        f"[cognicode] 环境探测：{verdict}（构建/测试命令逐条执行）"
        f"\n  exit_codes={probe['exit_codes']}"
        f"\n  notes={probe['notes'][-1] if probe['notes'] else ''}"
        f"\n  → {probe_file}"
    )

    # ---- 任务生成（#20）：探测成功才生成（Q17：探测全灭 → 整体降级）----
    # 三段式：tree-sitter 解析 → LLM 模板合成（offline 走确定性模板）→
    # 执行式验证过滤。判卷（F2P/P2P、位置匹配）归 #21。
    if probe["success"]:
        from cognicode.pipeline import generate_task_suite

        llm = None  # LLM 合成配置独立固定；offline 走确定性模板（Q17）
        if mode != "offline":
            # full 模式：生成走 llm 接口（配置独立固定），失败兜底确定性模板
            from cognicode.llm import PiLlmClient

            llm = PiLlmClient()

        suite = generate_task_suite(repo_path, llm=llm)
        tasks_file = run_dir / "tasks.json"
        tasks_file.write_text(
            json.dumps(
                {
                    "counts": {
                        k: len(v) for k, v in suite.items() if k != "dropped"
                    },
                    "dropped": suite["dropped"],
                    "tasks": [
                        {
                            "id": t.id,
                            "kind": t.kind,
                            "prompt": t.prompt,
                            "ground_truth": t.ground_truth,
                            "k": t.k,
                            "injection": getattr(t, "injection", None),
                            "bug": getattr(t, "bug", None),
                            "acceptance_files": getattr(t, "acceptance_files", []),
                            "guard_files": getattr(t, "guard_files", []),
                        }
                        for t in (
                            suite["search"] + suite["locate"] + suite["modify"]
                        )
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"[cognicode] 任务生成（{mode}）："
            f"检索 {len(suite['search'])} / 定位 {len(suite['locate'])} / "
            f"修改 {len(suite['modify'])}；砍掉 {len(suite['dropped'])} 个"
            f"\n  → {tasks_file}"
        )

        # ---- 单任务执行收 diff（#19 链路验证：harness 已在 #19 落地）----
        from cognicode.harness import WorktreeManager, run_task

        mgr = WorktreeManager(
            source_repo=repo_path,
            worktrees_dir=Path.cwd() / ".cognicode" / run_id / "worktrees",
        )
        demo = suite["search"] + suite["locate"] + suite["modify"]
        if demo:
            result = run_task(
                executor=executor,
                worktree_mgr=mgr,
                prompt=demo[0].prompt,
                task_id=demo[0].id,
                run_dir=run_dir,
                timeout_s=900,
            )
            if result is not None:
                print(
                    f"[cognicode] 演示任务（{demo[0].id}）：ok={result.ok} "
                    f"exit={result.exit_code} turns={result.stats.num_turns} "
                    f"tokens={result.stats.total_tokens}"
                    f"\n  trace={result.trace_file}"
                    f"\n  diff={result.diff[:200]!r}..."
                )
            else:
                print(
                    "[cognicode] 演示任务：worktree 失败（fail_env）",
                    file=sys.stderr,
                )
    else:
        print(
            f"[cognicode] 探测失败：任务生成降级跳过（Q17）——"
            f"本次仅静态面 + 探测（环境可用性低分信号，非评估失败）"
        )

    if mode != "offline":
        print(
            f"[cognicode] 动态判卷（F2P/P2P、位置匹配）尚未实现："
            f"任务已生成并落盘 tasks.json，判卷归 #21"
        )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """从运行目录生成报告（#21）：聚合 + 落盘 cognicode-report.md。

    输入：.cognicode/<run-id>/（static.json / verdicts.json / tasks.json /
    traces/diffs / probe.json）。verdicts.json 缺失（未判卷）→ 聚合层按
    无动态样本处理（静态面仍出分）；探测失败 → 整体降级（只出静态分）。
    """
    import json as _json

    run_id = args.run_id
    run_dir = Path.cwd() / ".cognicode" / run_id
    if not run_dir.is_dir():
        print(f"[cognicode] 错误：运行目录不存在 {run_dir}", file=sys.stderr)
        return 1

    # ---- 静态信号（#18 产物）----
    static_file = run_dir / "static.json"
    if not static_file.exists():
        print(f"[cognicode] 错误：缺少 static.json（运行未完成静态提取）", file=sys.stderr)
        return 1
    static = _json.loads(static_file.read_text(encoding="utf-8"))

    # ---- 判卷结果（#21 verdicts.json；缺失 = 未判卷）----
    verdicts = {"tasks": []}
    vfile = run_dir / "verdicts.json"
    if vfile.exists():
        verdicts = _json.loads(vfile.read_text(encoding="utf-8"))

    # ---- 探测（#19 产物）：探测失败 → 动态面未测降级 ----
    dynamic_measured = True
    probe_file = run_dir / "probe.json"
    if probe_file.exists():
        probe = _json.loads(probe_file.read_text(encoding="utf-8"))
        dynamic_measured = bool(probe.get("success", True))

    # ---- 效率中位数（success 运行，来自 verdicts 或 traces；缺 = 未采集）----
    medians = None
    med_file = run_dir / "medians.json"
    if med_file.exists():
        medians = _json.loads(med_file.read_text(encoding="utf-8"))

    # ---- 聚合（#21）----
    from cognicode.aggregate import aggregate_run

    # 语料各仓六维点值（敏感性判据②方向稳定性；缺 → 报告标「待语料」）
    repo_dims = None
    corpus_file = run_dir / "corpus.json"
    if corpus_file.exists():
        repo_dims = _json.loads(corpus_file.read_text(encoding="utf-8"))

    agg = aggregate_run(
        verdicts,
        static=static,
        medians=medians,
        dynamic_measured=dynamic_measured,
        run_id=run_id,
        repo_dims=repo_dims,
    )

    # ---- 归因管线（#23：三档「确定性优先、LLM 兜底」）----
    from cognicode.attribution import failure_sources, run_attribution

    f = failure_sources(verdicts)
    dim_points = {
        d: (agg["dimensions"].get(d) or {}).get("point") for d in (
            "solvability", "safety", "efficiency",
            "navigability", "buildability", "diagnosability",
        )
    }
    eff = (agg["dimensions"].get("efficiency") or {}).get("details")

    # 专属归因信号（测试覆盖缺口 / 单文件规模）：未落盘（提取器留给后续票）
    # → None → 只走产分信号档 + LLM 档
    attr_signals = None
    attr_file = run_dir / "attribution_signals.json"
    if attr_file.exists():
        attr_signals = _json.loads(attr_file.read_text(encoding="utf-8"))

    llm = None
    if dynamic_measured and not _run_offline(run_dir):
        from cognicode.llm import PiLlmClient

        llm = PiLlmClient()

    traces = _load_traces(run_dir)
    attr = run_attribution(
        f, static.get("signals", {}),
        llm=llm,
        attribution_signals=attr_signals,
        dim_points=dim_points,
        efficiency=eff,
        traces=traces,
    )

    # ---- 模块深度（#23/#14：LLM 判 deep/shallow 分布，重构参考，不进产分）----
    md = None
    repo_path = _repo_path_of(run_dir)
    if llm is not None and repo_path is not None:
        from cognicode.module_depth import run_module_depth

        md = run_module_depth(repo_path, llm=llm, max_modules=20)

    agg["attribution"] = {
        "suggestions": attr["suggestions"],
        "llm_groups": attr["llm_groups"],
        "llm_calls": attr["llm_calls"],
    }
    if md is not None:
        agg["module_depth"] = md

    agg_file = run_dir / "aggregate.json"
    agg_file.write_text(_json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    snap_file = run_dir / "snapshot.json"
    snap_file.write_text(
        _json.dumps(agg["snapshot"], ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 报告（#12）：终端摘要 + 全量落盘 cognicode-report.md ----
    from cognicode.report import render_report, render_terminal_summary

    signals = static.get("signals", {})
    print(render_terminal_summary(agg, static_signals=signals))
    print()
    report_file = Path.cwd() / "cognicode-report.md"
    report_file.write_text(
        render_report(agg, static_signals=signals),
        encoding="utf-8",
    )
    print(f"[cognicode] 报告已落盘：{report_file}（report-schema {agg['snapshot'].get('report-schema')}）")
    return 0


def _load_traces(run_dir: Path) -> dict[str, str]:
    """读运行目录 traces/*.jsonl → {task_id: 轨迹文本}（LLM 证据包用）。

    失败/缺目录 → 空 dict（LLM 归因的轨迹切片为空，不炸管线）。
    """
    traces: dict[str, str] = {}
    trace_dir = run_dir / "traces"
    if not trace_dir.is_dir():
        return traces
    for p in sorted(trace_dir.glob("*.jsonl")):
        try:
            traces[p.stem] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return traces


def _run_offline(run_dir: Path) -> bool:
    """本次运行是否 offline（LLM 全关：归因走确定性档、模块深度关）。"""
    rf = run_dir / "run.json"
    if rf.exists():
        try:
            import json as _j

            return _j.loads(rf.read_text(encoding="utf-8")).get("mode") == "offline"
        except Exception:
            pass
    return False


def _repo_path_of(run_dir: Path) -> Path | None:
    """run.json 里记录的被测仓库路径（模块深度判定读源码用）。"""
    rf = run_dir / "run.json"
    if not rf.exists():
        return None
    try:
        import json as _j

        p = _j.loads(rf.read_text(encoding="utf-8")).get("repo")
        if p:
            pp = Path(p)
            return pp if pp.is_dir() else None
    except Exception:
        pass
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "report":
        return _cmd_report(args)
    return 2  # 不可达（required=True）


if __name__ == "__main__":
    sys.exit(main())
