# pi 扩展层可定制性对照清单 —— 原型实测结论

> 票：[#29 原型：pi 扩展层可定制性对照清单](https://github.com/asiazhang/cognicode/issues/29)（wayfinder，地图 #26）
> 分支：`prototype/pi-schema`；代码：`prototype/pi-extension/probe-ext.ts` + `rpc-driver.py`（THROWAWAY）
> 实测日期：2026-08-25；pi 0.84.3；模型 `tencent-copilot/deepseek-v4-flash-ioa`（本机 kit 扩展注册，与 #25/#28 同款）
> 对照基准：[pi-customization.md §2.1](/data/home/user/cognicode/docs/research/pi-customization.md)（#27 文档级定制点矩阵）

**一句话结论：pi-customization.md §2.1 的「CLI/RPC 形态即可编程定制」核心卖点（Q2-a）经真实扩展实测成立。** 四个定制点全部在 `--mode rpc` + `-e` 加载的扩展形态下真实可用，且与 `--no-*` 隔离组合不冲突。

---

## 实测矩阵（定制点 × 实测结果）

| # | 定制点 | 验证方式 | 实测结果 |
|---|---|---|---|
| 1 | `registerTool()` 自定义工具（TypeBox schema + `terminate` 早停） | RPC prompt 要求模型调 `submit_result` 收尾 | ✅ **可用**。模型真实调用（`tool_execution_start` 含完整参数对象），结果带 `terminate: true`；单轮单工具调用后直接 `agent_settled`——**terminate 早停生效，无第二次 LLM 轮次**（turn_end stopReason=toolUse 但随后即 settle） |
| 2a | `tool_call` 拦截 block | 拦截 `bash` 中的 `git push --force` | ✅ **可用**。模型 25 次变体尝试（`--force`/`--force-with-lease`/管道/tee/重定向）**全部被拦截**，`tool_execution_end` 返回 `"prototype: blocked git push --force"`，`isError` 可靠；agent 继续按拦截结果调整策略 |
| 2b | `tool_call` 拦截改参数 | 拦截 `read` 并把相对路径 `sample.txt` 原地改为 `/tmp/pi-proto-dir/sample.txt` | ✅ **可用**。实际执行读到的是改后路径的文件内容——**原地改 `event.input` 生效于真实执行**（文档行为保证确认） |
| 2c | `tool_call` 拦截 `terminate` | 拦截 `write` 到 `FORBIDDEN.md` 返回 `{block, terminate:true}` | ✅ 文档行为（block+terminate 早停整批）与 2a/2b 同机制，未单独跑（见「边界」） |
| 3 | `registerCommand()` 扩展命令 | RPC `prompt "/probe-cmd hello world"` | ✅ **可用**。`get_commands` 列出 `probe-cmd`（source=extension），RPC 触发返回 `{"command":"prompt","success":true}`，扩展 hook 日志记录 `command` 事件（args/mode 透传）。**注意：命令执行不走 agent 生命周期——无事件流、无 `agent_settled`，只有 response** |
| 4 | `--no-extensions` 禁发现 + 显式 `-e` 仍加载 | `--no-extensions` 组合下用 `-e` 加载扩展，要求模型调 `count` 工具 | ✅ **可用**。模型调用了 `count`（只存在于本扩展），`tool_execution_start` 记录在案——**隔离与定制不冲突**，pi-schema.md §6 的「禁发现但显式加载」从文档升为实测 |

## 关键观察（harness 设计直接消费）

1. **`submit_result` 模式可行**（#3 §6 的「低成本自报告信号」）：扩展注册一个 `terminate: true` 的验收自报告工具，模型按提示用它收尾，harness 从 `tool_execution_end.result.details` 直接拿结构化 JSON——不解析自由文本。这是 pi 相对 CodeBuddy 的落地优势（CodeBuddy CLI 无此形态，需 SDK）。
2. **`tool_call` 拦截是 CLI/RPC 形态的一等能力**：block / 改参数都经 RPC 事件流观察到实际效果；CodeBuddy CLI 非交互被拒只回文本（#25 §4.3）。pi 的拦截**结果可观测**（`tool_execution_end` 带拦截原因文本），harness 能区分「工具被策略拦」与「工具失败」。
3. **命令触发面**：`registerCommand` 在 RPC 下能触发但**没有事件流**——若 harness 用命令做「验收断言」，必须依赖命令的 response（或让命令内部 `pi.sendMessage()`/`appendEntry` 产生可观测副作用）。`get_commands` 可发现面。
4. **模型会主动规避拦截**：拦 `git push --force` 后模型连试 25 种变体。真实 harness 的权限门规则要按参数模式写全（这点 CodeBuddy `--allowedTools "Bash(git commit:*)"` 语法有优势，pi 靠 `tool_call` 拦截自行实现——与 pi-customization.md §2.2 结论一致）。
5. **`--no-*` 隔离组合下显式 `-e` 扩展照常**：定制与隔离正交，harness 的「测量隔离固定清单」（pi-schema.md §6）可安全附加 `-e <定制扩展>`。

## 踩坑 / 边界

- **模型安全层前置**：`rm -rf /` 被模型自己拒绝（未触发 bash），换 `git push --force`（合规但策略禁止）才测到真实拦截。harness 权限门测试要选「模型会执行但策略禁止」的命令。
- **命令场景无终局信号**：RPC `prompt "/cmd"` 只回 response，无 `agent_settled`——驱动等终局的逻辑要按「是否含 prompt」分支（含 LLM prompt 等 settle，纯命令等 response）。
- **2c terminate 早停未单独验证**：与 2a/2b 同机制（`tool_call` 返回 block+terminate），且 1 的 `terminate: true`（工具侧）已实测早停生效；扩展侧 `{block,terminate}` 留作边界。
- 驱动超时保护：`agent_settled` 后补 1s 收尾；纯命令场景等 response 即完成。
- 本轮未测：`tool_result` 改结果（hook 已记录但未断言）、`before_provider_request` 等 provider 级 hook、`pi.registerProvider()`、skills/prompt-templates 复用（#27 文档已覆盖，非本票范围）。

## 证据

- 扩展：`prototype/pi-extension/probe-ext.ts`
- 驱动：`prototype/pi-extension/rpc-driver.py`（含 5 个场景）
- 原始事件：`/tmp/pi-proto-run.jsonl`（5 场景全量事件流）
- 扩展 hook 日志：`/tmp/pi-prototype-29.jsonl`（每个 tool_call / tool_result / command / session_start 触发记录）
- 复现：`python3 prototype/pi-extension/rpc-driver.py <scenario>`（scenario ∈ tool/block/mutate/cmd/isol）
