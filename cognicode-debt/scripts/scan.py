"""债扫描入口（#58）：确定性提取 → `.cognicode/debt-scan/` 工件落盘。

用法（单 skill 目录自包含，uv run 入口）：

    uv run cognicode-debt/scripts/scan.py <repo> [--extractors symbols,static-signals,probe]

产物与协议见 `ARTIFACTS.md`（工件位、信封形状、per-extractor 容错纪律）。
单提取器失败只缩窄产出（该工件 status=failed + 错误记录），不炸整趟扫描；
至少一个提取器产出工件时退出码 0，全部失败（或 repo 无效）退出码 1。

确定性纪律：工件内容与运行时间戳无关（时间戳只进 scan.json 的 started/
ended 元信息，不入提取器工件），同 commit 重跑 diff 稳定。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# 使 `uv run cognicode-debt/scripts/scan.py` 与 pytest 两种调用形态都能
# 导入 lib（前者 sys.path[0] 是 scripts/，后者是仓库根）
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from lib.probe import locate_probe_commands          # noqa: E402
from lib.static_signals import static_json           # noqa: E402
from lib.symbols import symbols_payload              # noqa: E402

# 提取器注册表：名称 → (载荷函数, 工件文件名)。顺序即默认执行顺序。
# hotspot 提取器归 #59；debt.json / report.html 是管线后段预留位（ARTIFACTS.md §4）。
EXTRACTORS: dict[str, tuple] = {
    "symbols": (symbols_payload, "symbols.json"),
    "static-signals": (static_json, "static_signals.json"),
    "probe": (
        lambda repo: _probe_payload(repo),
        "probe.json",
    ),
}

OUTPUT_DIR = ".cognicode/debt-scan"


def _probe_payload(repo: Path) -> dict:
    """probe 工件载荷：命令定位面（确定性、无执行）。"""
    commands, notes = locate_probe_commands(repo)
    return {
        "commands": [
            {
                "kind": c.kind,
                "name": c.name,
                "command": c.command,
                "source_file": str(c.source_file) if c.source_file else None,
            }
            for c in commands
        ],
        "notes": notes,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_envelope(path: Path, extractor: str, repo: str,
                    data: dict | None, error: str | None) -> None:
    """按工件信封协议（ARTIFACTS.md §3）落盘一个工件。"""
    envelope = {
        "schema": f"debt-scan/{path.stem}@1",
        "extractor": extractor,
        "status": "ok" if error is None else "failed",
        "repo": repo,
        "data": data,
    }
    if error is not None:
        envelope["error"] = error
    path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def scan(repo: str | Path, extractors: list[str] | None = None,
         quiet: bool = False) -> int:
    """跑一趟债扫描：提取 → 落盘工件。

    Args:
        repo: 被扫仓库根目录。
        extractors: 要跑的提取器名清单（None = 全部注册项）。
        quiet: 不打进度行。

    Returns:
        进程退出码：0 = 至少一个提取器产出工件；1 = repo 无效或全部失败。
    """
    root = Path(repo).resolve()
    if not root.is_dir():
        print(f"[debt-scan] 错误：{repo!r} 不是目录", file=sys.stderr)
        return 1
    started = _utcnow_iso()

    names = list(extractors) if extractors else list(EXTRACTORS)
    unknown = [n for n in names if n not in EXTRACTORS]
    if unknown:
        print(
            f"[debt-scan] 错误：未知提取器 {unknown}（可选：{list(EXTRACTORS)}）",
            file=sys.stderr,
        )
        return 1

    out_dir = root / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for name in names:
        fn, filename = EXTRACTORS[name]
        artifact = out_dir / filename
        if not quiet:
            print(f"[debt-scan] {name} → {OUTPUT_DIR}/{filename} ...")
        try:
            data = fn(root)
            _write_envelope(artifact, name, str(root), data, None)
            results.append({"extractor": name, "artifact": filename,
                            "status": "ok"})
        except Exception as exc:  # per-extractor 容错：缩窄不炸
            _write_envelope(artifact, name, str(root), None,
                            f"{type(exc).__name__}: {exc}")
            if not quiet:
                print(f"[debt-scan]   提取器 {name} 失败（已记录，继续）："
                      f"{type(exc).__name__}: {exc}", file=sys.stderr)
            results.append({"extractor": name, "artifact": filename,
                            "status": "failed",
                            "error": f"{type(exc).__name__}: {exc}"})

    # scan.json：本目录入口索引（含时间戳等元信息；提取器工件本身确定性）
    (out_dir / "scan.json").write_text(
        json.dumps(
            {
                "tool": "cognicode-debt/scripts/scan.py",
                "protocol": "debt-scan@1",
                "repo": str(root),
                "started": started,
                "ended": _utcnow_iso(),
                "extractors": results,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    ok = sum(1 for r in results if r["status"] == "ok")
    if not quiet:
        print(f"[debt-scan] 完成：{ok}/{len(results)} 个提取器成功 → {out_dir}")
    return 0 if ok > 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="debt-scan",
        description="债检测确定性提取：symbols / static-signals / probe → "
                    ".cognicode/debt-scan/（协议见 ARTIFACTS.md）",
    )
    parser.add_argument("repo", help="被扫仓库根目录路径")
    parser.add_argument(
        "--extractors",
        default=None,
        help=f"逗号分隔的提取器清单（默认全部：{','.join(EXTRACTORS)}）",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="不打印进度行"
    )
    args = parser.parse_args(argv)

    extractors = (
        [n.strip() for n in args.extractors.split(",") if n.strip()]
        if args.extractors else None
    )
    try:
        return scan(args.repo, extractors=extractors, quiet=args.quiet)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
