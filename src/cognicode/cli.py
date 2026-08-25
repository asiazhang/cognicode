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
import sys

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
    # pipeline 本体在后续票实现（harness/生成/静态提取）；这里先接壳。
    mode = "offline" if args.offline else "full"
    print(
        f"[cognicode] scan 管线（{mode}）尚未实现："
        f"对 {args.repo!r} 的评估由后续构建票落地"
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
