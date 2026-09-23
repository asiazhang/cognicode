# 资产盘点：现有仓库哪些代码与信号可复用为债检测

> 票：[资产盘点 #41](https://github.com/asiazhang/cognicode/issues/41) · 地图：[#39](https://github.com/asiazhang/cognicode/issues/39)
> 分支：`research/asset-inventory`
> 方法：通读 `src/cognicode/` 全部 19 个模块 + tests（24 个测试文件）+ docs/ADR/CONTEXT/README + git log，与「已实现/半成品/仅设计」三档逐项核对。只读调查，未跑测试（票约束）。

## 摘要（一屏版）

仓库是一个**评分工具的完整 MVP**（六维聚合打分 + 动静双测量），不是债检测工具。直接可复用的核心是「确定性提取层」——tree-sitter 符号提取、8 个静态产分信号、模块收集、报告模板——它们语言无关、纯函数、测试覆盖好（328 个测试函数），改造为 skill 内嵌脚本是**搬迁**而非重写。LLM 判定层（模块深度、归因兜底）的 prompt 协议可直接成为 SKILL.md 指令的雏形。动态测量 harness 工程完成度高但**从未在真实仓库跑通过**（试点两仓探测失败，动态面全靠仿真数据），且地图已锁定动态测量为二期，MVP 应整体搁置。六维度聚合/打分/敏感性分析与「按严重度排序的债项清单」形态冲突，大部分放弃。

汇总表：

| # | 资产 | 档位 | 复用角色 | 工作量 |
|---|------|------|----------|--------|
| 1 | tree-sitter 符号提取（symbols.py） | 已实现 | 确定性发现·引擎 | 小时级 |
| 2 | 静态信号集（static_signals.py，8 信号） | 已实现 | 确定性发现 | 小时级 |
| 3 | 模块深度 LLM 判定（module_depth.py） | 已实现 | LLM 推断发现 | 小时级 |
| 4 | 归因管线（attribution.py） | 半成品 | 部分复用（模板层） | 天级 |
| 5 | 环境探测（probe.py + ProbeRunner） | 已实现（但真实仓全灭） | 确定性发现（降级形态） | 小时级 |
| 6 | 动态测量 harness（harness/pi_executor/ext） | 半成品（未真跑通） | 放弃（MVP）/二期实证 | 周级（若二期启用） |
| 7 | 任务生成管线（generation/pipeline/verify） | 半成品 | 放弃（MVP） | 周级 |
| 8 | 判卷层（verdict.py） | 已实现 | 放弃（MVP） | — |
| 9 | 六维聚合（aggregate/score/statistics） | 已实现 | 放弃（框架语言保留） | — |
| 10 | 敏感性分析（sensitivity.py） | 已实现 | 放弃（MVP） | — |
| 11 | 报告生成（report.py/schema.py） | 已实现 | 改造复用 → DEBT.md | 天级 |
| 12 | LLM 客户端（llm.py） | 已实现 | 部分复用（prompt 协议） | 小时级 |
| 13 | CLI（cli.py） | 已实现 | 降级/重组 | 小时级 |
| 14 | 测试套件（tests/，328 个测试函数） | 已实现 | 随资产走 | — |
| 15 | 六维失败模式语言（CONTEXT.md + ADR） | 仅设计（领域语言） | 分类轴（直接继承） | 0 |
| 16 | 文档/ADR/研究（docs/） | 已实现（文档） | 决策输入 | 0 |

---

## 逐项明细

### 1. tree-sitter 符号提取 — `src/cognicode/symbols.py`

- **现状：已实现**（commit 6b477c1，#20）。`extract_symbols(repo)` 从 21 种源码扩展名提取函数/方法/类符号，产出语言无关的 `Symbol(kind, name, file, line)`，确定性、无 LLM。
- **技术细节**：tree-sitter-language-pack 统一解析；避开 `start_point` 段错误坑（用 `start_byte` 数行号，真仓 nbnbk 实测）；解析失败跳文件不炸管线。
- **复用角色**：确定性发现的**引擎底座**。债检测需要「位置 + 符号」锚点（超长函数、符号密度、重复符号名、无注释导出符号等债项信号都可从符号面派生）；DEBT.md 的每条债项要 file::symbol 定位，这套提取直接可用。
- **工作量：小时级**。包一层「信号→债项」的派生规则即可；注意它是为任务生成服务的，排除 test/docs 目录的口径（`_EXCLUDE_DIR_TOKENS`）需按债检测语义复核（债检测可能要扫测试）。
- **依据**：symbols.py 全文（204 行）；tests/test_symbols.py（124 行，含真实 PHP/JS fixture）。

### 2. 静态信号集（8 产分信号）— `src/cognicode/static_signals.py`

- **现状：已实现**（commit 8488343，#18）。8 个信号全部确定性、语言无关：可导航性 4（代理上下文文档、README、注释密度（tree-sitter）、入口清晰度）+ 环境可用性 4（构建定义、锁文件、CI、测试可发现性）。每信号产出 `(value, score, evidence)`，evidence 是文件路径/事实清单。
- **与新形态的映射**：这些信号本身就是「对 AI 不友好的债」的确定性判据——缺 AGENTS.md、缺 README、无锁文件、无 CI、测试不可发现，每一条在债形态下都是一条**确定性发现**（位置 = 仓库根，类型 = 环境可用性/可导航性失败模式，严重度可按缺失与否定档）。信号 → score 的离散刻度（0/0.5/1）是为打分设计的，可改译为严重度排序依据。
- **复用角色**：确定性发现的主力。8 个信号 ≈ MVP 确定性脚本的第一批内置检查。
- **工作量：小时级**。信号提取逻辑（`_extract_*` 各函数 + `_iter_files` 遍历 + 注释密度 tree-sitter 解析）全部纯函数可直接搬；要改的是输出结构（static.json 形状 → DEBT.md 债项条目）。
- **依据**：static_signals.py 全文（510 行）；tests/test_static_signals.py（260 行）；`.cognicode/scan-*` 11 个真实运行目录证明链路能跑。

### 3. 模块深度 LLM 判定 — `src/cognicode/module_depth.py`

- **现状：已实现**（commit 63d80ad，#23，ADR-0004 定位为归因信号不进产分）。`collect_modules()` 确定性收集文件级模块（排除 vendor/docs/test，跳过 <5 行平凡文件）；`judge_module_depth()` 用 LLM 按结构化协议判 deep/shallow（单 JSON 输出 + 重试 + 非法丢弃）；`run_module_depth()` 输出分布 + shallow 模块重构建议清单。
- **复用角色**：LLM 推断发现的直接雏形。判定协议（模块 id + 16K 字符源码预算 + 单标签 JSON 输出 + 容忍 ```json 包裹）就是 SKILL.md 里「LLM 推断档」指令的现成形态；「shallow 模块 = agent 要读大量接口才懂一点行为」的表述本身就是债语言。deep/shallow 二分在债形态下可能要细化为「为什么是债 + 修复建议」，prompt 要改，但骨架（收集→判定→建议）完整。
- **工作量：小时级**。collect_modules 确定性部分零改动可搬；prompt 按债分类学重写 + 输出从单标签扩为「债类型 + 置信度 + 理由」（地图决策 3：LLM 判定标置信度）。
- **依据**：module_depth.py 全文（257 行）；tests/test_module_depth.py（153 行，LLM 用假客户端注入）；ADR-0004。

### 4. 归因管线 — `src/cognicode/attribution.py`

- **现状：半成品**（commit 63d80ad，#23）。三档「确定性优先、LLM 兜底」框架已实现：失败样本→(维度×失败模式)聚合、产分信号命中→确定性模板建议、专属归因信号命中→模板、LLM 证据包综合归因。**缺口**：专属归因信号（测试覆盖缺口 test_gap、单文件规模 big_file）只有消费接口没有提取器——cli.py:268 明言「未落盘（提取器留给后续票）」，`attribution_signals.json` 从未被任何代码写入。
- **复用角色**：部分复用。三档哲学与「确定性发现 + LLM 推断发现」两档分类同构，是两档分类的先例；确定性模板层（`_SIGNAL_SUGGESTIONS` 式「信号缺失→建议+预期方向」）可平移为确定性债项的「修复建议」生成。但整条管线是围绕**动态失败样本**（verdicts.json）组织的，MVP 无动态测量则主管线空转。
- **工作量：天级**（若复用模板层与证据包思路）。test_gap/big_file 两个信号的提取器恰好是债检测的典型确定性债项（测试覆盖缺口、超大文件），值得单独拎出来实现——这是「半成品资产里最容易变现的一块」。
- **依据**：attribution.py 全文（701 行，其中约一半依赖动态 verdicts）；cli.py:265-268 注释；tests/test_attribution.py（409 行）。

### 5. 环境探测 — `src/cognicode/probe.py` + `harness.py` ProbeRunner

- **现状：已实现（代码层面）/ 但真实仓全灭（实证层面）**。probe.py 确定性定位构建/测试命令（composer.json/package.json/pyproject.toml/Cargo.toml/Makefile 等 7 类来源）；ProbeRunner 在 fresh worktree 直接执行命令记录真实退出码（commit 6f05acc 修复了 agent 包装码伪影）。试点语料两仓（nbnbk、Melissa-Core）探测均失败——这本身被定义为环境可用性低分信号。本仓 11 个真实 scan 运行也全部「无构建/测试命令可探测」。
- **复用角色**：确定性发现（降级形态）。「仓库声明了构建/测试命令但跑不通」或「根本没声明」在债形态下就是环境可用性债项的确定性判据。不需要跑通，只需「定位 + 存在性 + 声明一致性」的静态面。
- **工作量：小时级**。命令定位逻辑（`locate_probe_commands`）零改动可搬；执行部分（真跑命令）在 skill 形态下可选（skill 内嵌脚本跑真实命令有安全与时长约束，需设计）。
- **依据**：probe.py（213 行）；harness.py ProbeRunner；docs/smoke-e2e.md 探测判定表；`.cognicode/scan-1788340855/probe.json`。

### 6. 动态测量 harness — `harness.py`（WorktreeManager/run_task）+ `pi_executor.py` + `ext/cognicode-harness-ext.ts`

- **现状：半成品——工程完成度高，但从未在真实仓库跑通完整回路**。组件齐全：pi 0.84.3 RPC 长驻驱动（含 5 个实测坑规避）、fresh git worktree 隔离、测量隔离 TS 扩展（max-turns 早停 + 只读工具门 + submit_result 交卷）、轨迹/diff 采集。但冒烟记录（docs/smoke-e2e.md「已知边界」）明确：试点两仓探测失败 → 动态面降级 → verdicts.json 全部是**固定 seed 仿真数据**，真实 agent 执行 + F2P/P2P 红绿判卷从未发生过。CLI 的 `_cmd_scan` 也只跑一个演示任务收 diff，不做 k 次采样。
- **复用角色**：**MVP 放弃**（地图决策 5 已锁定动态测量为二期实证校验）。二期若启用，这套 harness 是起点而非废墟：pi RPC 驱动 + 测量隔离扩展都实测过（prototype/pi-extension/FINDINGS.md 有踩坑记录）。
- **工作量：周级**（二期启用时补：真实仓跑通探测 → k 次采样循环 → 判卷接线；当前卡点是「没有一个探测能成功的试点仓」）。
- **依据**：harness.py（466 行）、pi_executor.py（383 行）、ext TS 扩展、docs/smoke-e2e.md「已知边界」节、docs/research/pi-schema.md。

### 7. 任务生成管线 — `generation.py` + `pipeline.py` + `verify.py`

- **现状：半成品**。三段式（符号→LLM 模板合成→执行式验证过滤）代码齐全，offline 走确定性模板。但它的唯一用途是给动态测量造题——MVP 无动态测量则整条管线无用武之地。执行式验证过滤（verify.py）从未在「真跑测试红绿」意义上工作过（只做静态可应用性检查）。
- **复用角色**：**MVP 放弃**。二期与 harness 一起评估。唯一可能提前变现的碎片：verify.py 的「补丁可应用」判定，若二期债项验证需要。
- **工作量：周级**（二期启用时）。
- **依据**：generation.py（359 行）、pipeline.py（137 行）、verify.py（247 行）；tests/test_generation.py 等。

### 8. 判卷层 — `verdict.py`

- **现状：已实现**（#21）。五类 outcome 分类 + 位置匹配（检索 file::name 符号级、定位注入点±2 行容差）+ F2P/P2P 判定入口 + 轨迹交卷解析，纯函数、42 个单测全绿。
- **复用角色**：**MVP 放弃**（判卷服务于动态测量）。二期随 harness 复用。位置匹配的「符号级、容忍全路径差异」思路对债项定位有参考价值但代码本身不必搬。
- **依据**：verdict.py（244 行）；tests/test_verdict_judge.py。

### 9. 六维聚合 — `aggregate.py` + `score.py` + `statistics.py`

- **现状：已实现**（#21/#8/#10）。70/30 动静分、Wilson 95% CI、加权总分、区间解析传播、效率百分位、软横比——一个完整的**评分**引擎。
- **复用角色**：**放弃（作为代码）**。债形态是「按严重度排序的债项清单」（地图决策 4），可能纯排序不评分（#39 Not yet specified 明言待定）。六维度作为**分类轴/失败模式语言**通过 CONTEXT.md 存活，不通过这 400 行聚合代码存活。statistics.py 的 Wilson CI 若二期做通过率统计可捞回。
- **依据**：aggregate.py 头部决策锚点注释；地图 #39「每类债的严重度如何计算/加权（可能引入评分，可能纯排序）」。

### 10. 权重敏感性分析 — `sensitivity.py`

- **现状：已实现**（#22）。5⁶ 网格 + Dirichlet 200 采样，纯 Python 无 numpy。
- **复用角色**：**MVP 放弃**。它回答的问题是「总分对权重稳健吗」——没有总分就没有这个问题。若严重度引入加权才可能复活，届时网格扰动思路可参考。
- **依据**：sensitivity.py 头部；冒烟记录显示带宽 0.31/0.29 远超 0.05 判据（如实报告为参考）。

### 11. 报告生成 — `report.py` + `schema.py`

- **现状：已实现**（#21/#12）。终端摘要 + cognicode-report.md 全量落盘，单页三层（总览/维度明细/建议清单），纯文本无 ANSI、中文正文、schema 版本号。建议清单条目含「锚定信号 + 预期方向 + 可重测声明 + 失败任务引用」结构。
- **复用角色**：**改造复用 → DEBT.md 生成器**。DEBT.md 要求「可 diff、可追债的增减、兼作二次运行对比基准」（地图决策 7）——report.py 的纯文本 markdown 生成 + schema 版本化（`report_schema_marker()`） + 「可重测声明」结构都是直接可借鉴的骨架。要改的是：从「维度分明细」改为「按严重度排序的债项条目」，并新增「与上次 DEBT.md 的 diff」小节（新增/修复/滞留）。
- **工作量：天级**。渲染函数纯函数化好改；diff 逻辑是新增（git diff DEBT.md 或结构化比对）。
- **依据**：report.py（445 行）；schema.py；#39 决策 7。

### 12. LLM 客户端 — `llm.py`

- **现状：已实现**（#20/#23）。`LLMClient` 协议 + TemplateLLM（确定性兜底）+ PiLlmClient（经 pi RPC，pin 模型 tencent-copilot/deepseek-v4-flash-ioa）。
- **复用角色**：部分复用。skill 形态下 LLM 调用主体是**用户自己的 agent**（SKILL.md 指令驱动），不再需要 harness 自带 LLM 客户端。PiLlmClient 只在二期动态测量/独立批跑模块深度时有用。结构化输出解析 + 重试 + 非法丢弃的**协议模式**直接写进 SKILL.md 指令。
- **工作量：小时级**（把协议模式翻译成指令文本）。
- **依据**：llm.py（123 行）；地图决策 6（SKILL.md 管 LLM 推断档）。

### 13. CLI — `cli.py`

- **现状：已实现但为评分流程服务**。`cognicode scan <repo>`（静态+探测+演示任务）与 `cognicode report <run-id>`（聚合+落盘）两条命令，scan 与 report 间靠 `.cognicode/<run-id>/` 运行目录衔接。`_cmd_scan` 里混着「演示任务跑一个」的临时代码，`_cmd_report` 是六维聚合流程。
- **复用角色**：**降级/重组**（地图决策 6：CLI 降为脚本副产品）。scan 里的静态提取 + 探测段是可拆出的内核；评分流程（report 命令）随聚合层放弃。skill 形态下入口变成「确定性脚本 + SKILL.md」，CLI 若保留应瘦身为「跑确定性脚本 + 生成 DEBT.md 骨架」。
- **工作量：小时级**（拆内核）+ 重组。
- **依据**：cli.py 全文（385 行）；#39 决策 6。

### 14. 测试套件 — `tests/`（24 文件，328 个测试函数）

- **现状：已实现**，覆盖各模块（静态信号 260 行、归因 409 行、判卷 209+63 行等），LLM/executor 全部用注入假件（fake_pi.py），测试不依赖网络。
- **复用角色**：随被复用资产走——symbols/static_signals/module_depth/probe 的测试搬到新形态继续有效；aggregate/sensitivity/verdict 的测试随资产封存。
- **依据**：`grep -c "def test"` 统计；各测试文件头注释。

### 15. 六维失败模式语言 — `CONTEXT.md` + `docs/adr/`（5 篇）+ README

- **现状：仅设计（领域语言，无代码绑定）**。六维度失败模式（解不出/炸了别处/昂贵/找不到/跑不起/定位不了）是文档层的分类学，代码里只作为维度键名存在。
- **复用角色**：**直接继承为债分类轴**（地图决策 2：债的分类学沿六维度失败模式做类型轴）。这是本仓库最贵、迁移成本为零的资产——整套术语定义、Avoid 列表、决策记录（尤其 ADR-0004「LLM 判定不进产分」的历史论证，直接支撑两档检测的边界）。
- **工作量：0**（重定位改写 CONTEXT.md 是 #40/#42 的事）。
- **依据**：CONTEXT.md 全文；ADR-0001~0005。

### 16. 文档与前置研究 — `docs/research/`（5 篇）+ `docs/calibration/` + harness/task-generation/attribution 文档

- **现状：已实现（文档）**。pi headless schema 实测（pi-schema.md，含 5 坑）、CodeBuddy schema 对照、agent 驱动实测、prior-art 对标（RepoQA/SWE-bench 等）、试点语料 pin。
- **复用角色**：决策输入。prior-art.md 对债检测竞品扫描（SonarQube 等静态债工具的「不做换皮」约束来自地图决策 2）有直接参考价值；pi 系文档二期启用 harness 时复活。
- **工作量：0**。
- **依据**：docs/research/ 目录。

---

## 设计意图 vs 实际进度的差距（git log 与文档核对）

1. **评分闭环「绿」是仿真绿**：README 称「MVP 闭环已在试点语料上冒烟验证」，但 docs/smoke-e2e.md 明言动态面（verdicts.json）是固定 seed 仿真数据——真实 agent 执行判卷从未发生。这对重定位是**好消息**：放弃动态测量（MVP）没有扔掉任何真实工作过的东西。
2. **归因专属信号是显式欠账**：attribution.py 消费 `test_gap`/`big_file`，提取器「留给后续票」从未实现（cli.py:268）。这两个恰是债检测最典型的确定性债项，属于「设计已定、代码零行」的资产。
3. **依赖极轻**：pyproject.toml 运行时依赖只有 tree-sitter + tree-sitter-language-pack（无 package.json，票面线索有误——本仓库是 Python/uv 项目）。skill 内嵌确定性脚本若沿用 Python 生态，依赖面已是最小形态。
4. **ADR 全部围绕评分模型写就**：ADR-0001（静态入分）、0002（判卷权）、0003（执行者隔离）、0004（模块深度归位）、0005（pi 选型）——重定位后 0004 的「LLM 判定是特性不是缺陷」论证直接为两档检测背书，其余四篇主要服务动态测量。

## 对 skill 设计与 MVP 范围的直接建议（供 #42/#43 引用）

- **确定性脚本 v0 = symbols.py + static_signals.py（8 信号）+ probe.py 定位面 + attribution.py 模板层**：全部已实现、纯函数、有测试，搬迁成本以小时计。
- **SKILL.md 的 LLM 推断档 v0 = module_depth.py 判定协议改写**：收集→prompt→单 JSON→重试→丢弃的骨架现成，加置信度字段即可满足地图决策 3。
- **test_gap / big_file 提取器**：设计已有（#15/#18）、代码没有，是 MVP 确定性信号清单里唯一需要**新写**的部分（天级）。
- **DEBT.md 生成**：report.py 骨架 + 新增 diff 小节（天级）。
- **明确不做**：动态 harness、任务生成、判卷、六维聚合、敏感性——封存不删，二期实证校验时再评估。

## 附：证据索引

- 源码：`src/cognicode/`（19 模块，共约 5,000 行）
- 测试：`tests/`（24 文件，328 个测试函数；LLM/executor 全假件注入）
- 真实运行产物：`.cognicode/scan-*`（11 个目录，static.json + probe.json + run.json）
- 冒烟记录：`docs/smoke-e2e.md`（done 判定表 + 已知边界）
- 决策记录：`docs/adr/0001~0005`、`CONTEXT.md`、地图 #39 Notes
- git 历史：c65c080（HEAD of main）回溯至 cfd303a，实现票 #17~#24 逐票可溯
