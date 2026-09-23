"""CogniCode 薄 CLI 壳。

重定位（wayfinder #47 清理）后的残留形态：动态测量/报告管线已删，
仅静态提取保留。CLI 最终形态待 skill 结构票（#42）定夺——本壳只为
pyproject 入口不断裂而存在。

- `cognicode scan <repo>`: 静态信号提取（复用线，static_signals）
- `cognicode --version`: 版本串，含 report-schema 版本
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

    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _cmd_scan(args)
    return 2  # 不可达（required=True）


if __name__ == "__main__":
    sys.exit(main())
