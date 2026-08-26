# 归因管线与模块深度（#23）

> 票：[实现归因管线与模块深度](https://github.com/asiazhang/cognicode/issues/23)
> 决策：`#15`（归因到建议的管线与边界）、`#7`（静态信号集与归因层形态）、
> `#8`（LLM 约束与可验证性）、`#12`（报告呈现）、`#14`（模块深度降为归因信号）
> 分支：`prototype/pi-schema`

## 职责

把**失败样本 → 改进建议**的映射做成三档「确定性优先、LLM 兜底」管线
（`attribution.py`），并把**模块深度**（LLM 判 deep/shallow 分布）做成
可导航性静态面的归因信号模块（`module_depth.py`，ADR-0004：不进产分）。

两模块都是**纯函数 + 注入 LLM**：确定性档无 I/O、无 LLM；LLM 档经
`LLMClient` 接口注入（`llm.py`），offline（`llm=None`）时归因走确定性档、
模块深度关闭（地图 Notes 锁定）。

## 模块

| 模块 | 职责 |
|---|---|
| `attribution.py` | 归因管线：失败样本 → (维度×失败模式) 聚合 → 确定性模板 / LLM 综合归因 → 排序建议 |
| `module_depth.py` | 模块深度：文件级模块收集 + LLM 判 deep/shallow + 重构参考清单（不进产分） |
| `report.py`（扩展） | 建议条渲染失败任务引用 + 来源标签；报告后半渲染模块深度小节 |
| `cli.py`（扩展） | `report` 命令接入归因 + 模块深度（offline 关 LLM 档） |
| `llm.py`（扩展） | `PiLlmClient` 改单发 `-p --mode json`（RPC 长驻在本机 headless 不产 assistant 轮，实测） |

## 归因管线（attribution.py）

### 失败样本 → (维度 × 失败模式) 聚合（#15 §1/§5/§6）

- 检索 → 可导航性；定位 → 可诊断性；探测 → 环境可用性。
- 修改按判卷拆分：**F2P 未过 = 可解性**；**F2P 过但 P2P 未过 = 变更安全性**
  （判卷数据带 `runs[].f2p/p2p` 明细时逐条归类；无明细时 fail_incorrect 归可解性）。
- **fail_budget 归可解性**（#15 §1：超时是「解不出」的真实信号）。
- fail_env 剔除（#6），不产生归因候选。
- **m≥1 即产生候选**（#15 §3：不设硬阈值）；聚合单元 = (维度×失败模式)，
  同任务同模式合并计数（同根因去重）。

### 三档（#15 §2/§7/§8）

1. **产分信号命中**（可导航性/环境可用性静态信号低分）→ 确定性模板，
   锚定该信号，失败样本作为「预期方向的实证佐证」并入（不单独出条）。
2. **专属归因信号命中**（变更安全性 = 测试覆盖缺口；效率 = 单文件规模）
   → 确定性模板。效率走**独立低分驱动路径**（#15 §8：效率无失败样本，
   只由百分位低触发）。
3. **无静态信号维度**（可解性/可诊断性）或静态面合格却动态失败 → **LLM
   锚定维度综合归因**，输入 = 结构化证据包（判卷 + 轨迹确定性切片 +
   静态快照，不含任务原文），输出结构化 JSON，非法丢弃（#8 约束 c）。

### 排序（#8 §8）

确定性键为主（维度分最低优先 → 信号档位最低优先 → 影响面失败数多优先），
LLM 建议同档内按 `llm_rank` 重排。

### 失败任务引用（#12/#15）

`<类别> <m>/<k>（失败模式）`，m = 失败任务数（至少一次失败即计），
k = 该类别任务总数；如「检索 2/2 失败（解出失败；超时）」。

## 模块深度（module_depth.py）

- 单元 = **文件级模块**（语言无关；复用 `prototype/module-depth` 的
  `collect` 思路）；排除 test/spec/docs/vendor/隐藏目录；跳过平凡文件（<5 行）。
- 判定 = LLM 结构化 JSON（module_id + label），提示词与原型
  `judge_depth.py` 同源（deep/shallow 定义 + 模块 id + 源码头 16K 字符）。
- 非法输出重试后放弃（None）；判定不确定性是**特性**（ADR-0004：
  不强校验、不要求跨模型对齐、不要求重跑稳定）。
- offline（`llm=None`）→ `{enabled: false}`（模块深度关闭）。
- 输出 `distribution`（deep/shallow/unjudged）+ shallow 模块重构建议
  （合并/加深，参考性），**不进产分**。

## CLI 接入

`cognicode report <run-id>`：

1. 读 `static.json` / `verdicts.json` / `probe.json` / `medians.json` /
   `traces/*.jsonl` / `run.json`（扫描时记录被测仓库路径 + offline 标记）。
2. `aggregate_run` 出六维分（#21 原逻辑不变）。
3. `failure_sources` + `run_attribution`：offline → 确定性档；
   full → 调 `PiLlmClient` 归因 + 模块深度（最多 20 模块，冒烟限量）。
4. `agg["attribution"]` / `agg["module_depth"]` 并入 aggregate.json；
   报告渲染失败任务引用 + 来源标签 + 模块深度小节。

专属归因信号（`attribution_signals.json`，测试覆盖缺口 / 单文件规模）的
**提取器未在本票实现**（#23 只做管线；提取留给后续票）——未落盘时归因
只走产分信号档 + LLM 档，不炸管线。

## 验证

- 单测：`test_attribution.py`（23）+ `test_module_depth.py`（10）+
  报告/CLI 集成（+4/+3），全仓 316 全绿。
- 真仓冒烟（nbnbk）：确定性档离线出模板建议（含失败任务引用）；
  LLM 档出 solvability/diagnosability/navigability 综合归因 +
  模块深度 20 模块判定（deep 4 / shallow 16）落报告。
- 已知坑（实测）：pi 0.84.3 RPC 长驻模式在本机 headless 不产出
  assistant 轮（`message_end` 后即退）；`PiLlmClient` 改用单发
  `-p --mode json`（`message_end` 带最终文本）。
