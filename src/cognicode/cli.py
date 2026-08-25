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
    """扫描仓库：当前先落地静态提取（#18），动态管线由后续票实现。"""
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
    if mode != "offline":
        print(
            f"[cognicode] 动态测量（harness/生成/判卷）尚未实现："
            f"本次仅静态面（#18），后续票落地"
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
