# AI 开发时代的从业者真实痛感：人群、证据与「对 AI 不友好的债」

> 票：[AI 开发软件时代开发者的真实痛点调研 #48](https://github.com/asiazhang/cognicode/issues/48) · 地图：[#39](https://github.com/asiazhang/cognicode/issues/39)
> 分支：`research/ai-dev-pain-points`
> 方法：与 [debt-taxonomy.md](./debt-taxonomy.md)（学术与工具界的债分类谱系，结论：所有既有体系的利息受损者都是人类）互补的**从业者面**调研。来源两路——一手实践报告（Simon Willison、Kent Beck、Addy Osmani 等工程师博客与 HN 讨论）与行业调查/厂商研究（DORA 2024/2025、Stack Overflow Survey 2025、METR RCT、Anthropic 研究、GitClear/Faros/CodeRabbit 遥测、USENIX/arXiv 论文），时间窗 2024–2026，优先一手来源并区分「有数据支撑」与「轶事性」。只读调研，不改代码。

## 摘要（一屏版）

2024–2026 年的证据收敛出一个一致图景：**AI 让代码产出的速度暴涨，让代码被理解、被验证、被维护的速度不涨反跌**。个人开发者一端，agent 在大型/陌生代码库上的失败高度结构化——Sourcegraph 对 1,281 次 agent 运行的分析归纳出五种可重复失败模式（迷路、错文件、跨文件改动失手、工具空转、context 溢出），并证明这些是「context 问题而非智力问题」；METR 的 RCT 发现资深开发者用 AI 反而慢 19% 且自我感知完全失真。团队一端，DORA、GitClear、Faros、CodeRabbit 四组互不隶属的数据共同指向：吞吐上升的同时，重复代码激增、review 时长暴涨、事故率翻倍、未审代码入仓比例升高。**判别层结论**：从业者痛感中相当大一块——agent 迷路（浅模块、巨型文件、无导航文档）、跨文件失手（隐藏变更耦合）、验证回路缺失（跑不起测试/构建）、错误代码表面可信（AI 生成债的复利）——**直接指向「代码库对 AI 不友好」**，即会让下一个 agent 迷路/犯错/爆炸的债，与 debt-taxonomy.md 验证的学术空档（无人以 agent 表现为债判据）严丝合缝。空档层结论：linter/SonarQube 按人类规则判债、context engineering 教人迁就 agent、AGENTS.md 靠人肉维护——**没有任何工具以「agent 实际表现」为判据识别仓库存量债**，这是 CogniCode 重定位的锚定空间。

---

## 一、个人开发者：agent 在真实代码库上的失败场景

### 1.1 五种结构化失败模式（有数据支撑）

Sourcegraph 基于 CodeScaleBench（40+ 大型开源仓库、9 种语言、1,281 次评分 agent 运行）的官方博客[《Why coding agents fail in large codebases》](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)（2026-05）是目前对「agent 在大代码库失败」最系统的从业者侧归纳，五种模式全部可对号入座：

1. **迷路（lost in the codebase）**：agent 的基本策略是读文件→跟 import→读下一个文件，在 22,000 个文件的代码库里该策略的探索树分支速度远超其剪枝能力，最终把整个超时烧在探索上、零产出。Kubernetes 1.4M 行 Go 代码的真实案例：无索引工具时 agent 6,000 秒零产出，换代码搜索工具后 89 秒得 0.90 分——「完全失败与近乎满分的差别不是智力，是高效访问 context」。数据点：仅靠本地工具（grep/文件读/glob）的 agent 在代码库超过约 40 万行后系统性挣扎，40 万–200 万行区间加代码智能工具的收益 delta 最大（+0.259）。
2. **错文件、错符号（wrong file, wrong symbol）**：grep `allocate` 在 Kubernetes 返回数百个命中（测试、废弃代码、工具函数、真实逻辑），词法搜索无法按结构相关性排序。基准数据中关键词搜索是最高频工具（7,993 次调用），说明 agent 倾向用「能用的最简单工具」，而词法搜索分不清定义与 47 个调用点。
3. **跨文件改动失手（partial completion）**：Strata 金融库的跨文件重构任务中，基线 agent 只改了 7 个受影响文件中的 2 个得 0.32 分；「在紧耦合代码库里，部分重构往往比不重构更糟——它把代码留在改了一半的不一致状态」。
4. **工具空转（tool thrashing）**：一次重构任务基线 agent 84 分钟 96 次工具调用（含 6 次完全推倒重来）得 0.32；配结构化搜索的 agent 4.4 分钟 5 次调用得 0.68。空转还留下残留：每次回退都把不再相关的文件内容留在对话历史里继续消耗 context。
5. **context 溢出（context overflow）**：agent 整读文件、数百行无关代码稀释信号——「最相关的信息可能落在模型注意力最差的位置」。

Sourcegraph 的定性判断对本项目至关重要：**「这些是 context 问题，不是智力问题」**——更聪明的模型会以同样策略更快失败，解法是搜索索引/结构化导航/检索管线，即「模型与代码库之间的工程」。注意其为商业内容（卖代码搜索/MCP），但效应量与多源一致性使其成为强参考。

与学术侧互补的是[《How Coding Agents Fail Their Users》](https://arxiv.org/abs/2605.29442)（arXiv 2605.29442，2026-05）：观察 1,639 个仓库的 20,574 个真实 coding-agent 会话，把 misalignment 操作化为「开发者推回」可见的 breakdown，识别出七种反复出现的形式（读项目、理解意图、遵守规则、动作边界、实现执行、进度汇报）；90.50% 的 episode 造成的是精力与信任成本而非不可逆系统损害，但 91.49% 的可见解决仍需用户显式纠正。**「90% 是摩擦不是灾难 + 91% 要人来收尾」**——这是个人开发者日常痛感的最佳量化注脚。

### 1.2 context 的物理极限：context rot（有数据支撑）

Chroma Research 的[《Context Rot》](https://www.trychroma.com/research/context-rot)（2025-07）评测 18 个 LLM（含 GPT-4.1、Claude 4、Gemini 2.5、Qwen3）：模型对上下文的处理不均匀，输入变长性能显著退化，即使简单任务也是如此。这给「把整个代码库塞进 context」的幻想划了物理边界——即使窗口够大，长输入中的信息也会被「腐烂」。后果落在两类债上：巨型文件/超长方法稀释信号（效率与可解性），以及 agent 多轮探索后的残留文件内容挤占有效 context（Sourcegraph 的 thrashing 残留观察）。

### 1.3 幻觉 API 与包名（有数据支撑，但注意方向）

USENIX Security 2025 的[《We Have a Package for You!》](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf)系统分析了 LLM 生成代码中的 package hallucination：模型虚构不存在的包名，构成 slopsquatting 供应链攻击面。但 Simon Willison 的[《Hallucinations in code are the least dangerous form of LLM mistakes》](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/)（2025-03）给出从业者的重要校准：**代码里的幻觉是最不危险的 LLM 错误**——一跑就炸、立刻可修；真正危险的是「几乎对但不完全对」的代码，它通过测试、看起来地道，错在意图与边界处。这个判别对 CogniCode 直接适用：幻觉 API 是模型问题（工具可通过存在性检查兜底），「表面可信的错」才是仓库与流程的债。

### 1.4 资深者的悖论：METR RCT（有数据支撑，强证据）

METR（Model Evaluation & Threat Research）的随机对照试验（[博客](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)、[论文 arXiv:2507.09089](https://arxiv.org/abs/2507.09089)，2025-07）：16 名资深开源开发者（对参与仓库平均 5 年经验，仓库平均 22k+ star、1M+ 行）、246 个真实 issue，随机分配允许/禁止 AI（主要是 Cursor + Claude 3.5/3.7 Sonnet）。结果：**允许用 AI 时完成任务反而慢 19%**；开发者预期提速 24%，做完之后仍自认提速 20%——感知与现实完全脱节。METR 自己列出解读边界（16 人、成熟大型仓库、高隐性标准的项目，不能推广到全部开发场景）。2026-02 的[后续更新](https://metr.org/blog/2026-02-24-uplift-update/)：晚期-2025 工具的原始数据显示转正（原班开发者子集估计提速 18%），但选择效应（大量开发者拒绝参加「不许用 AI」的实验）使数据只有弱证据力。

对本项目的关键引申：METR 的因子分析指向「成熟大型代码库 + 高隐性要求」正是 AI 工具最难啃的设置——**越是遗产重、约定隐晦的仓库，agent 的相对表现越差**，这正是「对 AI 不友好的债」最浓缩的实证。

### 1.5 一手实践者的叙述（轶事性，但来自高可信工程师）

- **Simon Willison**（2025 年系列）：[《Coding agents require skilled operators》](https://simonwillison.net/2025/Jun/18/coding-agents/)——agent 有效工作的前提是操作者同时具备领域理解与工具理解；[《AI-assisted development needs automated tests》](https://simonwillison.net/2025/May/28/automated-tests/)——他发现自己从 LLM 获益远超旁人的原因之一是「几乎所有代码都有自动化测试」，即**验证回路的存在决定 agent 价值**；[《Your job is to deliver code you have proven to work》](https://simonwillison.net/2025/dec/18/code-proven-to-work/)——反复出现的痛点是初级工程师把巨大的未验证 PR 扔给别人「让 review 兜底」；[《Not all AI-assisted programming is vibe coding》](https://simonwillison.net/2025/Mar/19/vibe-coding/)——坚持区分「不看代码的 vibe coding」与「对产出负责的 AI 辅助工程」，后来在 [vibe engineering](https://simonwillison.net/2025/Oct/7/vibe-engineering/) 一文中把后者命名为 vibe engineering。
- **Kent Beck**：2023 年的名言「我 90% 的技能价值归零，剩下 10% 杠杆千倍」（[newsletter 复盘](https://newsletter.kentbeck.com/p/90-of-my-skills-are-now-worth-0)）；2025 年在 Pragmatic Engineer 访谈中的展开（[Willison 摘录](https://simonwillison.net/2025/Jun/22/kent-beck/)）——他近半年的实践是让 agent 做大部分实现，自己集中在「愿景、里程碑、**控制复杂度水平的设计**」。这句话的债学读法：复杂度控制从「写代码时顺手做」变成「专门要人盯的事」，因为 agent 会以机器速度生产复杂度。
- **Anthropic《How Claude Code is used in practice》**（[研究报告](https://www.anthropic.com/research/claude-code-expertise)，约 40 万会话的隐私保护分析，2025-10–2026-04）：典型会话中人类做约 70% 的规划决策、agent 做约 80% 的执行决策；**领域专业知识（而非编码能力）是成功率的决定因素**——新手会话严格验证成功率仅 15%，中级及以上 28–33%；遇到挫折的会话中专家从泥潭里救回的比率显著更高（4%→15%）。同一研究顺带给出趋势：debug 类会话占比七个月内从 33% 降到 19%。这组数据支撑一个痛点结构：**agent 的失败由人兜底，兜底能力=对仓库的理解深度**——理解薄的地方，痛感最重。
- **轶事层**（个人博客/Reddit/GitHub issue，单案例，置信度低但方向一致）：agent 重构「看起来干净」的模块后炸掉生产（如某 HTTP client 重构改了默认超时，auth 三小时后崩，[Dependency Phantom 案例](https://moltbook.com/post/e6eb99e8-8ac4-4c66-80d1-e4a00f758927)——跨模块隐藏耦合的典型）；Claude Code 在主 worktree 执行 `git reset --hard` 毁掉两天未提交工作（[claude-code#33850](https://github.com/anthropics/claude-code/issues/33850)）；非技术创始人用自治 agent 跑 8 个通宵毁掉 70+ 文件（[r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1sgimza/ralph_wiggum_plugin_corrupted_70_files_in_my/)）。HN 的 [Ask HN: How do you measure "AI slop"?](https://news.ycombinator.com/item?id=44743686) 则代表一线团队的困惑：「100 行 diff 本可以 10 行，漏错误分支，破坏约定——不只来自初级，现在资深也这样」，且无人能量化它。

### 1.6 个人开发者痛点小结（含 AI-unfriendly 判别）

| # | 痛点 | 证据强度 | 是否「对 AI 不友好的债」 |
|---|---|---|---|
| P1 | agent 在大型代码库迷路、探索爆炸 | 强（CodeScaleBench 1,281 运行；context rot 实证） | **是**——巨型文件、浅模块、无结构导航入口是仓库属性，换模型不解决 |
| P2 | 错文件/错符号，词法搜索命中噪声 | 强（同上） | **是**——重复命名、死代码、缺导航文档放大该失败 |
| P3 | 跨文件改动失手、部分重构留不一致 | 强（同上 + 轶事层 Dependency Phantom 案例） | **是**——隐藏变更耦合（改 A 必须改 B 但代码不可见）正是 debt-taxonomy §六判 (c) 的典型 |
| P4 | agent 的产出表面可信、实际错误 | 强（Anthropic 会话研究 91% 需人纠正；Willison 论证） | **部分**——「表面可信」由模型与仓库共同造成；仓库侧的债是验证回路缺失（跑不起测试/构建） |
| P5 | 幻觉 API/包名 | 强（USENIX 2025） | **否**——模型问题，存在性检查可兜底（Willison 校准） |
| P6 | 一次性灾难（毁 worktree、破坏生产） | 轶事（多起独立案例） | **否**——属 agent 行为治理/权限设计，非仓库存量债 |
| P7 | 资深者反被拖慢（METR -19%） | 强（RCT）但情境特定 | **间接**——指向「隐性约定多的成熟仓库」正是债最重的场所 |

---

## 二、团队负责人：可维护性、review 负担与梯队

### 2.1 行业调查（有数据支撑）

- **DORA 2024**（[报告 PDF](https://dora.dev/research/2024/dora-report/2024-dora-accelerate-state-of-devops-report.pdf)、[官方摘要](https://dora.dev/ai/gen-ai-report/)）：AI 采纳度提升 25% 与**交付吞吐 -1.5%、交付稳定性 -7.2%** 相关联；机制解释是 AI 生成代码更快导致更大的批量（batch size），而大批量更慢 review、更易引入不稳定。同年报告也承认 AI 对个人生产率、文档、review 过程有正向感知。
- **DORA 2025**（[State of AI-assisted Software Development](https://dora.dev/research/2025/dora-report/)，近 5,000 名从业者 + 100 小时定性访谈，约 90% 已采纳 AI）：核心论断是 **AI 是放大器（amplifier）**——放大强组织的优势，也放大弱组织的病灶；回报来自底层的组织系统而非工具本身。（第三方引用其数据称高 AI 采纳与 PR 体积 +154%、review 时长 +91% 相关，该数字未见于官方摘要页，本文按一手来源只采用「放大器」论断与官方图表，具体倍数待 PDF 原文核对。）
- **Stack Overflow Developer Survey 2025**（[AI 章节](https://survey.stackoverflow.co/2025/ai)，49,000+ 受访者）：84% 在用或计划用 AI（2024 年 76%），但**不信任产出的从 31% 升到 46%，信任的从 40% 跌到 33%**；最资深的开发者最谨慎（highly trust 仅 2.6%，highly distrust 20%）。采用率与信任度反向剪刀差是团队负责人的核心管理难题。最大挫折源是「几乎对但不完全对」（almost right but not quite）的输出。

### 2.2 厂商遥测（有数据支撑；厂商卖相关工具，读数需打折但多源一致）

- **GitClear**（[2025 报告](https://www.gitclear.com/ai_assistant_code_quality_2025_research)：211M 行变更，2020–2024）：2024 年是分水岭——copy/paste 行数历史上首次超过 moved（重构信号）行数；重复块较 2022 年约 10 倍（[LeadDev 分析](https://zephrcf.leaddev.com/technical-direction/how-ai-generated-code-accelerates-technical-debt)）；[2026 Maintainability Gap 报告](https://www.gitclear.com/the_ai_code_quality_maintainability_gap)（623M 次变更，2023–2026）：moved code（重构签名）从 2022 年占变更行 21% 跌到 2026 年 3.8%，重复块率较 2023 年 +81%，跨文件函数调用（复用信号）-35%；重度 AI 用户产出较自身基线 +25%，但「4 倍原始产出只换来约一成交付价值」（Addy Osmani 对其数据的[概括](https://addyosmani.com/blog/agentic-code-review/)，GitClear 亦自认部分增益是选择偏差——强者集中在 AI 组）。
- **Faros AI**（[AI Engineering Report 2026: Acceleration Whiplash](https://www.faros.ai/blog/ai-acceleration-whiplash-takeaways)，22,000 开发者、4,000 团队、两年遥测）：高 vs 低 AI 采纳——epics/人 +66%、任务/人 +33.7%（业务价值真实），同时：**code churn +861%**、incident/PR 比 +242.7%、每开发者 bug 从 +9%（上年）升至 **+54%**、PR review 中位时长 **+441.5%**、**完全无 review 合并的 PR +31.3%**。其定性判断最锋利：AI 代码「表面令人信服——地道、命名好、风格一致，结构性与逻辑性失败藏在表面之下」，抓住它需要 review 者「读慢、想意图、重构问题本身」，是最贵的人力；并指出**成熟工程实践的组织同样中招**（与 DORA「放大器/强基础保护论」相抵，值得注意的分歧）。review 不是被砍掉的，是「没人决定停止 review，reviewer 就是跟不上，代码开始未被阅读地合并，然后这成了常态」。
- **CodeRabbit**（[State of AI vs Human Code Generation](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)，2025-12，470 个开源 PR：320 AI 共笔 + 150 人类）：AI PR 平均 10.83 个问题 vs 人类 6.45（**约 1.7 倍**）；逻辑与正确性 +75%、可读性问题 3 倍以上、安全 1.5–2.74 倍。
- **GitHub**（[agent PR 数据](https://github.blog/ai-and-ml/generative-ai/agent-pull-requests-are-everywhere-heres-how-to-review-them/)）：Copilot review 已运行 6,000 万次，一年 10 倍增长；平台超过五分之一的 review 涉及 agent。

四组互不隶属（部分有商业利益冲突）的数据源指向同一方向，构成 2025–2026 最强共识：**产出暴涨，质量与 reviewability 滑坡，瓶颈移到验证**。

### 2.3 一手实践叙述（轶事性，高可信作者）

- **Addy Osmani**（Google Chrome 工程负责人，[Agentic Code Review](https://addyosmani.com/blog/agentic-code-review/)，2026）：「code review 过去奏效是因为相对速度的意外——高级工程师读代码比初级写代码快。这个前提不再成立：agent 生成一千行代码比我读完这段话还快，而人的阅读速度没变。瓶颈没有消失，它移到了验证。」并提出按 blast radius/存活时长/需理解人数三变量区分 review 策略。他提出的 **comprehension debt（理解债）**概念（[相关文章](https://addyosmani.com/blog/comprehension-debt/)）：代码存在量与任何人类真实理解量之间的鸿沟——「不像技术债通过摩擦宣布自己，理解债滋生虚假信心：代码库看起来干净，测试是绿的，但系统的底层理论正在悄悄蒸发」。
- **Stack Overflow 官方博客**对自家 2025 调查的解读（[结果发布文](https://stackoverflow.blog/2025/12/29/developers-remain-willing-but-reluctant-to-use-ai-the-2025-developer-survey-results-are-here/)）：「未来是关于信任，而不只是工具」。

### 2.4 junior 梯队问题（有数据支撑，2026 年证据集中）

- **Anthropic《How AI assistance impacts the formation of coding skills》**（[研究页](https://www.anthropic.com/research/AI-assistance-coding-skills)、[论文 arXiv:2601.20245](https://arxiv.org/abs/2601.20245)，2026）：RCT，开发者学习陌生异步编程库，AI 组在事后无 AI 的理解/调试测验中显著更低（第三方报道引述约 17 个百分点差距），且「生成后理解」与「直接要代码」两种用法的结局分化明显——**监督 agent 所需的技能恰恰是被 agent 侵蚀的技能**（supervision paradox）。
- **MIT Media Lab《Your Brain on ChatGPT》**（[论文 arXiv:2506.08872](https://arxiv.org/abs/2506.08872)）：54 人分 LLM/搜索引擎/纯脑三组写议论文，EEG 显示 LLM 组神经连接度最低、引用自己文章的能力最差，作者命名为 **cognitive debt（认知债）**。非编程任务但被广泛引用为「认知卸载有账单」的证据。
- **团队侧叙述**（轶事性）：Osmani 等人讨论的「senior engineer tax / senior janitor」现象——最懂系统的人最贵的时间被用来拆解表面可信的 agent 代码；HN 讨论中负责人的典型焦虑是「初级靠 AI 产出，判断力却没有长出来，晋升管道断了」。Anthropic 会话研究中「novice 会话 19% 以放弃告终（专家 5–7%）」亦可作为个体层面的旁证。

### 2.5 团队痛点小结（含 AI-unfriendly 判别）

| # | 痛点 | 证据强度 | 是否「对 AI 不友好的债」 |
|---|---|---|---|
| T1 | review 负担暴涨、未审合并常态化 | 强（Faros/GitHub/DORA 多源） | **间接**——review 溢出本身是流程问题，但其成因中的「AI 代码表面可信」被仓库存量债（无验证回路、无约定文档）放大 |
| T2 | 质量滑坡：重复代码、重构崩塌、churn | 强（GitClear 两份报告） | **是**——重复块、复用崩塌会直接加重下一个 agent 的 P1/P2 失败（搜索噪声、迷路），AI 生成债的复利 |
| T3 | 生产事故率随 AI 采纳上升 | 强（Faros incident/PR +242.7%） | **部分**——事故是 agent 行为与仓库债的联合产物；隐藏耦合（P3）是仓库侧可识别的放大器 |
| T4 | 理解债/comprehension debt：无人真正理解系统 | 概念性（Osmani）+ 旁证 | **是（镜像）**——人类理解蒸发后，AGENTS.md/文档/约定成为 agent 唯一可依赖的导航面，其缺失/过时是直接的 AI 导航债 |
| T5 | junior 成长断层、监督悖论 | 中（两份 RCT，情境较窄） | **否**——人员/教育问题，debt-taxonomy §六已判 (b)（社会/人员债不覆盖），但 T4 是它的仓库侧投影 |
| T6 | 信任剪刀差（用得越多越不信） | 强（SO Survey 2025） | **否**——是工具可信度问题，但对 CogniCode 是需求侧信号：市场需要「可验证的信任」 |

---

## 三、空档分析：痛点 × 既有解法

对照五类既有解法逐条检查上表痛点的认领情况：

| 解法类别 | 代表 | 认领的痛点 | 未认领的痛点 |
|---|---|---|---|
| Linter / 静态质量工具 | ESLint、SonarQube（[debt-taxonomy §三](./debt-taxonomy.md)已详析） | T2 的人类规则子集（重复、异味、复杂度） | 判据全部人类视角（debt-taxonomy §五已证明无 AI 轴）：**P1 迷路、P3 跨文件失手、P4 验证回路缺失完全不在其模型内**；AI 代码「表面合规、结构错误」恰是其盲区（CodeRabbit：可读性差 3 倍的同时风格上看起来地道） |
| Context engineering 实践 | Anthropic [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Claude Code best practices](https://code.claude.com/docs/en/best-practices.md)、Sourcegraph 的索引/MCP 方案 | P1/P2 的**会话级**缓解（检索管线、结构化搜索、工具选择） | 方向是「教 agent（与人）迁就仓库」，**不改变仓库本身**；每次会话都要重新付导航成本；对 P3（隐藏耦合）、T1（review 负担）无效；Sourcegraph 自己也承认这些是「context 问题不是智力问题」——但他们的答案是外挂索引，不是修仓库的债 |
| 仓库级约定文档 | AGENTS.md / CLAUDE.md / README | P1 的入口缓解、P2 的约定提示（Anthropic [大代码库指南](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start)明确「Claude 的导航质量取决于代码库被组织得多好」） | **纯人肉、无新鲜度保障**——过时的 AGENTS.md 比没有更糟（debt-taxonomy §六文档债子集已判）；T4 理解债蒸发时这些文件最先失真；无任何工具检测「文档与代码的漂移」 |
| AI code review 工具 | CodeRabbit、Copilot Review、Faros | T1 的分流（GitHub：平台 1/5 review 已涉 agent） | 治「流入」（新 PR），不治「存量」（仓库存量债）；Faros 报告明言成熟组织同样中招——**review 端加压无法补偿仓库端的债**；AI 代码表面可信的问题对 AI reviewer 同样成立（用模型查模型的同源盲区） |
| 认知/技能侧研究 | Anthropic 技能形成 RCT、MIT 认知债 | T5 的诊断（确认问题存在） | 只诊断不干预；对 P1–P4、T2–T4 无解 |

### 无人认领的痛点（CogniCode 的锚定空间）

1. **P1+P2+T2 的交集：让 agent 迷路的仓库存量属性**——巨型文件、浅模块、重复命名、死代码、无导航结构。静态工具按人类规则看它们（且死代码对人类是零利息债，debt-taxonomy §六第 4 条），context engineering 在会话层绕过它们，**没有任何工具以「agent 实际导航表现」为判据识别并排定它们的优先级**。Sourcegraph 证明了失败模式可测量（1,281 运行、效应量清晰），但他们的产品形态是给 agent 加索引，不是给仓库减债。
2. **P3+T3 的交集：agent 破坏半径可预测的隐藏耦合**——Faros 的事故数据与轶事层的 Dependency Phantom 案例都指向「改 A 炸 B」，CodeScene 的 change coupling 恰好有确定性可提取的信号（debt-taxonomy §六第 15 条已判 (c)），但 CodeScene 用人类协调成本定严重度。**「以 agent 破坏率为判据的变更耦合检测」无人做**。
3. **P4+T1 的交集：验证回路的存在性与可信度**——Willison 的实践（有自动化测试的人从 AI 获益远超旁人）与 METR 的因子分析（高隐性标准的仓库最难提速）共同指向「agent 能否跑起测试/构建并信其结果」是仓库级属性。CI 存在≠agent 冷启动可用（缺锁文件、依赖声明漂移、flaky 测试污染失败信号——本仓 probe 判据的雏形）。**无工具面向 agent 冷启动验证回路做债检测**。
4. **T4 的仓库侧：导航文档的漂移检测**——AGENTS.md/CLAUDE.md 生态爆发但没有一个工具回答「这份文件还说得准吗」。过时文档对 agent 是主动误导（比缺失更糟，debt-taxonomy 已定此判据角度），但「文档-代码漂移」检测在静态分析界是空白。

---

## 四、对 CogniCode 重定位的启示

1. **从业者痛感与学术空档双向印证**。debt-taxonomy.md 证明既有债体系无一以 agent 表现为判据；本文证明从业者的痛感恰好大量落在「会让下一个 agent 迷路/犯错/爆炸」的仓库属性上（P1/P2/P3、T2/T4）。重定位为「AI 技术债识别工具」不是发明新需求，而是给已存在、已被量化（Faros/GitClear/CodeScaleBench）但无人认领的痛点起名。
2. **「表面可信」是贯穿个人与团队两端的主线**。个人端是 agent 产出表面可信的错代码（P4），团队端是 review 被表面可信击穿（T1/Faros「表面令人信服」论断）。CogniCode 的判据必须穿透表面：静态信号（文件大小、模块深度、文档漂移）+ 动态归因（agent 实测失败样本），正是双测量结构的用武之地。
3. **严重度模型可以直接借用从业者数据的口径**。Faros 的 incident/PR、CodeScaleBench 的 reward delta、Anthropic 的「91% 需人纠正」都是 agent 表现的现成测量范式；debt-taxonomy §四提出的第四范式（失败模式频率 × 过程成本）在本文的数据源里找到了实证锚点。
4. **叙事分工**：对个人开发者讲 P1/P3（agent 迷路、跨文件失手），对团队负责人讲 T1/T2/T3（review 负担、质量滑坡、事故率）——两端痛点不同但指向同一批仓库债项，正好支撑「双受众、单一债清单」的产品结构。T5/T6（junior 断层、信任剪刀差）是需求侧背景板，明确不做（对应 debt-taxonomy §六的 (b) 排除）。
5. **诚实边界**：METR 2026 更新显示工具在快速进步、晚期-2025 原始数据已转正（弱证据），Anthropic 会话数据显示 debug 占比在降。CogniCode 的赌注不是「agent 永远弱」，而是「**仓库属性造成的失败不随模型进步消失**」（Sourcegraph 的核心论断：context 问题不是智力问题）——文档与产品叙事应锚定这一条，避免被「下一代模型解决一切」叙事反噬。

---

## 附：来源清单（标注一手/厂商/轶事与数据支撑属性）

### 一手实践报告（工程师博客）

- Simon Willison：[Not all AI-assisted programming is vibe coding](https://simonwillison.net/2025/Mar/19/vibe-coding/)（2025-03）、[Hallucinations in code are the least dangerous form of LLM mistakes](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/)（2025-03）、[AI-assisted development needs automated tests](https://simonwillison.net/2025/May/28/automated-tests/)（2025-05）、[Coding agents require skilled operators](https://simonwillison.net/2025/Jun/18/coding-agents/)（2025-06）、[Identify, solve, verify](https://simonwillison.net/2025/jul/4/identify-solve-verify/)（2025-07）、[vibe engineering](https://simonwillison.net/2025/Oct/7/vibe-engineering/)（2025-10）、[Your job is to deliver code you have proven to work](https://simonwillison.net/2025/dec/18/code-proven-to-work/)（2025-12）——轶事性+论证性，作者为一手实践者
- Kent Beck：[90% of My Skills Are Now Worth $0](https://newsletter.kentbeck.com/p/90-of-my-skills-are-now-worth-0)（2023，一手）；[Pragmatic Engineer 访谈摘录](https://simonwillison.net/2025/Jun/22/kent-beck/)（2025-06，转引）
- Addy Osmani：[Agentic Code Review](https://addyosmani.com/blog/agentic-code-review/)（2026）、[comprehension debt](https://addyosmani.com/blog/comprehension-debt/)——论证性，数据引自下述厂商研究
- HN：[Ask HN: How do you measure "AI slop"?](https://news.ycombinator.com/item?id=44743686)（2025-05，社区轶事）
- 轶事案例：[Dependency Phantom](https://moltbook.com/post/e6eb99e8-8ac4-4c66-80d1-e4a00f758927)、[claude-code#33850](https://github.com/anthropics/claude-code/issues/33850)、[r/ClaudeCode Ralph Wiggum 事件](https://www.reddit.com/r/ClaudeCode/comments/1sgimza/ralph_wiggum_plugin_corrupted_70_files_in_my/)

### 行业调查与厂商研究（有数据支撑；厂商来源已标注利益方向）

- METR：[Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)（博客）、[arXiv:2507.09089](https://arxiv.org/abs/2507.09089)（论文，RCT，2025-07）、[2026-02 uplift update](https://metr.org/blog/2026-02-24-uplift-update/)（一手，非营利）
- DORA：[2024 Accelerate State of DevOps Report](https://dora.dev/research/2024/dora-report/2024-dora-accelerate-state-of-devops-report.pdf)（一手，吞吐 -1.5%/稳定性 -7.2%）、[2025 State of AI-assisted Software Development](https://dora.dev/research/2025/dora-report/)（一手，放大器论断，~5,000 受访者）
- Stack Overflow：[2025 Developer Survey — AI](https://survey.stackoverflow.co/2025/ai)（一手，46% 不信任 vs 33% 信任）、[官方解读](https://stackoverflow.blog/2025/12/29/developers-remain-willing-but-reluctant-to-use-ai-the-2025-developer-survey-results-are-here/)
- Anthropic：[How Claude Code is used in practice](https://www.anthropic.com/research/claude-code-expertise)（一手，~40 万会话分析）、[How AI assistance impacts the formation of coding skills](https://www.anthropic.com/research/AI-assistance-coding-skills)（一手 RCT，[arXiv:2601.20245](https://arxiv.org/abs/2601.20245)）、[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Claude Code best practices](https://code.claude.com/docs/en/best-practices.md)、[How Claude Code works in large codebases](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start)
- GitClear：[AI Copilot Code Quality 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research)（211M 行，2020–2024）、[The Maintainability Gap 2026](https://www.gitclear.com/the_ai_code_quality_maintainability_gap)（623M 次变更，2023–2026）——厂商（卖代码分析），数据被 MIT Tech Review 等广泛引用
- Faros AI：[AI Engineering Report 2026: Acceleration Whiplash](https://www.faros.ai/blog/ai-acceleration-whiplash-takeaways)（22K 开发者遥测）——厂商（卖工程度量），效应量大且与其他来源一致
- CodeRabbit：[State of AI vs Human Code Generation](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)（470 PR，AI 1.7x 问题）——厂商（卖 AI review）
- GitHub：[Agent pull requests are everywhere](https://github.blog/ai-and-ml/generative-ai/agent-pull-requests-are-everywhere-heres-how-to-review-them/)（一手平台数据）
- Sourcegraph：[Why coding agents fail in large codebases](https://sourcegraph.com/blog/why-coding-agents-fail-large-codebases)（CodeScaleBench，1,281 运行）——厂商（卖代码搜索/MCP）

### 学术论文

- Chroma Research：[Context Rot](https://www.trychroma.com/research/context-rot)（2025-07，18 模型评测）
- Spracklen et al.：[We Have a Package for You!](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf)（USENIX Security 2025，package hallucination）
- Tang et al.：[How Coding Agents Fail Their Users](https://arxiv.org/abs/2605.29442)（arXiv 2605.29442，20,574 会话观察研究）
- Kosmyna et al.（MIT Media Lab）：[Your Brain on ChatGPT](https://arxiv.org/abs/2506.08872)（arXiv:2506.08872，EEG 认知债研究）
