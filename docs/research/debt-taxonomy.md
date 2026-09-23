# 既有技术债分类谱系：类型、判据、严重度

> 票：[业界技术债的既有谱系 #45](https://github.com/asiazhang/cognicode/issues/45) · 地图：[#39](https://github.com/asiazhang/cognicode/issues/39)
> 分支：`research/debt-taxonomy`
> 方法：对照两路一手来源——学术界（Kruchten/Avgeriou/Nord/Ozkaya/Li/Ernst 等论文与专著、Dagstuhl 16162 报告）与工业界（SonarQube/SQALE、CodeScene 官方文档与论文、Semaphore 博客）。只读调研，不改代码；分类轴已锁定为六维度失败模式，本票只供对照。

## 摘要（一屏版）

既有技术债（technical debt, TD）体系围绕两个正交问题展开：**债是什么**（类型学：代码债/设计债/架构债/测试债/文档债/构建债/基础设施债/需求债/缺陷债……）与**债多重**（严重度：remediation cost 本金 + interest 利息）。学术界的权威分类是 Li–Avgeriou–Liang 2015 系统映射研究的**十类分类树**（JSS 101:193-220），后被《Managing Technical Debt》（Kruchten/Nord/Ozkaya 2019）与《Technical Debt in Practice》（Ernst/Delange/Kazman 2021）两本专著吸收扩展；工业界的代表是 **SQALE 质量模型**（remediation cost 加总，被 SonarQube 内化为其「技术债 = 修复所有 code smell 的预估工时」指标）与 **CodeScene 行为代码分析**（用人类开发活动数据给静态问题排优先级，并引入社会性维度：知识孤岛、知识流失、变更耦合）。

**关键空档验证**：遍历上述体系的判据，债务的「利息」全部以**人类开发者**为受损主体——SQALE 的 business impact 定义为人类复现/定位/修 bug 的额外工作量，SonarQube 的三个 software quality（安全/可靠/可维护）没有 AI 轴，CodeScene 的全部行为度量（hotspot、知识分布、缺陷密度）取自人类 commit/Jira 数据，学术定义（Dagstuhl 16162）明确把债的损害限定为「内部质量，主要是可维护性与可演化性」。**没有任何体系以「AI agent 的工作效率/出错率」为债的判据**——该论断在本次调研的语料内成立。相邻工作存在（DAF 等静态 AI-readiness 打分、Ernst 团队「AI 时代的技术债」新方向），但前者不是债的分类学、后者的框架里 AI 是债的产生者与治理工具而非受损主体。这正是 CogniCode「对 AI 不友好的债」的定位空间。

对照结论速览：测试债、构建债、文档债（AI 相关部分）与六维度轴**强交集**（应覆盖）；代码债/设计债/架构债/变更耦合**部分交集**（只在「会让 agent 迷路/犯错/变慢」的子集上覆盖）；社会债/人员债/安全债/需求债/缺陷债/版本债**明确不覆盖**（判据与 AI 受损无关）。

---

## 一、债务隐喻与定义基线

### 1.1 源头：Cunningham 的金融隐喻（1992）

Ward Cunningham 在 1992 年 OOPSLA 的经验报告中首次用金融债务比喻「先发布、后完善」的工程决策，本意是**有意识、有计划地借债**（见 [Ward Explains Debt Metaphor](http://wiki.c2.com/?WardExplainsDebtMetaphor)，Cunningham 本人出镜解释的 c2 wiki 页面）。这个「借债是有意决策」的原义在后续传播中被稀释，是后来分类学混乱的根源之一。

### 1.2 学术界的共识定义

**Kruchten–Nord–Ozkaya（2012）**《Technical Debt: From Metaphor to Theory and Practice》（IEEE Software 29(6)）把债从博客隐喻提升为研究对象（[SEI 资产页](https://resources.sei.cmu.edu/library/asset-view.cfm?assetID=58789)，收录于 [SEI 架构技术债文库](https://sei.cmu.edu/library/architectural-technical-debt-library/)）。

**Dagstuhl 研讨会 16162（2016）**给出了被广泛引用的工作定义（[研讨会报告全文 PDF](https://drops.dagstuhl.de/storage/04dagstuhl-reports/volume06/issue04/16162/DagRep.6.4.110/DagRep.6.4.110.pdf)，Executive Summary 节）：

> 「在软件密集系统中，技术债是设计或实现构造的集合，它们在短期内是权宜之计，但建立了一个可能使未来变更更昂贵或不可能的技术语境。技术债是一种实际的或有的负债，其影响限于内部系统质量——主要是可维护性与可演化性。」

同一报告还划了边界：social debt（社会债）、people debt（人员债）、process debt（流程债）、infrastructure debt（基础设施债）等**被排除在这个核心定义之外**，作为「相关现象」另行研究（同报告 "The Essential Context" 节）。另据报告 Table 4 一节，学界明确列过 **non-TD** 清单：缺陷、未实现功能、缺乏支撑流程、未完成开发任务、琐碎的代码质量问题、低外部质量——其中「缺陷不是债」有 4 篇研究支持，但也有 11 篇把 defect TD 列为债类型，**学界本身未收敛**。

**Kruchten–Nord–Ozkaya 专著《Managing Technical Debt》（Addison-Wesley 2019）**沿用了上述定义（作者在 [SEI 博客第 1 章摘录](https://insights.sei.cmu.edu/sei_blog/2019/05/managing-the-consequences-of-technical-debt-5-stories-from-the-field.html)中逐字给出），并强调：债不等于「代码烂」——架构层的债可以存在于代码质量很好的系统里（同文 "Technical Debt A-B-C" 节，以银行合并后重建系统等 5 个案例说明）。

### 1.3 Fowler 象限：按「意图」分类

Martin Fowler 的 [Technical Debt Quadrant](https://martinfowler.com/bliki/TechnicalDebtQuadrant.html)（2009）给出与类型学正交的二轴分类：**prudent/reckless（审慎/鲁莽）× deliberate/inadvertent（有意/无意）**，回应 Uncle Bob「一团糟不是技术债」的争论，结论是「债/非债」之问本身是错问，应问「这个债务隐喻对沟通是否有用」。

---

## 二、学术界的类型谱系

### 2.1 权威分类：Li–Avgeriou–Liang 十类分类树（2015）

Zengyang Li、Paris Avgeriou、Peng Liang 的系统映射研究《A systematic mapping study on technical debt and its management》（Journal of Systems and Software 101 (2015) 193–220，[开放获取 PDF](https://pure.rug.nl/ws/files/239167347/1_s2.0_S0164121214002854_main.pdf)）筛选了 1992–2013 年 94 篇一手研究，是引用最广的 TD 类型学。其 Section 4.4.1.1 给出**十个粗粒度类型**（每类再按成因细分出子类型，构成分类树 Fig. 8）：

1. **需求债（requirements TD）**：最优需求规格与实际实现之间的距离（引自 Ernst 2012）。
2. **架构债（architectural TD）**：架构决策在可维护性等内部质量上妥协所导致的债。
3. **设计债（design TD）**：详细设计阶段走的技术捷径。
4. **代码债（code TD）**：违反最佳编码实践或编码规则的劣质代码，如代码重复、过度复杂。
5. **测试债（test TD）**：测试中的捷径，如缺乏单元/集成/验收测试。
6. **构建债（build TD）**：构建系统或构建过程中的缺陷，使构建过度复杂困难。
7. **文档债（documentation TD）**：任何开发环节文档的不足、不完整或过时，如过期的架构文档、缺失的代码注释。
8. **基础设施债（infrastructure TD）**：开发相关流程、技术、支撑工具的次优配置，负面影响团队产出质量产品的能力。
9. **版本控制债（versioning TD）**：源码版本管理中的问题，如不必要的代码分叉。
10. **缺陷债（defect TD）**：软件系统中发现的缺陷、bug 或故障。

几个重要的量化结论（同文）：代码债是被研究最多的类型（40% 的研究涉及），版本/需求/构建债最少（各 1–3%）；债损害的质量属性**压倒性地集中于可维护性**（Table 6：94 篇中约 49 篇提及 maintainability，其余质量属性各只有零星几篇）；描述债最常用的概念是 **interest（利息，35 篇）、principal（本金，17 篇）、risk（风险，11 篇）**（Table 5），且 TD item 的标准字段包含本金、利息额、**利息概率（interest probability）**、利息标准差（Table 10）——学术严重度模型是「本金 + 条件利息」的期望值结构，与金融隐喻严格对齐。

### 2.2 《Managing Technical Debt》（Kruchten/Nord/Ozkaya 2019）的七类

该书正文按软件开发生命周期组织债类型；流通较广的一份二手整理卡（[techdebtcost.com/types](https://techdebtcost.com/types)，标注来源为该书及 2012 IEEE Software 论文）将其归纳为七类：**code debt（代码债：代码异味、死代码、重复逻辑、超长方法）· design debt（设计债：模式违背、泄漏抽象、贫血领域模型）· architecture debt（架构债：系统级耦合、错误的服务边界、循环依赖）· test debt（测试债：覆盖缺失、flaky 测试、慢测试套件）· documentation debt（文档债：缺 ADR、过期 README、部落知识）· infrastructure debt（基础设施债：过时云配置、未打补丁镜像、过期 TLS 证书、依赖落后多个大版本）· build debt（构建债：不可复现构建、手工部署步骤、CI/CD 腐化、缺失回滚程序）**。注意：此卡为二手来源，七类口径与 Li 十类高度重叠（多了基础设施细节，少了需求/缺陷/版本）。

### 2.3 《Technical Debt in Practice》（Ernst/Delange/Kazman 2021）：扩展定义

Neil Ernst、Julien Delange、Rick Kazman 的专著（O'Reilly 2021 初版，MIT Press 2022 再版）**显式拓宽传统定义**，出版社简介列明其覆盖范围：「requirements debt, implementation debt, testing debt, architecture debt, documentation debt, deployment debt, and social debt」（需求债、实现债、测试债、架构债、文档债、部署债、社会债）（[Google Books 条目](https://books.google.com/books/about/Technical_Debt_in_Practice.html?id=1nQJEAAAQBAJ)）。相对 Li 十类：implementation debt ≈ code+design 债合并，新增 deployment debt（部署债），并正式把 social debt（社会债）纳入债的谱系。作者之一的 Neil Ernst 目前的研究方向自述为「Technical Debt and Software Design in the AI Era——技术债与软件设计在 LLM 时代的变化」（[作者研究页](https://neilernst.net/research/)），印证学界已开始关注 AI 对 TD 研究的影响，但其框架中 AI 是改变设计活动与产生债的因素，仍非债的判据主体（见 §五）。

### 2.4 架构债专门研究线（SEI/ICSA）

Nord、Ozkaya、Kruchten、Gonzalez-Rojas 的《In Search of a Metric for Managing Architectural Technical Debt》（WICSA 2012）获 ICSA 2022 最具影响力论文奖，贡献是**用变更传播（change propagation）度量估算架构债成本**（[SEI 新闻稿](https://sei.cmu.edu/news/2012-technical-debt-paper-co-authored-by-seis-nord-and-ozkaya-wins-most-influential-award/)，含评委会引语）。同一团队的后续工作《Bridging the Gap between Technical Debt and Software Architecture》（WICSA 2019，IEEE Xplore 8764253）继续弥合债项与架构决策的映射（原文全文未能在本次调研中获取，此处仅记录其存在与脉络，不引其内容）。这条线的要点：**架构债的判据是「变更传播成本」——一个模块的改动会强制连带改动多少其他模块**，严重度用变更传播估算的返工成本衡量。

### 2.5 自认技术债（SATD）：按检测通道而非债务本体分类

Potdar & Shihab《An Exploratory Study on Self-Admitted Technical Debt》（ICSME 2014，[论文 PDF](https://users.encs.concordia.ca/~eshihab/pubs/Potdar_ICSME2014.pdf)）定义了 **self-admitted technical debt（自认技术债，SATD）**：开发者明知故犯并在代码注释中承认的债。判据是**注释模式**：作者人工阅读 101,762 条注释，提炼出 62 个模式（如 `hack`、`fixme`、`is problematic`、`this isn't very solid`、`probably a bug`）；量化结果：四个大型开源项目（Eclipse、Chromium OS、Apache httpd、ArggoUML）中 2.4%–31% 的文件含 SATD，引入后仅 26.3%–63.5% 被移除，且时间压力与代码复杂度与 SATD 数量不相关（摘要与 Section IV）。后续 Maldonado & Shihab 的工作把 SATD 归为五种主类型：design、defect、documentation、requirement、test debt（转引自 [ScienceDirect 论文](https://www.sciencedirect.com/science/article/abs/pii/S0950584920300203)综述句）。SATD 是**检测通道**（注释挖掘）而非新债类型，但其「债在注释里自认」的思路对工具设计影响深远（SonarQube 亦检测 TODO/FIXME 类注释异味）。

### 2.6 工业界博客谱系（以 Semaphore 为代表）

Semaphore（CI/CD 厂商）的技术博客《How to Use AI to Reduce Technical Debt》（[semaphore.io/blog/ai-technical-debt](https://semaphore.io/blog/ai-technical-debt)）给出的工业界通行六分类：**code debt（意面代码、缺模块化、硬编码）· documentation debt（文档缺失/过时/不完整）· testing debt（跳过写测试或不维护测试套件）· architecture debt（早期架构决策导致难以修改扩展的设计）· infrastructure debt（手工部署、缺 CI/CD 管线、依赖遗留硬件）· security debt（忽视安全最佳实践，被称为「最危险的债」）**。该文同时代表了工业界对 AI 的主流姿态：**AI 是还债的工具**（代码分析、生成测试、生成文档、安全扫描），而非债的受害方——这一点对 §五的空档论证很重要。

---

## 三、工业界工具体系

### 3.1 SQALE：一切债折算成 remediation cost

SQALE（Software Quality Assessment based on Lifecycle Expectations）由 DNV ITGS France（后 inspearit）开发，CC BY-NC-ND 3.0 许可，方法定义见 [sqale.org](https://www.sqale.org/) 与 [Wikipedia: SQALE](https://en.wikipedia.org/wiki/SQALE)（含方法定义摘要）。

- **债务类型（质量模型）**：三层结构——特征（characteritics）→ 子特征 → 源码要求（requirements，即规则）。顶层特征沿用 ISO 9126：**Testability（可测试性）、Reliability（可靠性）、Changeability（可变更性）、Efficiency（效率）、Security（安全性）、Maintainability（可维护性）、Portability（可移植性）、Reusability（可复用性）**，每个特征有自己的指数（STI、SRI、SCI、SEI、SSI、SMI、SPI、SRuI），加总为 SQALE Quality Index（SQI）（Wikipedia "The indices" 节）。特征排序按软件生命周期依赖组织成金字塔（[Letouzey 的 Dagstuhl 演讲 PDF](https://mtd2016dagstuhldotorg.files.wordpress.com/2016/04/remediations-in-sqale-dagstuhl.pdf)，p.15-17），先修可测试性再修可靠性——修复动作有技术依赖顺序。
- **判据**：质量 = 与需求的符合度；每条规则是一个原子、可验证的要求（SonarSource 博客示例：「每个方法复杂度须小于 10」，见 [SQALE, the ultimate Quality Model](https://www.sonarsource.com/blog/sqale-the-ultimate-quality-model-to-assess-technical-debt/)）。**正交性**：一个质量缺陷在模型中只出现一次。
- **严重度依据**：双估算模型（Letouzey Dagstuhl 演讲 p.4）：**remediation cost（修复成本 = 本金）**——把工具报告的每个违规乘以单位修复时间加总（SonarSource 博客示例：某规则 4 次违规 × 10 分钟 = 40 分钟，逐层加总到 SQALE Index；SQALE Ratio = Index ÷ 从零重写整个应用的预估成本）；**non-remediation cost（不修复的代价 = 利息/business impact）**——按影响等级赋值：Very High 5000（如可能生产事故的除零/危险转型）、High 500（复现定位修复 bug 的重大额外工作量）、Medium 50（实现新功能的次要额外工作量）、Low 1（无显著影响，如缩进违规）（同演讲 p.12 影响等级表）。SQALE 强调加法聚合（「有多笔债时取平均没有意义」）与比率尺度合法性（Wikipedia "Fundamental principles" 节）。

### 3.2 SonarQube：SQALE 的工程化继承者

SonarQube 早年直接实现 SQALE（商业插件为官方实现），如今核心指标仍带 SQALE 烙印（`sqale_index`、`sqale_debt_ratio`、`sqale_rating`）。

- **债务类型**：当前有两套口径（[Changing instance modes](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/changing-modes/)）。**Standard Experience**：问题三分类——Bugs（缺陷）、Vulnerabilities（漏洞）、Code Smells（代码异味，即狭义技术债），每条规则单一严重度（Blocker/Critical/Major/Minor/Info）。**MQR 模式**（10.8+）：三分类换成三个 software qualities——**Security、Reliability、Maintainability**（[Software qualities](https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/managing-rules/software-qualities/)），一条规则可在不同质量维度上有不同严重度（Blocker/High/Medium/Low/Info）。
- **判据**：规则库（数千条静态分析规则，按语言），违反规则即产生 issue；另有 **Security Hotspot** 机制——安全敏感但需人工评审才能定性为漏洞的代码（如 cookie secure flag），评审优先级按 OWASP Top 10 / CWE Top 25 排序（[Managing Security Hotspots](https://docs.sonarsource.com/sonarqube-server/user-guide/security-hotspots/)）。
- **严重度依据**（[Understanding measures and metrics](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition/)，Maintainability 节）：**技术债 = 全部可维护性问题修复成本之和**，单条 issue 的成本取自规则预设的分钟数（8 小时折算 1 天）；**技术债比率 = 技术债 ÷（每行代码开发成本 30 分钟 × 行数）**；**可维护性评级按债比率分档：A ≤5%，B 5–10%，C 10–20%，D 20–50%，E >50%**。安全/可靠评级则按最高问题严重度定档（A=无/info 级，…，E=至少一个 blocker）。全部指标区分**总体代码 vs 新代码**（new code）——「Clean as You Code」策略只对新代码设质量门（Quality Gate 阈值化上述评级/比率）。

### 3.3 CodeScene：行为维度与社会性技术债

CodeScene（Adam Tornhill，《Your Code as a Crime Scene》《Software Design X-Rays》作者创立）代表第三条路线：**行为代码分析（behavioral code analysis）**——「不只看代码长什么样，还看你们怎么使用它」（[官方产品页](https://codescene.com/product/behavioral-code-analysis)）。其技术债文档明言：「CodeScene 按团队与代码的**交互方式**排定技术债优先级，而不是只看代码本身」（[Technical Debt — CodeScene Docs](https://codescene.io/docs/guides/technical/hotspots.html)）。

- **债务类型**（四层）：
  1. **代码健康（Code Health）**：基于 25+ 因子的聚合指标，覆盖模块异味（低内聚 LCOM4、God/Brain Class、大文件）、函数异味（Brain Method、复杂方法、大方法、原始类型偏执）、实现异味（嵌套复杂度、Bumpy Road、复杂条件、重复断言块）（[Code Health 文档](https://codescene.io/docs/guides/technical/code-health.html)）。
  2. **热点（Hotspots）**：高变更频率 × 低代码健康的交集——「复杂且常改的代码」（hotspots 文档）。方法级下钻由 X-Ray 完成（语言相关分析，[X-Ray 文档](https://codescene.io/docs/guides/technical/xray.html)）。
  3. **变更耦合（change coupling）**：两个模块在时间上共同变更（同 commit、同作者同时段、或同 ticket），揭示代码里看不出来的逻辑依赖（[Change Coupling 文档](https://codescene.io/docs/guides/technical/change-coupling.html)）。
  4. **社会性/知识维度**：知识孤岛（knowledge island，只有一人懂的代码）、关键人员风险、知识流失（knowledge loss，前雇员代码）、开发碎片化（fragmentation，fractal 值 0→1 表示并行开发人数，被引为发布后缺陷数的最佳预测因子之一）（[Knowledge Distribution](https://codescene.io/docs/guides/social/knowledge-distribution.html)、[Parallel Development and Code Fragmentation](https://codescene.io/docs/guides/social/fragmentation.html)）。
- **判据**：git 历史挖掘——变更频率、作者贡献（深度历史、改名/移动追踪）、commit 关联、Jira 工单关联；复杂度用语言中立的**缩进深度**（indentation-based complexity）而非圈复杂度做趋势分析（[Complexity Trends](https://codescene.io/docs/guides/technical/complexity-trends.html)）。
- **严重度依据**：**技术债摩擦（Technical Debt Friction）**——低代码健康 × 高开发活动的交集即「债实际拖慢团队之处」，明确反对静态分析工具「给你 5000 条待修清单」；优先级算法综合：变更频率、代码健康、需连带修改的模块数、涉及的开发者/团队数、协调瓶颈（hotspots 文档 "Focus on your Refactoring Targets" 节）。聚合时按文件 LoC 加权平均（避免小文件稀释大问题）。实证背书是 **Code Red 论文**（Tornhill & Borg，TechDebt 2022，[白皮书版](https://codescene.com/hubfs/web_docs/Business-impact-of-low-code-quality.pdf)）：39 个商业代码库，Green 代码实现任务比 Red 快 124%，Red 代码缺陷多 15 倍、最大完成时间不确定性高 9 倍。该论文还点名 SQALE/SIG 模型「**缺乏对真实业务影响的度量**——技术债的成本不是修代码要花的时间（那是修复工作），而是低质量导致的额外开发工作」（白皮书 p.5）。

### 3.4 三体系横向对照表

| 维度 | 学术十类（Li 2015） | SQALE/SonarQube | CodeScene |
|---|---|---|---|
| 债务类型 | 按开发生命周期工件分十类（需求/架构/设计/代码/测试/构建/文档/基础设施/版本/缺陷） | 按 ISO 质量特征分八类（SQALE）/ 按问题性质三类或三质量（SonarQube） | 按行为表现分四层（代码健康/热点/变更耦合/知识社会） |
| 判据 | 研究文献中各类型的成因与信号（静态分析、依赖分析为主，Table 8） | 规则违规（原子、可验证的源码要求） | git/Jira 行为数据 × 静态信号（变更频率、作者分布、共同变更） |
| 严重度 | principal + interest + interest probability（TD item 字段表，Table 10） | remediation cost 加总（分钟/天）+ 债比率分档 A–E + 规则严重度 | 代码健康分（LoC 加权）× 热点活动 = ROI 排序；缺陷密度验证 |
| 受损主体 | 人类开发者（可维护性/可演化性） | 人类开发者/业务（business impact = 人的额外工作量） | 人类团队（开发速度、协调成本、知识流失） |

---

## 四、严重度模型的三种范式

1. **修复成本范式（SQALE/SonarQube）**：严重度 ≈ 把代码修到合规要多久。优点是可加总、可换算成钱、对管理层友好；缺点（Code Red 论文直指）是**修复成本≠业务影响**——修 10 分钟的债可能造成数周的拖慢，反之亦然。
2. **本金 + 条件利息范式（学术界）**：TD item = 本金（修复成本）+ 利息额 + 利息概率 + 利息标准差（Li 2015 Table 10）。承认债是否「发作」取决于未来是否触碰该区域，比纯修复成本更精细，但估算困难（Dagstuhl 报告承认 principal/interest 的量化「被证明是困难的」）。
3. **摩擦/ROI 范式（CodeScene）**：严重度 =（静态缺陷 × 行为暴露度）的乘积——同样的坏代码，常改、多人协调、缺陷密集的才值得先修；用开发速度与缺陷数的实证相关性（Code Red）闭环验证。

CogniCode 的对应物是第四种：**失败模式频率 × 过程成本**（token/轮次/成本中位数 + 出错率 + 破坏率）——债的严重度由 agent 实际表现定义，与范式 3 的「行为暴露」思想同构，但行为数据源从人类 git 历史换成 agent 执行轨迹。

---

## 五、空档验证：AI agent 工作效率不是任何体系的债判据

逐体系检查「债的利息落在谁身上」：

| 体系 | 利息/受损主体的定义 | 出处定位 |
|---|---|---|
| Dagstuhl 16162 学术定义 | 「影响限于内部系统质量——主要是可维护性与可演化性」（人类维护者的变更成本） | 报告 Executive Summary |
| Li–Avgeriou–Liang | 利息 =「修改含债部分所需的额外努力」；受损质量属性映射到 ISO 25010，可维护性占绝对主导 | 论文 Table 5（interest 定义）与 Table 6 |
| SQALE | non-remediation cost =「对业务活动的负面影响」；High 级示例为「复现、定位、修复 bug 的重大额外工作量」——全部是人类工作量 | Letouzey Dagstuhl 演讲 p.4 与 p.12 |
| SonarQube | 三个 software qualities（安全/可靠/可维护）无 AI 轴；技术债 = 人类修复工时 | 官方文档 software-qualities 与 metrics-definition |
| CodeScene | 行为数据全部来自人类活动（commit、作者、Jira cycle time）；「债实际拖慢**团队**之处」 | hotspots 文档、Code Red 白皮书 |
| 《Technical Debt in Practice》 | 扩展到 social debt（人类社区质量），仍是人本 | 出版社简介 |
| Semaphore 等工业博客 | AI 是**还债工具**（生成测试/文档/安全扫描），不是受损主体 | semaphore.io 博客全文 |

**结论：论断成立。** 没有任何一个既有体系把「AI agent 的工作效率/迷路率/出错率」作为债的判据或严重度依据。需要诚实记录的两个相邻事实（均不推翻论断）：

1. **静态 AI-readiness 打分已存在**（DAF Benchmark 等，5 维度加权 0–5 分），本仓库 `docs/research/prior-art.md` 已调研过——但它们是「友好度评分」不是债分类学：无失败模式轴、无严重度/remediation 模型、不做 agent 执行测量。
2. **学术界开始出现「AI 时代的技术债」方向**（Neil Ernst 研究组自述研究主题「Technical Debt and Software Design in the AI Era」，见其[研究页](https://neilernst.net/research/)）——但其关注点是 LLM/vibe coding 如何**改变产生债的设计活动**（AI 是债的生产者），而非以 agent 受损定义债。产出方向与判据方向相反。

因此「对 AI 不友好的债」（是否会让下一个 AI agent 迷路/犯错/爆炸）是一个**既有谱系的真实空位**，不是对既有分类的重新包装。

---

## 六、对照节：逐类判断对 CogniCode 的覆盖关系

分类轴已锁定：六维度失败模式（可解性 solvability、变更安全性 safety、效率 efficiency、可导航性 navigability、环境可用性 buildability、可诊断性 diagnosability，见 CONTEXT.md）。债的定义锚定「对 AI 不友好的债」。判定记号：**(a)** 六维度轴可覆盖且应覆盖；**(b)** 与定义无关、明确不覆盖；**(c)** 错位或部分交集（指出错位在哪）。

| # | 既有债务类型 | 判定 | 理由与错位点 |
|---|---|---|---|
| 1 | 测试债（test debt）：覆盖缺失、flaky、慢测试 | **(a)** | 直接命中两个维度：agent 冷启动跑不起验证回路（环境可用性）+ 改完没有红绿信号可依（变更安全性）。flaky 测试对 agent 是双重毒药（误判失败/误判成功）。静态面可确定性检测（测试可发现性、覆盖缺口），动态面由 F2P/P2P 判卷直接测量。最强 (a)。 |
| 2 | 构建债（build debt）：不可复现构建、手工步骤 | **(a)** | 与环境可用性几乎一一对应（冷启动构建/测试 = probe 任务）；构建脚本腐化 = agent 跑不起验证回路。本仓 probe.py 已有确定性判据雏形。 |
| 3 | 文档债（documentation debt） | **(a)（限定子集）** | 子集划分：**面向 agent 的上下文文档**（AGENTS.md/README/入口说明/注释）缺失或误导 → 可导航性/可解性，明确应覆盖（本仓 static_signals 已有 4 个信号）。错位点：人类文档生态（ADR 决策记录、架构图、API 文档站点）中「对 agent 导航无用但对人重要」的部分是 (b)；**过时文档比缺失文档对 agent 更糟**（主动误导 → 可解性债），这是既有体系没有的判据角度。 |
| 4 | 代码债（code debt）：异味、重复、超长方法、死代码 | **(c)** | 部分交集：超长方法/大文件/深嵌套会拖慢 agent（效率：token 成本）并增加误解概率（可解性/可诊断性）→ 该子集应覆盖（本仓 big_file 归因信号已列）。错位点：命名规范、缩进风格、模式纯度类异味对 agent 几乎零利息（agent 不依赖命名美学理解代码）→ (b)；死代码对人类是零利息债（techdebtcost 卡自认），对 agent 反而是**负导航信号**（agent 可能调用到死代码）→ 判据方向相反。判据应以「agent 表现退化」而非「规则违规」为准。 |
| 5 | 设计债（design debt）：浅模块、泄漏抽象、pass-through | **(c)** | 部分交集：浅模块（小接口藏大行为）迫使 agent 读大量接口才懂一点行为 → 效率 + 可导航性（本仓 module_depth 信号已实现，deep/shallow 判定即为此设计）。错位点：模式纯度类设计债（贫血领域模型、feature envy）是维护者美学，agent 不受损 → (b)。 |
| 6 | 架构债（architecture debt）：耦合、错误边界、变更传播成本 | **(c)** | 部分交集：**隐藏的变更耦合**（改 A 必须改 B 但代码里看不出来）会让 agent 改一处漏一处 → 变更安全性。CodeScene 的 change coupling 判据（共同变更历史）恰好是 agent 破坏行为的预测器，可借鉴其信号但换判据。错位点：宏观架构治理（服务边界、团队所有权）本身对 agent 是不可见的——除非它表现为 agent 可感知的摩擦（改代码炸别处），否则 (b)。SEI 的变更传播成本严重度模型可平移为「agent 破坏半径」的经验测量。 |
| 7 | 需求债（requirements debt） | **(b)（几乎全部）** | 需求规格与实现的差距是**任务来源**（agent 的输入），不是 agent 工作的摩擦。需求不清晰时受害的是提问的人机回路，不是仓库。边界例外：实现与文档/注释的**矛盾**会误导 agent（可解性），但那归入文档债的「过时误导」子集。 |
| 8 | 基础设施债（infrastructure debt） | **(c)** | 部分交集：缺 CI、缺锁文件、依赖声明与实际不符 → 环境可用性（本仓已有锁文件/CI 信号）。错位点：服务器打补丁、TLS 证书、云配置老化等运维债对 agent 冷启动不可见 → (b)。 |
| 9 | 版本控制债（versioning debt） | **(b)** | 不必要的代码分叉等是人类协作问题；agent 在 fresh clone 上工作，分支治理不影响其失败模式。 |
| 10 | 缺陷债（defect debt） | **(b)** | 缺陷是 agent 的**工作对象**（任务本身），不是让 agent 迷路的债。注意学界对「缺陷算不算债」本就分裂（§1.2）。唯一交集：**flaky/不稳定环境**会污染 agent 的失败样本（fail_env 剔除逻辑），但那归环境可用性。 |
| 11 | 部署债（deployment debt，Ernst 书） | **(c)** | 部署脚本若承担「验证回路」角色（跑 e2e 才算验证）则部分进环境可用性；纯发布运维（回滚程序、发布频次）→ (b)。 |
| 12 | 社会债/人员债（social/people debt：知识孤岛、truck factor、知识流失、碎片化） | **(b)**——但有一个重要反转 | 判据完全人本：agent 不会离职、不遗忘、不需要协调。**反转点**：人类用文档/规范来对抗知识流失，而这些「补偿性工件」恰好是 agent 导航所依赖的——所以该类型的**产物**与可导航性重叠，但其**判据**（人员分布）与 AI 受损无关。CogniCode 应明确声明不按人员度量，避免与 CodeScene 正面竞争。 |
| 13 | 安全债（security debt） | **(b)** | 漏洞不会让 agent 迷路/犯错/变慢——按「对 AI 不友好的债」的定义不构成债。SonarQube 的 Security Hotspot 评审流程也是人类工作流。留作明确的非目标（防止 scope 蔓延），除非用户语境把 agent 引入漏洞视为变更安全性子问题（那是 agent 行为治理，不是仓库债）。 |
| 14 | SATD（自认技术债） | **(c)**（信号通道而非类型） | TODO/FIXME/hack 注释对 agent 是双向信号：既是「这里有坑」的提示（可诊断性正信号），也是「未完成工作」的误导（可解性负信号）。可作为确定性检测通道并入六维度，但不是类型轴上的一类。 |
| 15 | 变更耦合/时间耦合（CodeScene 专长） | **(c)** | 判据可借鉴（git 共同变更历史是确定性可提取的），但严重度要换轴：CodeScene 用人类协调成本，CogniCode 用 agent 破坏率（变更安全性维度的动态测量：fail_incorrect 样本中「破坏了未提及模块」的占比）。 |

### 对照节小结

- **应覆盖（a）**：测试债、构建债、文档债的 agent 相关子集——恰好是六维度中环境可用性、可导航性的主场，且本仓静态信号已有雏形。
- **部分交集（c）**：代码债、设计债、架构债、基础设施债、部署债、变更耦合——共同规律：**既有类型按「工件在哪」分类，CogniCode 按「agent 怎么失败」分类**，同一工件只在引发 agent 失败模式时才成为债项。这预示 CogniCode 的债项输出应是「六维失败模式 × 既有类型标签」的双轴标注（工件类型便于与 SonarQube/CodeScene 用户沟通，失败模式是本产品的判断轴）。
- **明确不覆盖（b）**：需求债、缺陷债、版本债、社会/人员债、安全债——每类都应在产品文档中显式声明排除及理由（本表可直接引用），这是定位声明的一部分：**不做通用代码质量工具，不做人类组织分析工具**。

### 对后续票（#40 分类学）的三点输入

1. **双轴标注**：债项类型学建议采用「失败模式（轴，已锁）× 工件类别（标签，借用 Li 十类的词汇）」，不要发明新的工件分类——十类词汇已是行业通用语，沿用可降低沟通成本。
2. **严重度第四范式**：借 SQALE 的「可加总、可换算」优点（输出 remediation 提示时给分钟数），借 CodeScene 的「摩擦交集」思想（只报 agent 实际踩到的债），但严重度主判据用 agent 实测（失败率、token 成本、破坏率），并像学术模型一样标注置信度（interest probability 的对应物，地图决策 3 已定）。
3. **确定性信号优先级**：对照表 (a) 行的三个类型（测试/构建/文档）全部可确定性检测且本仓已有雏形，应作为 MVP 确定性债项的首发集合；(c) 行的变更耦合信号值得单独立票评估（git 挖掘是确定性但工程量中等）。

---

## 附：来源清单（全部一手或官方来源）

- Li, Avgeriou, Liang.《A systematic mapping study on technical debt and its management》JSS 101 (2015) 193–220. https://pure.rug.nl/ws/files/239167347/1_s2.0_S0164121214002854_main.pdf（十类分类 §4.4.1.1、non-TD Table 4、概念 Table 5、质量属性 Table 6、TD item 字段 Table 10）
- Avgeriou, Kruchten, Ozkaya, Seaman (eds). Dagstuhl Seminar 16162 Report. https://drops.dagstuhl.de/storage/04dagstuhl-reports/volume06/issue04/16162/DagRep.6.4.110/DagRep.6.4.110.pdf（共识定义、社会债边界）
- Kruchten, Nord, Ozkaya《Managing Technical Debt》第 1 章摘录（SEI 博客）. https://insights.sei.cmu.edu/sei_blog/2019/05/managing-the-consequences-of-technical-debt-5-stories-from-the-field.html
- 七类整理卡（二手，基于 Managing Technical Debt）. https://techdebtcost.com/types
- Fowler. Technical Debt Quadrant. https://martinfowler.com/bliki/TechnicalDebtQuadrant.html
- Ernst, Delange, Kazman《Technical Debt in Practice》出版社条目. https://books.google.com/books/about/Technical_Debt_in_Practice.html?id=1nQJEAAAQBAJ
- SEI 新闻：In Search of a Metric（WICSA 2012）获 ICSA 2022 MIP 奖. https://sei.cmu.edu/news/2012-technical-debt-paper-co-authored-by-seis-nord-and-ozkaya-wins-most-influential-award/
- Potdar, Shihab. An Exploratory Study on Self-Admitted Technical Debt (ICSME 2014). https://users.encs.concordia.ca/~eshihab/pubs/Potdar_ICSME2014.pdf
- SonarSource. SQALE, the ultimate Quality Model to assess Technical Debt. https://www.sonarsource.com/blog/sqale-the-ultimate-quality-model-to-assess-technical-debt/
- Letouzey. The SQALE Method for Managing Technical Debt (Dagstuhl 演讲). https://mtd2016dagstuhldotorg.files.wordpress.com/2016/04/remediations-in-sqale-dagstuhl.pdf
- SQALE 方法摘要. https://en.wikipedia.org/wiki/SQALE ；方法官网 https://www.sqale.org/
- SonarQube 官方文档：[metrics-definition](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition/)、[software-qualities](https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/managing-rules/software-qualities/)、[changing-modes](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/changing-modes/)、[security-hotspots](https://docs.sonarsource.com/sonarqube-server/user-guide/security-hotspots/)
- CodeScene 官方文档：[hotspots](https://codescene.io/docs/guides/technical/hotspots.html)、[code-health](https://codescene.io/docs/guides/technical/code-health.html)、[change-coupling](https://codescene.io/docs/guides/technical/change-coupling.html)、[xray](https://codescene.io/docs/guides/technical/xray.html)、[complexity-trends](https://codescene.io/docs/guides/technical/complexity-trends.html)、[knowledge-distribution](https://codescene.io/docs/guides/social/knowledge-distribution.html)、[fragmentation](https://codescene.io/docs/guides/social/fragmentation.html)、[behavioral-code-analysis](https://codescene.com/product/behavioral-code-analysis)
- Tornhill, Borg. Code Red: The business impact of code quality（TechDebt 2022 白皮书版）. https://codescene.com/hubfs/web_docs/Business-impact-of-low-code-quality.pdf
- Semaphore. How to Use AI to Reduce Technical Debt. https://semaphore.io/blog/ai-technical-debt
- Neil Ernst 研究方向页（AI-era TD）. https://neilernst.net/research/
