"""JSON→HTML 确定性渲染器入口（#67 预留，实现归 #59/#61）。

读 `.cognicode/debt-scan/debt.json`（LLM 写手产出的债项清单）出 HTML
报告，零 LLM 参与。渲染产物落**临时目录**即开即看，不写被扫仓库
（#66 决议）。

本文件在 #58 只占协议入口位（ARTIFACTS.md §4 预留行）：入口签名与
落盘纪律先行锁定，渲染本体随 debt.json 契约（地图 #63 雾区）落地。
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    print(
        "[render] 渲染器未实现（归 #59/#61；debt.json 契约见地图 #63 雾区）",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
