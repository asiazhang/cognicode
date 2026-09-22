# harness 执行层（#19）

> 票：[实现 harness 与 pi executor](https://github.com/asiazhang/cognicode/issues/19)
> 前置研究：`docs/research/pi-schema.md`（#27，pi 0.84.3 headless schema 实测）
> 分支：`prototype/pi-schema`

## 职责

harness = 动态测量的执行层：环境探测 + 合成任务执行 + 产物收 diff，
经 `executor` 接口驱动 pi（唯一实现，ADR-0005 替换 CodeBuddy）。

本层**只做执行与采集**，不做判卷（五类 outcome 归 #20/#21）、不做任务生成
（归 #20）、不做聚合（归 #21）。判卷的客观判定（位置匹配/测试红绿/退出码）
由上层消费本层产出的 `RunResult` 与轨迹。

## 模块

| 模块 | 职责 |
|---|---|
| `executor.py` | `Executor` 协议 + `RunResult`/`TaskStats` 数据结构 |
| `pi_executor.py` | `PiExecutor`：pi 0.84.3 RPC 驱动 + 采集自算 + 测量隔离清单 |
| `ext/cognicode-harness-ext.ts` | 测量隔离扩展（max-turns 早停 / 只读门 / submit_result） |
| `probe.py` | 环境探测命令定位 + 成功判定（纯函数） |
| `harness.py` | `WorktreeManager`（fresh worktree）+ `ProbeRunner` + `run_task`/`run_samples` 编排 |

## 采集口径（pi-schema.md §7 归一化）

pi 无 CodeBuddy 的 `result.subtype/duration_ms/num_turns`，全部自算：

| 指标 | 采集方式 |
|---|---|
| 轮次 | `turn_start` 事件计数（= assistantMessages = 模型调用数） |
| 时长 | 首 `message_start` → `agent_settled` 时间戳差（ms） |
| token | `get_session_stats.tokens`（会话级聚合：input/output/cacheRead/cacheWrite/total） |
| 结局 | 是否等到 `agent_settled`（终局信号）+ 进程 exit code |
| 退出码 | 0 正常 / 1 参数错误 / 124 外层 timeout 杀 |
| 工具调用 | 轨迹里 `tool_execution_start/end`（本层留 0，上层按轨迹统计） |

**执行成功（`RunResult.ok`）= exit 0 且等到 `agent_settled`**。
注意：这不等于任务判卷通过——成功率由上层验收测试判定（ADR-0002）。

## 测量隔离固定清单（pi-schema.md §6 / ADR-0003）

```
pi --mode rpc --model tencent-copilot/deepseek-v4-flash-ioa \
   --no-session --no-approve -nc --no-skills --no-prompt-templates --no-themes \
   -e <provider-ext> -e <harness-ext>
```

- 不显式 `--provider`（#28 §9 坑：触发模型目录刷新时序 bug）
- 显式 `-e` 加载 provider 扩展（headless 不自动加载 settings packages）
- 首次跑前 `pi --list-models` 预热（provider 目录刷新）
- 5 个已实测坑内置规避（pi-schema.md §9）

## 测量隔离扩展（ext/cognicode-harness-ext.ts）

经**环境变量**传参（RPC 下 `getFlag` 读不到 CLI flag，实测 pi 0.84.3）：

| env | 默认 | 作用 |
|---|---|---|
| `HARNESS_MAX_TURNS` | 50 | 轮次上限（#6 锁定）；turn_start 计数达上限后 tool_call block+terminate 早停 |
| `HARNESS_READ_ONLY` | 0 | 只读门：禁 write/edit/patch + bash 写命令（检索/定位类任务） |
| `HARNESS_NO_SUBMIT` | 0 | 不注册 submit_result 工具 |

**max-turns 语义**：轮次 = LLM 调用轮（turn_start 计数，含工具轮与总结轮）。
达上限后：模型再调工具 → block+terminate 早停；模型纯文本总结收尾 → 正常结束
（总结轮是最后动作，不拦）。验证：max-turns=1 时第 2 次工具调用被拦
（`harness: max-turns(1) 已超限`）。

**submit_result**（ADR-0002 约定交卷格式，不进判卷）：结构化收尾工具，
`terminate: true` 早停。检索/定位类任务用它交卷（verdict + evidence）。

## 环境探测（probe.py + ProbeRunner）

- `locate_probe_commands(repo)`：定位仓库声明的构建/测试命令
  （composer.json / package.json / pyproject.toml / Makefile / 测试目录后备），
  纯确定性，无执行。
- `ProbeRunner.run(repo)`：每条命令在 fresh worktree 里让 pi agent 执行，
  记录 exit code 与耗时（探测超时 30 分钟，#6）。
- `probe_success(exit_codes)`：**「成功」= 至少一条构建 exit 0 且至少一条
  测试 exit 0**（地图 Notes 锁定）。无构建/无测试 → 失败（降级路径）。

nbnbk 实测：`test.phpunit: 0`（phpunit 真跑成功），但无构建命令
（composer.json 无 scripts.build）→ 探测失败 → `degrade: true`。

## 任务执行（harness.py run_task / run_samples）

`run_task` 执行单次任务并收集持久产物：
1. `WorktreeManager.worktree()`：fresh git worktree（clone 被测仓库，独立隔离）
2. `executor.run(prompt, worktree, timeout_s, trace_file)`：pi RPC 执行
   （外层 timeout 包裹，任务超时 15 分钟，#6）
3. harness 侧收集已跟踪和未跟踪改动的 diff
4. 全量事件轨迹落盘；executor 崩溃也写入 `executor_crash` 轨迹

`run_samples` 是固定采样次数 `k` 的任务级编排。每次采样使用新的 worktree，
并使用 `task-id__sample-N` 作为文件键，因此同一任务的 trace、diff 和结果可以
按 `task_id` + `sample_id` 定位。运行目录保留审计产物，worktree 在 `run_task`
返回后清理：

```
.cognicode/<run-id>/
├── traces/<task-id>__sample-N.jsonl
├── diffs/<task-id>__sample-N.diff
└── results/<task-id>__sample-N.json
```

`results/*.json` 保存 `ok`、退出码、结局说明、统计和 task/sample 标识。
超时（通常 exit 124）和 executor 崩溃是任务结果，不会中止其余采样；worktree
创建失败仍返回 `None`，作为 `fail_env` 信号。

## CLI

`cognicode scan <repo>`：静态提取（#18）+ 环境探测（#19）+
探测成功时演示任务（固定 prompt，验证「探测 + 单任务执行收 diff」链路）。
`scan --offline` 同链路（探测仍走 pi；LLM 类模块未开）。

产物：`.cognicode/<run-id>/{static.json, probe.json, traces/*.jsonl, diffs/*.diff}`。

## 已知边界

- 演示任务用固定 prompt，任务生成归 #20。
- 判卷（F2P/P2P、位置匹配）归 #20/#21。
- `tool_call` 钩子在 RPC 模式实测生效；`getFlag` 在 RPC 模式读不到 CLI flag
  （已改用 env）。
- 纯文本总结轮不计超限；「纯文本跑飞」（无限总结不收敛）由外层 timeout 兜底。
