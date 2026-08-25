"""报告 schema 版本（#12 锁定）。

报告头摘要行 + 运行环境快照都带 `report-schema` 版本号 + 权重版本
（#10 等权 1/6 版本化）。跨轮比较先校验 schema 兼容——不同 schema 下的
分数不得直接比大小。

版本语义：主版本不兼容（分数不可比）、次版本兼容（可比较）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cognicode.score import WEIGHT_VERSION

# 当前报告 schema 版本。主版本 = 分数结构兼容性；次版本 = 呈现/字段增补。
REPORT_SCHEMA_VERSION = "1.0"

# 允许的版本形态：主.次
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class SchemaVersion:
    """解析后的 schema 版本。"""

    major: int
    minor: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


def parse_schema_version(version: str) -> SchemaVersion:
    """解析 schema 版本串，非法形态抛 ValueError。"""
    m = _VERSION_RE.match(version)
    if not m:
        raise ValueError(
            f"非法 schema 版本 {version!r}；期望形态 <major>.<minor>"
        )
    return SchemaVersion(major=int(m.group(1)), minor=int(m.group(2)))


def schema_compatible(a: str, b: str) -> bool:
    """跨轮比较前校验 schema 兼容：主版本相同即可比较。

    主版本不同 → 分数结构不兼容，不得直接比大小。
    次版本差异允许（字段增补/呈现变化不伤可比性）。
    """
    return parse_schema_version(a).major == parse_schema_version(b).major


def report_schema_marker() -> dict[str, str]:
    """运行环境快照里的 schema 标识：report-schema 版本 + 权重版本。"""
    return {
        "report-schema": REPORT_SCHEMA_VERSION,
        "weights-version": WEIGHT_VERSION,
    }
