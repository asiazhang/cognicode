# cognicode-debt — 债扫描编排协议

> 票：[SKILL.md 编排协议 #60](https://github.com/asiazhang/cognicode/issues/60) · 父票：[#57](https://github.com/asiazhang/cognicode/issues/57) · 决议依据：[#42](https://github.com/asiazhang/cognicode/issues/42)（结构设计）· [#43](https://github.com/asiazhang/cognicode/issues/43)（样例实战回修点）· [#67](https://github.com/asiazhang/cognicode/issues/67)（终产物形态修订）· [#66](https://github.com/asiazhang/cognicode/issues/66)（报告=证据呈现器）
> 本文件只做**编排协议**：流程、派发、共享约定、校验与销账纪律。判据一律在外置的 [criteria/](criteria/) 七族文件中，此处不重复、不复述——判据问题一律以族文件为权威。

本 skill 是一个**三段管线**加一个确定性渲染器，产出两件东西：

- **JSON 债项清单**（`.cognicode/debt-scan/debt.json`，落被扫仓库）——销账与审计的基准物；
- **HTML 债报告**（渲染到临时目录，即开即看，不落被扫仓库）——证据呈现器，不产出「推荐先修」式行动指令。

**不变量**：确定性提取层零 LLM；LLM 只发生在第 2 段（分族子代理）与第 3 段（单写手）；主会话单写手是**唯一**写 `debt.json` 的角色。

## 术语

判据词汇（候选 / 证据包 / 单写手 / 严重度带 / 销账 / 唯一真值 / 证据等级语言）以被扫仓库或本仓库的 [CONTEXT.md](../CONTEXT.md) 为准。下文直接使用，不重述定义。

---

## 第 1 段：脚本确定性提取

对被扫仓库跑一趟提取器，全部工件落 `.cognicode/debt-scan/`：

```bash
uv run cognicode-debt/scripts/scan.py <被扫仓库根目录>
```

- 工件位、信封形状（`status: ok | failed` + 错误记录）、per-extractor 容错纪律：见 [scripts/ARTIFACTS.md](scripts/ARTIFACTS.md)，**先读它再消费任何工件**。
- 提取层零 LLM、同 commit 工件字节稳定；单个提取器失败只缩窄当趟产出（该族按「无候选」处理），不炸整趟。
- 需 tree-sitter 的提取器（symbols / test-gap / big-file）在本 skill 仓库内以 dev 环境运行；`uv run` 报导入错误时按 per-extractor 容错纪律继续。
- **大候选集分批**（#42 决议 6）：工件统计出单族候选 > 50 时，该族按候选清单**分批派发**（沿用本协议第 2 段规则，一族多代理并发），并在各批子代理提示中声明「本批为族候选的第 N/M 批」；单写手按族聚合时**批间不去重**——去重只发生在第 3.3 节规定的单写手层。

**族 × 工件消费表**（派发子代理时按下表装输入；工件缺失按「该族无候选」处理）：

| 族 | 工件 | 消费角色 | 族级候选门（机械判定，按工件信封与载荷字段） |
|---|---|---|---|
| A 结构 | `duplicate_exact.json` | exact 簇清单（`data.clusters` 非空即有候选） | **门控**：`status=ok` 且 `clusters` 数 > 0 才派子代理，否则 A 族跳过 |
| B 测试 | `test_gap.json` | 文件级漏斗（`data.files`）+ 符号级明细（`data.gap_symbols`） | **门控**：任一文件 `zero_touch=true` 或 `gap_symbols` 非空才派，否则 B 族跳过 |
| C 文档知识 | `symbols.json` | 断链比对锚（`data.symbols`；判据允许子代理直接读代理上下文文档原文，此表只列工件） | **始终派**（无确定性门可机械判定；子代理按判据自行判定无候选时回传空清单） |
| D 依赖环境 | `probe.json`、`static_signals.json` | probe 定位面（`data.commands`）+ 构建定义/锁文件/CI/测试可发现性 4 信号的取值与证据（`data.signals["buildability.*"]`） | **门控**：`probe.status=ok` 且 `commands` 非空（有命令声明面），或 `static_signals` 的 4 个 buildability 信号中任一 `value=1.0`（有构建定义/锁文件/CI/测试命令可发现——存在可读的配置源），才派；两者皆空即无配置声明面，D 族跳过 |
| E 进程 | `big_file.json`、`probe.json`、`symbols.json`、`test_gap.json` | 体量五元组与候选线（`data.candidates`、`data.files`）+ probe 证据链（E1–E4）+ 契约痕迹锚（symbols + test-gap 的符号/触达面） | **门控**：`big_file.status=ok` 且 `candidates` 非空，或 `probe.status=ok`（E1 全缺失仍需评估——定位面空仓本身就是 E1 信号），才派；两者皆否则 E 族跳过 |
| G 架构形状 | `symbols.json` | module-graph 底座（由 symbols 派生；模块清单/公开私有符号数） | **门控**：`symbols.status=ok` 且 `data.symbols` 非空（非空符号面）才派，否则 G 族跳过 |

门控不匹配任何族的工件（如 hotspot.json）由渲染器与单写手直接消费，不驱动派发。

**无候选的族不派子代理**——「无候选不调 LM」是管线的预算不变量：LLM 调用只发生在有确定性候选或无机械门的族上。门控判定本身是机械的（读工件信封与载荷字段），不做任何语义判断；候选是否真为债归第 2 段判据。

## 第 2 段：分族子代理

一族一子代理（大候选集分批时一族多代理，见第 1 段），**并行派发**，各自隔离：

**输入（每族子代理只载这两样）**：

1. 本族判据文件 `criteria/<族>.md` 全文——完整作业指令；
2. 本族证据包：第 1 段消费表指定的工件切片 + 候选对象源码，**总量 16K 字符预算**（16K 先例 = module_depth 判定协议的源码预算；候选多时超预算降采样，并在 rationale 中声明降采样）。组装预算内优先保全判据文件点名的证据（如 B 族「gap 上卷前的符号级明细」、A 族「簇内各副本」），降采样时优先裁长文件全文、保全判定必需的行锚。

**子代理提示模板**（五要素逐项填入，不留解释空间）：

```
你是 CogniCode 债扫描的 <族> 族分族子代理。

任务：按判据文件对本族候选逐个判定，产出本族债项清单。

指令（全部读取，判据问题以判据文件为权威）：
1. <判据文件路径>（本族判据，全文）
2. 证据包（16K 预算内的本族工件切片与候选源码）：见下方折叠区

规则：
- 证据等级语言：确证 = 可复现的静态实锤；风险 = 静态反模式命中 / LLM 推断，
  未动态验证。风险项必须标置信度，不得伪装确证。
- 只报告符合判据文件的债项；无候选时回传空 items 数组。
- 严重度带沿本族 rubric 主轴**提议**（high/medium/low），不终裁。
- 不臆造证据包之外的位置与行号；证据引用必须能在源码中复核。

输出格式：最终消息**只包含一个 JSON 对象**（可含 ```json 围栏），不写其他文字：
{"items": [{
  "slug": "<类型 slug，判据文件口径>",
  "location": "<位置锚原始串，三形态见主会话回传校验说明>",
  "severity_band_proposal": "high" | "medium" | "low",
  "evidence_class": "confirmed" | "risk",
  "confidence": "high" | "medium" | "low",
  "rationale": "<为什么是债：失败模式 + 判据依据>",
  "evidence": "<可复核证据引用（文件:行 + 原文/事实）>",
  "fix_suggestion": "<方向性修复建议，不给补丁>"
}]}
```

**规则**：

- **单 JSON 回传**：子代理的最终消息即回传载体，不落盘中间态。JSON schema 与校验/重试协议见下文「子代理 JSON 校验与重试」。
- **置信度三档**（high/medium/low）必填；`evidence_class` 按判据文件的本族口径（B 族「确证信号 vs 风险信号」等）。
- **严重度带只提议不终裁**：子代理沿本族 rubric 主轴提议 `severity_band_proposal`，带终裁权在第 3 段单写手。
- E 族 monolith-file 的修改局部性判定：沿用 module_depth 判定协议（收集 → 单 JSON prompt → 重试 → 非法丢弃；判定不确定性是特性，不要求重跑稳定）。
- 子代理不做跨族判断（如 A 族不因「doc-rot 同病」越界报 C 族类型）；跨族合并是单写手的职责。

### 子代理 JSON 校验与重试

样例实战实测子代理回传会**字段漂移/缺失**（丢 `severity_band_proposal`、字段名手滑）。主会话对每份回传执行机械校验，不假设回传完整：

1. **剥壳**：容忍 ```json 围栏与前后杂文字——截取首个 `{` 到末个 `}` 之间解析；解析失败视为非法。
2. **校验**（逐项机械执行，不带语义判断）：
   - 顶层含 `items` 数组（空数组合法 = 无候选）；
   - 每项含全部 8 个字段：`slug`（非空字符串，判据文件收录 slug）、`location`（非空字符串）、`severity_band_proposal` ∈ {high, medium, low}、`evidence_class` ∈ {confirmed, risk}、`confidence` ∈ {high, medium, low}、`rationale`（非空）、`evidence`（非空）、`fix_suggestion`（非空）。
   - 项级错则记录该 JSON 项索引，整项重试（不重试整份回传）。
3. **重试**：校验失败时向**同一子代理**回发错误描述 + 缺失/非法字段清单 + 「重新输出修正后的完整 JSON」指令；每项至多重试 2 次，仍非法则**丢弃该项并在报告备注**（不炸管线；丢弃协议沿 module_depth 先例）。
4. 主会话不做「帮子代理补字段」的代笔——缺字段项要么重试要么丢弃，不静默修复。

## 第 3 段：主会话单写手

单写手是**唯一**写 `debt.json` 的角色（分族子代理只回传，不写文件；格式纪律与 diff 稳定性只有单写手能保证）。单写手直接产出**最终 JSON 文档本身**：以第 3.5 节清单 schema 为模板，逐条填入各族通过校验的 items，边填边执行去重、定档与排序，不引入中间散文态。

### 3.1 跨族去重

样例实战：A 族（duplicate-code 视角）与 C 族（agent-doc-missing 视角）对同一「支持矩阵三份漂移」各自立案是**设计内行为**——子代理不互见，单写手合并：

- **同根不同载体独立成簇**：同一病根在两类载体上各自成债（文档矩阵漂移 vs 工作流重述分叉 = 两个独立债项），不合并。
- **同实例多 slug 并挂**：同一实例同时符合多类型判据（如同一模块 test-gap + implicit-contract 并挂）= **一个债项、slugs 数组多挂**，rationale 合并两侧视角。判据文件明示可并挂的组合（B 族三态 × E 族 fidelity、test-shape × implicit-contract 等）按其执行。
- **同簇并入**：同一重复簇内的子问题（如 fork 配置句式随矩阵收敛自动消解）并入主债项的 fix_suggestion，不独立立案。
- 去重只发生在单写手层；子代理回传一律保留原样进校验。

### 3.2 严重度带终裁与证据等级一致性

- 子代理的 `severity_band_proposal` 只是输入；单写手按 CONTEXT.md 严重度带纪律终裁（#66 图例裁决：严重度 = 违反后果类型，结合证据等级与热点），可上调/下调，不必与提议一致。
- `evidence_class` 与 `confidence` 字段全清单一致（confirmed/risk 二值、三档置信度）；渲染器报告语言遵循证据等级词汇——**确证 vs 风险**，风险项不得在报告层升格为确证表述。

### 3.3 排序稳定性（机械执行，无裁量项）

`debt.json` 的 `items` 数组排序全序定死，供渲染与 diff：

1. 严重度带降序（high → medium → low）；
2. 带内 slug 字母序（多 slug 并挂项取 slugs 数组字母序最小者参与排序）；
3. 前两者并列时位置锚（`location`）字母序。

排序即 `(band 序, slugs 最小 slug, location)` 三元组全序比较，逐项机械执行，无第三种裁量。

### 3.4 ID 生成

每条债项的 `id`（销账主键）由**脚本层规则生成**（LLM 只提供 `location` 原始串，不生成 ID——LLM 输出不要求跨次稳定，稳定层必须钉在确定性规则上）：

- **符号锚**（代码符号级）：`<slug>@<file>::<symbol>`，如 `monolith-file@Sources/App/AppModel.swift::AppModel`；
- **文档行区间锚**（文档债）：`<slug>@<doc 路径>::<section>`，如 `doc-rot@AGENTS.md::worktree-links`——section 短 slug 由单写手从该债项证据引用的文档行内容提炼，**不含行号**（行号随编辑漂移，进展示字段不进主键）；
- **多文件簇锚**（重复簇）：`<slug>@<簇锚>::<簇短 slug>`，簇锚取工件簇锚原样（exact 档 = `md5:<前 12 位>`，见 duplicate_exact.json 的 `clusters[].anchor`；外置 near 工具的簇锚按 ARTIFACTS.md 集成缝约定并轨），如 `duplicate-code@md5:3112f2776b27::logos-v7`；
- 多 slug 并挂项：`id` 取**字母序最小的 slug** 为前缀，其余 slug 只进 `slugs` 数组；
- 销账匹配口径：`id` 全串相等（slug + 位置锚 + 簇锚三段都稳定）；同根不同载体的两个债项因锚不同天然不同 ID，符合 3.1 的独立成簇裁决。

**ID 锚点三形态的地位**：它已从展示格式纪律**升级为销账匹配的主键构成依据**（#66/#67 决议）——主键必须由确定性段（file / symbol / md5 簇锚）构成，LLM 语义段（section/簇短 slug）不含行号与自增序号，编辑漂移不破坏匹配。

> **字段集占位**：终版 JSON 字段集（含 ID 具体生成方式的最终校准）挂 [地图 #63](https://github.com/asiazhang/cognicode/issues/63) 雾区，本节以雾区已裁方向（脚本生成 ID、三形态锚）为准；雾区裁点落地时以裁点为准修订本节。

### 3.5 `debt.json` 清单 schema（v1 草案，字段集挂雾区待终裁）

```jsonc
{
  "schema": "debt-scan/debt@1",          // 清单形状版本
  "repo": "<被扫仓库根绝对路径>",
  "base_commit": "<扫描基准 commit>",
  "scanned_at": "<ISO 8601 UTC>",        // 扫描时间，不参与 diff
  "families_skipped": ["D", "G"],        // 门控跳过或工件 failed 的族 + 原因
  "items": [
    {
      "id": "doc-rot@AGENTS.md::worktree-links",   // §3.4 三形态主键
      "slug": "doc-rot",                            // 主 slug（= id 前缀）
      "slugs": ["doc-rot"],                         // 全部并挂 slug（多挂时 >1）
      "location": "AGENTS.md:46,51,61",             // 人类可读位置（含行号，仅展示）
      "severity_band": "high",                      // 单写手终裁（高/中/低）
      "evidence_class": "confirmed",                // confirmed | risk（确证 | 风险）
      "confidence": "high",                         // high | medium | low
      "rationale": "<为什么是债：失败模式 + 判据依据>",
      "evidence": "<可复核证据引用（文件:行 + 原文/事实）>",
      "fix_suggestion": "<方向性修复建议，不给补丁>",
      "fix_cost_band": "high",                      // 修复成本档（R2 图例裁决：动作类型学）
      "hotspot_90d": 34                             // 90 天改动次数（hotspot.json 口径，无数据 null）
    }
  ]
}
```

**清单级校验**（子代理回传校验协议的复用，机械执行）：

- 顶层字段齐全；`items` 按 §3.3 全序排列（重排 = 单写手机械动作）；
- 每项含全部 13 个字段；`id` 与 `slug`/`location` 按 §3.4 规则逐条可复算（脚本可校验：`id` 前缀 = `slugs` 字母序最小者；簇锚项的簇锚存在于 `duplicate_exact.json` 的 clusters）；
- `severity_band` ∈ {high, medium, low}、`evidence_class` ∈ {confirmed, risk}、`confidence` ∈ {high, medium, low}、`fix_cost_band` ∈ {very-low, low, medium, high}；
- id 唯一（重复即去重遗漏，回到 §3.1 重做）。

校验失败 → 单写手修复后重验（清单层无「重试他人」——写手自查）。

## 渲染器调用协议

脚本确定性执行，**零 LLM 参与**（渲染器是确定性层，同 JSON 两次渲染逐字节一致）：

```bash
uv run cognicode-debt/scripts/render_report.py <被扫仓库根目录>
```

- 输入：`.cognicode/debt-scan/debt.json`（单写手产物）；输出：HTML 债报告。
- **HTML 落盘临时目录**（系统临时目录下随机命名子目录），打印即开即看的路径，**不落被扫仓库**（#66 决议：JSON 进仓库供 diff 与团队浏览，HTML 走临时目录）。
- 报告形态遵循 #66 评审决议：证据呈现器（无「推荐先修」）；严重度带分组（高带展开、中/低带默认折叠）；SVG 散点全景（严重度 × 近 90 天改动频率）；类型分区（本场景重点类型置顶展开、其余默认折叠）；导言默认折叠；严重度/成本档判据写进图例；热点数据取 `hotspot.json` 口径。
- 渲染器已随 #61 落地（`render_report.py`）：报告形态即本段决议——高带展开、中/低带 `<details>` 默认折叠、SVG 散点、重点类型置顶、判据图例外化；渲染确定性有随行测试（`tests/test_render_report.py`，同 JSON 两次渲染逐字节一致）。

## 销账与重跑

- **JSON 清单落仓库**（销账与审计基准）；**无状态字段**——`debt.json` 不带 open/fixed 状态，git 历史即审计轨迹。
- **重跑即销账**：修复后重跑扫描，`debt.json` 中对应条目按主键消失；「同一笔债」按 §3.4 脚本确定性 ID 匹配，不靠语义相似度。
- **diff 纪律**：diff 以 JSON 为基准、在 **ID 集合与确定性字段**（id / slug(s) / location / severity_band / evidence_class / hotspot_90d）上做——LLM 语义字段（rationale / evidence / fix_suggestion 的行文）允许跨次差异；渲染与比对脚本消费排序纪律（§3.3）假设成立的前提。

## 会话执行检查单

新会话执行一次完整扫描的顺序：

1. 读 [scripts/ARTIFACTS.md](scripts/ARTIFACTS.md)（工件协议）；
2. 第 1 段：跑 `scan.py`，按消费表读工件信封做族门控判定；
3. 第 2 段：逐族派子代理（并行；跳过门控不匹配的族）→ 回传校验与重试；
4. 第 3 段：单写手去重 → 终裁 → 排序 → 生成 ID → 写 `debt.json` → 清单级校验；
5. 渲染器调用协议段：跑 `render_report.py` 出 HTML（临时目录）；
6. 向用户报告：JSON 路径（仓库内）+ HTML 路径（临时目录）+ 门控跳过的族与原因。

修债工作流（修完债后）：定位（按 `id` 的位置锚）→ 修复 → 跑被扫仓库自己的验证回路确证 → 重跑第 1–3 段 + 渲染 → diff 确认销账。
