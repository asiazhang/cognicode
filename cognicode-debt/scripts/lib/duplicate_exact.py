"""重复检测 exact 档（#59 新写）：逐字重复簇，MD5 多文件簇锚。

判据权威来源：criteria/A-structural.md §2——确定性档 = **工具集成**
（jscpd/PMD CPD 类，「算法不自研」），near 档阈值留选型参数。本模块
是集成缝的 MVP 实现：

- **exact 档自产**（整文件逐字相同 → MD5 簇）：MD5 是零外部依赖的
  确定性事实，文件级 exact 簇不需要 jscpd 的 token 化——样例仓的
  实锤簇（design/v6+ v8 bundle 的 jsx/css 逐字重复、样例 DEBT.md 点
  名的 b654f7b5/3112f277/fd1bf176 三簇）全部是文件级逐字相同，MD5
  即可复现；
- **near 档 / 块级（函数粒度）重复不自研**：集成缝 = `tool_config`
  字段（near 档阈值参数占位）+ 消费约定（外置工具的块级输出未来按
  同一簇形状并轨）。exact 文件级簇先行，供 A 族子代理「簇内已分叉/
  无权威声明」的判定起步。

**MD5 簇锚 = 销账主键构成依据**（#66/#67 决议：多文件簇锚参与销账
ID 匹配）：簇锚 = `md5:<前 12 位>`，同一簇（同一批字节）重跑稳定。

排除口径：与 duplicate-code 确定性档同口径（判据原文）——vendored/
生成文件/@generated 标记/lockfile；**大小写下限**（小于阈值的文件
入簇只产噪音：样例仓 Assets/ 图标文件的合法重复被 _MIN_BYTES 滤掉
大头，但默认口径如实报告，由 LLM 语义档标注降级——判据原文「语言
惯用样板由 LLM 档标注降级」同理，白名单不自建）。

产物（duplicate_exact.json data 载荷）：
- `clusters`：exact 簇清单，每簇 = 簇锚（md5:xxxx）、副本文件清单、
  每副本字节数；
- `tool_config`：集成缝占位——near 档选型与阈值参数（`near: null`
  = 未接外置工具）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from lib.symbols import _EXCLUDE_DIR_TOKENS, file_language

# 入簇大小下限（字节）：小于此的文件（空文件、一行配置）不构成
# 「知识存在多份」的信号。校准：样例仓实锤簇最小 ~3KB。
_MIN_BYTES = 512

# 簇锚 MD5 截断长度（销账 ID 匹配用；12 hex = 48 bit，仓内簇数下无碰撞）
_ANCHOR_HEX = 12


def _is_excluded(rel: Path) -> bool:
    """与 duplicate-code 确定性档同口径的目录/文件排除。"""
    if any(part in _EXCLUDE_DIR_TOKENS for part in rel.parts):
        return True
    # design/ 等设计资产目录不排除（样例仓实锤簇就在 design/）
    return False


def duplicate_exact_payload(repo: str | Path) -> dict:
    """`duplicate_exact.json` 的 data 载荷（duplicate-exact 提取器产出）。

    只扫可解析源码域（`file_language` 非空——与 symbols/big-file 同域，
    md5 簇锚的销账语义挂在「源码/设计资产」上；二进制文件不入簇）。
    """
    root = Path(repo)
    by_hash: dict[str, list[dict]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if file_language(rel) is None:
            continue
        if _is_excluded(rel):
            continue
        try:
            raw = p.read_bytes()
        except Exception:
            continue
        if len(raw) < _MIN_BYTES:
            continue
        digest = hashlib.md5(raw).hexdigest()
        by_hash.setdefault(digest, []).append(
            {"file": rel.as_posix(), "bytes": len(raw)}
        )

    clusters = [
        {
            "anchor": f"md5:{digest[:_ANCHOR_HEX]}",
            "md5": digest,
            "copies": copies,
        }
        for digest, copies in sorted(by_hash.items())
        if len(copies) > 1
    ]

    return {
        "min_bytes": _MIN_BYTES,
        "clusters": clusters,
        # 集成缝：near 档与块级重复归外置工具（jscpd/PMD CPD 类），
        # 选型未定（票面：阈值留选型参数），先占位。
        "tool_config": {
            "exact": "builtin file-level md5",
            "near": None,  # 外置工具接入后填 {tool, threshold, ...}
        },
    }
