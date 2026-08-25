# 核对 pi 0.84.3 headless 输出 schema（实测 + 文档核对）

> 票：#27（wayfinder:research，评估 pi 替代 CodeBuddy 作为 harness 执行者）。实测日期：2026-08-25。测试版本：`pi 0.84.3`，模型 `tencent-copilot/deepseek-v4-flash-ioa`（本机认证 provider `tencent-copilot`，与 CodeBuddy 同源）。
>
> 本表对标 #25（docs/research/codebuddy-schema.md）的格式，补齐 pi 的 headless CLI（`-p` / `--mode json` / `--mode rpc`）输出 schema 事实基础。**事件字段与样例值来自 rpc.md/json.md 一手文档 + 本机真实 RPC 事件流**。每条结论可直接被 harness 的 pi executor 消费。原始证据见文末「复现命令」。

---

## TL;DR（harness 必读）

1. **三种输出形态是三套不同的消费模型**：
   - `-p`（print，text）：stdout 是纯文本回复，无统计、无事件。token/工具调用/轮次全拿不到，只适合人看。
   - `--mode json`：stdout 是 **JSONL 事件流**（首行 `session` 头 + `agent_start`/`turn_*`/`message_*`/`tool_execution_*`/`agent_end`/`agent_settled` 事件）。**事件内嵌完整 usage**（每轮 `message_end`/`message_update` 带 `usage`），但**没有会话级聚合统计**——要总数需自己累加，或用 RPC。
   - `--mode rpc`：stdin/stdout 长驻 JSON 协议。**命令 + 事件**双通道，`get_session_stats` 提供**会话级 token/cost/toolCalls/contextUsage 聚合**。这是 harness 首选形态。
2. **token 统计是 pi 相对 CodeBuddy 的重大改进**：
   - CodeBuddy 的 `total_cost_usd` 恒为 0（#25 §TL;DR#2，成本不可用）。
   - pi 的 `cost` 也是 0（本机 copilot 账号，模型 cost 表全 0），**但 pi 的 token 字段完整且可靠**：事件级 `usage.{input,output,cacheRead,cacheWrite,reasoning,totalTokens}`，会话级 `get_session_stats.tokens`。
   - 与 CodeBuddy 另一差异：**pi 没有 `modelUsage`/`_meta` 按模型聚合与上下文类别拆分**；pi 用 `contextUsage`（tokens/contextWindow/percent）表达上下文占用。
3. **退出码三态**（实测）：`0` 正常（含任务自认失败——pi 无任务失败专用码）、`1` 参数错误（stderr 报错，stdout 空）、`124` 外层 timeout 杀死（stdout 0 字节）。**与 CodeBuddy 完全一致**（#25 §3），无「任务失败」码，成功率必须 harness 判定。
4. **事件流以 `agent_settled` 为终局信号**：`agent_end` 后可能还有 retry/compaction/排队 follow-up，**`agent_settled` 才表示彻底结束**（文档明示）。harness 采集应等 `agent_settled`。
5. **配置隔离 flag 全部实测生效**：`--no-context-files`（AGENTS.md/CLAUDE.md 加载，实测对照组含注入标记、加 flag 后消失）、`--tools`/`--exclude-tools` 白/黑名单（实测只读集只有 `read` 被调用）、`--no-session`（不落盘）、`--no-skills`/`--no-extensions`/`--no-prompt-templates`/`--no-themes`（禁发现，显式 `-e`/`--skill` 仍加载）。pi **没有** CodeBuddy 的 `--setting-sources`，但 `--no-*` 组合 + `--no-approve`（忽略项目本地资源）可达到同等隔离。
6. **RPC 模式下扩展 UI 走子协议**：`ctx.ui.select/confirm/input/editor` 转成 stdout 的 `extension_ui_request` + stdin 的 `extension_ui_response`。harness 若加载会弹对话框的扩展，必须实现该子协议，否则对话框挂起（有 timeout 才自动化解）。

---

## 1. 三种输出形态

| 形态 | 启动方式 | stdout | 统计 | 适用 |
|---|---|---|---|---|
| print/text | `pi -p "msg"` | 纯文本回复 | 无 | 人工单发 |
| JSON 事件流 | `pi --mode json "msg"` | JSONL（首行 `session` 头 + 事件） | 事件级 `usage`（需自行累加） | 简单采集 |
| RPC | `pi --mode rpc`（stdin 命令 + stdout 事件） | JSONL 事件 + `response` 混合流 | `get_session_stats` 会话级聚合 | **harness 首选** |

> 注意：`--mode json` 与 `--mode rpc` 的 `-p` 语义不同——`pi -p --mode json "msg"` 是「单发 json 事件流，跑完退出」；`pi --mode rpc` 无 `-p` 是「长驻，等 stdin 命令」。RPC 下也有单发等价物（发 `prompt` 后等 `agent_settled` 再收 `get_session_stats`）。

### 1.1 `--mode json` 事件序列（实测，简单回复）

```
{"type":"session","version":3,"id":"...","timestamp":"...","cwd":"/tmp/pi-probe"}   ← 首行 session 头
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"user",...}}
{"type":"message_end","message":{"role":"user",...}}
{"type":"message_start","message":{"role":"assistant","content":[],"usage":{...0...},"stopReason":"pending",...}}
{"type":"message_update","usage":{...},"assistantMessageEvent":{"type":"thinking_start","contentIndex":0}}
{"type":"message_update",...,"assistantMessageEvent":{"type":"text_delta","contentIndex":1,"delta":"Hello"}}
{"type":"message_end","message":{"role":"assistant","content":[...],"usage":{"input":9085,...},"stopReason":"stop"}}
{"type":"turn_end","message":{...},"toolResults":[]}
{"type":"agent_end","messages":[...],"willRetry":false}
{"type":"agent_settled"}
```

### 1.2 `--mode rpc` 事件序列（实测，带工具调用读文件）

```
response command=prompt success=true          ← prompt 受理
agent_start
turn_start
message_start (user) / message_end (user)
message_start (assistant)
message_update (thinking_*/text_*/toolcall_* delta)
tool_execution_start  {"toolCallId":"call_00_...","toolName":"read","args":{"path":"/tmp/pi-probe/sample.txt"}}
tool_execution_end    {"toolCallId":"call_00_...","toolName":"read","result":{"content":[{"type":"text","text":"hello world\nsecond line\n"}]},"isError":false}
message_end (assistant, usage 含 cacheRead)
turn_end               {"message":{...},"toolResults":[{...}]}
agent_end              {"messages":[...],"willRetry":false}
agent_settled
response command=get_session_stats success=true data={...}   ← harness 收尾拉统计
```

---

## 2. 事件类型全集与字段结构

文档（rpc.md「Events」+ json.md）列出的完整事件类型：

| 事件 | 字段 | 说明 |
|---|---|---|
| `session`（仅 json 模式首行） | `type, version, id, timestamp, cwd` | 会话头，json 模式独有 |
| `agent_start` | 无 | agent 开始处理 prompt |
| `agent_end` | `messages: AgentMessage[], willRetry: bool` | 一次底层 agent 跑完；`willRetry=true` 表示随后自动重试 |
| `agent_settled` | 无 | **全会话落定**：无 retry/compaction-retry/排队 follow-up 再继续。终局信号 |
| `turn_start` | 无 | 新 turn（一次 LLM 回复 + 工具调用） |
| `turn_end` | `message: AgentMessage, toolResults: ToolResultMessage[]` | turn 完成 |
| `message_start` / `message_end` | `message: AgentMessage` | user/assistant/toolResult 消息生命周期 |
| `message_update` | `usage: Usage, assistantMessageEvent: {...delta}` | 流式 delta（见 §2.1）；**不含累计 message 快照**（json/rpc 均如此） |
| `bash_execution_update` | `id, delta` | RPC `bash` 命令输出块（非 LLM 工具调用） |
| `tool_execution_start` | `toolCallId, toolName, args` | 工具开始执行 |
| `tool_execution_update` | `toolCallId, toolName, args, partialResult` | 流式部分结果（累计，非 delta） |
| `tool_execution_end` | `toolCallId, toolName, result, isError: bool` | 工具完成 |
| `queue_update` | `steering: string[], followUp: string[]` | 排队消息变化 |
| `compaction_start` | `reason: "manual"\|"threshold"\|"overflow"` | 压缩开始（手动/自动） |
| `compaction_end` | `reason, result, aborted, willRetry` | `result` 含 `summary/firstKeptEntryId/tokensBefore/estimatedTokensAfter/usage/details` |
| `auto_retry_start` | `attempt, maxAttempts, delayMs, errorMessage` | 瞬时错误自动重试开始 |
| `auto_retry_end` | `success, attempt, finalError?` | 重试结束 |
| `summarization_retry_scheduled` | `attempt, maxAttempts, delayMs, errorMessage` | 压缩/分支摘要重试调度 |
| `summarization_retry_attempt_start` | `source: "compaction"\|"branchSummary", reason?` | 重试请求开始 |
| `summarization_retry_finished` | 无 | 重试循环完成 |
| `extension_error` | `extensionPath, event, error` | 扩展抛错（agent 继续） |

> 对照 CodeBuddy（#25）：CodeBuddy stream-json 是 `system/init` + `assistant`/`user`/`result` 消息模型；pi 是**显式事件模型**——没有 `result` 汇总事件（统计走 RPC `get_session_stats`），没有 `system/init`（运行快照靠 `get_state` + 首行 session 头）。

### 2.1 `message_update` 的 `assistantMessageEvent` delta 类型

| 类型 | 字段 | 说明 |
|---|---|---|
| `text_start` / `text_delta` / `text_end` | `contentIndex, delta`/`content` | 文本块流式 |
| `thinking_start` / `thinking_delta` / `thinking_end` | `contentIndex, delta`/`content` | 推理块流式 |
| `toolcall_start` | `contentIndex, id, toolName` | 工具调用开始（含 id） |
| `toolcall_delta` | `contentIndex, delta` | 工具参数 JSON 流式块（需缓冲拼装） |
| `toolcall_end` | `contentIndex, toolCall` | 完整 toolCall 对象 |

> 文档明示：`message_update` **故意省略**累计 `message` 字段；需要实时 partial 文本必须按 `contentIndex` 自行拼装。`message_end.message` 才是权威快照。`toolcall_start` 带 `id`+`toolName`（常量大小），`toolcall_end` 带完整 `toolCall`。

### 2.2 `message_update` 顶层 `usage`（实测值）

```json
{"input": 9085, "output": 15, "cacheRead": 0, "cacheWrite": 0, "reasoning": 13, "totalTokens": 9100,
 "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}}
```

- 流式期间 `usage` 可能全 0（provider 完成时才报）；`thinking_end`/`text_end` 时变为真实累计值。
- `reasoning` 字段（推理 token）是 pi 独有，CodeBuddy 无对应。

---

## 3. 统计字段（`get_session_stats` RPC 命令）

实测完整返回（一次「读文件并回复」任务后）：

```json
{
  "type": "response",
  "command": "get_session_stats",
  "success": true,
  "data": {
    "sessionId": "01a0380e-6dee-7165-b91c-72184c614eb8",
    "userMessages": 1,
    "assistantMessages": 1,
    "toolCalls": 0,
    "toolResults": 0,
    "totalMessages": 2,
    "tokens": {"input": 9085, "output": 15, "cacheRead": 0, "cacheWrite": 0, "total": 9100},
    "cost": 0,
    "contextUsage": {"tokens": 9100, "contextWindow": 1000000, "percent": 0.91}
  }
}
```

逐字段：

| 字段 | 类型 | 含义 / 样例 | 采集建议 |
|---|---|---|---|
| `sessionId` | string | 会话 id | 会话追踪 |
| `userMessages` / `assistantMessages` | number | 用户/助手消息条数（1/1） | 轮次粗信号 |
| `toolCalls` / `toolResults` | number | 工具调用/结果数（0/0——本任务只读文件但按「消息」计数需注意：`toolCalls` 统计的是**工具消息**数，工具调用本身走事件） | — |
| `totalMessages` | number | 消息总数（2） | — |
| `tokens.input` | number | 输入 token | `input_tokens` |
| `tokens.output` | number | 输出 token | `output_tokens` |
| `tokens.cacheRead` | number | 缓存命中 token | `cached_tokens`（读） |
| `tokens.cacheWrite` | number | 缓存写入 token | `cached_tokens`（写） |
| `tokens.total` | number | input+output+cacheRead+cacheWrite（9100） | `total_tokens` |
| `cost` | number | **本机恒 0**（cost 表全 0） | 不可用，忽略（同 CodeBuddy #25） |
| `contextUsage.tokens` | number | 当前上下文占用估计（9100） | 上下文占用 |
| `contextUsage.contextWindow` | number | 模型上下文窗口（1000000） | 模型上限 |
| `contextUsage.percent` | number | 占用百分比（0.91） | 上下文膨胀信号 |

> 文档要点：`tokens`/`cost` 含助手消息、工具上报的嵌套 usage、压缩/分支摘要生成——**全会话聚合**。`contextUsage` 在无模型/无窗口时省略；压缩后 `tokens`/`percent` 为 null 直到新的 assistant 响应产生有效 usage。
>
> 对照 CodeBuddy（#25 §1.1）：pi 的 `tokens.cacheRead/cacheWrite` 对应 CodeBuddy `usage.cache_read_input_tokens/cache_creation_input_tokens`；pi 无 `duration_ms`/`num_turns`/`total_cost_usd`/`_meta.usageByCategory`。**pi 的轮次/时长需 harness 自己从事件算**（`turn_start` 计数 = 轮次，`message_end` 时间戳差 = 时长）；CodeBuddy 这些在 `result` 里现成。

---

## 4. 工具调用事件（字段级，实测）

### 4.1 `tool_execution_start / update / end`

```json
{"type": "tool_execution_start", "toolCallId": "call_00_ISWWqPHcZDYKlNjOODV15183", "toolName": "read",
 "args": {"path": "/tmp/pi-probe/sample.txt"}}
{"type": "tool_execution_end", "toolCallId": "call_00_ISWWqPHcZDYKlNjOODV15183", "toolName": "read",
 "result": {"content": [{"type": "text", "text": "hello world\nsecond line\n"}]}, "isError": false}
```

- **关联**：`toolCallId` 贯穿 start/update/end 三事件；也出现在 `turn_end.message.content[].type=="toolCall"` 的 `.id` 与 `toolResults[].toolCallId`。
- **`args` 已是对象**（非 JSON 字符串——对比 CodeBuddy `function_call.arguments` 是字符串需二次解析，#25 §1.3）。
- **`result.content[]`** 是 text 块数组；`isError` 标记失败。`tool_execution_update.partialResult` 是**累计输出**（非 delta），客户端可直接替换显示。
- 并行工具模式：`start` 按 assistant 源码序 preflight，`update` 跨工具交错，`end` 按完成序。最终 toolResult 消息事件按源码序后发。

### 4.2 turn 消息内的工具调用

`turn_end.message`（assistant）与 `turn_end.toolResults` 携带完整调用/结果：

```json
{"type": "turn_end",
 "message": {"role":"assistant","content":[
   {"type":"thinking","thinking":"...","thinkingSignature":"reasoning_content"},
   {"type":"toolCall","id":"call_00_ISWWq...","name":"read","arguments":{"path":"/tmp/pi-probe/sample.txt"}}],
  "api":"openai-completions","provider":"tencent-copilot","model":"deepseek-v4-flash-ioa",
  "usage":{...},"stopReason":"toolUse","timestamp":1787646879941},
 "toolResults": [{"role":"toolResult","toolCallId":"call_00_ISWWq...","toolName":"read",
   "content":[{"type":"text","text":"hello world\nsecond line\n"}],"isError":false,"timestamp":1787646882046}]}
```

- `stopReason` 取值：`stop` / `length` / `toolUse` / `error` / `aborted`（文档）。工具循环中为 `toolUse`。
- `message.usage` 每条 assistant 消息带（含 `cacheRead`、`reasoning`）。

---

## 5. 退出码语义（实测）

| 场景 | exit code | stdout | stderr |
|---|---|---|---|
| 正常跑完 | **0** | 完整（text 或事件流） | 空 |
| 任务自认失败/无法完成 | **0**（无专用码） | 完整（agent 自己解释） | 空 |
| 参数错误（unknown option） | **1** | 空 | `Error: Unknown option: --xxx` |
| 外层 `timeout` 杀掉 | **124** | 0 字节 | 空 |

实测命令与结果：

```bash
pi -p "Reply with the single word: OK"                      # EXIT=0, stdout="OK"
pi -p "say OK" --definitely-not-a-real-flag                 # EXIT=1, stderr=Error: Unknown option
timeout 5 pi -p "长任务..."                                  # EXIT=124, stdout 空
```

结论（与 CodeBuddy #25 §3 完全一致）：**exit code 只有 0/1/124 三类，不区分任务成败**。成功率必须 harness 判定：事件流里没有 `result.is_error`/`subtype` 等价物，pi 侧靠「验收测试 + 产物 diff」，辅助信号是 agent 最终文本（`get_last_assistant_text` RPC 命令可取）。

> 注意差异：CodeBuddy 有 `result.subtype`（`success`/`error_during_execution`）作为结局信号（#25 §3）；**pi 无此字段**。pi 的错误形态是：a) prompt 受理失败 → `response.success=false` + `error` 字段；b) 运行中错误 → 事件流里 `auto_retry_*`/`extension_error`，agent 若彻底失败会以普通 assistant 文本结束（exit 仍 0）。harness 需以「是否等到 `agent_settled` + 验收测试」为准。

---

## 6. 配置隔离 flag 实测结论

| Flag | 行为 | 实测 |
|---|---|---|
| `--no-context-files` / `-nc` | 关闭 AGENTS.md/CLAUDE.md 发现（全局 + 项目 + 上级目录） | ✅ 注入标记对照实验：无 flag 时 assistant 输出含 AGENTS.md 指令（`ZXQPLM OK`），加 `-nc` 后消失（`OK`） |
| `--tools <list>` / `-t` | 全工具白名单（内置 + 扩展 + 自定义） | ✅ 只读集 `read,grep,find,ls` 下同任务仅调用 `read`，无 bash |
| `--exclude-tools <list>` / `-xt` | 黑名单过滤 | ✅ 文档确认（`--exclude-tools ask_question` 例） |
| `--no-builtin-tools` / `-nbt` | 禁内置工具，保留扩展/自定义 | ✅ 文档确认 |
| `--no-tools` / `-nt` | 禁全部工具 | ✅ 文档确认 |
| `--no-session` | 不落盘会话（ephemeral） | ✅ 跑批必加（对照 CodeBuddy `--no-session-persistence`） |
| `--no-skills` / `--no-extensions` / `--no-prompt-templates` / `--no-themes` | 禁发现；**显式 `--skill`/`-e`/`--prompt-template`/`--theme` 仍加载** | ✅ 文档确认（`--no-extensions -e ./x.ts` 组合例） |
| `--no-approve` / `-na` | 忽略项目本地文件（.pi/settings.json、项目扩展等） | ✅ 文档确认；非交互默认 `defaultProjectTrust`（`ask`/`never` 忽略项目资源） |
| `--approve` / `-a` | 本次信任项目本地文件 | ✅ 文档确认 |
| `--no-context-files` 组合建议 | `-p --no-session --no-approve --no-skills --no-extensions -nc` | harness 固定清单 |

> 对照 CodeBuddy：pi **无** `--setting-sources`（CodeBuddy 用它收窄注入源，但 #25 §4.4 实测无法完全清空注入）。pi 的等价隔离 = `--no-*` 组合 + `--no-approve`，**能彻底清空**：`-nc` 关上下文文件、`--no-extensions` 关扩展、`--no-skills` 关技能、`--no-approve` 忽略项目资源。pi 的非交互模式本就不弹信任对话框（usage.md 明示），配合 `--no-approve` 可做到「零项目/用户配置干扰」——这是相对 CodeBuddy 的一个可复现性优势。
>
> ⚠️ 本机注意：显式传 `--provider tencent-copilot` 会触发模型目录刷新时序问题，偶发 `Unknown provider`（见 §8「意外」）。**建议 harness 不显式传 provider，靠 settings 默认 + `--model` 校验**。

---

## 7. 字段级核对表（harness executor 直接消费）

归一化目标字段（内部统一口径，见 #3 §6）→ pi 采集方式：

| 归一化指标 | 采集方式 | 真实字段 | 样例值 |
|---|---|---|---|
| 会话 id | `get_session_stats`（或首行 session 头） | `sessionId` / `id` | `01a0380e-...` |
| input_tokens | `get_session_stats` | `tokens.input` | `9085` |
| output_tokens | `get_session_stats` | `tokens.output` | `15` |
| cached_tokens（读） | `get_session_stats` | `tokens.cacheRead` | `0`（本任务无缓存命中；对照事件级 `cacheRead: 9088` 在第二轮出现） |
| cached_tokens（写） | `get_session_stats` | `tokens.cacheWrite` | `0` |
| total_tokens | `get_session_stats` | `tokens.total` | `9100` |
| 推理 token | `message_end.message.usage` | `usage.reasoning` | `13`（CodeBuddy 无此字段） |
| 事件级 token | `message_end`/`message_update` | `usage.{input,output,cacheRead,cacheWrite,reasoning,totalTokens}` | 见 §2.2 |
| cost | `get_session_stats` | `cost` | **恒 0，不可用** |
| 轮次（turn 数） | 计数 `turn_start` 事件 | — | 本任务 2（读文件 + 回复） |
| 模型调用次数 | 计数 `message_end`(role=assistant) | — | 与 turn 数一致（pi 每 turn 一次 LLM 调用） |
| wall_time_ms | 事件时间戳差（首 message_start → agent_settled） | `timestamp`（毫秒 epoch） | —（pi 无现成 `duration_ms`） |
| 结局 | 是否等到 `agent_settled` + 验收测试 | `agent_settled` 事件 | — |
| 工具调用 | `tool_execution_start/end` | `toolCallId` / `toolName` / `args`(对象) / `result.content[]` / `isError` | `read` + `{"path":"/tmp/pi-probe/sample.txt"}` |
| 工具调用（消息内） | `turn_end` | `message.content[].type=="toolCall"`（`.id/.name/.arguments`）+ `toolResults[]`（`.toolCallId/.content/.isError`） | 见 §4.2 |
| 上下文占用 | `get_session_stats` | `contextUsage.{tokens,contextWindow,percent}` | `9100` / `1000000` / `0.91` |
| 上下文膨胀归因 | **无**（对比 CodeBuddy `_meta.usageByCategory`） | — | 需自行实现（如扩展注入分类） |
| 最终回复文本 | RPC `get_last_assistant_text` | `data.text` | `"hello world\nsecond line"` |
| 运行快照（模型/权限/cwd） | RPC `get_state` | `data.model.{id,provider,contextWindow,...}`、`sessionFile` 等 | `deepseek-v4-flash-ioa` / `tencent-copilot` |

---

## 8. 复现命令（证据）

所有事件证据来自以下命令（本机 `pi 0.84.3`，provider `tencent-copilot`，模型 `deepseek-v4-flash-ioa`，`/tmp/pi-probe` 内含 `sample.txt` = 两行文本）：

```bash
# 1) RPC 长驻 + 简单回复 + 会话统计（核心证据，Python 客户端）
#    发 {"type":"prompt","message":"Reply with the single word: OK"}
#    等 agent_settled → 发 {"type":"get_session_stats"} → 发 {"type":"get_state"}
# 2) RPC + 工具调用（读文件）
#    {"type":"prompt","message":"Read the file sample.txt and tell me its exact contents, one line per line, nothing else."}
# 3) JSON 事件流形态
pi -p --mode json "Reply with the single word: OK"
# 4) 退出码
pi -p "Reply with the single word: OK"                    # exit 0
pi -p "say OK" --definitely-not-a-real-flag               # exit 1
timeout 5 pi -p "长任务"                                   # exit 124
# 5) 工具白名单
pi --tools read,grep,find,ls --no-session --mode json -p "Read sample.txt and tell me its first line"
# 6) --no-context-files 注入对照（AGENTS.md 含"ALWAYS reply starting with ZXQPLM"）
pi --no-session --mode json -p "Reply with the single word: OK"    # 输出含 ZXQPLM
pi --no-context-files --no-session --mode json -p "Reply with the single word: OK"  # 不含
```

原始事件文件（本机）：`/tmp/pi-probe/events4.jsonl`（简单回复 + stats）、`events5.jsonl`（工具调用 + turn_end 全量）。

---

## 9. 遗留 / 边界

- **本机实测的意外（值得记录）**：a) 显式 `--provider tencent-copilot` 触发模型目录刷新时序 bug，偶发 `Unknown provider "tencent-copilot"`（stderr 提示用 `--list-models` 刷新）；不加 `--provider` 时偶发 `Warning: No models match pattern "..."`（后台刷新未完成），但最终模型解析成功。**harness 首次跑前应先 `pi --list-models` 预热目录**，并固定 settings 默认模型。b) `--no-*` 全禁组合（含 `--no-extensions`）下 `get_state` 返回 `model: unknown` 且 prompt 报 `No API key found`——疑似与模型目录刷新交互，最简参数正常；需在 harness 里验证该组合的稳定性。
- `compaction_start/end`、`auto_retry_*`、`summarization_retry_*`、`extension_error`、`queue_update` 事件本机简单任务未触发，字段结构取自 rpc.md 文档（未实测）。
- RPC `bash` 命令与 `bash_execution_update` 事件（非 LLM 工具调用路径）未实测；`steer`/`follow_up`/`abort` 等命令未实测。
- `cost` 非零场景（有计费映射的 API key）未验证，本机恒 0。
- `--mode json` 与 `--mode rpc` 事件字段是否完全一致（json.md 的 `WithoutPartial` 类型变换）未做逐事件 diff。
- 扩展 UI 子协议（`extension_ui_request`/`extension_ui_response`）未实测——harness 若加载交互式扩展需实现。
