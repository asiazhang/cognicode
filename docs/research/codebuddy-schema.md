# 核对 CodeBuddy headless 输出 schema（实测）

> 票：#25（wayfinder:research，Part of #16）。实测日期：2026-08-21。测试版本：`codebuddy 2.137.1`，模型 `deepseek-v4-flash-ioa`，认证来源 `copilot.tencent.com`。
>
> 本表是 #3（docs/research/agent-driving.md）遗留空缺「headless JSON result 完整 schema / result 统计字段名 / 退出码值」的实测补齐。**所有字段名与样例值均来自本机真实命令输出**，每条结论可直接被 harness 的 CodeBuddy executor 消费。原始输出证据见文末「复现命令」。

---

## TL;DR（harness 必读）

1. **两种输出格式是两套不同的消息模型**，不要假设字段互通：
   - `--output-format json`：stdout 是一个 **JSON 数组**，元素是「会话消息列表」（`type` 取 `message`/`reasoning`/`function_call`/`function_call_result`/`result`），**没有** `system/init` 事件，也没有 `modelUsage`、`_meta`。
   - `--output-format stream-json`：stdout 是 **JSONL 事件流**，以 `system/init` 开始、`system/status` 跟随，中间 `assistant`/`user` 事件，最后 `result`。**只有 stream-json 的 result 才有 `modelUsage` 与 `_meta`**（`_meta` 含按类别拆分的上下文用量）。
2. **`total_cost_usd` 恒为 `0`**：本机用腾讯云 copilot 账号（无计费额度映射），`result.total_cost_usd` 始终是 `0`。**成本指标不可用，必须改用 token 用量**。权威 token 字段见下。
3. **`--max-turns` 触顶在两种格式下行为不一致，且 exit code 都是 0**：
   - `stream-json`：正常出完整事件流，`result.subtype = "error_during_execution"`、`is_error = true`、`errors = ["Max turns (1) exceeded"]`。
   - `json`：**stdout 为空**，错误文本打到 **stderr**（`Max turns (1) exceeded`），exit code 仍为 0。
   - 结论：**判定「触顶」不能只看 exit code**，必须解析 result 的 `subtype`/`is_error`/`errors`；且用 `json` 格式时 stdout 可能为空，需同时捕获 stderr。
4. **退出码语义极简**：0 = 进程正常结束（包括成功、max-turns 触顶、权限被拒后 agent 自行收尾）；1 = 参数错误（unknown option，stderr 报错，stdout 空）；被外层 `timeout` 杀 = 124（无 result 事件）。**没有「任务失败」专用退出码**，成功率必须由 harness 自己判定。
5. **`num_turns` 是「模型 API 调用次数」而非「agent 往返轮次」**：一个「读文件再回答」的任务 `num_turns ≈ 4–5`，而 stream-json 里只有 2 条 assistant 消息。harness 若需「用户可见轮次」，应统计 assistant 消息数；若需「模型调用数」，用 `result.num_turns`。
6. **工具调用在两种格式里的结构不同**：`stream-json` 是 `assistant` 事件的 `message.content[].type=="tool_use"` 块（`.name`/`.input`）+ `user` 事件的 `tool_result`；`json` 是独立的 `type=="function_call"`（`.name`/`.arguments` 为 JSON 字符串）与 `type=="function_call_result"`（`.output`）消息。

---

## 1. `--output-format json` 完整字段结构

stdout 是一个 JSON 数组（不是 JSONL），按时间顺序排列会话消息。实测一个「读文件并回复」任务的完整元素序列：

| # | type | role | 说明 |
|---|---|---|---|
| 0 | `message` | `user` | 用户输入（`content` 含 `input_text` 块，system-reminder + user_query） |
| 1 | `reasoning` | — | 推理（`rawContent[].type=="reasoning_text"`） |
| 2 | `function_call` | — | 工具调用（`name`/`arguments`） |
| 3 | `function_call_result` | — | 工具结果（`output`/`status`） |
| 4 | `message` | `assistant` | 回复（`content[].type=="output_text"`） |
| 5 | `result` | — | 统计汇总 |

### 1.1 `result` 消息（json 格式，字段级）

真实字段名与样例值（成功、无工具调用）：

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "OK",
  "uuid": "5363d6b8-fe92-40e6-a5a1-8c18604b434f",
  "session_id": "1fce4b19-b2d1-4a31-a147-efc6c3d98cc9",
  "duration_ms": 2075,
  "duration_api_ms": 2074,
  "num_turns": 2,
  "total_cost_usd": 0,
  "usage": {
    "input_tokens": 21340,
    "output_tokens": 2,
    "cache_creation_input_tokens": 18268,
    "cache_read_input_tokens": 3072,
    "cache_creation": null,
    "server_tool_use": null,
    "service_tier": null
  },
  "permission_denials": [],
  "__timestamp": "2026-08-21T07:13:46.309Z"
}
```

逐字段：

| 字段 | 类型 | 含义 / 样例 | 采集建议 |
|---|---|---|---|
| `type` | string | `"result"` | 定位 result 消息 |
| `subtype` | string | `"success"`（见 §3 全部取值） | 结局判定主信号 |
| `is_error` | bool | `false` / `true` | 结局判定主信号 |
| `result` | string | 最终文本回复，如 `"OK"` | 任务自报告正文 |
| `uuid` | string | result 消息自身 id | — |
| `session_id` | string | 会话 id，如 `1fce4b19-...` | 会话追踪 |
| `duration_ms` | number | 墙钟时长 ms，含工具执行 | `wall_time_ms` |
| `duration_api_ms` | number | API 调用时长 ms | — |
| `num_turns` | number | **模型 API 调用次数**（见 TL;DR#5） | `turns` |
| `total_cost_usd` | number | **恒为 0**（本机） | 不可用，忽略 |
| `usage.input_tokens` | number | 输入 token | `input_tokens` |
| `usage.output_tokens` | number | 输出 token | `output_tokens` |
| `usage.cache_creation_input_tokens` | number | 缓存写入 token | `cached_tokens`（写） |
| `usage.cache_read_input_tokens` | number | 缓存命中 token | `cached_tokens`（读） |
| `usage.cache_creation` / `usage.server_tool_use` / `usage.service_tier` | null | 恒为 null | 忽略 |
| `permission_denials` | array | 被拒权限记录，本机实测恒为 `[]`（非交互模式下被拒信息走 tool_result 文本，见 §4.3） | — |
| `structured_output` | object（可选） | 仅在传 `--json-schema` 且校验通过时出现，值为**对象**（非字符串），如 `{"line_count": 2}` | 结构化自报告 |
| `errors` | array（可选） | 仅错误时出现，如 `["Max turns (1) exceeded"]` | 错误详情 |
| `__timestamp` | string | ISO-8601 UTC，`"2026-08-21T07:13:46.309Z"` | 结束时间戳 |

> 注意：`json` 格式的 result **没有** `modelUsage` 与 `_meta`（那是 stream-json 独有）。

### 1.2 `message`（user / assistant）

- user：`content[]` 元素为 `input_text`（`.text`），`providerData.agent=="cli"`、`providerData.__codebuddySensitiveUserInputReviewed==true`。
- assistant：`status=="completed"`，`content[]` 元素为 `output_text`（`.text`）。`providerData` 内含：`model`、`requestModelId`、`requestModelName`、`traceId`、`conversationRequestId`、`agent`、以及**两份 usage**：
  - `providerData.rawUsage`：`prompt_tokens` / `completion_tokens` / `total_tokens` / `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` / `completion_tokens_details.cached_tokens` / `prompt_tokens_details.cached_tokens` 等。
  - `providerData.usage`：`requests` / `inputTokens` / `outputTokens` / `totalTokens` / `inputTokensDetails[].cached_tokens` / `outputTokensDetails[].reasoning_tokens`。

### 1.3 工具调用在 `json` 格式里的表现

**独立消息类型**（不是嵌在 assistant content 里）：

```json
// 工具调用
{
  "type": "function_call",
  "callId": "call_00_n0lEWsD7v7go4lqw5x9h3980",
  "name": "Read",
  "arguments": "{\"file_path\": \"/tmp/cb-probe/sample.txt\"}",
  "timestamp": 1787296486496,
  "sessionId": "904fb09b-57f9-4b5a-96c1-382ab3d3a51f",
  "parentId": "0530e274-9d37-4d87-a6ea-129f5f19fcde"
}
// 工具结果
{
  "type": "function_call_result",
  "name": "Read",
  "callId": "call_00_n0lEWsD7v7go4lqw5x9h3980",
  "status": "completed",
  "output": { "type": "text", "text": "   1→hello world from file\n   2→second line\n   3→" },
  "timestamp": 1787296486750,
  "sessionId": "904fb09b-57f9-4b5a-96c1-382ab3d3a51f",
  "parentId": "d158791e52b94d8b86c5f62cbe5a9851"
}
```

要点：
- `function_call.arguments` 是 **JSON 字符串**（需 `json.loads` 二次解析）；`name` 是工具名（`Read`）。
- `function_call_result.output` 是对象，文本在 `.output.text`；`providerData.toolResult.title` **含 ANSI 颜色码**（如 `"Read \x1b[38;5;255m3\x1b[39m lines"`），解析需 strip。
- 一次工具调用对应 `function_call` + `function_call_result` 两条相邻消息，靠 `callId` 关联。

---

## 2. `--output-format stream-json` 事件类型与顺序

stdout 是 JSONL，每行一个 JSON 对象。实测一个「回复 OK」任务的事件序列：

```
[0] system/init
[1] system/status
[2] assistant   （thinking 块）
[3] assistant   （text 块）
[4] result/success
```

带工具调用（读文件）时：

```
[0] system/init
[1] system/status
[2] assistant（tool_use 块）
[3] user（tool_result）
[4] assistant（text 块）
[5] result/success
```

### 2.1 `system/init`（运行环境快照，适合可复现性审计）

```json
{
  "type": "system",
  "subtype": "init",
  "uuid": "50cf3ce8-...",
  "session_id": "50cf3ce8-...",          // 注意：与 result.session_id 相同
  "apiKeySource": "copilot.tencent.com",
  "cwd": "/tmp/cb-probe",
  "model": "deepseek-v4-flash-ioa",
  "permissionMode": "bypassPermissions",  // 传 -y 时；不传为 "default"
  "mcp_servers": [],
  "tools": ["Agent","Read","Write","Edit","Bash","Glob","Grep","WebFetch","WebSearch", ...],
  "slash_commands": ["add-dir","agents", ...],
  "output_style": "default",
  "__timestamp": "2026-08-21T07:14:09.348Z",
  "_requestId": "f98aac843875495896b8f90030afa4d6"
}
```

- `system/status` 事件紧随 init，`status` 字段为 `null`（本机）。
- 每条事件都带 `session_id`、`uuid`、`__timestamp`、`_requestId`。

### 2.2 `assistant` 事件

`message` 字段含 `id`/`model`/`role`/`type`/`stop_reason`/`usage`/`content[]`。`content` 元素类型：
- `thinking`（`.thinking` 文本，`.signature` 空）
- `text`（`.text`）
- `tool_use`（`.id`、`.name`、`.input`——**input 已是对象**，如 `{"file_path": "/tmp/cb-probe/sample.txt"}`）

每条 assistant 事件的 `message.usage` 记录该次 API 调用的 token（成功段与失败段分开两条事件）。

### 2.3 `user` 事件（工具结果回传）

`message.content[]` 为 `tool_result` 块：`.tool_use_id`（关联 assistant 的 tool_use `.id`）、`.content[].text`、`.is_error`。顶层 `parent_tool_use_id` 亦携带关联 id。

### 2.4 `result` 事件（stream-json 独有字段）

在 §1.1 基础上**额外**包含：

```json
{
  "modelUsage": {
    "deepseek-v4-flash-ioa": {
      "inputTokens": 0,
      "outputTokens": 17,
      "cacheReadInputTokens": 21248,
      "cacheCreationInputTokens": 92,
      "contextWindow": 1000000,
      "maxOutputTokens": 50000
    }
  },
  "_meta": {
    "codebuddy.ai/contextUsed": 21340,
    "codebuddy.ai/usageByCategory": {
      "systemPrompt": 1842,
      "conversation": 125,
      "tools": 19039,
      "mcp": 0,
      "skills": 334,
      "version": 1
    }
  }
}
```

- `modelUsage.<model>.inputTokens/outputTokens/cacheReadInputTokens/cacheCreationInputTokens/contextWindow/maxOutputTokens`：按模型聚合的用量（**注意 camelCase**）。
- `_meta["codebuddy.ai/contextUsed"]`：上下文窗口占用；`_meta["codebuddy.ai/usageByCategory"]` 按 systemPrompt/conversation/tools/mcp/skills 拆分——harness 若要「上下文膨胀」归因，用这个。

> harness 建议：**优先用 stream-json**，因为 init 事件提供运行快照、result 提供 modelUsage/_meta，且错误场景 stdout 不丢（对比 json 格式 max-turns 时 stdout 为空）。

---

## 3. 退出码与 `subtype` 语义（实测）

| 场景 | exit code | stdout | stderr | result.subtype | is_error |
|---|---|---|---|---|---|
| 正常跑完 | 0 | 完整 | 空 | `success` | false |
| `--max-turns` 触顶（stream-json） | **0** | 完整事件流 | 空 | `error_during_execution` | true（`errors=["Max turns (1) exceeded"]`） |
| `--max-turns` 触顶（json） | **0** | **空** | `Max turns (1) exceeded` | （无 result，无 stdout） | — |
| 权限被拒后 agent 收尾 | 0 | 完整 | 空 | `success`（agent 自行解释，见 §4.3） | false |
| 参数错误（unknown option） | **1** | 空 | `error: unknown option '...'` | — | — |
| 外层 `timeout N` 杀掉 | **124** | 空（本机 0 行） | 空 | — | — |

`subtype` 观测取值：`success`、`error_during_execution`（max-turns 触顶用这个，**没有**独立的 `error_max_turns`）。

关键结论：
1. **exit code 只有 0/1/124 三类**，不区分任务成败。成功率判定必须：`result.is_error`/`subtype` + harness 自己的验收测试。
2. **max-turns 触顶不是进程失败**：exit code 仍 0。用 json 格式时 stdout 会整个空掉——**harness 若用 json 格式必须同时读 stderr**，否则会把「触顶」误判成「无输出」。
3. 被 `timeout` 杀（124）时没有 result 事件，harness 需单独处理「超时」分支。

---

## 4. CLI flag 实测行为（v2.137.1）

### 4.1 `--max-turns <n>`

- 生效，但**不是严格轮次上限**：`--max-turns 1` 下模型仍发出 `num_turns=5` 后才停（先读文件再回答的任务）。模型会持续请求直到判定「无工具可继续」，随后 CLI 检查轮次计数并报 `Max turns (1) exceeded`。
- 判定方式见 §3。注意「触顶阈值」与 `num_turns` 的关系在本机非线性（`max-turns=1` 报触顶、`max-turns=2` 即成功，但两者 `num_turns` 都约 5）——**不要把 `--max-turns` 当成精确轮次熔断，只当软上限**。

### 4.2 `-y`（`--dangerously-skip-permissions`）≡ `--permission-mode bypassPermissions`

- 生效。`stream-json` 的 `system/init.permissionMode` 直接反映：传 `-y` → `"bypassPermissions"`，不传 → `"default"`。
- 不传时，需要授权的工具（如 Bash）会被拒，agent 收到 tool_result 里的英文提示文本（见 §4.3），然后自行解释并结束，**exit code 仍 0**。

### 4.3 非交互模式下的权限拒绝（不传 `-y`）

实测让 agent 用 Bash 工具跑 `echo`：

- 工具结果以 `user` 事件 `tool_result` 回传，`.is_error=false`，文本为：
  `"Error: Permission to use Bash has been denied because this tool requires approval but permission prompts are not available in non-interactive mode. ... re-run with codebuddy -p -y ... or add \"Bash\" to the \"permissions.allow\" list ..."`
- 之后 agent 放弃该动作、正常回复，`result.subtype=success`、`permission_denials=[]`。
- 结论：**非交互模式没有权限提示，直接拒绝**；被拒信息藏在 `tool_result.content[].text` 里，`result.permission_denials` 不记录。harness 要捕获「被拒的工具调用」，需扫描 user 事件的 tool_result 文本，或干脆固定传 `-y`（配合沙箱）。

### 4.4 `--setting-sources <sources>`

- 值取 `user,project,local` 的组合（默认 `user,project,local`）。**无效值（如 `bogus`）不报错、静默接受**（exit 0）。
- 实测行为（通过 user 消息里注入的 system-reminder 内容判断）：
  - `user,project,local`（默认）：注入 `# codebuddyMd` 上下文 = 全局 `/root/.codebuddy/CODEBUDDY.md` + 项目 `AGENTS.md`。
  - `user`：只注入 codebuddyMd（全局 + 项目 AGENTS.md），**无** memory 提示。
  - `project`：**不注入 codebuddyMd**，改为注入 `<system-reminder data-role="memory">`（自动记忆系统提示，13241 字符）。
  - `local`：同 `project`，注入 memory 提示、不注入 codebuddyMd。
- 结论：`--setting-sources` 能改注入内容，但**没有组合能完全清空注入**（`project`/`local` 会注入 memory 提示，`user` 会注入 CODEBUDDY.md + AGENTS.md）。harness 要稳定复现，需固定该 flag 并接受「memory 提示」或「codebuddyMd」二者其一必在。

### 4.5 `--no-session-persistence`

- 生效。干净对照实验：先 `rm -rf /root/.codebuddy/projects/tmp-cb-probe`，带 `--no-session-persistence` 跑完**不落盘**（目录不存在）；不带 flag 跑完落盘 `<uuid>.jsonl`。
- harness 跑批建议加此 flag，避免会话 transcript 泄漏到 `~/.codebuddy/projects/<cwd-路径>/`。

### 4.6 `--json-schema`

- 生效。传 schema 且校验通过时，`result.structured_output` 为**对象**（json 格式：`{"line_count": 2}`；stream-json 同理，但 stream-json 里 `result` 字段为空字符串）。校验失败行为本票未覆盖。

---

## 5. 字段级核对表（harness executor 直接消费）

归一化目标字段（内部统一口径，见 #3 §6）→ 采集方式：

| 归一化指标 | 采集方式（优先 stream-json） | 真实字段名 | 样例值 |
|---|---|---|---|
| 运行快照（模型/权限/cwd/工具） | `system/init` 事件 | `model` / `permissionMode` / `cwd` / `tools` / `apiKeySource` | `deepseek-v4-flash-ioa` / `bypassPermissions` / `/tmp/cb-probe` / `["Read","Bash",...]` / `copilot.tencent.com` |
| input_tokens | `result.usage` | `usage.input_tokens` | `21340` |
| output_tokens | `result.usage` | `usage.output_tokens` | `2` |
| cached_tokens（读） | `result.usage` | `usage.cache_read_input_tokens` | `3072` |
| cached_tokens（写） | `result.usage` | `usage.cache_creation_input_tokens` | `18268` |
| 分模型 token | stream-json `result.modelUsage` | `modelUsage.<model>.inputTokens/.outputTokens/.cacheReadInputTokens/.cacheCreationInputTokens` | `{inputTokens:0, outputTokens:17, ...}` |
| turns（模型调用数） | `result` | `num_turns` | `2` |
| wall_time_ms | `result` | `duration_ms` | `2075` |
| cost_usd | `result` | `total_cost_usd` | **恒为 0，不可用** |
| 会话 id | `result` / 各事件 | `session_id`（`init` 事件的 `session_id` 与 `result.session_id` 相同） | `1fce4b19-b2d1-4a31-a147-efc6c3d98cc9` |
| 结局 | `result` | `subtype` + `is_error`（+ `errors[]`） | `success` / `error_during_execution` + `["Max turns (1) exceeded"]` |
| 结构化自报告 | `result`（需 `--json-schema`） | `structured_output` | `{"line_count": 2}` |
| 工具调用（stream-json） | `assistant` 事件 | `message.content[].type=="tool_use"` → `.name`/`.input`；`user` 事件 `tool_result` → `.tool_use_id`/`.content[].text` | `{"name":"Read","input":{"file_path":"..."}}` |
| 工具调用（json） | 独立消息 | `type=="function_call"` → `.name`/`.arguments`（JSON 字符串）；`type=="function_call_result"` → `.output.text`/`.status` | `{"name":"Read","arguments":"{\"file_path\":\"...\"}"}` |
| 上下文膨胀归因 | stream-json `result._meta` | `_meta["codebuddy.ai/contextUsed"]` / `_meta["codebuddy.ai/usageByCategory"]` | `21340` / `{systemPrompt:1842, conversation:125, tools:19039, mcp:0, skills:334}` |
| 权限拒绝 | 无专用字段 | `result.permission_denials` 恒 `[]`；被拒信息在 `user` 事件 `tool_result.content[].text` | （见 §4.3 文本） |

---

## 6. 复现命令（证据）

所有输出证据来自以下命令（本机 `codebuddy 2.137.1`，`/tmp/cb-probe` 内含 `sample.txt` = 两行文本）：

```bash
# 1) json 格式（简单回复）
codebuddy -p "Reply with the single word: OK" --output-format json -y --no-session-persistence

# 2) stream-json 格式
codebuddy -p "Reply with the single word: OK" --output-format stream-json -y --no-session-persistence

# 3) 工具调用（读文件）
codebuddy -p "Read the file sample.txt and tell me its exact contents, one line per line, nothing else." \
  --output-format stream-json -y --no-session-persistence
# 同上换 --output-format json 观察 function_call/function_call_result

# 4) max-turns 触顶
codebuddy -p "First read the file sample.txt, then tell me its contents" \
  --output-format stream-json -y --no-session-persistence --max-turns 1

# 5) 超时
timeout 2 codebuddy -p "Read sample.txt, then write a haiku..." --output-format stream-json -y --no-session-persistence

# 6) 不带 -y 触发权限拒绝（Bash）
codebuddy -p "Use the Bash tool to run: echo hello-from-bash" --output-format stream-json --no-session-persistence

# 7) 结构化输出
codebuddy -p "Report how many lines sample.txt has, as structured JSON." \
  --output-format json -y --no-session-persistence \
  --json-schema '{"type":"object","properties":{"line_count":{"type":"number"}},"required":["line_count"]}'

# 8) setting-sources 行为（观察 user 消息里的 system-reminder）
codebuddy -p "say OK" --output-format json -y --no-session-persistence --setting-sources project

# 9) 参数错误退出码
codebuddy -p "say OK" --output-format json --definitely-not-a-real-flag   # exit 1
```

---

## 7. 遗留 / 边界

- `--json-schema` 校验失败（agent 输出不合 schema）时的 `subtype`/`is_error` 未实测。
- `total_cost_usd` 在**有计费映射的账号**（如 Anthropic/OpenAI key）下是否非零未验证——本机账号恒为 0。
- 后台任务事件（#3 提到的 `task_started`/`task_progress` 等）在本机简单任务中未出现，未实测。
- `usage` 与 `modelUsage` 在「多模型/子代理」场景的一致性未验证。
