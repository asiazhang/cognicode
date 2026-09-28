"""债检测确定性提取层库（cognicode-debt/scripts/lib/）。

从 `src/cognicode/` 复用资产收缩而来（#58，asset-inventory 盘点定复用面）：

- `symbols`：tree-sitter 符号提取（资产 #1）——目录排除口径已按债检测
  语义修正（**要扫测试**，test-gap 检测需要测试文件符号）。
- `static_signals`：8 静态信号（资产 #2）——口径不变。
- `probe`：环境探测定位面（资产 #5 降级形态）——纯定位、无执行。
- `module_depth`：模块深度判定协议（资产 #3）——`collect_modules` 确定性
  收集与 LLM deep/shallow 判定协议，G 族（shallow-module）复用；注意其
  排除口径面向**判定面**（排除 test/docs），与 symbols 的债检测口径不同，
  见各模块 docstring。

本目录自包含（#58 验收）：不 import `src/cognicode/`，也不依赖仓库根的
pyproject——tree-sitter 由消费环境提供（`uv run` 于本仓库时可用）。

工件落盘协议（`.cognicode/debt-scan/`）见 `../ARTIFACTS.md`。
"""
