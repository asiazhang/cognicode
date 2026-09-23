# AI 开发软件时代的痛点全景：从业者真实痛感、证据来源、与「对 AI 不友好的债」的判别

> 票：[研究：AI 开发软件时代的痛点与问题全景 #48](https://github.com/asiazhang/cognicode/issues/48) · 地图：[#39](https://github.com/asiazhang/cognicode/issues/39)
> 分支：`research/ai-dev-pain-points-ds`（独立视角，与同票另一路 `research/ai-dev-pain-points` 并行、互不引用结论）
> 调研日期：2026-09-23。范围：2024–2026 语料，优先 2026 一手来源。
> 方法：多角度并发检索 + 一手来源直取（论文原文/官方报告/官方文档/一线工程师博客/HN 原始讨论），关键量化论断回到发布方原文核对。**只读调研，不改代码。**

**与本仓既有调研的关系（交叉引用）**：本票是 [`docs/research/debt-taxonomy.md`](./debt-taxonomy.md)（票 #45，学术界与工业界的债分类谱系）的**互补面**——那张票看的是「债的既有分类学」，结论是所有既有体系的利息受损者都是人类；本票看的是「当下从业者的真实痛感」，结论是从业者痛感与既有债分类**只在部分处重合**，重合处正是「对 AI 不友好的债」的定义域。另：面向仓库的基准与 AI-readiness 静态打分工具的既有工作已在 [`docs/research/prior-art.md`](./prior-art.md) 中调研，本票不重复其内容，只在 §五的空档分析中引用其结论。

---

## 摘要（一屏版）

2024–2026 的从业者痛感可以归纳成一句话：**AI 把「写代码」变便宜了，于是瓶颈全部后移到「验证、理解、和让下一个 agent 别踩坑」上。**

- **个人开发者**的主要痛点不是「AI 写不出代码」，而是：agent 在真实代码库里**找不对地方**（探索多、token 贵）、**长会话丢失早期约束**（compaction 丢失用户指令）、**改动跨文件失手**（改了 A 漏了 B、编译通过但语义静默错误）、**验证回路跑不起来**（测试慢/缺测试/环境装不上）、以及**大规模返工**（JetBrains 两年 IDE 遥测：AI 用户每月删除/撤销动作比非用户多约 93 次）。
- **团队负责人**的痛点已经从「质量滑坡」具体化为**容量问题**：AI 生成的 PR 更大（+51%）、更多（GitHub PR 量三年 5 倍）、更容易带缺陷（~1.7x），而 review 人力没变 → 中位 review 时长 +441%、31% 的 PR 干脆不做任何 review；**「代码库理解」被 55% 的工程负责人列为头号担忧**，但「几乎没人在 code review 之外建立任何应对」。
- **最有说服力的三条数据**：(1) METR RCT——16 名资深开源开发者在自己熟悉的仓库上，允许用 AI 时任务耗时 **+19%**（而他们认为自己变快了）；(2) Sonar 2026 调查（1,149 人）——AI 已占已提交代码的 **42%**，**96% 的人不完全信任** AI 代码，但**只有 48% 每次提交前验证**；(3) Meta 工程博客——把 4,100+ 文件的部落知识编译成 59 份上下文文件后，agent 每次任务的工具调用与 token **减少约 40%**，上下文覆盖率从 **5% 升到 100%**。
- **判别结论（本票核心价值）**：从业者痛感里，真正指向「**代码库对 AI 不友好**」的是**一部分**，不是全部。指向该定义的主要是：未外化的部落知识、隐藏的跨模块依赖、验证回路缺失/慢、重复逻辑与多份真源、过时文档与死代码的主动误导、巨型文件与浅模块。**不指向**的同样重要：review 容量不足、junior 技能萎缩、信任与治理缺口、审查工具误报——这些是**人的组织问题**，不是仓库债（虽然会被 AI 债放大）。
- **最大空档**：所有既有解法都在**「改代码的人/AI」这一侧**发力（linter 管风格、Sonar 管规则违规、CodeScene 管人类 git 行为、context engineering 靠人写文档、AI review 只看 diff），**没有任何工具以「下一个 agent 在这个仓库里会不会迷路/犯错/多花 token」为判据、可测量、可跨语言复现地识别仓库债**。ETH Zurich 2026 年的 AGENTS.md 实验进一步说明：连「context 文件到底有没有用」这件事，业界此前都在猜，且**几乎没有人做过仓库级验证**。

---

## 一、证据分级与读法

本票把来源分成四档，正文中逐条标注：

| 标记 | 含义 | 例子 |
|---|---|---|
| **[RCT]** | 随机对照实验 / 受控实验 | METR 开发者生产力 RCT、Anthropic 技能形成 RCT |
| **[数据]** | 大样本调查或大规模遥测（含厂商遥测，需注明厂商身份） | DORA、Stack Overflow、Sonar、Faros、LinearB、JetBrains ICSE 2026、GitClear |
| **[论文]** | 同行评审或预印本的经验研究（非 RCT） | ETH AGENTS.md、Beyond Resolution Rates、CodeRabbit 审查研究 |
| **[一手实践]** | 一线工程师/团队的公开第一人称报告、HN 原始讨论、厂商工程博客 | Simon Willison、Kent Beck、Armin Ronacher、Meta Engineering、HN 讨论串 |

**读法警告（诚实记录）**：
1. **厂商数据要打折**。Faros（AI 工程效能平台）、LinearB（工程效能平台）、Sonar（代码质量厂商）、CodeRabbit（AI review 厂商）、GitClear（代码分析厂商）、Augment Code（AI 编码厂商）、GitLab（DevOps 平台）的报告都同时是**产品营销**。它们的数字方向彼此一致（review 变重、PR 变大、缺陷变多），但具体倍数不应作为独立验证。
2. **自我感知与客观数据系统性背离**。METR（开发者以为变快、实测变慢）、JetBrains（半数受访者认为编辑行为没变、日志显示删除量暴增）两处独立证据都指向同一现象。因此本票把「开发者自述」与「遥测/实验」分开标注。
3. **趋势正在快速变化**。METR 2026-02 主动声明其原始结论（19% 变慢）在 2026 年已不适用：同一批开发者在 2025 下半年估计为 **-18% 加速**（置信区间 -38%～+9%），新招募者 -4%，但样本存在严重选择偏差，作者自称「只有非常弱的证据」。**任何「AI 让开发者变快/变慢 X%」的静态结论都不可作为长期前提。**

---

## 二、人群 A：个人开发者——agent 在自己代码库上的失败现场

### 2.1 有数据支撑的失败模式

#### (A1) agent 找不对地方：探索成本高、检索失败
- **[论文]** 对 19 个 agent（8 框架 × 14 LLM）在 500 个 SWE-bench Verified 任务上的 **9,374 条轨迹**分析发现：成功与失败的判别信号不是轨迹长度（控制任务难度后该相关性反转，是混杂因子），而是**轨迹结构**——「先收集上下文再编辑、并投入验证」的 agent 稳定更成功，且这些策略是 agent 自定的、不随任务难度自适应（[Beyond Resolution Rates, arXiv:2604.02547](https://arxiv.org/html/2604.02547)，Abstract 与 RQ2）。同文记录：截至 2026-02，头部 agent 仍在 **20% 以上**的 SWE-bench Verified 任务上失败；**12 个「从未被任何 agent 解出」的任务只需要很简单的补丁**，人类标注者认为是简单题，所有 agent 都因**架构推理与领域知识缺口**而失败（Abstract、RQ1）。
- **[一手实践]** Meta 工程团队自述：把 agent 指向 Meta 的一条大规模数据流水线（4 个仓库、3 种语言、4,100+ 文件）时，「**agent 无法足够快地做出有用的编辑**」，原因是「**AI 没有地图**」——它不知道两种配置模式对同一操作使用不同字段名（搞混就静默输出错误），也不知道几十个「已废弃」枚举值绝不能删（序列化兼容性依赖它们）。无上下文时 agent 会「猜、探索、再猜，经常产出能编译但**微妙地错误**的代码」（[Meta Engineering, 2026-04-06](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)）。
- **[一手实践]** HN 上的直接问答串「Has anyone made a legacy codebase more legible to AI coding agents?」——提问者列出自己代码库的四类病：重复业务逻辑（无单一真源）、僵尸表/列、**隐式依赖与高变更耦合（「改这里也要改那里」）**、零文档（[HN 49698073](https://news.ycombinator.com/item?id=49698073)）。
- **[一手实践]** Armin Ronacher（Flask 作者）：「**上下文工程与管理仍然是重大挑战**。尽管我努力帮 agent 从各种文件和命令里拉取正确的数据，它们仍然不可靠——**拉得太多或太少**。长会话会让开头的上下文被遗忘。」（[Agentic Coding Things That Didn't Work, 2025-07-30](https://lucumr.pocoo.org/2025/7/30/things-that-didnt-work/)）

#### (A2) 上下文溢出与 compaction 丢失约束
- **[论文]** Chroma 的 *Context Rot* 技术报告评估 18 个模型（含 GPT-4.1、Claude 4、Gemini 2.5、Qwen3），发现模型**并非均匀使用上下文**：输入越长，即使在简单任务上性能也显著下降（[Context Rot, Chroma](https://www.trychroma.com/research/context-rot)）。
- **[论文]** 对「compaction（压缩上下文以继续任务）」的专门研究识别出一类**会话约束（Session Constraints）**——例如「在我确认前不要删除任何邮件」这类需要跨轮保持的用户指令——在上下文压力下被压缩后**系统性丢失**（[Lost in Compaction, arXiv:2608.11242](https://arxiv.org/abs/2608.11242)）。相关研究把这一现象称为 long-horizon agent 的 **compaction cliff**（[arXiv:2608.22752](https://arxiv.org/html/2608.22752)）。
- **[一手实践]** Ronacher 的「长会话会让开头的上下文被遗忘」与上述论文相互印证（同上）。
- **判别提示**：这一条**只有一部分**是仓库债（见 §四）。

#### (A3) 跨文件改动失手、静默错误
- **[论文]** Meta 的案例给出了最具体的失败形态：搞混两种配置模式的字段名 → **静默的错误输出**；引用错误的下游临时字段名 → **代码生成静默失败**；删除「已废弃」枚举值 → 破坏向后兼容。这些都不是语法错误，编译/静态检查抓不到（[Meta Engineering](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)）。
- **[一手实践]** HN 评论（原帖讨论「代码库维护该往哪走」）：「在我的经验里，发生的是代码库开始在自己重量下崩塌。**改一件事不可能不破坏另一件事**。coding agent 无法识别问题的全局范围，反复尝试局部修复。进度越来越慢，新功能成本越来越高。**全是新手在 greenfield 项目上会遇到的那套问题**。」（[HN 46521072](https://news.ycombinator.com/item?id=46521072)）
- **[一手实践]** HN「大型混乱遗留代码库上怎么用 AI」串：一位受访者给出的工作法本身就暴露了痛点——先把仓库喂给 agent 让它分析，产出优化建议 md，**必须在重构循环里带上全部相关测试**，并对比改前改后的输出「确保什么都没坏」；另一位提醒不要试图「教 AI 理解整个遗留代码库」，因为「**你只会耗尽全部可用上下文，塞满无关信息，agent 变得更笨更贵**」（[HN 47890749](https://news.ycombinator.com/item?id=47890749)）。

#### (A4) 验证回路跑不起来 / 缺测试
- **[论文]** Beyond Resolution Rates 的核心行为学结论即「**投入验证**的 agent 更成功」，且这一策略是 agent 自定的——意味着仓库若提供不了低成本验证回路，agent 就不会去验证（[arXiv:2604.02547](https://arxiv.org/html/2604.02547)）。
- **[一手实践]** Meta 的「五问」框架把「修改这个模块会破坏什么」列为必答项，说明**破坏面信息在仓库里本来不存在**，要靠 agent 扫描补出来（[Meta Engineering](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)）。
- **[一手实践]** HN 47890749 的建议明确要求「把全部相关测试纳入重构循环」——即验证回路是前提条件而非可选项。

#### (A5) 大规模返工（rework）
- **[数据]** JetBrains HAX 团队在 **ICSE 2026** 发表的研究：两年 IDE 遥测 + 800 名开发者 + 问卷与访谈。AI 用户的**删除/撤销动作每月显著增加约 100 次**，非 AI 用户同期只增加约 7 次（约 14 倍差距）；而**半数受访者认为自己采纳 AI 后编辑行为没有变化**（[JetBrains Research, 2026-04](https://blog.jetbrains.com/research/2026/04/ai-impact-developer-workflows/)）。
- **[数据]** DORA 2024（39,000+ 受访者）把 **rework rate** 新增为稳定性因子；同年 Google Cloud 官方博文给出的估算是：AI 采纳度上升伴随**交付吞吐下降 1.5%、交付稳定性下降 7.2%**（[Google Cloud Blog: Announcing the 2024 DORA report](https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report)；[DORA 2024 报告页](https://dora.dev/research/2024/dora-report/)）。DORA 2024 报告页亦明确「AI 也负面影响了软件交付的稳定性与吞吐」（[dora.dev](https://dora.dev/research/2024/dora-report/)）。
- **[RCT]** METR 早期研究：16 名资深开源开发者、246 个任务、在平均有 5 年经验的成熟仓库上，允许用 AI 时任务耗时**增加 19%**（CI +2%～+39%），而开发者主观认为自己变快（[METR blog](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)、[arXiv:2507.09089](https://arxiv.org/abs/2507.09089)）。**2026 年更新已推翻其现时有效性**（[METR, 2026-02-24](https://metr.org/blog/2026-02-24-uplift-update/)），但该研究的方法学价值在于：**主观速度感与客观耗时可以完全相反**。

#### (A6) 生成的代码「看起来对」——幻觉与似是而非
- **[数据]** CodeRabbit 分析 470 个真实开源 PR（320 个 AI 共同署名 / 150 个人类）：「AI PR 的问题数约 **1.7 倍**」（平均 10.83 vs 6.45），逻辑与正确性问题高 **75%**，安全问题上至 **2.74 倍**，可读性问题 3 倍以上（[CodeRabbit 报告](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)、[报告 PDF](https://hs-43613284.f.hubspotemail.net/hubfs/43613284/CodeRabbit%20-%20State%20of%20AI%20vs%20Human%20Code%20Generation%20-%20Report%20-%20Lite.pdf)；第三方转述 [The Register](https://www.theregister.com/software/2025/12/17/ai-authored-code-needs-more-attention-contains-worse-bugs/2576263)）。
- **[数据]** GitClear 分析 2020–2024 年 **2.11 亿行**结构化代码变更：「代码克隆 4 倍增长」，且历史上首次出现**复制粘贴的代码行数超过「移动」的代码行数**（[GitClear](https://www.gitclear.com/ai_assistant_code_quality_2025_research)；二手摘要 [LeadDev](https://zephrcf.leaddev.com/technical-direction/how-ai-generated-code-accelerates-technical-debt)）。
- **[数据]** Veracode 2025 GenAI 代码安全报告：80 个任务 × 100+ LLM，**45% 的任务产出了带 OWASP 类风险的代码**；当同时存在安全写法与不安全写法时，模型选择不安全写法的比例同样是 45%（[Veracode 报告](https://www.veracode.com/resources/analyst-reports/2025-genai-code-security-report/)、[报告 PDF](https://www.veracode.com/wp-content/uploads/October-2025-GenAI-Code-Security-Report-Update.pdf)）。
- **判别提示**：CodeRabbit/Veracode 衡量的是**产出缺陷**，不是「仓库债」。二者不可混淆（见 §四）。

### 2.2 轶事性的失败现场（无量化，但形态重要）

- **[一手实践]** Simon Willison 给出的「生产级 AI 编程黄金法则」：**「如果我不能向别人准确解释这段代码在做什么，我就不把它提交进仓库。」** 他同时指出 vibe coding 的定义正在被稀释成「一切 AI 辅助编程」，而真正的 vibe coding 是「**不看生成的代码**」（[Not all AI-assisted programming is vibe coding, 2025-03-19](https://simonwillison.net/2025/Mar/19/vibe-coding/)；[Two publishers and three authors fail to understand what "vibe coding" means, 2025-05-01](https://simonwillison.net/2025/May/1/not-vibe-coding/)）。
- **[一手实践]** Kent Beck 的「augmented coding」系列把设计退化讲得很直白：标题即 **「The Genie Eats The Seed Corn（精灵吃掉了种子玉米）」**——AI 会消耗掉未来的设计余量换取当下的功能推进；他同时认为当前的 genie「**擅长探索（exploration），不擅长扩展与萃取（expansion & extraction）**」（[Augmented Coding & Design](https://newsletter.kentbeck.com/p/augmented-coding-and-design)；[Augmented Coding is Good For Exploration](https://newsletter.kentbeck.com/p/augmented-coding-is-good-for-exploration)；[Augmented Coding: Beyond the Vibes](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes)）。
- **[一手实践]** HN 上反复出现的 brownfield 判断：LLM 在遗留项目上表现差，是因为这些代码库「以专有方式实现了框架、或根本不用公共框架、或写得非常小众」，因此**训练语料里没有相似代码**（[HN 45127624](https://news.ycombinator.com/item?id=45127624)）；「所有成功案例看起来都是 greenfield……三周后任务变成对已完成东西的维护和迭代时呢？」（[HN 42618961](https://news.ycombinator.com/item?id=42618961)）；「Opus 在试图……时会明显翻车」（[HN 48560711](https://news.ycombinator.com/item?id=48560711)）。
- **[一手实践]** 反例也记录：HN 49698073 中一位开发者称，把一个 TypeScript 代码库整理到「类型检查是因为正确的理由而通过」之后，「**代码变好之后我能轻松改，agent 也能**」——他自己并未大量投入 AGENTS.md，而是写「对任何人都说得通」的注释（[HN 49698073](https://news.ycombinator.com/item?id=49698073)）。

---

## 三、人群 B：团队负责人——可维护性、review 负担、质量滑坡、junior 成长

### 3.1 采纳面：AI 已是默认，且体量惊人

- **[数据]** DORA 2025（近 5,000 名技术从业者）：**90%** 在工作中使用 AI（同比 +14%），**80% 以上**认为生产力提升，但 **30% 表示对 AI 生成的代码「几乎没有信任」**；报告主线结论是「**AI 是放大器**——放大高效组织的优势，也放大挣扎组织的失能」（[dora.dev/research/2025](https://dora.dev/research/2025/dora-report/)；[Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report)；[Thoughtworks 版 PDF](https://www.thoughtworks.com/content/dam/thoughtworks/documents/report/tw_report_state_of_ai_assisted_software_development_2025.pdf)）。
- **[数据]** Stack Overflow 2025（49,000+ 受访者、177 国）：**84%** 使用或计划使用 AI；**46% 主动不信任** AI 输出准确性，仅 **33% 信任**，**只有 3% 表示「高度信任」**；资深开发者最谨慎（高度信任 2.6%、高度不信任 20%）。同期关于 agent：**52% 不用 agent 或只用更简单的 AI 工具，38% 明确没有采纳计划**（[Stack Overflow 2025 AI 章节](https://survey.stackoverflow.co/2025/ai)；[官方新闻稿](https://stackoverflow.co/company/press/archive/stack-overflow-2025-developer-survey/)）。Stack Overflow 官方博客另给出信任从 2024 年 40% 降至 2025 年 29%（[Stack Overflow Blog](https://stackoverflow.blog/2025/12/29/developers-remain-willing-but-reluctant-to-use-ai-the-2025-developer-survey-results-are-here/)）。
- **[数据]** Stack Overflow 2026 年 5 月 pulse 调查：**agentic 使用率较上次年度调查近乎翻倍（59%）**，但「**大多数仍是单 agent 且受人工监控**」（[Agents on a leash, 2026-05-27](https://stackoverflow.blog/2026/05/27/agents-on-a-leash-agentic-ai-remains-mostly-monitored-at-work/)）。
- **[数据]** Sonar 2026 State of Code（1,149 名专业开发者，2025-10 田野）：**72%** 用过 AI 的人每天使用；**AI 已占已提交代码的 42%**，预计 2027 年达 **65%**；**96% 不完全信任 AI 代码功能正确**；**只有 48% 每次提交前都验证**；**38% 表示 review AI 代码比 review 人类代码更费力**（[Sonar 新闻稿](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/)、[报告 PDF](https://www.sonarsource.com/state-of-code-developer-survey-report.pdf)）。
- **[数据]** GitLab 2026 AI Accountability Report（Harris Poll，1,528 名开发者与技术决策者，6 国）：**80%** 认为组织采纳 AI 工具的速度快于其治理政策的建立；**92%** 报告对 AI 生成代码存在治理挑战；**91%** 组织同时使用 2 个以上 AI 编码工具、54% 用 3 个以上；60% 称 ROI 超预期（[GitLab 新闻稿, 2026-06-23](https://about.gitlab.com/press/releases/2026-06-23-gitlab-research-reveals-organizations-are-generating-ai-code-faster-than-they-can-control-it/)、[报告页](https://about.gitlab.com/resources/ai-accountability-survey-2026/)）。
- **[数据]** Google 官方口径的演进：2024-10 「超过 25% 的新代码由 AI 生成，再由工程师审核接受」→ 2026-04 「**75% 的新代码由 AI 生成**」（[ITPro 2024](https://www.itpro.com/technology/artificial-intelligence/sundar-pichai-says-more-than-25-percent-of-googles-code-is-now-generated-by-ai-and-its-a-big-hint-at-the-future-of-software-development)；[Business Insider 2026-04-22](https://www.businessinsider.com/google-ai-generated-code-75-gemini-agents-software-2026-4)）。
- **[数据]** GitHub Octoverse 2025：一年新增 3,600 万开发者（180M+ 总量）、9.86 亿次 commit；**80% 的新开发者在第一周内使用 Copilot**；Copilot coding agent 已产出 **100 万+ PR**（[Octoverse 2025](https://octoverse.github.com/)、[GitHub Blog](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/)）。

### 3.2 痛点 B1：可维护性与「代码库理解」——负责人口中的头号担忧

- **[数据]** Augment Code《State of AI-Native Engineering 2026》（**219 名工程负责人**）：**48% 的代码由 AI 生成**；**「代码库理解（codebase comprehension）是头号担忧，55% 将其列为最大忧虑，但几乎没人在 code review 之外建立任何应对」**；**89% 的负责人听到工程师担心自身技能相关性，但只有 19 个组织调整了岗位定义**（[Augment Code 报告页](https://www.augmentcode.com/resources/state-of-ai-native-engineering-2026)、[报告 PDF](https://www.augmentcode.com/downloads/state-of-ai-native-engineering-2026.pdf)）。厂商身份需计入折扣，但「55% 列头号担忧」与「无人认领」这两个命题在 Faros/Madrona/GitLab 三处独立来源方向一致。
- **[数据]** LeadDev《Engineering Leadership Report 2026》：工程领导者的优先级里，「改善既有产品质量」51%、「技术债与维护」48%——即团队在做「存量收拾」而非「增量扩张」（[LeadDev 报告 PDF](https://leaddev.com/wp-content/uploads/2026/06/ENGINEERING_LEADERSHIP_REPORT_2026_FINAL.pdf)）。

### 3.3 痛点 B2：review 负担——从「质量滑坡」变成「容量崩塌」

- **[数据]** Faros AI《AI Engineering Report 2026 – Acceleration Whiplash》（数千个工程团队的遥测）：高 AI 采纳度下，**PR 体积 +51.3%**、**每 PR 修改文件数 +59.7%**、**每 PR bug 数 +54%**、**中位 PR review 时长 +441.5%**（平均 +199.6%）、**首次 review 等待时间 +156.6%**、**未做任何 review 就合并的 PR +31.3%**、**任务在制品时长 +225.2%**；2026 年 **25% 的 PR 由 AI agent 审查**（2025 年为 0%）（[Faros Blog](https://www.faros.ai/blog/ai-code-quality-senior-engineer-review-burden)）。**厂商遥测，但「review 队列断裂」的方向在四处独立来源重复。**
- **[数据]** LinearB 2026 Benchmarks（2.7M PR）：**88.3% 的组织每天或每周使用 AI 辅助工具**（2024 年初为 71.6%）；**AI agent 产出的 PR 等待首次 review 17.6 小时，无辅助 PR 为 3.4 小时（5.25 倍差距）**；AI PR 30 天内合并率 **32.7%**，无辅助 PR 为 **84.4%**；**44.7% 的组织没有正式度量 AI 的影响**；即便是「精英」组织，**自主 agent 产出的 PR 占比仍低于 5%**（[LinearB: AI in software development 2026](https://linearb.io/library/ai-in-software-development)、[2026 Benchmarks 报告 PDF](https://assets.linearb.io/image/upload/v1777392920/resources/LinearB_2026_Software_Engineering_Benchmarks_Report.pdf)）。
- **[论文]** 企业「2× 命令」纵向案例研究：**802 名开发者、196,212 个 PR（2024-01 至 2026-04）**，人均吞吐最终达基线 **2.09 倍**；代价是**每位 reviewer 的负载大致翻倍**，**自动审查量超过人工审查量**，而 merge 与 revert 率保持稳定（[arXiv:2607.01904](https://arxiv.org/html/2607.01904v1)）。
- **[数据]** Madrona 2026 Builders Summit 调查（**49 名产品/工程负责人，合计 10,000+ 工程师**）：瓶颈已转移——**57% 点名「code review 队列时间」**、**49% 点名「规格/需求清晰度」**；「什么在阻止团队给 AI 更多自主权」的头号答案是**验证与人工 review 的容量**（小团队与大团队各约 35%）；**63% 主要依赖轶事反馈与团队情绪度量生产力，仅 16% 用 DORA 式指标**；19%（小团队）/17%（大团队）报告「更快但质量更波动或更差」（[Madrona](https://www.madrona.com/on-to-the-next-bottleneck-what-product-engineering-leaders-told-us-about-ai-in-software-development/)）。
- **[一手实践]** Gergely Orosz 汇总了业界正在试的七种应对：人类 review「AI 的 review」、按 blast radius 分级（OpenAI/Anthropic 在用）、只 review 计划/测试/数据库 schema 而不 review 实现、让 agent 产出更小的 PR、全人工 review、以及「要不要干脆取消人工 review」；他同时给出背景数据：**三年间 GitHub 上打开的 PR 数增长 5 倍，且从 2025 年底起 PR 与 commit 数近乎翻倍**（[Pragmatic Engineer: What is happening with code reviews?](https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews)）。
- **[论文]** 「AI 生成的代码更难 review」有可解释的机制：AI 代码**在风格上是得体的**，失败在表面之下（误解需求、看似合理的错误边界处理、解决了相似但非指定的问题），因此人类 review 者惯用的「气味信号」失效，必须切换到「重建意图」的高强度认知模式（[Faros Blog](https://www.faros.ai/blog/ai-code-quality-senior-engineer-review-burden)；引语来自该文引用的工程负责人，属轶事性）。

### 3.4 痛点 B3：junior 成长与「never-skilling」

- **[RCT]** Anthropic 与研究者合作的随机对照实验（Shen & Tamkin）：52 名（多为 junior）工程师学习一个新的 Python 异步库，AI 组 vs 手写组。AI 组任务完成**略快但不显著**；测验分数 **50% vs 67%**（约差近两个字母等级；Cohen's d=0.738，p=0.01），**差距最大的是调试类题目**。且「怎么用 AI」决定结果：以生成后追问/混合解释方式使用的人得分高，纯委托/渐进依赖/让 AI 调试的人得分低（[Anthropic 研究博客](https://www.anthropic.com/research/AI-assistance-coding-skills)、[arXiv:2601.20245](https://arxiv.org/abs/2601.20245)、[ICLR 2026](https://iclr.cc/virtual/2026/10022087)）。作者明确提示：真实 agentic 产品的影响「**可能比本研究结果更显著**」。
- **[数据]** Microsoft Research 与 CMU 的调查（319 名知识工作者、936 个一手案例）：对 AI 越有信心，投入批判性思考的努力越少；自述性质（[论文 PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2025/01/lee_2025_ai_critical_thinking_survey.pdf)、[出版页](https://www.microsoft.com/en-us/research/publication/the-impact-of-generative-ai-on-critical-thinking-self-reported-reductions-in-cognitive-effort-and-confidence-effects-from-a-survey-of-knowledge-workers/)）。
- **[一手实践]** Anthropic 内部调研（2025-08，132 名工程师/研究员 + 53 次深度访谈）：Claude 覆盖其 60% 的工作，自评生产力提升 50%；**27% 的 Claude 辅助工作是本来不会做的工作**；但**大多数人表示只能把 0–20% 的工作「完全委托」**；技能上「**广度扩大、深度退化**」的担忧普遍存在，员工对此态度分裂（[Anthropic: How AI is transforming work at Anthropic](https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic)）。
- **[一手实践]** Microsoft 的两位知名开发者（Russinovich、Hanselman）公开警告 agentic AI 的生产力收益正在**抽空 junior 开发者管道**（[The New Stack, 2026-04-02](https://thenewstack.io/agentic-ai-junior-developer-crisis/)）。
- **[数据]** Augment Code 的 89% / 19 个组织对比（见 §3.2）是同一痛点在企业侧的量化镜像。

### 3.5 痛点 B4：信任、治理与「验证缺口」

- **[数据]** Sonar 的「验证缺口」：96% 不完全信任 vs 只有 48% 每次验证 vs 38% 认为 review AI 代码更费力——三者构成一个自相矛盾的循环（[Sonar](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/)）。
- **[数据]** GitLab：92% 报告 AI 生成代码的治理挑战、80% 采纳快于治理（[GitLab](https://about.gitlab.com/press/releases/2026-06-23-gitlab-research-reveals-organizations-are-generating-ai-code-faster-than-they-can-control-it/)）。
- **[数据]** DORA 2025：30% 对 AI 生成代码「几乎没有信任」，报告据此提出「**需要批判性验证技能**」（[dora.dev](https://dora.dev/research/2025/dora-report/)）。
- **[数据]** Madrona：63% 靠轶事度量、44.7%（LinearB）不正式度量——**「质量是否滑坡」这个问题在多数组织里连度量手段都没有**。

### 3.6 反例与减弱的信号（诚实记录）

- **[RCT]** METR 2026 更新：同一批开发者现在估计 **-18% 加速**（选择偏差严重，作者自称证据很弱）（[METR](https://metr.org/blog/2026-02-24-uplift-update/)）。
- **[论文]** 企业 2× 案例中 **merge 率与 revert 率保持稳定**，自动审查接管了大部分 review（[arXiv:2607.01904](https://arxiv.org/html/2607.01904v1)）。
- **[一手实践]** Anthropic「How Claude Code is used in practice」（约 **400,000 个会话**、约 235,000 人、2025-10 至 2026-04）：在编码任务上，**各类职业的会话成功率与软件工程师接近**；**调试类会话占比在七个月内下降近一半**；人类做「做什么」的规划决策，Claude 做「怎么做」的执行决策；**领域专长越高，单条指令下 Claude 完成的工作越多**（[Anthropic](https://www.anthropic.com/research/claude-code-expertise)）。→ 这条对 CogniCode 很重要：**agent 能力在快速上升，仓库债的相对重要性会随之变化**。
- **[数据]** Faros 引用的 CodeRabbit 数据：AI review 评论数 +25%、平均评论长度 +22.7%，但人类 review 负担未降——**AI 审 AI 不是解药**（[Faros](https://www.faros.ai/blog/ai-code-quality-senior-engineer-review-burden)）。

---

## 四、核心判别：哪些痛点指向「对 AI 不友好的债」

定义（本仓锚定）：**「对 AI 不友好的债」= 会让下一个 AI agent 在这个仓库里迷路 / 犯错 / 爆炸（含多花 token、多走弯路）的仓库状态。** 判据主体是 agent 的表现，不是人类的维护成本（对照见 [`debt-taxonomy.md`](./debt-taxonomy.md) §五：既有体系无一以 agent 表现为判据）。

### 4.1 判别表

| # | 从业者痛点（出处） | 指向「对 AI 不友好的债」？ | 六维度映射 | 关键证据 |
|---|---|---|---|---|
| 1 | 部落知识/隐式约定未外化，agent 无「地图」（Meta、HN 49698073、Ronacher） | **是（最强）** | 可解性 + 可导航性 | Meta：上下文覆盖 5%→100%，工具调用/token **-40%**；无上下文时 agent 反复猜、产出「能编译但微妙错误」的代码 |
| 2 | 隐藏的跨模块依赖/变更传播（改 A 必须改 B，代码里看不出来） | **是** | 变更安全性 | Meta 的 50+「非显然模式」（字段名不一致导致静默错误、废弃枚举不能删）；HN「改一处必坏另一处」 |
| 3 | 重复业务逻辑 / 多份真源（GitClear 克隆 4 倍增长） | **是** | 变更安全性 + 可解性 | agent 改一处漏一处；CodeScene 的 change coupling 判据可平移为「agent 破坏半径」 |
| 4 | 验证回路缺失/慢：缺测试、测试慢、环境装不上 | **是** | 环境可用性 + 变更安全性 | Beyond Resolution Rates：**先收集上下文再编辑 + 投入验证** 的 agent 稳定更成功；HN 47890749 把「带上全部相关测试」列为前提 |
| 5 | 过时文档 / 死代码主动误导 | **是** | 可解性（负信号） | HN 49698073 与 47890749 的实践共识；既有体系中「死代码对人类零利息」的判断在此反转 |
| 6 | 巨型文件 / 浅模块 / 深嵌套 | **是（效率子集）** | 效率 + 可导航性 | 与 Chroma context rot、Lost in Compaction 的机制叠加：token 越多、模型越不可靠；本仓 `big_file`/`module_depth` 信号已实现 |
| 7 | flaky / 不稳定环境 | **是** | 可诊断性 | agent 会误判失败为成功、误判成功为失败；且污染任何动态测量的样本 |
| 8 | 长会话中丢失会话约束（compaction 丢弃用户指令） | **部分（仓库侧子集）** | 可诊断性 + 可解性 | Lost in Compaction 证明是**运行时机制**问题；仓库侧的可控子集是「关键约束是否被外化到 agent 每次都能读到的位置」 |
| 9 | agent 找不到正确文件、探索成本高 | **部分** | 可导航性 | Beyond Resolution Rates：12 个「简单补丁但全员失败」的任务，根因是**架构推理与领域知识**而非补丁复杂度——其中「领域知识」部分是可债化的仓库状态 |
| 10 | 需求/规格不清（Madrona 49% 点名） | **部分（边界）** | — | 按 `debt-taxonomy.md` §六第 7 行，需求债几乎全部判 (b)：需求是 agent 的**输入**而非仓库摩擦；但「实现与文档矛盾」会误导 agent，归入 #5 |
| 11 | review 容量崩塌 / senior engineer tax（Faros、LinearB、Madrona） | **否** | — | 这是**人的组织容量**问题；仓库债会放大它，但它本身不是仓库状态 |
| 12 | junior 技能萎缩 / never-skilling（Anthropic RCT、MS/CMU） | **否** | — | 人的认知问题，与仓库是否对 agent 友好正交 |
| 13 | 信任下降 / 治理缺口（GitLab、DORA、Sonar） | **否** | — | 政策与流程问题 |
| 14 | AI 代码引入安全漏洞（Veracode 45%） | **否**（按定义） | — | 漏洞不让 agent 迷路/变慢；与 `debt-taxonomy.md` §六第 13 行一致，应显式列为非目标 |
| 15 | AI 审查工具误报率高（CodeRabbit 研究：56.3% 被拒） | **否** | — | 工具质量问题，不是仓库债；但它解释了为什么「AI 审 AI」不能替代仓库级债识别 |
| 16 | 「代码库理解」成为头号担忧但无人应对（Augment 55%） | **是（需求信号，不是债本身）** | 全部 | 这是本票最重要的**市场证据**：痛点被负责人确认，解法空缺 |

### 4.2 三条判别法则（供 CogniCode 债项判定复用）

1. **换主体测试**：把受损方从「人类维护者」换成「下一个 agent」，痛感是否仍然成立且可观测？成立 → 是 AI 不友好债；不成立 → 是人本问题（#11–#13）。
2. **产物 vs 判据**：社会债/人员债的**产物**（文档、规范、补偿性工件）恰好是 agent 导航所依赖的，但其**判据**（人员分布、知识流失）与 agent 受损无关。凡属此类，只取其产物、不取其判据（与 `debt-taxonomy.md` §六第 12 行一致）。
3. **产出缺陷 ≠ 仓库债**：AI 生成了带 bug 的代码（#14、CodeRabbit 的 1.7x）说明的是**生成质量**；仓库债说的是**仓库状态让任何 agent 都更容易出错**。区分方法是：换一个更强的模型、重跑同一任务，痛感是否消失？消失 → 生成质量问题；不消失 → 仓库债。（Meta 的「无地图时任何模型都要猜」与 Beyond Resolution Rates 的「换更强 LLM 后框架差异缩小、但 12 个任务全员失败」正好给出两侧的实证。）

### 4.3 从痛感到债项的「可测量信号」候选

以下信号在语料中反复出现，且**理论上可确定性提取**（不依赖 LLM 判分）：

| 债项 | 可测信号 | 语料依据 |
|---|---|---|
| 部落知识缺失 | 关键模块无注释/无 README/无 AGENTS.md 覆盖；跨模块依赖只能靠读代码发现 | Meta 的覆盖率指标（5%→100%）与「五问」框架 |
| 隐式变更耦合 | git 共同变更历史（CodeScene 式）+ 静态 import/call 图之差 | Meta 的跨仓依赖索引（把「什么依赖 X」从 ~6000 token 的探索降到 ~200 token 的图查询） |
| 重复逻辑 | 克隆检测（GitClear 的 copy/paste vs moved 指标） | GitClear 4 倍克隆增长 |
| 验证回路缺失 | 是否有测试命令、测试能否冷启动跑通、测试耗时、F2P/P2P 覆盖 | Beyond Resolution Rates 的「验证投入」结论；本仓 probe 资产 |
| 主动误导 | 文档/注释与实现矛盾、死代码可被 import | HN 实践共识 |
| 导航摩擦 | 巨型文件/深嵌套/浅模块、入口可发现性 | Chroma context rot（token 越多越不可靠）+ 本仓已有信号 |

---

## 五、空档分析：既有解法各自认领了什么，谁没被认领

### 5.1 既有解法覆盖表

| 痛点（§四编号） | linter / 静态分析 | SonarQube 类 | CodeScene 类 | context engineering（人写） | AGENTS.md / CLAUDE.md | spec-driven（spec-kit / Kiro） | AI code review 工具 | 无人认领？ |
|---|---|---|---|---|---|---|---|---|
| #1 部落知识缺失 | 否 | 否 | 部分（知识孤岛是人类维度） | 部分（靠人写，无验证） | 部分（且实证效果边际） | 部分（只覆盖新功能） | 否 | **是** |
| #2 隐式变更耦合 | 部分（静态图） | 部分 | 是（共同变更，判据是人的协调成本） | 否 | 否 | 否 | 否 | **部分** |
| #3 重复逻辑 | 是 | 是（code smell） | 部分 | 否 | 否 | 否 | 部分 | 否 |
| #4 验证回路缺失 | 否 | 否 | 否 | 部分（规范要求，无测量） | 部分 | 部分 | 否 | **是** |
| #5 过时文档误导 | 否 | 部分（TODO/FIXME） | 否 | 部分 | 部分 | 否 | 否 | **是** |
| #6 巨型文件/浅模块 | 是 | 是（复杂度规则） | 是（code health） | 否 | 否 | 否 | 否 | 否 |
| #7 flaky 环境 | 否 | 否 | 否 | 否 | 否 | 否 | 否 | **是**（人类 CI 工具管 flaky，但**不以 agent 为受害方**） |
| #9 找不到文件 | 否 | 否 | 否 | 部分（靠人维护检索线索） | 部分 | 否 | 否 | **是** |
| #10 规格不清 | 否 | 否 | 否 | 否 | 否 | **是（这正是 SDD 的主场）** | 否 | 否 |
| #11–#15 人本/治理/生成质量 | 部分 | 部分 | 部分 | 否 | 否 | 否 | 是（AI review） | 否（有明确归属方） |

### 5.2 逐个解法的能力边界与证据

1. **linter / 静态分析**：只能抓风格、语法、复杂度、部分安全模式。Faros 的表述最直白：**「linting 无法抓住与错误需求解释内在一致的逻辑失败。一个以完美语法处理了错误边界情况的函数会通过所有 linter 检查，但它仍然是错的。」**（[Faros](https://www.faros.ai/blog/ai-code-quality-senior-engineer-review-burden)）此外，静态分析在工业界本身还受高误报率困扰（[ICSE 2026 SEIP: Reducing False Positives in Static Bug Detection with LLMs](https://conf.researchr.org/details/icse-2026/icse-2026-software-engineering-in-practice/72/Reducing-False-Positives-in-Static-Bug-Detection-with-LLMs-An-Empirical-Study-In)）。
2. **SonarQube 类**：仍以「规则违规」为判据，债 = 修复工时的加总（见 [`debt-taxonomy.md`](./debt-taxonomy.md) §3.2）。Sonar **已经认识到 AI 代码需要不同标准**，推出了 *AI Code Assurance* 与 **`Sonar way for agentic AI` quality gate**，官方说明其动机是「传统质量配置与质量门是为人类开发者调优的，把 agentic AI 代码按同一标准要求并不合适」（[AI Code Assurance](https://www.sonarsource.com/solutions/ai/ai-code-assurance/)、[Sonar way for agentic AI quality gate](https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/ai-code-assurance/quality-gate-for-agentic-ai)）。**但它的做法仍是「对 AI 生成的代码用更严的规则阈值」，而不是「测量仓库是否让 agent 迷路」**——这是最接近的邻接者，也是定位必须区分的对象。
3. **CodeScene 类**：行为数据全部来自人类活动（commit 频率、作者分布、Jira），严重度是人的协调成本与缺陷密度（见 [`debt-taxonomy.md`](./debt-taxonomy.md) §3.3）。它的 **change coupling** 判据（git 共同变更）恰好是 agent 破坏行为的天然预测器——**信号可借用，判据必须换轴**（从「人类协调成本」换成「agent 破坏率/返工率」）。
4. **context engineering（实践）**：Anthropic 把它定义为「为 agent 策划最小高信号 token 集合」的纪律，并给出子 agent 隔离上下文、程序化工具调用等手法（[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)）。**它是一套人/框架侧的做法，不含任何仓库级测量或验收。** Ronacher 的一手报告正好说明其脆弱性：他试过 slash commands、hooks、sub-agents 自动化，「**几乎没有一样留下来**」，最后回到「多跟机器说话、多给上下文」；并指出 agent 拉取上下文「**拉得太多或太少**」（[Ronacher](https://lucumr.pocoo.org/2025/7/30/things-that-didnt-work/)）。
5. **AGENTS.md / CLAUDE.md**：格式无实质规范、建议高度同质化，且**有效性此前无严格验证**。ETH Zurich 的研究（2026）用 AGENTbench + SWE-bench Lite 系统测试后给出反直觉结论：**开发者手写的 context 文件平均只带来 +4% 提升，LLM 自动生成的文件平均带来 -3% 的负效果，而两者都把推理成本推高 20% 以上**（context 文件让 agent 探索/测试/推理更多）；建议「暂时不要用 LLM 生成的 context 文件，手写文件只写**无法推断的**最小要求（如特定工具链、自定义构建命令）」（[Evaluating AGENTS.md, arXiv:2602.11988](https://arxiv.org/html/2602.11988v1)）。另一项研究从效率角度切入（10 个仓库、124 个 PR）评估 AGENTS.md 对运行时间与 token 消耗的影响（[arXiv:2601.20404](https://arxiv.org/html/2601.20404)）。
   - **重要反例**：Meta 公开反驳了上述结论的普适性——ETH 的实验跑在 Django/matplotlib 这类**模型预训练里已经很熟**的开源库上，此时 context 文件是冗余噪音；而 Meta 的专有 config-as-code 里，部落知识**不存在于任何模型的训练数据中**。Meta 的三条设计约束（**每份文件 25–35 行 ≈1,000 token、按需加载而非常驻、多轮 critic 质量门**）使其得到 +40% 效率的结果（[Meta Engineering](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/)）。
   - **对 CogniCode 的直接含义**：context 文件的效果**依赖于仓库**——这恰好证明「**仓库级测量**」是必要的，而不是「写一份更好的 AGENTS.md」是通用解。
6. **spec-driven development（spec-kit / Kiro）**：认领的是 #10（规格不清）——把规格前置为工件（[github/spec-kit](https://github.com/github/spec-kit/)、[Kiro 对比](https://codemyspec.com/blog/spec-kit-vs-kiro)）。它解决「agent 的输入质量」，不解决「仓库本身让 agent 迷路」。且已有实践报告指出 spec-kit 的 branch-per-spec 工作流本身会**加重 review 负担**（[Particula](https://particula.tech/blog/spec-driven-development-tools-spec-kit-vs-kiro-vs-tessl)）。
7. **AI code review 工具（CodeRabbit/Greptile/Copilot Review/…）**：认领 #11（review 容量）。实证效果并不乐观：
   - **[论文]** 31,073 条 review–反馈配对（10,191 个 PR、239 个仓库）：**36.4% 被接受、7.3% 引发讨论、56.3% 被拒**；被拒主因是误报、冗余、超范围、与开发者意图/实践不符；且 agentic review **更偏功能性问题、更少涉及可演化性（evolvability）问题，而后者恰恰更容易无效**（[arXiv:2607.03316](https://arxiv.org/abs/2607.03316)）。
   - **[论文]** 54,791 条 agent 生成的 review 评论（5 个 agent × 342 个 Python 仓库）：未解决评论的主因是「建议本身错误」与「这是有意的设计决策」；**内联代码建议是评论被解决的最强预测因子，冗长复杂的评论更少被采纳**（[arXiv:2607.21997](https://arxiv.org/abs/2607.21997)）。
   - **[论文]** SWE-PRBench：8 个前沿模型在「只看 diff」的配置下**只能检出 15–31% 的人类标注问题**（[SWE-PRBench](https://www.researchgate.net/publication/403262187_SWE-PRBench_Benchmarking_AI_Code_Review_Quality_Against_Pull_Request_Feedback)）。
   - **关键结构性问题**：AI review 工具看的是 **diff**，不是 **仓库**。它无法知道「这个改动会撞上哪条没写下来的约定」，因为这恰恰是 #1/#2 类债。
8. **「vibe code cleanup」服务**：市场已经出现专门的「AI 代码清理」咨询与外包（[Proof of Work Studio](https://proofofwork.studio/writing/vibe-code-cleanup)、[Scrums.com](https://www.scrums.com/blog/vibe-coding-cleanup-as-a-service)、[Triple Minds](https://tripleminds.co/ai/vibe-coding-cleanup-services)、[Builder.io 的 de-slop 实践](https://www.builder.io/blog/de-slop-ai-generated-codebase)）。这证明**需求真实且已付费**；但它是**人力、一次性、无标准度量**的——「清理到什么程度算好」没有判据，也无法证明下一个 agent 会变好。
9. **组织侧框架（DORA AI Capabilities Model 等）**：DORA 2025 给出七个能力（技术+文化）来放大 AI 的正向影响（[dora.dev](https://dora.dev/research/2025/dora-report/)）。层次是**组织/流程**，不是仓库；且 Madrona 数据显示只有 16% 的组织在用 DORA 式指标，说明其落地率有限。
10. **静态 AI-readiness 打分（DAF 等）**：见 [`prior-art.md`](./prior-art.md) §三——纯静态信号、无 agent 执行、权重无实证校准。

### 5.3 空档总结：三块真正无人认领的地方

1. **以「下一个 agent 的表现」为判据的仓库级债识别。** 所有既有工具或从「规则违规」（Sonar）、或从「人类行为数据」（CodeScene）、或从「人写的文档」（AGENTS.md/context engineering）、或从「diff」（AI review）出发。**没有一个是把「agent 在这个仓库里迷路/犯错/多花 token」当作被测量的对象。** 这与 [`debt-taxonomy.md`](./debt-taxonomy.md) §五的结论互为正反面：学术分类学没有 agent 判据，从业者工具也没有。
2. **「仓库对 AI 友好度」的可验证性。** ETH 的 AGENTS.md 实验与 Meta 的反驳共同暴露了一个空白：**context 文件/文档/规范的有效性高度依赖仓库，但业界既无验证手段也无验收标准。** Meta 自己造了一套（50+ agent、59 份文件、多轮 critic、定期自刷新），但那是**一次性工程**，不是可复用的工具能力。**「这份 AGENTS.md 在这个仓库上到底有用吗」——没人能回答。**
3. **验证回路与 flaky 环境的 agent 视角。** CI 工具管 flaky 测试是为了人类不被打扰；但 flaky 对 agent 的伤害是**双向的**（误判失败/误判成功），且直接污染任何基于 agent 执行的测量。这个受害方视角目前**没有工具认领**。

---

## 六、对 CogniCode 重定位的启示

**定位陈述的证据基础**（把本票证据直接映射到「为什么是现在、为什么是 CogniCode」）：

1. **「为什么是现在」有三重证据**：
   - **体量**：AI 已占已提交代码 42%（Sonar 2026）、Google 新代码 75%（2026-04）、GitHub PR 量三年 5 倍。
   - **痛感已被决策层确认**：55% 工程负责人把「代码库理解」列为头号担忧，且自认**没有 code review 之外的应对**（Augment Code 219 人）；57% 点名 review 队列、49% 点名规格清晰度（Madrona 49 人 / 10,000+ 工程师）；92% 报告治理挑战（GitLab 1,528 人）。
   - **现有解法已被证伪或不足**：AI 审 AI 的接受率仅 36.4%、拒收 56.3%（31,073 条实证）；AGENTS.md 在通用开源库上边际甚至负收益（ETH）；「vibe code cleanup」只能靠人力外包。
2. **「为什么是 CogniCode」的差异化来自三条既有体系都没有的东西**：
   - **判据换主体**：债的利息受损者 = 下一个 agent（对照 [`debt-taxonomy.md`](./debt-taxonomy.md) §五的空档验证）。
   - **动态而非静态**：`prior-art.md` 已确认「用真实 agent 执行合成任务来动态测量仓库 AI 友好度」无公开先例。
   - **仓库级而非组织级**：DORA/Madrona/Augment 都在组织层描述问题，没有工具把问题**落到具体仓库**并给出可修复项。
3. **产品形态上的四条具体建议（由本票证据推导）**：
   - **输出应回答「修哪里能让下一个 agent 少走多少弯路」**，而不是「你有多少条规则违规」。Meta 的 40% 工具调用下降 + 覆盖率 5%→100% 是可对标的**效果量级**；CogniCode 的对应输出应是「修复该债项后 agent 的 token/轮次/失败率预计改善」。
   - **债项应双轴标注**：失败模式（六维度轴）× 工件类型（沿用 Li 十类词汇）。本票 §4.1 的判别表可直接作为初始映射表，其中 #1–#7 是首发确定性债项候选（部落知识缺失、隐式变更耦合、重复逻辑、验证回路缺失、主动误导、巨型文件/浅模块、flaky 环境）。
   - **必须处理「context 文件有效性」这个空白**：这是本票发现的、最贴合 CogniCode 能力边界的机会点——「AGENTS.md 在该仓库上是否真的降低了 agent 成本」是可以用 agent 实测回答的问题（同一任务、有/无 context 文件、对比 token 与成功率），而 ETH 与 Meta 的分歧恰好说明这个测量有真实市场。
   - **显式声明非目标**：review 容量、junior 技能、治理流程、安全漏洞、生成质量缺陷（§4.1 的 #11–#15）。每条都有明确的既有归属方（GitLab/DORA/Veracode/CodeRabbit），CogniCode 不与其正面竞争，避免 scope 蔓延。
4. **风险与前提（必须写进决策文档）**：
   - **agent 能力在快速上升**：METR 的结论一年内反转、Anthropic 400k 会话显示调试类会话占比减半。**「AI 不友好的债」的相对重要性会随模型变强而变化**——因此测量必须能随模型版本重跑，不能固化成静态规则清单（这与 `prior-art.md` 的「分数稳定」硬需求一致）。
   - **厂商数据不可作为独立验证**：本票所有「倍数级」数字都来自厂商遥测，方向一致但幅度存疑；CogniCode 的对外叙述应以**可复现的自家测量**为主证据，以行业报告为背景。
   - **「代码库理解」这个痛点里，有一部分是不可债化的**（需求模糊、规格缺失）——它属于 agent 输入侧，应交给 spec-driven 工具链，CogniCode 只覆盖「实现与文档矛盾」这个可债化子集。

---

## 附：来源清单

### A. 随机对照实验与受控实验（**[RCT]**）

- METR. *Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity*. https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ ；论文 https://arxiv.org/abs/2507.09089
- METR. *We are Changing our Developer Productivity Experiment Design*（2026-02-24 更新，含 -18% 估计与选择偏差说明）. https://metr.org/blog/2026-02-24-uplift-update/
- Shen, Tamkin. *How AI Impacts Skill Formation*. https://arxiv.org/abs/2601.20245 ；Anthropic 官方解读 https://www.anthropic.com/research/AI-assistance-coding-skills ；ICLR 2026 https://iclr.cc/virtual/2026/10022087

### B. 大样本调查与大规模遥测（**[数据]**）

- DORA. *Accelerate State of DevOps Report 2024*. https://dora.dev/research/2024/dora-report/ ；关键数字（吞吐 -1.5%、稳定性 -7.2%）见 Google Cloud Blog https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report
- DORA. *State of AI-assisted Software Development 2025*（90% 采纳、>80% 生产力感知、30% 低信任、AI 是放大器）. https://dora.dev/research/2025/dora-report/ ；Google Cloud Blog https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report ；Thoughtworks 版 PDF https://www.thoughtworks.com/content/dam/thoughtworks/documents/report/tw_report_state_of_ai_assisted_software_development_2025.pdf
- Stack Overflow. *2025 Developer Survey — AI 章节*（49,000+ 受访者；46% 不信任 / 33% 信任 / 3% 高度信任；agent 采纳）. https://survey.stackoverflow.co/2025/ai ；新闻稿 https://stackoverflow.co/company/press/archive/stack-overflow-2025-developer-survey/
- Stack Overflow. *Agents on a leash*（2026-05 pulse：agentic 使用近乎翻倍至 59%，多数受人工监控）. https://stackoverflow.blog/2026/05/27/agents-on-a-leash-agentic-ai-remains-mostly-monitored-at-work/
- Sonar. *State of Code Developer Survey 2026*（1,149 人；AI 占已提交代码 42%→2027 预计 65%；96% 不完全信任；48% 每次验证；38% 认为 review AI 代码更费力）. 新闻稿 https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/ ；报告 PDF https://www.sonarsource.com/state-of-code-developer-survey-report.pdf ；解读 https://www.sonarsource.com/blog/state-of-code-developer-survey-report-the-current-reality-of-ai-coding/
- GitLab（Harris Poll）. *2026 AI Accountability Report*（1,528 人；80% 采纳快于治理、92% 治理挑战、91% 用 2+ 工具）. 新闻稿 https://about.gitlab.com/press/releases/2026-06-23-gitlab-research-reveals-organizations-are-generating-ai-code-faster-than-they-can-control-it/ ；报告页 https://about.gitlab.com/resources/ai-accountability-survey-2026/
- Faros AI. *AI Engineering Report 2026 – Acceleration Whiplash* 与其解读 *How AI-Generated Code Is Increasing Code Review Burden*（PR +51.3%、bug/PR +54%、中位 review 时长 +441.5%、未 review 合并 +31.3%）. https://www.faros.ai/blog/ai-code-quality-senior-engineer-review-burden
- LinearB. *AI in software development: what the 2026 data shows*（88.3% 日常使用；AI PR 等待 review 17.6h vs 3.4h；30 天合并率 32.7% vs 84.4%）. https://linearb.io/library/ai-in-software-development ；Benchmarks 报告 PDF https://assets.linearb.io/image/upload/v1777392920/resources/LinearB_2026_Software_Engineering_Benchmarks_Report.pdf
- JetBrains Research（ICSE 2026）. *Understanding AI's Impact on Developer Workflows*（800 名开发者、两年遥测；AI 用户每月删除/撤销 +约 100 次 vs 非用户 +约 7 次）. https://blog.jetbrains.com/research/2026/04/ai-impact-developer-workflows/
- Madrona. *On to the Next Bottleneck*（49 名负责人 / 10,000+ 工程师；57% review 队列、49% 规格清晰度；63% 靠轶事度量）. https://www.madrona.com/on-to-the-next-bottleneck-what-product-engineering-leaders-told-us-about-ai-in-software-development/
- Augment Code. *The State of AI-Native Engineering in 2026*（219 名工程负责人；48% 代码 AI 生成；55% 把代码库理解列为头号担忧；89% 技能相关性担忧 vs 仅 19 个组织调整岗位）. https://www.augmentcode.com/resources/state-of-ai-native-engineering-2026 ；PDF https://www.augmentcode.com/downloads/state-of-ai-native-engineering-2026.pdf
- GitClear. *AI Copilot Code Quality: 2025*（2.11 亿行；克隆 4 倍增长；复制粘贴首次超过移动）. https://www.gitclear.com/ai_assistant_code_quality_2025_research
- CodeRabbit. *State of AI vs Human Code Generation*（470 个 PR；1.7x 问题；逻辑 +75%；安全至 2.74x）. https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report ；报告 PDF https://hs-43613284.f.hubspotemail.net/hubfs/43613284/CodeRabbit%20-%20State%20of%20AI%20vs%20Human%20Code%20Generation%20-%20Report%20-%20Lite.pdf
- Veracode. *2025 GenAI Code Security Report*（80 任务 × 100+ LLM；45% 引入 OWASP 类风险）. https://www.veracode.com/resources/analyst-reports/2025-genai-code-security-report/ ；更新版 PDF https://www.veracode.com/wp-content/uploads/October-2025-GenAI-Code-Security-Report-Update.pdf
- Microsoft Research & CMU. *The Impact of Generative AI on Critical Thinking*（319 名知识工作者、936 个案例）. https://www.microsoft.com/en-us/research/wp-content/uploads/2025/01/lee_2025_ai_critical_thinking_survey.pdf
- LeadDev. *Engineering Leadership Report 2026*（技术债与维护 48% 为优先事项）. https://leaddev.com/wp-content/uploads/2026/06/ENGINEERING_LEADERSHIP_REPORT_2026_FINAL.pdf
- GitHub. *Octoverse 2025*（3,600 万新开发者、9.86 亿 commit、Copilot coding agent 100 万+ PR、80% 新开发者首周用 Copilot）. https://octoverse.github.com/ ；https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/
- Google 官方口径（Pichai）：>25%（2024-10）→ 75%（2026-04）新代码由 AI 生成. https://www.itpro.com/technology/artificial-intelligence/sundar-pichai-says-more-than-25-percent-of-googles-code-is-now-generated-by-ai-and-its-a-big-hint-at-the-future-of-software-development ；https://www.businessinsider.com/google-ai-generated-code-75-gemini-agents-software-2026-4

### C. 经验研究论文（**[论文]**）

- *Beyond Resolution Rates: Behavioral Drivers of Coding Agent Success and Failure*（9,374 条轨迹 / 19 agent / 500 任务；先收集上下文再编辑 + 投入验证者更成功；12 个简单补丁任务全员失败于架构推理与领域知识）. https://arxiv.org/html/2604.02547
- *Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?*（ETH Zurich；手写 +4%、LLM 生成 -3%、成本 +20%+）. https://arxiv.org/html/2602.11988v1
- *On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents*（10 仓库、124 PR）. https://arxiv.org/html/2601.20404
- *Lost in Compaction: Evaluating Side-Constraint Loss under Context Compaction*（会话约束在压缩中丢失）. https://arxiv.org/abs/2608.11242
- *The Compaction Cliff in Long-Running AI Agent Memory*. https://arxiv.org/html/2608.22752
- Chroma. *Context Rot: How Increasing Input Tokens Impacts LLM Performance*（18 个模型）. https://www.trychroma.com/research/context-rot
- *AI Writes Faster Than Humans Can Review: A Longitudinal Study of an Enterprise "2×" Mandate*（802 名开发者、196,212 个 PR；吞吐 2.09x；每 reviewer 负载翻倍；自动审查超过人工）. https://arxiv.org/html/2607.01904v1
- *Is Agentic Code Review Helpful? Mining Developers' Feedback to CodeRabbit Reviews in the Wild*（31,073 条配对；36.4% 接受 / 56.3% 拒绝）. https://arxiv.org/abs/2607.03316
- *"Go Home Copilot, You're Drunk": Understanding Developer Responses to Agent-Generated Code Review Comments*（54,791 条评论 / 5 agent / 342 仓库）. https://arxiv.org/abs/2607.21997
- *SWE-PRBench: Benchmarking AI Code Review Quality Against Pull Request Feedback*（8 个前沿模型仅检出 15–31% 人类标注问题）. https://www.researchgate.net/publication/403262187_SWE-PRBench_Benchmarking_AI_Code_Review_Quality_Against_Pull_Request_Feedback
- *Reducing False Positives in Static Bug Detection with LLMs: An Empirical Study in Industry*（ICSE 2026 SEIP）. https://conf.researchr.org/details/icse-2026/icse-2026-software-engineering-in-practice/72/Reducing-False-Positives-in-Static-Bug-Detection-with-LLMs-An-Empirical-Study-In
- *Comprehension Debt in GenAI-Assisted Software Engineering Projects*（EASE 2026 / LEARNER 2026）. https://arxiv.org/html/2604.13277v1 ；https://conf.researchr.org/details/ease-2026/learner-2026-papers/3/Comprehension-Debt-in-GenAI-Assisted-Software-Engineering-Projects
- Storey, M-A. *How Generative and Agentic AI Shift Concern from Technical Debt to Cognitive Debt*. http://margaretstorey.com/blog/2026/02/09/cognitive-debt/
- *From Technical Debt to Cognitive and Intent Debt: Rethinking Software Health in the Age of AI*（ACM Queue 版）. https://queue.acm.org/detail.cfm?id=3807966

### D. 一手实践报告（**[一手实践]**）

- Simon Willison. *Not all AI-assisted programming is vibe coding (but vibe coding rocks)*. https://simonwillison.net/2025/Mar/19/vibe-coding/ ；*Two publishers and three authors fail to understand what "vibe coding" means*. https://simonwillison.net/2025/May/1/not-vibe-coding/ ；*Will the future of software development run on vibes?* https://simonwillison.net/2025/Mar/6/vibe-coding/
- Kent Beck. *Augmented Coding & Design*（"The Genie Eats The Seed Corn"）. https://newsletter.kentbeck.com/p/augmented-coding-and-design ；*Augmented Coding: Beyond the Vibes*. https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes ；*Augmented Coding is Good For Exploration*. https://newsletter.kentbeck.com/p/augmented-coding-is-good-for-exploration
- Armin Ronacher. *Agentic Coding Things That Didn't Work*（上下文工程仍不可靠；长会话遗忘）. https://lucumr.pocoo.org/2025/7/30/things-that-didnt-work/ ；*Agentic Coding Recommendations*. https://lucumr.pocoo.org/2025/6/12/agentic-coding/
- Gergely Orosz. *What is happening with code reviews?*（PR 量三年 5 倍；七种应对策略）. https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews
- Meta Engineering. *How Meta Used AI to Map Tribal Knowledge in Large-Scale Data Pipelines*（4 仓库 / 3 语言 / 4,100+ 文件；59 份上下文文件；覆盖 5%→100%；工具调用 -40%；并对 ETH AGENTS.md 结论提出反例）. https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/
- Anthropic. *How AI is transforming work at Anthropic*（132 名工程师 + 53 次访谈；60% 工作覆盖；0–20% 完全可委托）. https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic
- Anthropic. *How Claude Code is used in practice*（约 400,000 会话 / 235,000 人；调试类会话占比减半）. https://www.anthropic.com/research/claude-code-expertise
- Anthropic Engineering. *Effective context engineering for AI agents*. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- The New Stack. *Microsoft execs warn agentic AI is hollowing out the junior developer pipeline*. https://thenewstack.io/agentic-ai-junior-developer-crisis/
- Hacker News 原始讨论串：*Ask HN: How are you using AI code assistants on large messy legacy code bases?* https://news.ycombinator.com/item?id=47890749 ；*Has anyone made a legacy codebase more legible to AI coding agents?* https://news.ycombinator.com/item?id=49698073 ；*Ask HN: Where is legacy codebase maintenance headed?* https://news.ycombinator.com/item?id=46547015 ；brownfield 讨论 https://news.ycombinator.com/item?id=45127624 、https://news.ycombinator.com/item?id=46521072 、https://news.ycombinator.com/item?id=48560711 、https://news.ycombinator.com/item?id=42618961

### E. 既有解法与其边界（用于 §五）

- Sonar. *AI Code Assurance*（面向 AI 生成代码的质量门与认证流程）. https://www.sonarsource.com/solutions/ai/ai-code-assurance/ ；文档 https://docs.sonarsource.com/sonarqube-server/2026.1/ai-capabilities/ai-code-assurance ；*Sonar way for agentic AI quality gate*. https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/ai-code-assurance/quality-gate-for-agentic-ai
- GitHub. *spec-kit*. https://github.com/github/spec-kit/ ；SDD 工具对比（含 spec-kit 加重 review 负担的观察）https://particula.tech/blog/spec-driven-development-tools-spec-kit-vs-kiro-vs-tessl ；https://codemyspec.com/blog/spec-kit-vs-kiro
- Builder.io. *How to De-Slop an AI-Generated Codebase*. https://www.builder.io/blog/de-slop-ai-generated-codebase
- 「vibe code cleanup」市场证据：https://proofofwork.studio/writing/vibe-code-cleanup 、https://www.scrums.com/blog/vibe-coding-cleanup-as-a-service 、https://tripleminds.co/ai/vibe-coding-cleanup-services
- 本仓内部对照：`docs/research/debt-taxonomy.md`（债分类学与判据空档）、`docs/research/prior-art.md`（基准与静态 AI-readiness 工具现状）
