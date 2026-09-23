# CogniCode

> 仓库级 **AI 技术债**识别与展示工具（转型中）。

AI 编程 agent 正在成为代码的主要作者之一，一种新的债随之积累：**对 AI 不友好的债**——会让下一个 agent 迷路、犯错或返工的仓库状态，比如没人外化的隐式约定、改 A 必须改 B 但代码里看不出来的耦合、跑不起来的验证回路、主动误导人的过时文档。这种债的利息由 agent 支付（多花 token、改错地方、部分重构留下不一致），但既有工具全部以人类维护成本为判据，没有谁测量它。

CogniCode 正在从「AI 原生程度打分工具」转型为这个空档的填补者：**扫描一个仓库，产出按严重度排序的债项清单**——每项标注位置、类型、为什么是债、修复建议，落盘为仓库内 `DEBT.md`，可 diff、可追债的增减。

## 为什么是现在

（调研证据见 [`docs/research/ai-dev-pain-points-synthesis.md`](docs/research/ai-dev-pain-points-synthesis.md)）

- **体量**：AI 已占已提交代码的 42%（Sonar 2026），Google 报告 75% 的新代码由 AI 生成。
- **痛感已被决策层确认**：55% 的工程负责人把「代码库理解」列为头号担忧，且多数承认在 code review 之外没有应对手段（Augment 2026）。
- **既有解法被证伪**：AI 审 AI 的建议拒收率 56%（31,073 条实证）；AGENTS.md 在通用开源库上边际甚至负收益（ETH Zurich）。
- **空档双向印证**：学术界的债分类体系（Li–Avgeriou–Liang、SQALE、CodeScene）全部以人类为利息受损者，无一以 agent 表现为判据；从业者侧的痛点恰好大量落在「会让下一个 agent 迷路」的仓库属性上。

## 方法学

### 债的定义

**对 AI 不友好的债** = 会让下一个 AI agent 在这个仓库里迷路 / 犯错 / 爆炸的仓库状态。判据主体是 agent 的表现，不归因谁写的代码——人类视角的零利息债（如死代码）在这里可能利息很高，反之亦然。

### 判别法则（调研收敛，详见 synthesis 文档）

1. **换主体测试**：把受损方从「人类维护者」换成「下一个 agent」，痛感是否仍然成立且可观测？
2. **产物 vs 判据**：社会债的产物（文档、规范）恰是 agent 导航所依赖的，但其判据（人员分布、知识流失）与 agent 无关——只取产物、不取判据。
3. **产出缺陷 ≠ 仓库债**：AI 生成了带 bug 的代码说明生成质量问题；换更强的模型重跑同一任务，痛感不消失才是仓库债。

### 债分类学（20 类型，7 个工件族）

沿六维度失败模式做类型轴，双层结构：失败模式做判断轴、债类型（slug）做检测与报告单元、工件族做展示标签。完整清单见 [`docs/research/debt-types.md`](docs/research/debt-types.md)。

### 检测分两档

- **确定性发现**：可复现的静态提取与工具集成（tree-sitter 符号分析、重复检测、文档漂移对照），同一仓库永远得出同一结果。
- **LLM 推断发现**：语义级判断（如「仅凭名字能否预测这个符号做什么」），标注置信度。

### 六维度语言

转型不是推翻而是重定位：原有的六维度失败模式语言降级为债识别的信号引擎——

| 维度 | 失败模式 |
|---|---|
| **可解性**（solvability） | 解不出 |
| **变更安全性**（safety） | 解出但炸了别处 |
| **效率**（efficiency） | 解出但昂贵 |
| **可导航性**（navigability） | 找不到该找的代码 |
| **环境可用性**（buildability） | 跑不起验证回路 |
| **可诊断性**（diagnosability） | 定位不了失败 |

### 唯一真值原则

同一知识在仓库中应只存在一份权威版本；存在多份且未声明哪份权威，即构成债形态。这是横贯多个债类型的判断原则（重复代码、文档腐烂、配置漂移、隐式契约）。

## 交付形态（转型目标）

- **载体 = skill 集合**：`SKILL.md` 管 LLM 推断档与报告组织，内嵌确定性分析脚本管可复现提取；skill 仓库本身是分发单元，CLI 降为脚本副产品。
- **报告 = 仓库内 `DEBT.md`**：按严重度排序的债项清单，可 diff、可追债的增减，兼作二次运行对比基准。
- **首发受众**：个人开发者为主（agent 迷路、跨文件失手），团队负责人为辅（review 负担、质量滑坡）——两端痛点不同但指向同一批债项。
- **动态测量**（跑真实 agent 验证债项的实际伤害）为二期实证校验，首发不含。

## 当前状态

转型进行中（v0.2.0-dev）。已完成：债分类学（20 类型）、痛点与空档调研、资产盘点与仓库清理；进行中：skill 集合结构设计（[#42](https://github.com/asiazhang/cognicode/issues/42)）、DEBT.md 样例（[#43](https://github.com/asiazhang/cognicode/issues/43)）、重定位决策文档（[#44](https://github.com/asiazhang/cognicode/issues/44)）。规划与决策索引见 [wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39)。

现存 CLI 为重定位清理后的静态提取壳（`cognicode scan <repo>`，tree-sitter 符号提取 + 静态信号），最终形态待 skill 结构票定夺：

```bash
git clone https://github.com/asiazhang/cognicode.git
cd cognicode
uv sync --extra dev
cognicode scan <repo>          # 静态信号提取（复用线）
```

## 项目结构

```
src/cognicode/
├── symbols.py          # tree-sitter 符号提取（复用线）
├── static_signals.py   # 静态信号提取（复用线）
├── module_depth.py     # 模块深度判定（LLM 归因信号，复用线）
├── probe.py            # 环境探测命令定位（复用线）
├── attribution.py      # 归因管线（复用线）
├── llm.py              # LLM 调用封装
├── report.py           # 报告组织
├── schema.py           # 版本与结构
└── cli.py              # 静态提取壳（待 #42 定夺）
tests/                  # pytest 测试套件
docs/                   # ADR / 调研 / 域文档
cognicode-debt/
├── SKILL.md            # （待建）skill 编排协议
└── criteria/           # 判据：分族子代理作业指令
    ├── A-structural.md … G-architecture-shape.md   # 七族判据（F 并入 E）
    └── rules/          # 17 类型逐规则详解（人类向，含正反例，供讨论）
```

## 文档

- [`CONTEXT.md`](CONTEXT.md) — 领域词汇表（术语的唯一权威定义）
- [`docs/research/debt-types.md`](docs/research/debt-types.md) — 债分类学：20 类型清单
- [`docs/research/debt-candidates.md`](docs/research/debt-candidates.md) — 广义债候选观点集
- [`docs/research/debt-taxonomy.md`](docs/research/debt-taxonomy.md) — 业界技术债既有谱系调研
- [`docs/research/ai-dev-pain-points-synthesis.md`](docs/research/ai-dev-pain-points-synthesis.md) — AI 开发时代痛点全景（双模型交叉验证综合结论）
- [`docs/research/asset-inventory.md`](docs/research/asset-inventory.md) — 既有资产盘点：哪些代码可复用为债检测
- [`cognicode-debt/criteria/`](cognicode-debt/criteria/) — 分族判据：A–G 七族子代理作业指令
- [`cognicode-debt/criteria/rules/`](cognicode-debt/criteria/rules/) — **逐规则详解（含实例）**：17 个债类型每条规则一份文档，正例带 agent 失败形态与预期报告行、反例讲清不报边界，「讨论要点」节留给评审
- [`docs/adr/`](docs/adr/) — 架构决策记录
- [`docs/agents/`](docs/agents/) — agent 工作约定（issue 跟踪、triage、域文档）

## 状态

转型中。决策流程走 [wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39)，issue 跟踪见 [GitHub Issues](https://github.com/asiazhang/cognicode/issues)。

## License

MIT
