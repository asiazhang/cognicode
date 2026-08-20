# 现有工作调研：仓库级 AI 基准与评测

> 票 #2（wayfinder:research）的调研产出。调研日期：2026-08-20。
> 问题：现有面向仓库/代码库的 AI 评测体系（SWE-bench 系列、Aider polyglot、RepoQA、terminal-bench 等）各自如何构造任务、定义指标、对抗评测噪声？哪些设计可以被 CogniCode 的「合成基准任务 + 真实 agent 执行」路线直接借鉴，哪些坑要避开？有没有人做过「评估仓库本身对 AI 友好度」的工作？

## TL;DR

1. **任务验证的行业共识是「执行式验证」**：任务必须在构造阶段被真实执行验证（gold patch 前后测试状态翻转 FAIL_TO_PASS / PASS_TO_PASS），不可解/装不上的实例要砍掉（SWE-bench 第三阶段过滤砍掉约一半候选）。
2. **可复现性三件套**：容器化执行环境（Docker）+ 固定 commit/镜像版本 + 多次采样统计。其中多次采样在社区基准中做得很不充分（SWE-bench 主榜单基本单次运行），是公认的噪声来源，CogniCode 把分数稳定当硬需求恰好是差异化机会。
3. **合成任务已有成熟先例**（SWE-smith、R2E-Gym、SWE-rebench），但**跨语言合成仍是空白**——所有自动合成管线都只覆盖 Python 或单生态；跨语言实例（Multi-SWE-bench）靠的是重人力（68 名标注者）。
4. **「评估仓库 AI 友好度」确有先例，但全是静态打分**：DAF Benchmark（5 维度加权 0-5 分）等商业工具；**未发现任何「用真实 agent 执行合成任务来动态测量仓库 AI 友好度」的公开工作**。CogniCode 的路线是空白区。静态工具的维度划分（上下文可读性、测试基础设施权重最高）可作为维度模型票（#4）的参考输入，但其权重缺乏实证校准正是它们的方法学弱点。

---

## 一、逐项分析

### 1. SWE-bench（及 Verified、Multimodal、收集管线）

来源：SWE-bench 论文（arXiv:2310.06770，ICLR 2024）、[SWE-bench/SWE-bench 仓库](https://github.com/SWE-bench/SWE-bench)。

**任务构造**（三阶段管线，~90k PR → 2,294 实例）：

- **阶段一选仓**：按 PyPI 下载量选 top 100 包中的 12 个仓库（django、sympy、matplotlib 等）。理由：流行仓库维护好、贡献指南清晰、测试覆盖好。
- **阶段二属性过滤**：PR 已合并 + 通过 "fixes/closes/resolves #N" 关联到 issue + 引入了新测试文件。
- **阶段三执行式过滤**：真实跑测试，保留「至少一个测试从 fail 翻转为 pass」的实例；剔除安装/运行报错、pre-solution 日志有 ImportError/AttributeError、以及测试引用了「答案中新命名的函数/类」的实例（后者对人类也不可解）。此阶段砍掉约一半（11,407 → 2,294）。
- **实例四元组**：base commit 处的代码库 C + 问题陈述 P（issue 正文 + PR 首次 commit **之前**的评论，防答案泄漏）+ gold patch δ + 测试 patch T，外加结构化字段 `FAIL_TO_PASS`、`PASS_TO_PASS`。

**指标**：主指标为「解决率」——补丁能应用 **且** 全部 FAIL_TO_PASS（均值 9.1 个/实例）**且** 全部 PASS_TO_PASS（中位数 51 个/实例）测试通过。次指标 % Apply（补丁应用成功率）用于区分「打不上补丁」与「解不对」。

**抗噪与可复现**：

- **SWE-bench Verified**（arXiv:2410.03859）：500 实例由人类软件工程师确认可解——承认并修复了原集中不可解/有歧义实例造成的噪声。这是「任务本身是坏的」这一噪声类型的标杆处理方式。
- Docker 全容器化评测、预构建镜像、按 `run_id`+`instance_id` 缓存结果；`--gold` 自检（用 gold patch 验证 harness 本身正确）。
- 镜像仓库（mirror）保存原始 commit 哈希，防上游仓库变动污染任务。
- Multimodal 变体把测试集评测私有化（经云端 sb-cli），防过拟合测试集。

**对 CogniCode 的启示**：

- F2P/P2P 双验证是合成任务验证的黄金标准，直接照搬：**合成任务的验收测试必须证明「改动前失败、改动后通过、不破坏既有测试」**。
- 执行式过滤 + gold-patch 自检应成为 CogniCode 任务生成器的内置环节。
- SWE-bench 论文明确承认「测试通过 ≠ 代码质量（可读性/全面性/效率）」——CogniCode 若只用「任务解出与否」做信号，要意识到这个粒度限制，多维信号需要更细的观测。

### 2. SWE-bench 衍生：跨语言与合成管线

#### Multi-SWE-bench（ByteDance Seed，NeurIPS 2025 D&B）

来源：[multi-swe-bench/multi-swe-bench](https://github.com/multi-swe-bench/multi-swe-bench)、论文 arXiv:2504.02605。

- 7 语言（Java/TS/JS/Go/Rust/C/C++），1,632 实例（从 2,456 候选筛出），**68 名专业标注者双标注交叉审核**对标 SWE-bench Verified 的质量。
- 实例结构与 SWE-bench 相同（fix.patch + test.patch + Docker 镜像）。2025/09 给所有实例补 `hints` 字段（描述 patch 中新定义的变量），说明**原始 issue 缺少解题所需信息是普遍噪声**。
- 补丁应用失败时回退 `patch --fuzz=5`——宽松应用本身是噪声源。
- **启示**：跨语言的真实任务构造目前仍是重人力活；「环境构建」是跨语言扩展的最大工程成本。CogniCode 面向任意语言，不能走「每语言重金标注」路线，必须把语言相关成本压到任务模板层（见 RepoQA 的 tree-sitter 路线）。

#### SWE-smith（arXiv:2504.21798，Stanford/Princeton）

来源：[swesmith.com](https://swesmith.com/)。

- **证明「对任意 GitHub 仓库在 10 分钟内合成 100 个任务实例」可行**：已为 128 个仓库合成 50k+ 实例（bug 注入式）。
- **关键局限：仅支持 Python**，其路线图明确把「扩展到非 Python 仓库」列为待办——跨语言自动合成是公认未解问题。
- **启示**：这是与 CogniCode 路线最接近的先例（合成任务 + 可执行验证），可复用其「合成 → 执行验证 → 过滤」的骨架；CogniCode 的语言无关性是明确的增量贡献点。

#### R2E-Gym（COLM 2025，arXiv:2504.07164）

来源：[R2E-Gym/R2E-Gym](https://github.com/R2E-Gym/R2E-Gym)。

- **基于 commit（而非 PR）做环境构造**：不依赖人工写好的 PR/单测，从 commit 直接合成可执行环境 + 单测 + 自然语言任务描述，8.1k 实例、13 个仓库。
- **混合验证器**：执行式验证（专门训练的 Testing Agent 生成针对性单测）+ 免执行验证（Verifier Agent 用 LLM 判断重排），两者互补，单独使用各有盲区。
- 工程细节：每个 Docker 环境约 300–500MB——**实例级容器的存储成本不可忽视**，CogniCode 本地 CLI 场景需要更轻量的环境策略。
- **启示**：「commit 作为任务源」比「issue/PR 作为任务源」对冷启动仓库更普适；混合验证（执行为主、LLM 判断为辅）值得借鉴。

#### SWE-bench-Live / SWE-rebench（Microsoft / Nebius）

来源：GitHub topics 检索确认项目存在（microsoft/SWE-bench-Live 等）；未深查论文细节。

- 动机是**评测污染**：静态基准会被训练语料吞掉，用「持续从新 PR 抽取新鲜任务」对抗。
- SWE-rebench 用 LLM 自动生成环境安装指令再执行验证——环境构建自动化是核心难点。
- **启示**：CogniCode 的任务是「现场合成 + 现场执行」，天然免疫训练集污染，这是动态路线的固有优势，值得在方法学叙述中明确。

### 3. Aider polyglot

来源：[aider 榜单文档](https://aider.chat/docs/leaderboards/)、[polyglot 发布博文](https://aider.chat/2024/12/21/polyglot.html)、[benchmark harness README](https://github.com/Aider-AI/aider/tree/main/benchmark)（以下 harness 细节引自仓库 `benchmark/README.md`）。

**任务构造**：

- 6 语言（C++/Go/Java/JS/Python/Rust）中 Exercism 的 697 个练习里，选**最难**的 225 个。难度标定方法极具参考价值：让 7 个头部模型各做全部 697 题，**只保留 ≤3 个模型解出的题**（225 题），258 题全被解出的直接淘汰。语言分布：C++ 26 / Go 39 / Java 47 / JS 49 / Python 34 / Rust 30。
- 动机是老基准（133 个 Python 题）在 80%+ 饱和，头部模型每次只多解 1–2 题，失去区分度。

**指标与执行**：

- 指标：`pass_rate_1`（一次通过全部单测的练习百分比，榜单主指标）与 `pass_rate_2`（允许第二次尝试，带失败测试反馈）；另报「使用正确编辑格式的百分比」（区分模型能力与格式失败）。
- 全程 Docker 隔离执行 LLM 生成的代码（安全考虑，README 给出理由：无人监督地执行 LLM 代码有 `rm -rf` 风险）；练习随机顺序执行；记录模型/编辑格式/commit 哈希/成本/耗时，保证可复现。

**对 CogniCode 的启示**：

- **用一组参考模型实测通过率来标定任务难度**——CogniCode 可用同一组任务在参考模型集上的通过率作为难度锚点/基线，把「这个仓库比那个仓库难」与「任务本身难」解耦（这直接服务分数归因与跨仓库可比性）。
- Docker 隔离 + 随机顺序 + 全量元数据记录（模型、版本、成本、commit）是低成本高回报的可复现性手段。
- **坑**：Exercism 练习是「单文件从零写」，不涉及仓库导航、既有代码修改、测试基建——aider 自己也承认这只是测「编辑能力」。CogniCode 的任务必须发生在**真实仓库语境**里，这正是与 polyglot 的本质区别。

### 4. RepoQA（ICML 2024 Long-Context Workshop）

来源：[evalplus.github.io/repoqa](https://evalplus.github.io/repoqa.html)、论文 arXiv:2406.06025。

**任务构造**：Search Needle Function（SNF）——给定按 import 依赖拼出的 16K token 长代码块和一段自然语言描述，找出对应函数。5 语言 × 10 仓库 × 10 needle = 500 子任务。数据集四步构造：按质量指标选宽松许可证仓库 → 分析文件依赖 → **tree-sitter 解析全部函数选 needle** → GPT-4 Turbo 生成函数描述。

**指标**：生成函数与 ground truth 相似度为所有候选中最高 **且** 相似度超阈值（默认 0.8，BLEU）。

**抗噪与可复现**：greedy decoding；但官方 FAQ 明确承认**商用 API 仍非完全确定、本地推理的并行配置也影响复现**——「理论上确定性 ≠ 实际确定性」的诚实教训。已知局限：描述被迫写得冗长以避免一对多映射，与真实开发者的短描述习惯不符。

**对 CogniCode 的启示**：

- **tree-sitter 多语言统一解析是「语言无关任务合成」的已验证技术路线**——CogniCode 的静态归因信号提取（票 #7）和任务模板可建立在 tree-sitter 之上。
- 非确定性教训直接支持「多次采样 + 统计聚合」的设计选择：即使控制解码参数，agent 执行层面仍有方差。
- 16K 固定上下文的「检索 needle」设计与「仓库可导航性」相关，其按语言分列的成绩表（.py/.cpp/.rs/.java/.ts）是「按维度分列报告」的榜样。

### 5. Terminal-Bench（1.0 → 2.0，ICLR 2026）

来源：[harbor-framework/terminal-bench](https://github.com/harbor-framework/terminal-bench)、Terminal-Bench 2.0 论文（arXiv:2601.11868）、[tbench.ai](https://www.tbench.ai/)。

**任务构造**：每个任务 = 独立 Docker 终端环境 + 自然语言任务描述 + 人类编写的 oracle 解法 + 验收测试。2.0 为 89 个任务（1.0 为 80），来自真实工作流灵感，经过提议评审（rubric）→ 自动化检查 → 人工评审多轮把关；60+ 任务作者。持续演进：太简单的任务（如 hello-world）会被移除。

**指标**：强制**二值 reward**（每条 verifier 写出的 reward 必须恰为 0 或 1；连续分数必须阈值化，细粒度子分作为 provenance 附带报告而非进入 reward）。

**抗噪与可复现**：

- **oracle 解法必须 5 连跑全过**（`-k 5 --agent oracle`）才算任务合格，专治 flaky 测试/环境不稳定；oracle 在维护者本地 flake 是必须开 issue 的硬性要求。
- 沙箱化（Modal）统一执行环境；数据集带版本标签发布，榜单对标固定版本。
- 2.0 论文：前沿模型/agent 得分 <65%，并做了错误归因分析。

**对 CogniCode 的启示**：

- **「oracle 解法 N 连跑稳定性验证」应原样照搬**：合成任务的验收测试本身必须先证明稳定，否则测的是噪声不是仓库。这是把「分数稳定是硬需求」落地的最直接手段。
- **二值信号 + 富 provenance** 的分层设计值得采纳：多维分的底层观测用二值/阈值化保证统计性质稳定，丰富上下文（失败日志、子分）作为归因与建议的证据，不直接进分数。
- 任务演进机制（移除过易任务）与提议评审 rubric 是质量治理的范本——CogniCode 的任务生成器同样需要「生成后自动质检」门槛。

---

## 二、横向主题

### 跨仓库/跨语言任务构造的三条路线

| 路线 | 代表 | 语言无关性 | 成本 | 适配 CogniCode |
|---|---|---|---|---|
| 真实 issue/PR 抽取 | SWE-bench、Multi-SWE-bench | 差（每语言重做环境+标注） | 极高（68 人标注 1,632 实例） | 不适合：被评仓库未必有带测试的历史 PR |
| bug 注入/合成 | SWE-smith、R2E-Gym | 目前仅 Python（SWE-smith 明示待扩展） | 中 | **主干路线**：需补齐 tree-sitter 级语言无关层 |
| 统一 IR 解析合成 | RepoQA（tree-sitter） | 好（5 语言同一管线） | 低 | 借其技术底座，任务形态换成「可执行验证」 |

结论：CogniCode 要的「任意语言 + 现场合成 + 可执行验证」组合没有现成实现，但每块积木都有已验证先例：tree-sitter 统一解析（RepoQA）+ 注入式合成与执行过滤（SWE-smith）+ F2P/P2P 验证（SWE-bench）。

### 可复现性：多次采样与统计聚合现状

- pass@k 无偏估计（Chen et al. 2021, arXiv:2107.03374, Codex/HumanEval）是多次采样聚合的标准工具：`pass@k = 1 - C(n-k, n)/C(n, n)`（n 次采样中至少 k 次通过的无偏估计）。CogniCode 的任务级得分可直接套用。
- 社区实践参差：SWE-bench 主榜单基本单实例单次运行（其论文对多设置取最优，本身引入选择偏差）；Terminal-Bench 对 agent 用多次运行（`-k`）、对 oracle 用 5 连跑；RepoQA 承认即使 greedy 也非确定。
- 对 CogniCode 的含义：**「分数稳定」需要在协议层显式设计**——任务级多次采样（n 次执行，取 pass@1 估计或通过率）、报告置信区间、区分「模型方差」与「仓库信号」（例如用参考模型集的方差做归一化基准）。这块是社区公认短板，做扎实即是贡献。

### 评测噪声类型清单（及各基准的对策）

| 噪声类型 | 案例 | 对策先例 |
|---|---|---|
| 任务不可解/歧义 | SWE-bench 原集 → Verified 人工筛 500 | 执行式过滤 +（自动化后的）oracle 验证 |
| 验收测试 flaky | terminal-bench oracle flake | oracle N 连跑稳定性门槛 |
| 环境装不起来 | SWE-bench 阶段三剔除 ImportError | 安装冒烟测试前置 |
| issue 信息不足 | Multi-SWE-bench 补 hints 字段 | 任务描述自动完备性检查 |
| 单次运行方差 | RepoQA greedy 仍非确定 | 多次采样 + 统计聚合 |
| 训练集污染 | SWE-bench-Live 的动机 | 现场合成天然免疫 |
| 基准饱和 | aider 老基准 80%+ | 难度标定（参考模型通过率） |
| 补丁宽松应用 | Multi-SWE-bench `patch --fuzz=5` 回退 | 尽量严格应用、失败即记 0（SWE-bench 式） |
| 答案泄漏 | SWE-bench 截断 PR 首次 commit 后的评论 | 合成任务的「解」与「题面」生成隔离 |

---

## 三、「评估仓库 AI 友好度」的现有工作

**有，但全是静态打分，未发现动态测量先例。**

### DAF Benchmark（benchmark.darkagentfactory.ai，Woodstock Software）

与 CogniCode 目标最接近的公开产品。扫描 GitHub 仓库，从 5 个维度给「AI readiness」打 0–5 分：

| 维度 | 权重 |
|---|---|
| Context Readiness（AI 无人讲解能否理解代码库） | 25% |
| Test Infrastructure（AI 能否自我验证改动） | 25% |
| Architecture Clarity（AI 能否导航代码/理解组件边界） | 20% |
| Automation Maturity（多少流程无需人工） | 15% |
| AI Integration（AI 是否一等开发伙伴） | 15% |

- 权重依据是「23 个仓库的 AI 生产开发经验」，**方法学与权重无发表、无同行评审、无实证校准**——这正是 CogniCode 想用「测量精度需求反推」解决的问题。
- 有个值得注意的设计：**Complexity Tier（1–5）分层**，避免拿单文件工具库和多云服务平台直接比——「仓库间公平比较」的机制值得进入维度模型/聚合票的讨论。
- 扫描在临时容器中进行、不留存源码——CogniCode 本地 CLI 天然满足的隐私姿态。
- **纯静态信号检测**（"concrete signals we detect in your repository"），无 agent 执行、无任务、无动态测量。

### 其他

- Codebase Readiness（ecommerceguide.com 的 MCP 工具）：8 维度静态审计，社区工具级，无方法学发表。
- 学术侧检索（GitTaskBench、agent-eval-harness 等）命中的都是「用仓库任务评 AI」而非「评仓库」；Alibaba aacr-bench 等是多语言代码修改基准，同样评 AI 不评仓库。

**结论**：「以真实 agent 执行合成任务来动态测量仓库 AI 友好度」目前没有公开先例；静态审计工具（DAF）验证了这个需求真实存在且有商业化迹象，但其「无动态证据、无校准的权重」正是 CogniCode 的差异化和机会所在。DAF 的维度划分（上下文可读性与测试基础设施权重最高）可作为票 #4 维度模型的外部对照。

---

## 四、给 CogniCode 决策票的输入

### 可直接借鉴（按票号）

- **票 #5（合成任务集）**：SWE-smith 的「合成 → 执行验证 → 过滤」骨架；SWE-bench 的 F2P/P2P 双验证；R2E-Gym 的 commit-as-task-source（对无规范 issue 历史的仓库更普适）；RepoQA 的 tree-sitter 统一解析做语言无关底座。
- **票 #6（测量协议）**：terminal-bench 的 oracle N 连跑稳定性门槛；pass@k 无偏估计做任务级聚合；aider 式全量元数据记录（模型/版本/commit/成本）；报告置信区间并把「模型方差」与「仓库信号」显式分离（可用参考模型集方差归一）。
- **票 #4（维度模型）**：DAF 五维 + Complexity Tier 作外部对照；RepoQA 按语言分列报告的先例。
- **票 #7（静态归因信号）**：SWE-bench 的检索噪声分析（BM25 长上下文定位失败）说明「可导航性/可检索性」是真实痛点、可观测；RepoQA 的依赖拼接上下文构造方式。
- **票 #8（评分聚合）**：terminal-bench 的「二值 reward + 富 provenance」分层：底层观测二值化保统计稳定，细粒度信息只做归因与建议证据。

### 要避开的坑

1. **只做单次执行就出分**——社区最大噪声源，直接违反本项目「分数稳定是硬需求」。
2. **验收测试自己就是 flaky**——不经 N 连跑验证的任务会把环境噪声伪装成仓库信号。
3. **实例级重容器**——R2E-Gym 每实例 300–500MB，本地 CLI 场景撑不住；需要共享基础镜像 + 按仓库定制的轻量环境策略。
4. **跨语言靠每语言人工管线**——Multi-SWE-bench 的 68 人标注不可复制；语言差异必须收敛到统一 IR（tree-sitter 级）。
5. **静态基准语料污染**——不要把「标准任务库」硬编码分发；现场合成天然免疫。
6. **测试通过即质量的幻觉**——SWE-bench 论文自认不足；多维信号需要测试结果之外的观测面。
7. **宽松的补丁/答案匹配**——fuzz 应用、低阈值匹配都会稀释信号；宁可判 0 并归因，不可放宽。
8. **饱和与难度漂移**——任务难度要随 agent 能力演进做标定（aider 教训），否则分数会随时间失去区分度。

### 遗留问题（不在本票范围，供后续票参考）

- 参考模型集怎么选、几个模型才够做难度锚点/方差基准（票 #6）。
- 无测试基建的仓库如何构造可执行验证（合成任务能否自带测试，SWE-smith 式）。
- Complexity Tier 式分层是否纳入跨仓库可比性设计（票 #8）。

---

## 参考来源（均为一手来源）

- SWE-bench 论文：https://arxiv.org/abs/2310.06770（任务构造、F2P/P2P、指标）
- SWE-bench 仓库：https://github.com/SWE-bench/SWE-bench（Verified、容器化、缓存、gold 自检）
- SWE-bench Verified：https://arxiv.org/abs/2410.03859
- Multi-SWE-bench：https://github.com/multi-swe-bench/multi-swe-bench 、论文 https://arxiv.org/pdf/2504.02605
- SWE-smith：https://swesmith.com/ 、论文 https://arxiv.org/abs/2504.21798
- R2E-Gym：https://github.com/R2E-Gym/R2E-Gym 、论文 https://arxiv.org/abs/2504.07164
- Aider polyglot 博文：https://aider.chat/2024/12/21/polyglot.html
- Aider 榜单：https://aider.chat/docs/leaderboards/
- Aider benchmark harness：https://github.com/Aider-AI/aider/tree/main/benchmark
- Aider polyglot 题库：https://github.com/Aider-AI/polyglot-benchmark
- RepoQA：https://evalplus.github.io/repoqa.html 、论文 https://arxiv.org/abs/2406.06025
- Terminal-Bench 仓库：https://github.com/harbor-framework/terminal-bench
- Terminal-Bench 2.0 论文：https://arxiv.org/abs/2601.11868
- DAF Benchmark：https://benchmark.darkagentfactory.ai/ 、https://benchmark.darkagentfactory.ai/about
- pass@k 无偏估计：Chen et al., "Evaluating Large Language Models Trained on Code", https://arxiv.org/abs/2107.03374
