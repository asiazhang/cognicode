# pi vs CodeBuddy：扩展层定制能力对照清单

> 票：#27（wayfinder:research，评估 pi 替代 CodeBuddy 作为 harness 执行者）。调研日期：2026-08-25。pi 侧依据官方文档 extensions.md / sdk.md / skills.md / prompt-templates.md / themes.md / rpc.md（本机 0.84.3 安装）；CodeBuddy 侧依据 #25 实测（docs/research/codebuddy-schema.md）与 #3 调研（docs/research/agent-driving.md §1，CodeBuddy hooks `PreToolUse`/`PostToolUse`、Agent SDK、`--allowedTools` 细粒度规则）。
>
> 用途：评估「用 pi 做 harness 执行者时，能否达到或超过 CodeBuddy 的定制/观测能力」。矩阵中「pi 独占」= CodeBuddy 无对应能力或显著弱于 pi。

---

## 1. 定制点 × 能力矩阵

| 定制点 | pi | CodeBuddy | 结论 |
|---|---|---|---|
| **工具白名单/黑名单** | `--tools` / `--exclude-tools`（CLI，支持内置+扩展+自定义工具名）；SDK `tools`/`excludeTools`/`noTools` | `--tools`（内置白名单，`""` 全禁）；`--allowedTools`/`--disallowedTools`（**支持 `Bash(git commit:*)` 前缀细粒度规则**） | ⚖️ 同级，CodeBuddy 粒度更细（规则语法） |
| **工具调用拦截（权限门）** | 扩展 `pi.on("tool_call")`：**可 block、可原地改参数、可 `terminate`**；`tool_result` 可改结果 | SDK hooks `PreToolUse`/`PostToolUse`（可拦截记录）；CLI 非交互无权限提示（#25 §4.3，被拒走 tool_result 文本） | ✅ **pi 独占优势**：拦截是扩展层一等能力（`tool_call` 事件），CLI 形态即可用；CodeBuddy CLI 非交互被拒只回文本、`permission_denials` 恒空（#25），需靠 SDK 才有 hooks |
| **自定义工具** | 扩展 `pi.registerTool()`（TypeBox schema、流式 `onUpdate`、嵌套 usage 上报、`terminate` 早停、覆盖内置工具、动态工具加载 `setActiveTools`）；SDK `defineTool`/`customTools` | SDK 自定义工具（预览 v0.1.0+，接口可能变动）；CLI 侧无 | ✅ **pi 独占/显著优势**：CLI+RPC 形态即可注册自定义工具（`-e` 加载扩展）；CodeBuddy 自定义工具基本绑定 SDK |
| **会话级聚合统计** | RPC `get_session_stats`（tokens/cost/toolCalls/contextUsage） | result 消息 `usage`/`modelUsage`/`_meta.usageByCategory`（#25 §2.4） | ⚖️ 同级，CodeBuddy 的 `_meta.usageByCategory`（systemPrompt/tools/mcp/skills 拆分）pi 无对应 |
| **事件流观测** | `tool_execution_start/update/end`（含 `toolCallId` 关联、`args` 为对象、`isError`）；`message_update` delta 流；`agent_settled` 终局 | stream-json 的 `tool_use` 块 + `tool_result`；`result` 汇总事件 | ✅ **pi 独占优势**：显式工具执行事件（CodeBuddy 靠消息块推断）；`args` 是对象（CodeBuddy `function_call.arguments` 是 JSON 字符串需二次解析，#25 §1.3） |
| **扩展事件 hooks 全集** | `session_start`/`session_shutdown`/`session_before_switch`/`session_before_fork`/`session_before_compact`/`input`/`before_agent_start`/`context`/`tool_call`/`tool_result`/`model_select`/`project_trust`/`before_provider_headers`/`before_provider_request`/`after_provider_response` 等 ~25 类 | SDK hooks：`PreToolUse`/`PostToolUse`/`SessionStart`/`SessionEnd` 等（文档列举较少） | ✅ **pi 独占优势**：事件面宽得多，且**粒度更细**（`before_provider_request` 可改 provider payload、`session_before_fork` 可取消 fork/clone）；CodeBuddy 聚焦工具前后 hook |
| **权限/信任（CLI 非交互）** | `--no-approve`/`--approve` + `defaultProjectTrust`；非交互不弹信任框（usage.md 明示）；`project_trust` 事件可编程决策 | `-y`/`--permission-mode` 6 档；非交互被拒只回文本（#25 §4.3） | ⚖️ 同级偏 pi：pi 的信任决策可被扩展接管（`project_trust` 事件返回 yes/no），CodeBuddy CLI 无编程化权限决策 |
| **上下文注入控制** | `--no-context-files`（实测彻底关闭 AGENTS.md/CLAUDE.md）；`--system-prompt`/`--append-system-prompt`；扩展 `before_agent_start` 可改 system prompt | `--setting-sources`（实测无法完全清空注入，#25 §4.4：`project`/`local` 会注入 memory 提示） | ✅ **pi 独占优势**：可复现性关键——pi 的注入能完全关掉；CodeBuddy 的 memory 提示去不掉 |
| **项目资源信任门** | `--no-approve` 忽略 `.pi/settings.json`、项目扩展、`.agents/skills` | 无对应 CLI flag（靠 `--setting-sources` 收窄） | ✅ pi 独占 |
| **skills（技能包）** | 实现 Agent Skills 标准（agentskills.io）：`~/.pi/agent/skills/`、`.pi/skills/`、`.agents/skills/`（含 Claude Code/Codex 技能目录直接复用）；`--no-skills` 关闭；`/skill:name` 命令 | 有 skills 概念（#25 §2.4 `_meta` 有 skills 类别），但 CLI 文档未列技能加载/隔离 flag | ✅ **pi 独占/显著优势**：技能标准实现 + 跨 harness 技能复用（可直接用 `~/.claude/skills`/`~/.codex/skills`，skills.md 明示） |
| **prompt templates** | `.pi/prompts/*.md`（参数展开 `$1`/`${@:-default}`）；RPC `prompt` 可展开 `/template`；`--no-prompt-templates` | 无对应（CodeBuddy 有 slash commands 但为内置清单，非文件模板） | ✅ pi 独占 |
| **RPC 命令扩展** | 扩展 `pi.registerCommand()` 注册 `/cmd`，RPC `prompt "/cmd"` 可直接执行（rpc.md 明示）；`get_commands` 列出 extension/prompt/skill 三类命令 | SDK `query()` 为主；CLI 无命令扩展面 | ✅ pi 独占 |
| **模型/provider 注册** | 扩展 `pi.registerProvider()`（动态 provider、OAuth、`refreshModels`、流式 API）；`--list-models` | 文档未列 CLI 侧 provider 扩展 | ✅ pi 独占 |
| **会话树/分支** | 会话是 append-only 树（`get_entries`/`get_tree`/`fork`/`clone`，entry id 可作持久游标）；SDK `SessionManager` | CodeBuddy 有 session 概念，树/分支未文档化 | ✅ pi 独占（对 harness 分支实验有价值） |
| **沙箱** | **无 OS 级沙箱**（usage.md 明示不内置；靠扩展工具 operations 代理、容器/tmux 外部方案） | **Bash 沙箱**（bubblewrap/Seatbelt + 网络代理 + 容器/E2B `--sandbox`，#3 §1.2） | ❌ **CodeBuddy 显著优势**：OS 级隔离是 pi 明确不内置的（设计取舍）。pi 侧需 harness 自己加沙箱（容器/扩展） |
| **输出截断** | 内置 50KB/2000 行截断 + 截断工具函数（`truncateHead`/`truncateTail`） | 未文档化 | ✅ pi 独占（对避免上下文膨胀重要） |
| **扩展错误隔离** | `extension_error` 事件 + 「扩展抛错 agent 继续」；`tool_call` 错误 fail-safe 阻塞 | 未文档化 | ✅ pi 独占 |

---

## 2. 定制点分类结论

### 2.1 pi 独占或显著优于 CodeBuddy（harness 可利用）

1. **工具执行事件是显式一等事件**（`tool_execution_start/update/end` + `toolCallId` + 对象 `args`）——harness 采集工具调用不需解析消息块，比 CodeBuddy stream-json 的消息块推断更稳。
2. **CLI/RPC 形态即可编程定制**：自定义工具、命令、事件 hooks 全部走 `-e` 加载的扩展，不需要像 CodeBuddy 那样绑定预览版 SDK。RPC 模式扩展照样跑（`ctx.mode=="rpc"`）。
3. **配置注入可完全关闭**（`-nc` + `--no-approve` + `--no-skills`/`--no-extensions` 组合）——CodeBuddy 的 `--setting-sources` 做不到完全清空（#25 §4.4）。
4. **技能标准实现 + 跨 harness 复用**：`~/.agents/skills/`、`.claude/skills`、`.codex/skills` 直接可用；对「技能注入会不会影响测量」的对照实验是现成工具。
5. **RPC 双向可编程**：`prompt "/cmd"` 直接跑扩展命令、`extension_ui_request/response` 子协议、`get_commands` 发现面——harness 可把「验收断言」「结构化自报告」做成扩展命令经 RPC 触发。
6. **会话树 + 持久游标**（`get_entries since`）对多轮/分支实验天然支持。

### 2.2 CodeBuddy 显著优于 pi（harness 需补）

1. **OS 级沙箱**：CodeBuddy 内置 bubblewrap/Seatbelt + 网络代理 + 容器/E2B（#3 §1.2）；pi 设计上不内置（usage.md「Design Principles」明示：无内置 MCP、sub-agent、权限弹窗、plan mode、todo、background bash——都靠扩展）。**harness 用 pi 跑不可信任务必须自带沙箱**（容器/fresh worktree 是最小兜底，与 #3 §6 的既有结论一致）。
2. **`--allowedTools "Bash(git commit:*)"` 细粒度规则语法**：CodeBuddy 比 pi 的纯工具名白名单更细（可按工具参数模式放行）。pi 侧等价能力要靠扩展 `tool_call` 拦截自己写规则。
3. **上下文占用归因**（`_meta.usageByCategory` 按 systemPrompt/conversation/tools/mcp/skills 拆分，#25 §2.4）：pi 只有 `contextUsage` 总量。需要归因时 pi 侧得用 `before_agent_start` 的 `systemPromptOptions` + 事件 usage 自行估算。

### 2.3 同级（harness 选型不影响）

- 工具白名单/黑名单（粒度除外）、会话级 token 统计、退出码语义（0/1/124 两栈一致）、成本字段不可用（两栈恒 0）。

---

## 3. 对 harness 选型的直接启示

1. **pi 替代 CodeBuddy 作为执行者，观测面不降反升**：事件级 + 会话级统计齐全，工具调用采集更直接，且 CLI 形态就能挂自定义工具/命令做「验收自报告」（如注册 `submit_result` 工具返回结构化 JSON，`terminate: true` 早停——extensions.md 的 `structured-output.ts` 模式正是 #3 §6 想要的低成本自报告信号）。
2. **沙箱是 pi 的唯一硬缺口**：CodeBuddy 的 `--sandbox`/bubblewrap 无对应。若基准任务不可信，pi 侧必须容器化或坚持 fresh git worktree + 只读工具集（`--tools read,grep,find,ls` 实测有效）。
3. **测量隔离固定清单（pi 版）**：`-p --mode rpc --no-session --no-approve -nc --no-skills --no-extensions --no-prompt-templates --no-themes --tools <固定集>` + 预热 `pi --list-models`（见 pi-schema.md §8 的模型目录刷新注意）。
4. **RPC 扩展 UI 子协议**：若 harness 加载会弹 `ctx.ui.confirm/select` 的扩展（如权限门扩展），RPC 下必须实现 `extension_ui_response` 应答或给对话框设 timeout，否则挂起。

---

## 4. 来源

**pi（本机 0.84.3 安装文档）**：`docs/extensions.md`（事件 hooks、`tool_call`/`tool_result`、`registerTool`/`registerCommand`/`registerProvider`、自定义 UI、错误处理、Mode Behavior 表）、`docs/sdk.md`（createAgentSession/tools/excludeTools/noTools、SessionManager 树 API）、`docs/skills.md`（Agent Skills 标准、跨 harness 复用）、`docs/prompt-templates.md`、`docs/themes.md`、`docs/rpc.md`（RPC 命令 + 事件 + 扩展 UI 子协议）、`docs/usage.md`（CLI 参考、`--no-*` flag、非交互信任行为、Design Principles）。
**CodeBuddy**：`docs/research/codebuddy-schema.md`（#25 实测：`--allowedTools`/`--disallowedTools`、hooks、SDK、`permission_denials` 恒空、`_meta.usageByCategory`）、`docs/research/agent-driving.md`（#3：`--setting-sources`、Bash 沙箱、容器/E2B、SDK 选项）。
