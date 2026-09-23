# D 族判据：依赖与环境债（config-drift；dep-stale / lockfile-drift 留册带过）

> Part of [Wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39) · 来源：[#52](https://github.com/asiazhang/cognicode/issues/52) 判据细则 + [#40](https://github.com/asiazhang/cognicode/issues/40) 类型清单 + [debt-types.md](../../docs/research/debt-types.md)
> 本文件是 D 族分族子代理的完整作业指令。跨族共享约定（证据包 16K 预算、回传 JSON schema、严重度带定档流程）见 [SKILL.md](../SKILL.md)，此处不重复。

> 逐类型人类向详解（含实例）见 [rules/config-drift.md](rules/config-drift.md)（D 族独苗）
## 0. 族概览

| slug | 名称 | 覆盖 | 检测档 | rubric 主轴 | 预排 |
|---|---|---|---|---|---|
| `dep-stale` | 依赖陈旧（含依赖文档消失） | **留册不覆盖** | — | — | 高 |
| `lockfile-drift` | 锁文件漂移 | **留册不覆盖** | — | — | 中 |
| `config-drift` | 配置漂移 | **D 族独苗，覆盖** | 确定性（候选生成）+ LLM（路径评估器） | 冷启动阻断度 | 中 |

**族级判断背景**：验证回路三轴叙事（可启动性 / 保真度 / 延迟）——债的利息以 agent 的验证速度计价（AI 让写代码变便宜，瓶颈后移到验证与理解）。三轴→类型映射：可启动性 → config-drift + build-entry-unclear（E 族），保真度 → fidelity-debt（E 族），延迟 → build-entry-unclear 信号档。本族只承载 config-drift 一类。

## 1. config-drift（D 族独苗）

### 判据

= **验证回路执行路径上的配置可达性**。病因（gitignore 的 `.env`）对 agent 不可见，报错与代码错误同形，归因路径被系统性污染（环境可用性 + 可诊断性）。

**路径收口为收录门槛**（非排序维度）：只有落在验证回路（构建 + 测试 + 本地运行，见 CONTEXT.md 环境可用性词条）执行路径上被读的配置才进检测面；纯生产/部署路径的配置键无 agent 失败形态，**不报**。防换皮正向案例：传统 config lint 报所有未定义键（人类运维视角），本类型只报验证回路路径上的（agent 视角）。

### 两端夹检测

- **一端 = 读取痕迹**：env 无默认值读取 + 显式配置文件键。**CLI 参数是接口不是环境前提、代码内常量不是配置，均不收。**
- **另一端 = 可见配置源六项**：① 配置模板/默认值文件 ② CI workflow ③ agent 上下文文档 ④ README 配置段 ⑤ compose/基建文件 ⑥（六项以 CONTEXT.md / #52 决议 2 为准清点）。compose/基建文件入源清单使「本地 PG 起不来」场景可表达：读取痕迹有 PG 连接配置、六源全无 → 实例。
- 病因本身不可见，只能从两端对撞。各语言 env 读取语法表留雾区（确定性脚本技术选型）。

### 三档信号

| 档 | 检测 | 判定 |
|---|---|---|
| **C1 读而无源** | 确定性候选生成（存在性确证）+ LLM 路径评估器 | 评估器判「是否在验证回路执行路径上」定收录（同 test-shape 候选评估器结构），标置信度；**有默认值的读取不报**（不炸，弱信号不占报告面） |
| **C2 多源矛盾** | 确定性档提取 (键, 值, 源) 三元组 | 值不同不自动判债，LLM 裁「同语义环境下是否互斥」——localhost vs staging-db 为正当环境差异，同环境两个 DEBUG 才是矛盾；同值多源不报（多份同值的痛感是变更安全机制，归 duplicate-code 家族，不在本类型预支） |
| **C3 文档配置断言** | README 等声称的配置 ↔ 代码读取事实双向比对 | 按失败模式裁不按载体裁：配置断言的失败落点是环境可用性不是可解性，故归本类型不归 doc-rot；README 只划「配置断言」一个切面，长文档其他信号仍留雾区 |

### 实例粒度

配置项级。

### rubric 与严重度带提议

主轴 = **冷启动阻断度**（只锁方向）：无源必需键（直接炸，agent 无法将 KeyError 归因于配置缺失）＞ 多源矛盾（悄悄错，污染后续行为）＞ 文档误导（排障绕路，通常不炸）。子代理沿主轴提议严重度带，不终裁。

## 2. 留册类型（一行带过）

| slug | 为何不覆盖 | 捡回条件 |
|---|---|---|
| `dep-stale` | web search 普及使利息降为效率损耗（失败形态降级而非消失）；版本比对与上游文档可达性信号设计存档于 #52 | 二期实证发现无搜索 agent 痛感显著 |
| `lockfile-drift` | 检测商品化 + `npm ci` 类工具矛盾时硬失败且报错清晰，agent 可诊断性不差；唯一真值表述（依赖版本知识多份载体未声明权威）存档备用 | 无捡回条件 |

## 3. 子代理执行协议

- **候选来源**：确定性档 = env 读取痕迹提取（无默认值读取）+ 六源配置键提取 + (键, 值, 源) 三元组比对 + README 配置断言提取；LLM 档 = C1 路径评估器（验证回路收录判定）、C2 互斥裁定。
- **中间产物消费**：本族不消费 test-scan / module-graph；读取痕迹提取依赖代码扫描（各语言 env 读取语法表留雾区）。
- **族内分野规则**：C3 与 doc-rot 的分界 = 失败模式落点（环境可用性归本类型、可解性归 doc-rot）；C2 同值多源不报（让渡 duplicate-code 家族）；compose 缺失信号让渡 build-entry-unclear E4（不重复挂）。
- **证据包组装**：每候选附读取点代码行 + 相关源文件相应段（或「六源全无」的检索空白证据），总量 16K 预算内，超预算降采样并在 rationale 声明。
- **输出 schema**：`{slug, location, confidence, rationale, fix_suggestion}` + 提议严重度带。C1 无源候选的 fix_suggestion 须指出应补进六源中的哪一源。
