"""git 热点提取器（#59 新写，#67 增补）：90 天窗口 per-file 改动次数。

「拖慢后续开发」场景轴的数据来源（地图 #63：第二轴 = git 热点，「每次
迭代都被踩到的债」优先于「沉睡区的债」）。#64 原型的热点系手工测算
（`git log --since="3 months ago"`，无可复用资产），本提取器固化该口径。

**确定性锚点 = HEAD commit 日期**（不是运行时的 now）：同基准 commit
重跑，窗口起点一致、工件字节稳定（#57 幂等验收的提取层前提）。#64
手工口径以运行日为锚（"3 months ago"），两口径对样例仓实测：HEAD 锚
163 commits vs 手工口径 153——量级一致（票面验收允许方法差异）。

口径细节：
- 窗口：`HEAD 日期 - 90 天` 起（含端点日），git log `--since` 语义；
- 计数：窗口内**改动过该文件的 commit 数**（`git log --name-only`，
  含 merge commit 带的文件）；
- 域：全部文件（不只 Sources——doc-rot 的沉睡带判定需要文档文件的
  热点，README 三件套的 34 次矩阵重复也是文档文件）；
- 非 git 仓库 / 无 commit：`degraded` 标注 + 空计数（big-file 的
  hotspot 位会记 null=未知，不炸管线）。

产物（hotspot.json data 载荷）：
- `window_days` / `since` / `head`：窗口口径自描述（消费方可校验锚点）；
- `files`：文件 → 改动次数映射（仅含窗口内至少一次改动的文件）；
- `total_commits`：窗口内 commit 总数（报告叙事用，如 #64 的 153）。
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

WINDOW_DAYS = 90


def _run_git(root: Path, *args: str) -> str | None:
    """跑 git，失败（非仓库/无 git）返回 None（不炸管线）。"""
    try:
        r = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return None
        return r.stdout
    except Exception:
        return None


def hotspot_payload(repo: str | Path) -> dict:
    """`hotspot.json` 的 data 载荷（hotspot 提取器产出）。"""
    root = Path(repo)
    head = _run_git(root, "log", "-1", "--format=%H %cI")
    if head is None:
        return {
            "degraded": "not a git repo (no commits / git unavailable)",
            "window_days": WINDOW_DAYS,
            "files": {},
            "total_commits": 0,
        }
    head_hash, head_date = head.strip().split(maxsplit=1)
    # %cI 形如 2026-09-15T07:41:42+00:00 → 日期运算用 datetime
    d = datetime.fromisoformat(head_date)
    since = (d - timedelta(days=WINDOW_DAYS)).isoformat()
    # 传完整时间戳（非裸日期）：git 按本地时区解析裸日期，跨时区跑同一
    # 仓库会漂一天；ISO 时间戳带 tz offset，解析无歧义
    names = _run_git(root, "log", f"--since={since}", "--name-only",
                     "--pretty=format:")
    commits = _run_git(root, "log", f"--since={since}", "--format=%H")

    files: dict[str, int] = {}
    if names:
        for line in names.splitlines():
            if line.strip():
                files[line.strip()] = files.get(line.strip(), 0) + 1

    return {
        "window_days": WINDOW_DAYS,
        "since": since,
        "head": head_hash,
        "total_commits": len([l for l in (commits or "").splitlines()
                              if l.strip()]),
        "files": files,
    }
