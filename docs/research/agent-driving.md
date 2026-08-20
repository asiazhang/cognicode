# 调研：以可编程方式驱动编程 agent 执行任务并采集数据

> 票：#3（wayfinder:research）。调研日期：2026-08-20。所有结论均来自各家官方一手文档（文末来源列表），版本随文档当前状态（2026-08 抓取）。

## TL;DR

- **四家 agent 全部具备非交互 CLI 入口**：CodeBuddy `codebuddy -p`、Claude Code `claude -p`、Codex `codex exec`、Aider `aider --message`。前三家还提供 SDK（CodeBuddy/Claude Code：TS + Python；Codex：GitHub Action/app-server）。
- **结构化日志能力分两档**：CodeBuddy / Claude Code / Codex 均可输出 JSON/JSONL 事件流，且**自带 token 用量与轮次统计**（CodeBuddy `total_cost_usd`/usage、Claude Code `num_turns`/`usage`/`modelUsage`、Codex `turn.completed` 携带 `usage`）；**Aider 无结构化输出**，token 用量只能靠 `/tokens` 命令或解析 `--verbose` stdout。
- **成功率判定要靠 harness 自己定义**：exit code 只反映「进程是否正常跑完」，不反映「任务是否做对」；任务级成功率需结合测试通过与否 / 产物 diff 判定。CodeBuddy / Claude Code / Codex 均支持 JSON Schema 约束的结构化自报告，可作为辅助判定信号。
- **沙箱**：Codex（Seatbelt / bwrap+seccomp，三档模式 + 网络代理）与 CodeBuddy（bubblewrap / Seatbelt + 网络代理 + 容器/E2B `--sandbox`）有 OS 级隔离；Aider 完全无隔离。git worktree/clone 是所有家通用的产物隔离兜底手段。
- **对 #6（测量协议）的直接约束**：以「fresh git worktree + headless CLI + stream-json/stdout 捕获 + git diff 收产物」为核心的 harness 模式对所有家可行；模型、权限模式、max-turns、配置来源隔离（CodeBuddy `--setting-sources` / Claude Code `--bare` / Codex `--ignore-user-config`）必须逐项固定才能满足分数稳定硬需求。

---

## 1. CodeBuddy Code（本项目 dogfooding 的执行者）

### 1.1 可编程入口

**无头模式（`codebuddy -p` / `cbc -p`）**（headless.md、cli-reference.md）：

```bash
codebuddy -p "任务描述" \
  --output-format json \        # text | json | stream-json
  --model <model> \
  --max-turns 3 \               # 限制非交互模式轮次
  --setting-sources project \
  -y                            # 非交互模式下执行需授权操作的必需参数
```

- 输入：命令行参数、stdin 管道（`echo "..." | codebuddy -p`）、`--input-format stream-json`（stdin 逐行 JSON 用户消息，支持多轮长驻进程、base64 图片）。
- 输出格式三档：`text` / `json`（含元数据的单对象）/ `stream-json`（逐行事件流，以 `init` 系统消息开始、以含统计的 `result` 系统消息结束）。
- 多轮：`--continue` / `--resume <session-id>`，或 stream-json stdin 长驻进程。
- `--json-schema` 配合 `--output-format json` 可得 `structured_output` 字段的结构化自报告。
- 会话隔离：`--no-session-persistence`（不落本地 transcript）；`--setting-sources` 默认 `user,project,local`，可显式收窄以隔离环境。

**Agent SDK**（sdk.md）：`@tencent-ai/agent-sdk`（npm）/ `codebuddy-agent-sdk`（pip），`query({ prompt, options })` 异步迭代返回 `system` / `assistant` / `result` 消息。关键选项：`permissionMode`、`canUseTool` 回调、`maxTurns`、`settingSources`（默认不加载任何文件系统配置——天然适合可复现 harness）、`cwd`、`model`、`allowedTools`、`hooks`（`PreToolUse`/`PostToolUse`/`SessionStart`/`SessionEnd` 等，可拦截每次工具调用做记录）。SDK 预览阶段（v0.1.0+），接口可能变动。

### 1.2 权限与沙箱

- 非交互模式执行文件读写/命令/网络必须显式给权限策略：`-y`（`--dangerously-skip-permissions`）、`--permission-mode auto|dontAsk|acceptEdits|plan|bypassPermissions|default`、`--allowedTools`/`--disallowedTools`（支持 `Bash(git commit:*)` 细粒度规则）、`--tools`（内置工具白名单，`""` 全禁）。
- **Bash 沙箱**（bash-sandboxing.md）：OS 级强制（Linux bubblewrap、macOS Seatbelt），文件系统 + 网络双隔离，代理管控域名；`settings.json` 中 `sandbox.enabled`、`autoAllowBashIfSandboxed`、`excludedCommands` 可配；配置文件本身写保护防逃逸。
- **容器沙箱**：`--sandbox`（无参/container 用 Docker/Podman；传 E2B URL 用云沙箱）、`--sandbox-upload-dir`、`--sandbox-kill`、`CODEBUDDY_SANDBOX_IMAGE`。

### 1.3 度量采集（字段级）

| 指标 | 采集方式 | 字段 |
|---|---|---|
| token / 成本 | `--output-format json` 的 result | `.total_cost_usd`、`.session_id`、`.result`；后台任务事件含 `usage:{total_tokens, tool_uses, duration_ms}` |
| 交互轮次 | `--max-turns` 限界；result 系统消息含统计 | 文档未逐一列举字段名（确认有统计信息；Claude Code 同源结构有 `num_turns`，CodeBuddy 文档暂未确认同名字段） |
| 工具调用 | `stream-json` 事件流 | assistant 消息的 `tool_use` 块（`.name`/`.input`）、user 消息 `tool_use_result`；后台任务事件 `task_started`/`task_progress`/`task_updated`/`task_notification`（含 `task_id`、`tool_uses`、`duration_ms`） |
| 成功率 | exit code + stderr；`--json-schema` 结构化自报告 | 文档未列具体退出码值，最佳实践是检查退出码与 stderr、用 `timeout` 包裹 |
| 产物 diff | git worktree + `git diff` | 无内置 diff 报告，靠 harness 收集 |

已知文档空缺：完整 JSON result schema 未在文档中列举（仅 jq 示例确认 `.result`/`.total_cost_usd`/`.session_id`/`.structured_output`）；实现 harness 时应以实际输出为准做一次字段核对。

---

## 2. Claude Code（headless.md、cli-reference.md、Agent SDK 文档）

### 2.1 可编程入口

```bash
claude -p "任务描述" \
  --output-format stream-json \
  --include-partial-messages \
  --max-turns 3 \
  --permission-mode acceptEdits \
  --allowedTools "Bash(git diff *),Read,Edit"
```

- `--output-format text|json|stream-json`；`--input-format text|stream-json`（print 模式）；`--include-partial-messages` 需 `-p` + `stream-json`。
- 多轮：`--continue` / `--resume <session-id>`（v2.1.223 起跨目录）；`--session-id` 直接指定 UUID。
- `--json-schema` 结构化输出（非法 schema 显式报错退出）。
- `--bare` 模式（官方推荐用于脚本/CI/SDK，未来将成 `-p` 默认）：跳过 hooks/skills/plugins/MCP/CLAUDE.md 自动发现，只留 Bash/读/写工具，必须 API key 认证——对可复现测量极具价值。
- stdin 管道上限 10MB；退出码：0 成功、非零失败、143 = SIGTERM；参数错误走 stderr，运行中失败打进 stdout 的 result。
- Agent SDK（TS/Python）：`query()` + `canUseTool` 回调、`maxTurns`、`maxBudgetUsd`、hooks。

### 2.2 权限与沙箱

- `--permission-mode default|acceptEdits|plan|auto|dontAsk|bypassPermissions`；`--allowedTools` / `--disallowedTools`（前缀匹配规则语法）；`--dangerously-skip-permissions` ≡ `bypassPermissions`。
- `-p` 默认 Manual 模式，测量时必须显式传权限模式。
- 注意：CodeBuddy 的 Bash 沙箱文档指出其沙箱运行时即开源的 `anthropic-experimental/sandbox-runtime`（`npx @anthropic-ai/sandbox-runtime`），与 Claude Code 生态同源。

### 2.3 度量采集（字段级，Agent SDK TS 文档）

- **system/init 事件**：`claude_code_version`、`model`、`tools`、`mcp_servers`、`permissionMode`——适合做运行环境快照（可复现性审计）。
- **assistant 消息**：`message.usage`（Anthropic BetaMessage）；`context_usage`（结构化 `/context` 报告）；`parent_tool_use_id` 区分子代理。
- **result 消息**（最重要）：
  - `num_turns`、`duration_ms`、`duration_api_ms`、`ttft_ms`（首 token 延迟）
  - `total_cost_usd`（客户端估算）、`usage`（仅主循环）、`modelUsage`（按模型聚合，含子代理/压缩——官方建议 token/成本记账用这个）
  - `is_error`、`subtype`：`success | error_max_turns | error_during_execution | error_max_budget_usd | ...`
  - `permission_denials`（被拒工具调用清单）、`structured_output`
- **工具调用**：assistant 消息 `tool_use` 块 + user 消息 `tool_result`；`SDKPermissionDeniedMessage`；stream 事件可按 `stream_event` 过滤。

结论：Claude Code 是四家中**度量字段文档化最完整**的，可直接作为 harness 的参照实现。

---

## 3. Codex CLI（noninteractive 文档、developer-commands、approvals-security 文档）

### 3.1 可编程入口

```bash
codex exec "任务描述" \
  --sandbox workspace-write \
  --ask-for-approval never \
  --json \                      # stdout 变为 JSONL 事件流
  -o /tmp/final-message.txt     # --output-last-message：最终消息写文件
```

- 位置参数传 prompt；stdin 管道作附加上下文（prompt+stdin 模式）；`codex exec -` 把整个 stdin 当 prompt。
- 进度流到 stderr、最终消息到 stdout；`--ephemeral` 不落盘会话文件。
- `--json`：stdout 为 JSONL 事件流，事件类型 `thread.started` / `turn.started` / `turn.completed` / `turn.failed` / `item.*` / `error`；item 类型含 agent 消息、reasoning、**command_execution（命令执行）、file_change（文件变更）、mcp_tool_call、web_search、plan 更新**——工具调用粒度的事件直接内置。
- **token 用量**：`turn.completed` 事件携带 `usage: {input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}`。
- 结构化输出：`--output-schema ./schema.json` + `-o out.json`。
- 会话续跑：`codex exec resume --last "..."` 或 `codex exec resume <SESSION_ID>`。
- **必须在 git 仓库内运行**（防破坏性变更），可 `--skip-git-repo-check` 豁免。
- 认证：`CODEX_API_KEY` 仅 `codex exec` 支持；官方提供 GitHub Action（openai/codex-action，代理保护 key）。
- `--ignore-user-config`（不加载 `~/.codex/config.toml`）、`--ignore-rules`——配置隔离。

### 3.2 沙箱（四家中最强、文档最全）

- 三档：`read-only`（默认，CI 推荐 `--sandbox read-only --ask-for-approval never`）/ `workspace-write`（版本控制目录默认；网络默认关）/ `danger-full-access`（≡ `--dangerously-bypass-approvals-and-sandbox` / `--yolo`）。
- 审批策略：`--ask-for-approval untrusted|on-request|never` + granular 策略（config.toml `approval_policy = { granular = {...} }`）。
- OS 级强制：macOS Seatbelt（`sandbox-exec` profile）、Linux `bwrap` + `seccomp`、Windows 独立沙箱。
- 网络代理：`[sandbox_workspace_write] network_access = true` + `[features.network_proxy]`（域名 allowlist/denylist、本地地址默认封禁）。
- 可写根保护：`<root>/.git`、`.agents`、`.codex` 强制只读——**意味着 harness 想让 Codex 提交产物 commit 需用 `--add-dir` 或在沙箱外收 diff**。
- `--full-auto` 已废弃（打印警告），新脚本用显式 `--sandbox workspace-write`。

### 3.3 度量采集

| 指标 | 采集方式 |
|---|---|
| token | `turn.completed.usage`（input/cached_input/output/reasoning_output tokens） |
| 交互轮次 | 统计 `turn.started`/`turn.completed` 事件数 |
| 工具调用 | `item.started`/`item.completed` 的 item 类型（command_execution / file_change / mcp_tool_call / web_search） |
| 成功率 | `turn.failed` / `error` 事件 + exit code；`--output-schema` 结构化自报告 |
| 产物 diff | `item.completed` 的 `file_change` 事件 + git diff；CI 模式（patch artifact）官方文档有完整示例 |

---

## 4. Aider（scripting、git、commands、FAQ 文档）

### 4.1 可编程入口

**CLI 单发模式**：

```bash
aider --message "任务描述" file1.py \
  --yes \                 # 全部确认自动 yes
  --no-stream \
  --model <model> --api-key <provider>=<key>
```

- `--message` / `-m` / `--message-file`：单条消息，处理完即退出（禁用聊天模式）。
- `--yes`、`--auto-commits`/`--no-auto-commits`、`--dirty-commits`/`--no-dirty-commits`、`--dry-run`、`--no-git`。
- `--verbose --no-pretty`：输出原始 LLM 往返数据。
- 环境变量支持每个选项（`AIDER_MESSAGE`、`AIDER_YES` 等），适合 CI。

**Python API**（scripting.md）：

```python
from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput

io = InputOutput(yes=True)
coder = Coder.create(main_model=Model("..."), fnames=[...], io=io)
coder.run("任务描述")      # 单条指令，返回后可继续
coder.run("/tokens")       # 可执行 in-chat 命令
```

官方声明：**Python API 非官方支持、无向后兼容承诺**。

### 4.2 权限与沙箱

**无沙箱、无权限系统**。Aider 在用户环境直接运行；只有 `--dry-run`（不改文件）和 git 本身兜底。不适合在不可信任务上裸跑。

### 4.3 度量采集（四家中最弱）

| 指标 | 采集方式 |
|---|---|
| token | `/tokens` 命令报告当前上下文用量；`--verbose` stdout 解析；**无结构化 JSON 字段** |
| 交互轮次 | 概念不适用——`--message` 是单发模型，多轮需多次 `coder.run()` 自己驱动 |
| 工具调用 | 无工具调用抽象（非 agent-loop 架构）：文件编辑走 edit format diff；`/run` `/lint` `/test` 可执行命令并回灌输出 |
| 成功率 | exit code；产物测试 |
| 产物 diff | **最成熟**：默认 auto-commit，author/committer 带 `(aider)` 标记、Conventional Commits 消息，`/undo` 可回滚；或 `--no-auto-commits` 后 `git diff` |
| 会话记录 | `.aider.chat.history.md`（markdown 聊天记录，官方 FAQ 确认） |

---

## 5. 横向对比矩阵

| 能力 | CodeBuddy Code | Claude Code | Codex CLI | Aider |
|---|---|---|---|---|
| 非交互 CLI | ✅ `codebuddy -p` | ✅ `claude -p` | ✅ `codex exec` | ✅ `aider --message` |
| SDK | ✅ TS + Python（预览） | ✅ TS + Python | ⚠️ 无官方本地 SDK（有 GitHub Action / app-server） | ⚠️ Python API（非官方支持） |
| JSON/JSONL 事件流 | ✅ `stream-json` | ✅ `stream-json` | ✅ `--json` | ❌ |
| token 用量字段 | ✅ `total_cost_usd`、usage | ✅ `usage`/`modelUsage`/`total_cost_usd` | ✅ `turn.completed.usage` | ❌（`/tokens` 文本报告） |
| 轮次统计 | ✅（result 统计，字段未全列） | ✅ `num_turns` | ✅ turn 事件计数 | ❌（单发模式） |
| 工具调用事件 | ✅ tool_use 块 + 任务事件 | ✅ tool_use 块 | ✅ item 级事件（command/file_change/mcp） | ❌（非 agent-loop） |
| max-turns 限界 | ✅ `--max-turns` | ✅ `--max-turns` | ⚠️ 配置项（文档未列 CLI flag） | ❌ |
| JSON Schema 结构化输出 | ✅ `--json-schema` | ✅ `--json-schema` | ✅ `--output-schema` | ❌ |
| 退出码语义 | ⚠️ 文档未列具体值 | ✅ 0/非零/143 | ✅ error 事件 + 退出 | ⚠️ 未文档化 |
| 权限模式 | ✅ 6 档 + allowedTools | ✅ 6 档 + allowedTools | ✅ 沙箱三档 + 审批策略 | ⚠️ 仅 `--yes` / `--dry-run` |
| OS 级沙箱 | ✅ bubblewrap/Seatbelt + 容器/E2B | ⚠️ 同源 sandbox-runtime（未在本调研详查） | ✅ Seatbelt / bwrap+seccomp + 网络代理 | ❌ |
| 配置隔离 | ✅ `--setting-sources` / SDK 默认不加载 | ✅ `--bare` | ✅ `--ignore-user-config` | ⚠️ 选项级环境变量 |
| 产物 diff | git diff（harness 自采） | git diff（harness 自采） | file_change 事件 + git diff | ✅ auto-commit + `(aider)` 归因 |
| 多轮会话续跑 | ✅ `--resume`/`--continue` | ✅ `--resume`/`--continue` | ✅ `codex exec resume` | ✅ Python `coder.run()` 串联 |

## 6. 对测量协议（#6）的约束与启示

1. **harness 骨架可行**：每任务 = fresh git worktree/clone（Codex 强制要求 git 仓库，正好统一）→ headless CLI 单发执行（固定 `--model`、权限模式、`--max-turns`、配置隔离 flag）→ 捕获 JSONL 流 → `git diff`/commit range 收产物 → 跑任务验收测试判成功率。此骨架对四家全部成立（Aider 需降级：无 JSONL，token 靠文本解析）。
2. **指标分两家口径**：
   - CodeBuddy / Claude Code / Codex：token、轮次、工具调用可从结构化输出自动采集，跨家可比但字段名不同，需 harness 做归一化层（建议内部统一为：input_tokens、output_tokens、cached_tokens、turns、tool_calls[]、wall_time_ms、cost_usd）。
   - Aider：只能测「成败 + diff + 粗粒度 token」，建议 Aider 不进核心测量集或单列。
3. **成功率必须 harness 判定**：agent 的 exit code 只说明进程结局（且 CodeBuddy/Aider 退出码语义未文档化）；「任务成功」= 验收测试通过 + diff 符合任务规约。三家支持 JSON Schema 自报告，可作低成本辅助信号但不能当真值。
4. **分数稳定的固定清单**（每家逐项钉死并记录进运行快照）：模型 ID 及版本、权限模式、allowedTools 集合、max-turns、配置来源（CodeBuddy `--setting-sources`/SDK 默认隔离；Claude `--bare`；Codex `--ignore-user-config`）、autocompact 窗口、网络开关。Claude Code 的 `system/init` 事件（model/tools/mcp_servers/version）是现成的运行快照格式，可作为 CogniCode 运行元数据的参考结构。
5. **沙箱是双刃剑**：Codex 的 workspace-write 默认保护 `.git` 只读，会挡住「让 agent 自己 commit」的协议设计——产物采集建议统一放在 harness 侧（agent 只改工作区，harness 收 diff），这也让四家行为一致。CodeBuddy 需注意 `-y` 在无沙箱时的风险，基准任务跑批建议 `sandbox.enabled` + `autoAllowBashIfSandboxed` 或容器 `--sandbox`。
6. **超时与失控**：三家均可用外层 `timeout` 包裹（CodeBuddy 文档示例即如此）；Claude Code 有 SIGTERM→143 的干净退出语义；`--max-turns` / `maxBudgetUsd`（Claude SDK）是内建的失控熔断。
7. **CodeBuddy 文档空缺需实测补齐**：headless JSON result 的完整 schema、result 统计字段名、退出码值——harness 开发第一步应做一次字段核对实测（这属于 #6 测量协议的前置实验）。

## 来源（均为一手文档，2026-08-20 抓取）

**CodeBuddy Code**（官方 docs，cnb.cool/codebuddy/codebuddy-code）：
- 无头模式：https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/headless.md
- CLI 参考：https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/cli-reference.md
- Agent SDK：https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/sdk.md
- Bash 沙箱：https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/bash-sandboxing.md
- 文档地图：https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/codebuddy_code_docs_map.md

**Claude Code**（官方 docs，code.claude.com）：
- Headless：https://code.claude.com/docs/en/headless
- CLI 参考：https://code.claude.com/docs/en/cli-reference
- Agent SDK（TypeScript，消息/usage 字段）：https://code.claude.com/docs/en/agent-sdk/typescript

**Codex CLI**（官方 docs，developers.openai.com / learn.chatgpt.com）：
- 非交互模式：https://developers.openai.com/codex/noninteractive
- CLI 概览与命令参考：https://developers.openai.com/codex/cli 、https://learn.chatgpt.com/docs/developer-commands?surface=cli
- 审批与沙箱：https://learn.chatgpt.com/docs/agent-approvals-security
- GitHub 仓库 exec 文档（指向 noninteractive）：https://github.com/openai/codex/blob/main/docs/exec.md

**Aider**（官方 docs，aider.chat）：
- Scripting：https://aider.chat/docs/scripting.html
- Git 集成：https://aider.chat/docs/git.html
- In-chat 命令（/tokens 等）：https://aider.chat/docs/usage/commands.html
- FAQ（.aider.chat.history.md）：https://aider.chat/docs/faq.html
