# CogniCode

> 仓库级 AI 原生程度评估与打分工具。

CogniCode 用**合成基准任务驱动真实编程 agent 执行**，动态测量一个代码仓库对 AI 的友好程度——不是靠规则打分，而是让 agent 真刀真枪地在仓库上「找代码 / 跑环境 / 查问题 / 改代码」，从执行结果与过程信号中取值。

## 六个维度

「AI 原生程度（AI-native readiness）」由六个概念维度聚合度量，每个维度对应一种独立的失败模式：

| 维度 | 失败模式 |
|---|---|
| **可解性**（solvability） | 解不出 |
| **变更安全性**（safety） | 解出但炸了别处 |
| **效率**（efficiency） | 解出但昂贵 |
| **可导航性**（navigability） | 找不到该找的代码 |
| **环境可用性**（buildability） | 跑不起验证回路 |
| **可诊断性**（diagnosability） | 定位不了失败 |

## 工作原理

### 双测量（dual measurement）

同一维度同时由两条独立链路观测，动静互为校验：

- **动态测量**：让真实编程 agent 在仓库上执行合成基准任务，从执行结果与过程信号取值。
- **静态测量**：不经执行，直接从仓库文件与结构中提取信号。分两档——**产分信号**（进入维度分，全部语言无关、可确定性提取）与**归因信号**（解释失败、驱动建议，如模块深度判定）。

### 任务生成三段式

1. **符号提取**：tree-sitter 从源码提取命名符号（函数/方法/类），语言无关、确定性，产出符号级验收对照（`file::name`）。
2. **LLM 模板合成**：生成三类任务——检索（语义→位置）、定位（症状→根因）、修改/修复（描述→改动），以及零合成的**环境探测**（冷启动跑起构建与测试）。生成配置独立钉死，`--offline` 时降级为确定性模板。
3. **执行式验证过滤**：生成的任务必须过 harness 侧客观判定（位置匹配 / 测试红绿 / 退出码）才保留，无效实例当场砍掉。

### 判卷与聚合

- **判卷权只属于 harness**：F2P（改动前失败、改动后通过）与 P2P（前后都须通过）双闸判定，agent 的自报告只约定交卷格式、不参与判定。
- **结果类别**五类互斥：`success` / `fail_incorrect` / `fail_budget` / `fail_env`，前三类计入统计，`fail_env` 剔除并重跑。
- **采样次数 k 固定**，agent 的随机性由重复采样与区间估计消化，不依赖温度控制。
- **权重敏感性分析**：每次打分随报告输出确定性网格扰动 + Dirichlet 采样，判定总分带宽与排序稳定性。

### 报告

本地 CLI 输出两层：终端打印「总览 → 维度明细 → 建议清单」一屏摘要，全量落盘 `cognicode-report.md`（信号明细、失败任务证据、运行环境快照、敏感性输出）。每条改进建议附**可重测声明**：锚定信号 + 预期方向 + 重跑同一套任务可验证。

跨仓库排序仅作**软横比**参考，不做硬承诺；缺少运行环境快照的分数不可比较。

## 安装

要求 Python ≥ 3.11，推荐 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/asiazhang/cognicode.git
cd cognicode
uv sync --extra dev
```

## 使用

```bash
# 对一个仓库跑完整评估
cognicode scan <repo>

# 确定性链路：LLM 全关（仅静态提取 + 探测）
cognicode scan --offline <repo>

# 从运行目录生成报告
cognicode report <run-id>

# 版本（含 report-schema 版本号）
cognicode --version
```

每次运行的产物落在 `.cognicode/<run-id>/`（static.json、probe.json、tasks.json、verdicts.json、aggregate.json、snapshot.json、`cognicode-report.md` 等）。

端到端冒烟：

```bash
uv run python scripts/smoke_e2e.py --offline        # 确定性链路
uv run python scripts/smoke_e2e.py --live           # 开 LLM（归因兜底 + 模块深度）
uv run python scripts/smoke_e2e.py --offline --tasks 2   # 减量验证
```

## 项目结构

```
src/cognicode/
├── symbols.py          # 三段式第一段：tree-sitter 符号提取
├── generation.py       # 第二段：LLM / 确定性模板合成任务
├── verify.py           # 第三段：执行式验证过滤
├── pipeline.py         # 三段式整合
├── probe.py            # 环境探测命令定位与成功判定
├── harness.py          # fresh worktree + 探测/任务执行编排
├── executor.py         # Executor 协议 + RunResult/TaskStats
├── pi_executor.py      # pi headless RPC 驱动（唯一 executor 实现）
├── verdict.py          # 判卷（F2P/P2P、位置匹配、五类 outcome）
├── static_signals.py   # 静态产分/归因信号提取
├── aggregate.py        # 六维聚合
├── attribution.py      # 归因管线（确定性优先、LLM 兜底）
├── module_depth.py     # 模块深度（参考性归因信号，不进产分）
├── sensitivity.py      # 权重敏感性分析
├── report.py           # 终端摘要 + cognicode-report.md
├── schema.py           # report-schema 版本与报告结构
└── cli.py              # 薄 CLI 壳
tests/                  # pytest 测试套件
docs/                   # harness / 任务生成 / 校准 / ADR / 前置研究
prototype/              # pi 扩展原型（findings 与 RPC 驱动）
scripts/smoke_e2e.py    # 端到端冒烟脚本
```

## 文档

- [`CONTEXT.md`](CONTEXT.md) — 领域词汇表与评分模型（术语的唯一权威定义）
- [`docs/adr/`](docs/adr/) — 架构决策记录（静态信号进分、判卷权、executor 选型等）
- [`docs/harness.md`](docs/harness.md) — 动态测量执行层与测量隔离
- [`docs/task-generation.md`](docs/task-generation.md) — 三段式任务生成管线
- [`docs/attribution.md`](docs/attribution.md) — 归因管线
- [`docs/calibration/`](docs/calibration/) — 校准与语料方向预期

## 状态

早期阶段（v0.1.0），MVP 闭环已在试点语料上冒烟验证。issue 跟踪见 [GitHub Issues](https://github.com/asiazhang/cognicode/issues)。

## License

MIT
