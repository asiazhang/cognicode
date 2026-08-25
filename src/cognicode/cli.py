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

    # ---- 演示任务（#19 验收：能独立跑通一次探测 + 单任务执行收 diff）----
    # 任务生成管线归 #20；这里用固定探测 prompt 验证链路
    if probe["success"]:
        from cognicode.harness import WorktreeManager, run_task

        mgr = WorktreeManager(
            source_repo=repo_path,
            worktrees_dir=Path.cwd() / ".cognicode" / run_id / "worktrees",
        )
        result = run_task(
            executor=executor,
            worktree_mgr=mgr,
            prompt=(
                "对当前仓库执行构建与测试，报告结果。"
                "若构建或测试命令存在，运行它们并总结输出。"
            ),
            task_id="probe-demo",
            run_dir=run_dir,
            timeout_s=900,
        )
        if result is not None:
            print(
                f"[cognicode] 演示任务：ok={result.ok} "
                f"exit={result.exit_code} turns={result.stats.num_turns} "
                f"tokens={result.stats.total_tokens}"
                f"\n  trace={result.trace_file}"
                f"\n  diff={result.diff[:200]!r}..."
            )
        else:
            print("[cognicode] 演示任务：worktree 失败（fail_env）", file=sys.stderr)

    if mode != "offline":
        print(
            f"[cognicode] 动态测量（生成/判卷）尚未实现："
            f"本次仅静态面 + 探测（#18/#19），后续票落地"
        )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    print(
        f"[cognicode] report 生成尚未实现："
        f"运行 {args.run_id!r} 的报告由后续构建票落地"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "report":
        return _cmd_report(args)
    return 2  # 不可达（required=True）


if __name__ == "__main__":
    sys.exit(main())
