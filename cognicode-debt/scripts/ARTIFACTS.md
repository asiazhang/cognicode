# 债扫描工件目录协议（`​.cognicode/debt-scan/`）

> 票：[脚本骨架 #58](https://github.com/asiazhang/cognicode/issues/58) · 父票：[#57](https://github.com/asiazhang/cognicode/issues/57)
> 状态：**草约**——终版字段集属地图 [#63](https://github.com/asiazhang/cognicode/issues/63) 雾区（「终版 JSON 契约」），本协议只锁工件位与容错纪律，字段集随 #59/#60/#61 落地细化。

## 1. 定位与原则

确定性提取层（`cognicode-debt/scripts/`）对被扫仓库产出的全部工件，落盘到**被扫仓库根**的 `.cognicode/debt-scan/`。

- **确定性**：同一 commit 重复扫描，工件字节稳定（提取层零 LLM；LLM 语义输出发生在管线后段，不落本目录）。
- **per-extractor 容错**：单个提取器失败只**缩窄**当趟产出（该提取器工件记 `status: "failed"` + 错误记录），不炸整趟扫描。某类工件缺失时，消费方按「该族无候选」处理。
- **自描述**：每个工件带提取器名（`extractor`）与状态（`status: "ok" | "failed"`），失败时附错误摘要。
- **被扫仓库视角零侵入**：只写 `.cognicode/debt-scan/`；渲染器输出（HTML）落**临时目录**（#66 决议），不写被扫仓库。

## 2. 工件位

```
.cognicode/debt-scan/
├── scan.json          # 扫描元信息（本目录的入口索引）
├── symbols.json       # 符号提取（symbols 提取器）
├── static_signals.json# 8 静态信号（static-signals 提取器）
├── probe.json         # 环境探测定位面（probe 提取器）
├── hotspot.json       # git 热点（hotspot 提取器；提取器本体归 #59）
├── debt.json          # 债项清单（LLM 写手产出；管线后段，本骨架预留位）
└── report.html        # 渲染产物（渲染器产出；临时目录，本骨架预留位）
```

未实现的提取器（hotspot、debt 清单、report 渲染）不落空文件，只是位在协议中预留（见 §4）。

## 3. 工件信封（通用形状）

每个提取器工件是一个 JSON 对象，信封字段统一：

```jsonc
{
  "schema": "debt-scan/<工件名>@1",   // 工件形状版本（协议演进用）
  "extractor": "<提取器名>",          // 见 §4 提取器清单
  "status": "ok" | "failed",
  "repo": "<被扫仓库根绝对路径>",
  "data": { ... },                   // status=ok 时的载荷（形状随提取器定）
  "error": "<错误摘要>"              // status=failed 时必填
}
```

- `status: "failed"` 时 `data` 为 `null`。消费方（SKILL.md 管线 / 渲染器）必须先验信封再看 `data`。
- 日期时间字段一律 ISO 8601 UTC 字符串。

## 4. 提取器清单

| 提取器名 | 工件 | 状态 | 归属票 |
|---|---|---|---|
| `symbols` | `symbols.json` | 本票实现 | #58 |
| `static-signals` | `static_signals.json` | 本票实现 | #58 |
| `probe` | `probe.json` | 本票实现 | #58 |
| `hotspot` | `hotspot.json` | 预留位，提取器本体待写 | #59 |
| （LLM 写手） | `debt.json` | 预留位，管线后段（LLM 产出，非确定性提取） | #60 |
| （渲染器） | `report.html` | 预留位，读 `debt.json` 出 HTML，落临时目录 | #59/#61 |

## 5. 单工件最小样例

`symbols.json`（载荷形状与 `Symbol` 字段一致，见 `scripts/lib/symbols.py`）：

```jsonc
{
  "schema": "debt-scan/symbols@1",
  "extractor": "symbols",
  "status": "ok",
  "repo": "/path/to/scanned-repo",
  "data": {
    "symbols": [
      { "kind": "function", "name": "fetch_by_id", "file": "src/cart.py", "line": 3 }
    ]
  }
}
```

`static_signals.json` / `probe.json` 载荷形状复用既有模块输出（`static_json` / `locate_probe_commands`），字段以随行测试为准。

## 6. 目录排除口径（债检测语义）

与任务生成服务的旧口径（排除 test/docs）不同，债检测**要扫测试**：

- `symbols` 提取器：移除 test/spec 目录排除（`tests/`、`__tests__/`、`test_*.py` 等照常入符号面——test-gap 检测需要测试文件符号作分子）；保留 vendor/node_modules/dist/build 等依赖与产物目录排除，`docs/doc` 排除保留（非源码）。
- `static-signals` / `probe`：口径不变（信号面本就含测试可发现性；探测定位的是仓库声明的构建/测试命令）。
- `module_depth` 判定协议资产（G 族复用）：`collect_modules` 排除口径**不复用**——其排除 test/docs 的语义面向判定面而非符号面，G 族消费 `symbols.json` 时自行过滤。

## 7. 工具约定

- 入口：`uv run cognicode-debt/scripts/scan.py <repo> [--extractors symbols,static-signals,probe] [--help]`。
- 脚本零第三方依赖可直接运行的用 stdlib 运行；需 tree-sitter 的提取器在**本仓库**内以 `uv run --extra` / dev 环境运行（迁移脚本不自带依赖；独立分发的依赖管理属 #59）。
- 重复运行幂等覆盖（同基准 commit 两次扫描 diff 稳定的验收在父票 #57）。

## 8. 关联

- 终版 JSON 契约（含 debt.json 字段集、ID 生成方式）：地图 [#63](https://github.com/asiazhang/cognicode/issues/63) 雾区，管线实施时定。
- `debt.json` 的 ID 锚点三形态（符号锚 / 文档行区间锚 / 多文件簇锚）：[修订 #67](https://github.com/asiazhang/cognicode/issues/67)。
