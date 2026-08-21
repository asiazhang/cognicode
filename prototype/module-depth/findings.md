# 模块深度 LLM 判定：可复现性与区分度原型（wayfinder #14）

**弃用原型（throwaway）**：本文件与 `judge_depth.py`、`results.jsonl` 是为回答
#14 的一次性实验产物，不是生产代码。结论是**方法学决策**，代码不进主分支。

## 问题

LLM 对「模块 deep/shallow」的判定是否可复现、能否在试点仓库集上拉开区分度？
（#13 的门槛：一致性达标 →「模块深度」进产分信号；否则降为归因信号。）

## 协议

- 单元：**文件级模块**（语言无关、最接近 #13 的「seam=代码里真实存在的接口」；
  Python 模块=文件、PHP 类=文件、Lua 模块=文件）。排除 test/spec/docs/vendor 目录。
- 每仓哈希采样 10 个模块；每模块构造一个 prompt（模块 id + 源码头 16K 字符）；
  temperature=1.0，每模型独立判定 **m=5** 次。
- 模型：`deepseek-v4-flash-ioa`、`glm-5.3-ioa`（同一 tencent-copilot 网关）。
- 三指标：同模块同模型一致性（within-model agreement）、跨模型一致性、
  deep 占比区分度。

## 结果（n=10 模块/仓，m=5 次/模块）

### 同仓同模块 N 次一致性 —— 高，不是问题

| 仓库 | deepseek | glm |
|---|---|---|
| Melissa-Core | 0.96 | 0.94 |
| nbnbk | 0.98 | 0.96 |
| umi-dva-antd-mobile | 0.98 | 0.94 |
| kindlepdfviewer | 0.94 | 0.84 |

→ #13 担心的「采样方差」**不成立**：单模型对自己的判定高度稳定。

### 跨模型一致性 —— 崩塌（致命）

| 仓库 | 同模块两模型 mode 一致率 |
|---|---|
| Melissa-Core | 0.50 |
| nbnbk | 0.70 |
| umi-dva-antd-mobile | 0.70 |
| kindlepdfviewer | 0.40 |

→ 同一段代码，两个模型给出相反判定 30%–60%。deepseek 把几乎所有模块判
shallow（deep 占比 ~0%），glm 判 30%–50% deep。

### deep 占比区分度 —— 不存在（或噪声级）

| 仓库（预期） | deepseek deep% | glm deep% |
|---|---|---|
| Melissa-Core（温和） | 0.00 | 0.50 |
| nbnbk（脏乱） | 0.00 | 0.30 |
| umi-dva-antd-mobile（前端遗留） | 0.00 | 0.30 |
| kindlepdfviewer（环境敌对） | 0.00 | 0.50 |

- deepseek：全仓 deep≈0%，**零区分度**。
- glm：Melissa 与 nbnbk 方向「碰巧」对（0.50 > 0.30），但差仅 2 个模块、
  且 kindle（环境敌对）与 Melissa（温和）同为 0.50，方向在语料内不成立。

## 结论（待 human 确认）

**「模块深度」不达标 → 降为归因信号，不进产分。** 失败模式是**跨模型不一致**
（模型间对「deep」的判定基率与语义不统一），而非 #13 预想的采样方差——多次采样
救不了模型间系统性分歧。这与 #11 的教训同构：测量对象在语义上不稳定时，静态信号
不可入分。

## 已知 confound（不影响主结论）

- 仅 2 个模型、同网关；文件级单元未必是 #13 心中「module」的全部语义；
  二元强制选择 + temperature=1.0；n=10/仓偏小。这些都可能改变幅度，但**不会
  把 0.40–0.70 的跨模型一致率抬到入分阈值**。

## 资产

- `judge_depth.py`：判定脚本（含协议与语言无关的文件级模块分组）。
- `results.jsonl`：400 条原始判定（4 仓 × 10 模块 × 2 模型 × 5 次）。
- `summary-file.json`：按（仓、模块、模型）折叠的一致性汇总。
