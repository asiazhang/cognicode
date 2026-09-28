# 20 债类型对 AI 协作伤害的证据分级（类型级校准）

> 票：[研究：20 债类型对 AI 协作伤害的证据分级（类型级校准）#65](https://github.com/asiazhang/cognicode/issues/65) · 地图：[#63](https://github.com/asiazhang/cognicode/issues/63)
> 输入：[debt-types.md](./debt-types.md)（20 类型清单）、[debt-taxonomy.md](./debt-taxonomy.md)（#45）、[ai-dev-pain-points.md](./ai-dev-pain-points.md) / [ai-dev-pain-points-ds.md](./ai-dev-pain-points-ds.md)（#48 双模型研究）、[ai-dev-pain-points-synthesis.md](./ai-dev-pain-points-synthesis.md)、六族判据文件（cognicode-debt/criteria/）
> 效力：**类型级证据校准**（地图 #63 种子决策 3：不引外部实例级数据）。产出每类型「对 agent 伤害」的证据强度分级，供 rubric 主轴与严重度带预排校准。不改变收录判定（收录判据是「能否重述为 agent 失败形态」，与伤害证据强度正交）。

## 摘要（一屏版）

对 20 个债类型逐一检索业界实证（2024–2026 语料）后，证据分布**极不均匀**，且与预排并不对齐：

- **强证据带（业界直接实证过该失败形态）**：doc-rot、agent-doc-missing、monolith-file、build-entry-unclear、test-gap、implicit-contract、naming-debt。新发现的直接证据包括：过时文档受控实验（单变量操纵下 agent 成功率从 94–100% 崩塌至 0–32%，误导率 68–100%，且**模型能力不提供抵抗**）；环境引导基准（SOTA agent 仓库搭建成功率仅 34–62%，三种系统性失败模式全部映射到 build-entry-unclear / config-drift 的判据设计）；以及九类失败模式分类学中 agent 失败的**最大单一类别恰是「理解失败」**——不是代码写不出来，是被仓库的状态带偏。
- **间接证据带（人类侧强证据 + 机制平移）**：duplicate-code、test-rot、fidelity-debt、config-drift、flaky-test、misplaced-seam。人类侧证据强（克隆增长 10 倍、变更耦合与缺陷正相关、SQLite/PG 类环境分叉的经典工程史），但「agent 受损」尚无直接测量的研究。
- **仅推演带（方法论自建）**：oral-tradition、test-shape、shallow-module、hypothetical-seam——四个类型是本方法论的判断轴创新（存在性候选、假保护分型、上下文性价比、假可换信号），业界只有机制级旁证（context rot、agent 从不改测试结构等）。
- **留册带（留册不覆盖，证据与 MVP 决策互证）**：dead-code、dep-stale、lockfile-drift、vendored-dep。
- 预排上调候选 3 个（doc-rot→高加强、naming-debt 低→中、config-drift 中→高），下调候选 1 个（implicit-contract 高→中，实验证据指向「有 doc 就不查」比「契约未声明」伤害更大）。

一个贯穿性的反直觉发现：**文档债族（C 族）拿到的直接实验证据比代码结构债更强**——业界受控实验证明「给 agent 一份自信的过时文档」比「什么都不给」更糟（agent 停止自行验证），这直接支撑本方法论「误导 > 缺失」的 rubric 主轴方向，也提示 C 族的 LLM 检测档值得投入。

---

## 一、方法与证据分级标尺

每类型按四级分类，判据是「agent（LLM/coding agent）在该失败形态上的直接测量证据」：

| 级 | 标记 | 判据 |
|---|---|---|
| 强证据 | **[强]** | 存在针对 agent 的受控实验/大样本轨迹分析/基准，直接测量该类型导致的 agent 失败 |
| 间接证据 | **[间接]** | 人类侧有强实证 + 对 agent 的作用机制有共识（或 agent 侧只有轶事级/小样本证据），可平移但幅度未知 |
| 仅推演 | **[推演]** | 无 agent 侧实证；伤害机制是本方法论从失败模式轴推演的（判断轴创新所在） |
| 留册 | **[留册]** | 留册不覆盖类型——MVP 决策已包含证据判断（检测商品化/利息降级/低频），本票与其互证 |

外部来源分四档沿用 #48 DS 版标注法：[RCT]（受控实验）、[数据]（大规模遥测/调查）、[论文]（同行评审或预印本经验研究）、[一手]（一线工程报告）。既有材料（#45/#48）只做类型级重读，不重复引用其原始数字；本票新引的外部证据全部给出链接。

类型清单 20 个（debt-types.md 基准，#53 后为 21 类型、新口径计 20）：A 族 dead-code / duplicate-code / naming-debt；B 族 test-gap / test-rot / flaky-test / test-shape；C 族 doc-rot / oral-tradition / agent-doc-missing；D 族 dep-stale / lockfile-drift / config-drift；E+F 族 build-entry-unclear / monolith-file / implicit-contract / fidelity-debt / vendored-dep；G 族 shallow-module / misplaced-seam / hypothetical-seam。

---

## 二、本票新引入的外部证据（类型级重读用）

既有研究（#45/#48）已覆盖：Sourcegraph CodeScaleBench 五种失败模式、Beyond Resolution Rates（9,374 轨迹）、ETH AGENTS.md 实验 vs Meta 反例、METR RCT、GitClear 克隆增长、Anthropic 40 万会话、How Coding Agents Fail Their Users（20,574 会话）。本票补充检索新引入四组证据：

1. **过时文档对 agent 的受控实验（本票最强新证据）**：单变量操纵文档准确性（代码不变、任务不变、模型不变），stale doc 条件下 agent 任务成功率从 fresh doc 的 94–100% 崩塌至 0–32%，主动误导率（自信断言假命题）68–100%；机制是「**上下文里存在任何权威文档都会关掉 agent 的自行验证**」（无 doc 时 agent 读隐藏依赖 ~100%，有 doc 后跌至 0–33%），**模型能力不提供抵抗**（最强模型同样中招）。修正信息（drift report）可恢复至 90–100%[预注册实验， 3,250 完成样本、5 模型、3 供应商](https://github.com/Connorrmcd6/surface-bench/blob/main/PAPER.md)。小样本诊断研究同向：stale-only 检索让模型锚定过时仓库状态，比无检索更糟（Qwen 15/17、gpt-4.1-mini 13/17 样本产出过时引用，[arXiv:2605.14478](https://arxiv.org/html/2605.14478v1)）。
2. **环境引导基准**：[SetupBench](https://arxiv.org/pdf/2507.09063v1)（93 实例，裸 Linux 沙箱起步）——SOTA agent 仓库搭建成功率 38.9–57.4%，三种系统性失败模式：忽略隐式开发工具链（tox.ini 类信号不读）、幻觉任务约束、环境修改不持久；38–69% 的动作相对人类最优路径是浪费。同类工作 [SetupX](https://arxiv.org/html/2605.26186v2) 与 EnConda-Bench（README 注入错误法）证明 README 配置错误是 agent 环境失败的可控变量。→ build-entry-unclear / config-drift 的直接证据。
3. **SWE-bench 过程级错误分析**：[Beyond Final Code](https://dl.acm.org/doi/10.1145/3744916.3773140)（ICSE 2026，3,977 求解轨迹 + 3,931 测试日志）——最常见错误是 ModuleNotFoundError（1,053 次）与 TypeError（992 次）；数据库相关错误（IntegrityError）复发率高、调试投入显著。另一项 [150 失败实例的九类失败模式分类学](https://arxiv.org/abs/2505.24286)（arXiv:2505.24286）发现 agent 架构失败的最大单一类别是「理解/推理失败」（错误定位占 pipeline 类工具失败的 51.3%，agentic 工具则陷入认知死循环）。→ 环境债与「可解性」轴的证据。
4. **API 演化下的 context-memory 冲突**：[270 个真实 API 变更 × 11 模型](https://arxiv.org/html/2604.09515v1)——即使把更新的 API 文档放进 prompt，平均只有 42.55% 的生成代码可执行；42.1% 的失败是彻底忽略提供的文档（锚定参数记忆中的过时 API）。→ dep-stale 留册决策「利息降级为效率损耗」的反向证据（见下文留册带讨论）。

---

## 三、20 类型 × 证据分级总表

| slug | 预排 | 证据级 | 一句话判据（判据文件口径） | 最强证据来源 |
|---|---|---|---|---|
| `doc-rot` | 高 | **[强]** | 注释断言与代码现实分叉，主动误导 | 受控实验：stale doc 致成功率 0–32% |
| `agent-doc-missing` | 高 | **[强]** | 代理上下文文档缺失/撒谎/冲突 | Meta 5%→100% 覆盖 + ETH/Meta 对照 |
| `build-entry-unclear` | 高 | **[强]** | 验证回路入口的证据链断裂 | SetupBench：仓库搭建成功率 38.9–57.4% |
| `monolith-file` | 高 | **[强]** | 单次典型修改的上下文占比过高 | Context Rot（18 模型）+ CodeScaleBench 迷路 |
| `test-gap` | 高 | **[强]** | 源→测试无保护，agent 无法自证 | Beyond Resolution Rates：投入验证者更成功 |
| `implicit-contract` | 高 | **[间接]** | 仓库痕迹与接口声明面的差集 | 12 个全员失败任务归因架构推理+领域知识 |
| `naming-debt` | 低 | **[强]**（但严重度低） | 检索索引失效，agent 找错符号 | CodeScaleBench「错文件错符号」+ grep 噪声 |
| `duplicate-code` | 高 | **[间接]** | 同一知识多份且未声明权威 | GitClear 克隆 10 倍增长（人类侧）+ 改A忘B 轶事 |
| `test-rot` | 高 | **[间接]** | 假保护：测试在但不测东西 | SATD 文献 + 变异性测试传统（人类侧强） |
| `fidelity-debt` | 高 | **[间接]** | 全绿但保的是替身不是本体 | SWE-bench DB 错误复发率；经典工程史 |
| `config-drift` | 中 | **[强]** | 验证回路配置不可达，归因污染 | SetupBench 三种失败模式；EnConda README 注错 |
| `flaky-test` | 中 | **[间接]** | 随机红绿污染失败归因 | #48 判别表 #7；无 agent 侧直接测量 |
| `misplaced-seam` | 中 | **[间接]** | 连带编辑半径大，agent 改一处漏一片 | EC-缺陷相关性（人类侧）+ CodeScaleBench partial completion |
| `oral-tradition` | 高 | **[推演]** | 应知知识未被 agent 高触达载体覆盖 | Meta 部落知识为概念级旁证（非该类型直接测量） |
| `test-shape` | 中 | **[推演]** | 真保护焊死错误对象，重构被惩罚 | 无直接证据；机制推演自红绿信号反馈 |
| `shallow-module` | 高 | **[推演]** | 穿越多层薄壳的上下文性价比损失 | 无 agent 侧直接测量；CodeScaleBench 迷路是旁证 |
| `hypothetical-seam` | 中 | **[推演]** | 单实现抽象的假「可换」信号误导规划 | 无直接证据；YAGNI 审查传统为人类侧对照 |
| `dead-code` | 中（留册） | **[留册]** | 死代码浪费推理预算、误导导航 | CodeScaleBench「错符号」中废弃代码是噪声源 |
| `dep-stale` | 高（留册） | **[留册]** | 训练截止错位 → 过时 API 写法 | API 演化研究：42.55% 可执行率 |
| `vendored-dep` | 中（留册） | **[留册]** | 改 vendor 副本制造永久分叉 | 无 agent 侧证据（留册理由之一） |

（`lockfile-drift` 在 21 类型新口径中为独立留册类型，D 族文件留册理由 = 检测商品化 + 工具报错清晰，agent 可诊断性不差——本票无新反证，维持留册。）

---

## 四、逐类型证据分析

### 4.1 强证据带（7 类型）

**doc-rot（预排高 → 建议：高，且是「高」中最有底气的）**
本票最重要的校准发现。受控实验把文档准确性做成唯一变量：stale doc 条件下五个模型（GPT-5.4、Claude 三档、Gemini 3.5 Flash）成功率 0–32%、主动误导率 68–100%，且 agent 从 ~100% 的自行验证率跌至 0–33%——**伤害机制不是「信息缺失」而是「验证行为被抑制 + 错误锚定」**。三个失败模式各有形态：盲从型（GPT 停止验证）、抑制但可救型（Claude 验证者 95% 正确但验证行为被压）、验证后仍从众型（Gemini 读了真代码仍跟文档走）。关键反直觉：**模型能力不提供抵抗**（Opus 同样 68% 被误导）——这直接支撑「仓库属性造成的失败不随模型进步消失」的核心赌注（地图 #39）。小样本诊断研究（[stale 检索让模型锚定过时仓库状态](https://arxiv.org/html/2605.14478v1)）同向。对 rubric 的校准含义：误导度主轴（行为反转 > 断链 > 陈旧）方向正确；「语义分叉（描述与实现相反）」是实验中的最恶性条件，预排高维持且置信度上调。
- 来源：[Surface 预注册实验 PAPER.md](https://github.com/Connorrmcd6/surface-bench/blob/main/PAPER.md)（3,250 样本、5 模型、Holm 校正）、[arXiv:2605.14478](https://arxiv.org/html/2605.14478v1)、既有 #48 判别表 #5。

**agent-doc-missing（高 → 建议：高，维持）**
ETH Zurich（手写 context 文件平均 +4%、LLM 生成 -3%）与 Meta（覆盖 5%→100%，工具调用/token -40%）构成证据对：**上下文文件的有效性高度依赖仓库，且对训练语料里没有的专有知识效果巨大**——agent-doc-missing 的存在性态（文档全缺失）是 Meta 案例的起点态。ETH 结论同时校准「过时」态：无效 context 文件把推理成本推高 20%+，与 agent-doc-missing 过时态「第一信源误导放大」判据一致。
- 来源：[ETH arXiv:2602.11988](https://arxiv.org/html/2602.11988v1)、[Meta Engineering](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)、既有 #48。

**build-entry-unclear（高 → 建议：高，维持）**
SetupBench 给出该失败形态的第一次规模化直接测量：SOTA agent（OpenHands + 五个模型）在真实仓库搭建任务上成功率 34.4–62.4%，仓库设置类 38.9–57.4%。「忽略 tox.ini 类隐式工具链信号」「引用不存在的配置」「38–69% 无效动作」三种失败模式与 E1–E4 四档信号几乎一一对应；EnConda-Bench 用 README 注错法证明「声明存在但撒谎」（E3）是独立的可控失败变量。既有旁证：Beyond Resolution Rates 中「先收集上下文再编辑、投入验证」的 agent 更成功——验证回路跑不起来直接压低成功率。
- 来源：[SetupBench arXiv:2507.09063](https://arxiv.org/pdf/2507.09063v1)、[EnConda-Bench](https://arxiv.org/html/2510.25694)、[Beyond Resolution Rates](https://arxiv.org/html/2604.02547)。

**monolith-file（高 → 建议：高，维持）**
双通道强证据。机制通道：Chroma Context Rot（18 模型）——输入越长性能越差，即使简单任务；「有效理解质量衰减远早于窗口上限」（判据文件 32K 候选线的依据）与该研究「模型并非均匀使用上下文」结论互证。行为通道：CodeScaleBench 迷路模式（读文件→跟 import→探索树爆炸）+ context 溢出模式（整读文件稀释信号）；Sourcegraph 的量化：「仅靠本地工具的 agent 在代码库超过约 40 万行后系统性挣扎」。人类侧 LoC 基线在维护性预测上 AUC 0.95 与 SotA ML 持平（大文件难维护在 agent 侧的机制重述 = 上下文占比）。
- 来源：[Context Rot](https://www.trychroma.com/research/context-rot)、[Sourcegraph CodeScaleBench](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)、既有 #48。

**test-gap（高 → 建议：高，维持）**
Beyond Resolution Rates 的行为学结论——「投入验证的 agent 稳定更成功，且该策略是 agent 自定的、不随任务难度自适应」——意味着**仓库若提供不了低成本验证回路，agent 就不会去验证**；test-gap 使该策略失效。Willison 的实践证词（有自动化测试的人从 AI 获益远超旁人）与 Anthropic 40 万会话（91% 可见解决仍需人纠正——人成为验证回路）从两侧印证。这是「验证回路存在性 → agent 成功率」的最强因果链。
- 来源：[Beyond Resolution Rates](https://arxiv.org/html/2604.02547)、[Willison](https://simonwillison.net/2025/May/28/automated-tests/)、既有 #48。

**implicit-contract（高 → 建议：中偏高，小幅下调）**
间接证据为主但方向密集：Beyond Resolution Rates 的 12 个「简单补丁但全员失败」任务归因于**架构推理与领域知识缺口**（agent 正确定位 bug 但干预在错误的架构层、修补症状而非根因）——「根因在接口未声明的不变量上」正是 implicit-contract 的失败形态；Meta 的「两种配置模式字段名搞混→静默错误输出」「废弃枚举不能删（序列化兼容性）」是契约未外化的具体案例；SWE-bench 错误分析中 DB IntegrityError 类错误复发率高（agent 难以自行发现 schema 约束）。但注意反面校准：doc-rot 实验证明「有 doc 就不查」——同样的机制意味着 agent 对隐式契约的损害常被其自身的高验证率兜底（无 doc 时代理读隐藏依赖 ~100%），真正炸掉的是「agent 以为懂了」的场景。判据文件的「存在性候选」证据等级定位是对的；预排高沿 test-rot 同档的理由（假保护）不如 test-rot 充分，建议降为中偏高、等二期动态测量。
- 来源：[Beyond Resolution Rates](https://arxiv.org/html/2604.02547)、[Meta](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)、[Beyond Final Code](https://dl.acm.org/doi/10.1145/3744916.3773140)。

**naming-debt（低 → 建议：中，上调）**
本票第二反直觉发现：#49 把 naming-debt 降为低的理由（agent 有完整上下文兜底）在检索证据面前站不住——**实际工作流里 agent 不读全库，靠词法检索导航**。CodeScaleBench 五种失败模式之二「错文件、错符号」的直接证据：grep `allocate` 在 Kubernetes 返回数百个命中（测试、废弃代码、工具函数、真实逻辑混杂），词法搜索无法按结构相关性排序；关键词搜索是 agent 最高频工具（7,993 次调用）——**agent 倾向用「能用的最简单工具」，而这个工具的噪声直接由命名质量决定**。命名误导（预测到错的方向）正是检索噪声的结构性来源。上调为中；仍不到高（agent 有上下文兜底的场景真实存在，伤害集中在「名字指向错误方向」而非「名字无信息」——判据文件的 rubric 主轴方向正确，只调预排）。
- 来源：[Sourcegraph CodeScaleBench](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)、[Beyond Resolution Rates](https://arxiv.org/html/2604.02547)。

**config-drift（中 → 建议：高，上调）**
SetupBench 的三种系统性失败模式中，「忽略隐式工具链」（tox.ini 存在但不读）与「幻觉任务约束」都落在配置可达性失败上；EnConda-Bench 证明 README 配置断言错误是独立失败变量，且 agent「能定位错误但难以转化为正确修复」——归因污染（KeyError 无法归因于配置缺失）的机制得到过程级验证。SWE-bench 错误分析中 ModuleNotFoundError 为最高频错误（1,053 次）也与「读取痕迹 vs 可见源两端断链」的判据呼应。预排中→高：冷启动阻断度主轴（无源必需键直接炸）与实验证据吻合。
- 来源：[SetupBench](https://arxiv.org/pdf/2507.09063v1)、[EnConda-Bench](https://arxiv.org/html/2510.25694)、[Beyond Final Code](https://dl.acm.org/doi/10.1145/3744916.3773140)。

### 4.2 间接证据带（6 类型）

**duplicate-code（高 → 建议：高，维持）**
人类侧证据强：GitClear 克隆块 2020–2024 四倍增长（AI 时代在加速制造该债）、Code Red（低质量代码缺陷 15 倍）等。agent 侧是机制平移 + 轶事：HN 49698073 提问者自列「重复业务逻辑（无单一真源）」为 agent 痛点；CodeScaleBench partial completion 模式（改 7 个受影响文件只改 2 个）是「改 A 忘 B」的失败形态在 agent 上的呈现——但严格说该证据锚定的是「共编辑耦合」（misplaced-seam 主锚）而非文本/语义重复。判定：维持高（机制清晰、人类侧强、agent 侧轶事一致），但如实标注「agent 直接测量证据缺乏，是 A 族中证据最弱的类型」。
- 来源：[GitClear](https://www.gitclear.com/ai_assistant_code_quality_2025_research)、[HN 49698073](https://news.ycombinator.com/item?id=49698073)、[CodeScaleBench](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)、既有 #45/#48。

**test-rot（高 → 建议：高，维持）**
人类侧强（SATD 文献、变异性测试传统、skip 堆叠的工程共识），agent 侧间接：假保护机制 = agent 信任红绿信号 → 错误放行，与 Beyond Resolution Rates「投入验证者更成功」构成镜像（验证投入的前提是验证结果可信——rot 使该前提为假）。doc-rot 实验的「权威信号抑制验证」机制在「权威测试信号」上同样适用：agent 对绿测试的信任与对文档的信任同源。无直接测量「烂断言 → agent 错误放行」的研究；判据文件把断言质量层标为「风险 + 置信度、不得伪装实锤」与证据现状精确对齐。维持高。
- 来源：[Potdar & Shihab SATD](https://users.encs.concordia.ca/~eshihab/pubs/Potdar_ICSME2014.pdf)、[Beyond Resolution Rates](https://arxiv.org/html/2604.02547)、[Surface 实验](https://github.com/Connorrmcd6/surface-bench/blob/main/PAPER.md)（机制平移）。

**fidelity-debt（高 → 建议：高，维持）**
间接但多向：SWE-bench 错误分析中数据库错误（IntegrityError）是 agent 最难解的错误类别之一（复发率 50–57%、平均复发 10–12 次）——agent 在数据库约束/替身差异面前反复挣扎的直接观察；工程史上 SQLite 替 PG 型静默分叉是经典模式（该类型的动机案例）；「全绿证据同时在手」的条件与 test-rot 的假保护机制共享「权威信号误导」结构。无直接研究测量「替身环境全绿 → agent 放行真实环境破坏」。维持高（沿 test-rot 假保护同档），标注证据等级为机制同构 + 过程级旁证。
- 来源：[Beyond Final Code](https://dl.acm.org/doi/10.1145/3744916.3773140)、既有 #53 判据。

**flaky-test（中 → 建议：中，维持）**
#48 判别表 #7 已定「对 agent 是双向伤害（误判失败/误判成功）且污染任何动态测量样本」——这是机制推演 + 共识，无 agent 侧受控测量。人类侧 flaky 测试研究成熟（普遍存在、修复成本高）。维持中，并提示：该类型对 CogniCode 自身的二期动态测量（跑 agent 对比修复前后表现）是**测量基础设施问题**——flaky 污染的正是我们的判据采样。
- 来源：既有 #48（判别表 #7、DS 版 flaky 环境条目）；人类侧综述见 [debt-taxonomy.md](./debt-taxonomy.md)。

**misplaced-seam（中 → 建议：中，维持）**
双锚点证据错位：git 共编辑提升度的人类侧证据**强**（变更耦合与缺陷正相关的多篇工业级研究，如 [7 年 17.6 万文件的双工业系统研究](https://uhra.herts.ac.uk/id/eprint/6277/1/Published_Version.pdf)——EC 与缺陷普遍正相关但强度随模块/缺陷类型变化）；agent 侧是 CodeScaleBench partial completion（跨文件改动失手）与 Meta「改 A 炸 B」轶事——**该证据锚定「共编辑耦合」本身，与提升度信号吻合**，但「agent 连带编辑半径」尚无测量。维持中；若二期动态测量做「agent 改一处漏一片」的破坏率统计，本类型是首选校准对象。
- 来源：[Herts EC-缺陷研究](https://uhra.herts.ac.uk/id/eprint/6277/1/Published_Version.pdf)、[CodeScaleBench](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)、既有 #45（CodeScene 判据可平移论断）。

**test-shape / oral-tradition / shallow-module / hypothetical-seam（中/高/高/中 → 建议：维持，见下节）**

### 4.3 仅推演带（4 类型：方法论判断轴创新）

**oral-tradition（高 → 建议：高，维持但标注）**
最微妙的一档。部落知识未外化的 agent 侧证据其实**接近强**：Meta 案例（「AI 没有地图」、专有知识不在训练数据、无上下文时「猜、探索、再猜」）是oral-tradition 存在性态的最生动实证——但严格说 Meta 测的是「外化后的收益」，oral-tradition 作为**检测类型**（应知清单 vs 载体差集）的判据设计是本方法论独创，业界无对应物（#48 空档分析：知识孤岛是人类维度，无人以 agent 触达率定义应知性）。判定：维持「推演」级（判据设计层面）+ 标注「概念级证据强」（Meta/ETH/Meta 反驳链）。预排高维持——概念级证据的方向与预排一致。
- 来源：[Meta](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)、[ETH](https://arxiv.org/html/2602.11988v1)、既有 #48 空档分析。

**test-shape（中 → 建议：中，维持）**
零 agent 侧证据；「真保护焊死错误对象 → agent 学会不重构」的行为学习污染层判据文件已锁二期动态验证。间接机制旁证：agent 从不迁移测试结构（业界共识轶事——agent 补测试/改实现，不做测试接口迁移这类重构）；Anthropic 40 万会话中 agent 做执行、人做规划——深度化重构属规划密集动作，测试形状债对其惩罚机制的推演成立但未测。维持中。

**shallow-module（高 → 建议：高，维持但降置信）**
无 agent 侧直接测量（无人测过「穿越 N 层薄壳的 token 成本溢价」）；CodeScaleBench 迷路模式（探索成本）是最接近的行为证据但混杂了导航/检索因素。Ousterhout 的人类侧判据（deep module）+ 本仓 module_depth 判定协议是自建资产。判据文件要求的「阈值论证义务」在证据现状下尤其重要——预排高维持，但这是 G 族中证据最弱的类型，建议报告语言保持「架构候选」谨慎度。
- 来源：既有 #40/#54；CodeScaleBench 作行为旁证。

**hypothetical-seam（中 → 建议：中，维持）**
零 agent 侧证据；「假可换信号误导规划」与 Beyond Resolution Rates 的「架构推理缺口」概念相邻但未被直接研究覆盖。人类侧 YAGNI 审查传统是对照而非证据。维持中。

### 4.4 留册带（4 类型，证据与 MVP 决策互证）

- **dead-code（留册）**：CodeScaleBench「错符号」模式中「废弃代码」被点名为 grep 噪声源之一——agent 侧伤害存在但被 naming-debt/检索问题吸收，与「检测商品化、委托不自制」的留册决策一致。捡回条件不变。
- **dep-stale（留册）**：本票新证据**反向拉扯**——API 演化研究（270 真实变更 × 11 模型）显示即使提供更新文档，平均仅 42.55% 生成代码可执行、42.1% 失败源于彻底忽略文档——比「web search 普及使利息降级」的 #52 判断更悲观。但该证据锚定的是「模型参数知识过时」（生成侧），不是「仓库依赖陈旧」（仓库侧）——换更强模型可部分缓解的是前者。维持留册，但建议把「无搜索 agent 痛感」的捡回条件观测门槛放低：42.55% 可执行率意味着痛感可能比 #52 估计的大。
- **lockfile-drift / vendored-dep（留册）**：无新证据；维持原决策（前者检测商品化 + 报错清晰；后者低频）。

---

## 五、结论：对严重度带校准的建议

### 5.1 预排调整（供 rubric / 严重度带定档参考，非终裁）

| slug | 现预排 | 建议 | 依据 |
|---|---|---|---|
| `naming-debt` | 低 | **中（上调）** | 「agent 有完整上下文兜底」前提失效——实际靠词法检索导航，命名误导是检索噪声的结构性来源（CodeScaleBench 错文件错符号 + grep 噪声实证） |
| `config-drift` | 中 | **高（上调）** | SetupBench/EnConda 过程级验证：配置可达性失败是 agent 环境失败的独立变量，归因污染机制被证实 |
| `implicit-contract` | 高 | **中偏高（小幅下调）** | 间接证据为主；「agent 高自行验证率」部分兜底；等二期动态测量再定高 |
| `doc-rot` | 高 | 高（**置信度大幅上调**） | 受控实验直接命中判据（stale doc → 成功率 0–32%），「误导 > 缺失」主轴被实验证实 |

其余 16 类型维持现预排。两个「不调」的说明：duplicate-code 维持高（证据间接但机制与人类侧证据均强，无下调理由）；shallow-module 维持高（推演档中概念基础最扎实，与 monolith 互为镜像的对称性成立）。

### 5.2 结构性发现（对方法论的意义）

1. **C 族（文档知识债）的证据地位被本票大幅抬升**：业界最严格的受控实验（单变量操纵、预注册、Holm 校正）打在 doc-rot/agent-doc-missing 上，而非任何代码结构债上。「权威文档存在 → agent 停止自行验证」的机制给了 C 族 rubric 主轴（误导度 / 误导方向）最强的实验背书——「撒谎 > 缺失」的排序方向被证实。
2. **证据强度与预排的相关性整体为正但不均匀**：7 个强证据类型中 5 个预排高；但预排为低的 naming-debt 有强证据、预排为高的 implicit-contract 只有间接证据——预排直觉在个别类型上系统性偏差（方向相反的各一例），说明类型级校准确有必要（本票存在的原因）。
3. **「能力不提供抵抗」是贯穿性强证据**：doc-rot 实验（最强模型同样中招）+ Beyond Resolution Rates（12 个简单补丁任务全员失败）+ CodeScaleBench（context 问题不是智力问题）三处独立来源同向，支撑核心赌注「仓库属性造成的失败不随模型进步消失」——这句话从 #48 的判断升格为有直接实验证据的立场。
4. **推演带类型的共同缺口是「二期动态测量的天然校准对象」**：oral-tradition / test-shape / shallow-module / hypothetical-seam 四类型的伤害量化只能靠 agent 实测（地图 #63 Out of scope 已锁二期），本票的分级可作为二期测量的优先级输入。

### 5.3 局限声明

- 「强证据」指该失败形态被业界直接测量过，**不等于伤害幅度可比**（受控实验的效应量不能直接换算成仓库级扫描的严重度权重——幅度校准只能靠 CogniCode 自家动态测量）。
- Surface 实验（doc-rot 主证据）是单一工具作者的预注册研究，样本是合成任务而非真实仓库全貌；按 #48 的读法警告，单一来源的方向性结论需在自家数据上复现。
- 检索覆盖 2024–2026 公开语料；agent 侧实证研究本身在爆发期，分级是时点快照，应随模型版本重检（与「测量须能随模型版本重跑」的既定风险声明一致）。

## 附：本票新增外部来源清单

- Surface / Connorrmcd6. *Pre-registered benchmark of stale docs on coding agents*（3,250 样本、5 模型、3 供应商、Holm 校正）. https://github.com/Connorrmcd6/surface-bench/blob/main/PAPER.md
- *When Retrieval Hurts Code Completion: A Diagnostic Study of Stale Repository Context*（stale 检索锚定过时仓库状态）. https://arxiv.org/html/2605.14478v1
- *SetupBench: Assessing Software Engineering Agents' Ability to Bootstrap Development Environments*（93 实例环境引导基准）. https://arxiv.org/pdf/2507.09063v1
- *SetupX: Can LLM Agents Learn from Past Failures in Functionality-Correct Code Repository Setup?*（100 仓库设置经验学习）. https://arxiv.org/html/2605.26186v2
- *Process-Level Trajectory Evaluation for Environment Configuration in Software Engineering Agents*（EnConda-Bench，README 注错法）. https://arxiv.org/html/2510.25694
- *Beyond Final Code: A Process-Oriented Error Analysis of Software Development Agents*（ICSE 2026，3,977 轨迹 + 3,931 测试日志）. https://dl.acm.org/doi/10.1145/3744916.3773140 ；https://arxiv.org/html/2503.12374v3
- *An Empirical Study on the Failure Modes of Automatic Issue Solving Tools*（150 失败实例、九类失败模式分类学）. https://arxiv.org/abs/2505.24286
- *When LLMs Lag Behind: Knowledge Conflicts from Evolving APIs in Code Generation*（270 API 变更 × 11 模型）. https://arxiv.org/html/2604.09515v1
- *Evolutionary Coupling and Its Impact on Software Defects*（双工业系统 7 年研究）. https://uhra.herts.ac.uk/id/eprint/6277/1/Published_Version.pdf
- *Code Red / Code Health 验证研究*（CodeScene AUC 0.95、LoC 基线持平）. https://github.com/codescene-research/code-red-techdebt-2022 ；[Zenodo 复现包研究](https://zenodo.org/)（见 #45 已录的 Code Red 白皮书）

既有材料（#45/#48/#40）引用的来源不重复列出，见各文档附清单。
