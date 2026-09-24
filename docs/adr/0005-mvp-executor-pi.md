# 测量用执行者改用 pi：可定制性优先于 CodeBuddy 的成熟路径


> **Status**: superseded by [ADR-0006](0006-relocate-to-ai-debt-identification.md)——动态测量主线随重定位封存删除，本文仅作历史决策记录。
CogniCode 动态测量的执行者（无头 CLI agent）由 CodeBuddy 2.137.1 改为 pi 0.84.3（同经 tencent-copilot 网关、同模型底 deepseek-v4-flash-ioa，差异在 agent 层）。#26 实测证据链（#27 schema / #28 真实任务冒烟 / #29 扩展层定制实测）显示：pi 的事件 schema 完整支撑 harness 采集（`tool_execution_*` 显式事件、`get_session_stats` 会话级统计、`agent_settled` 终局，轮次/时长/结局由 harness 自算），且扩展系统在 CLI/RPC 形态即可编程定制（`registerTool`/`registerCommand`/事件 hooks，4 定制点全实测通过）。CodeBuddy CLI 面窄、可定制性弱（自定义工具/命令绑定预览版 SDK），harness 实际用不到其大量功能；「可定制性」是取舍的决定性标准。代价已排定：采集字段须自算、5 个已实测坑须 harness 内置规避（provider 目录刷新预热、stdin 保持打开、显式 `-e` 加载 provider 扩展、stats 等 `agent_settled`、`--no-*` 全禁组合在带项目资源 cwd 触发 `model: unknown`）、pi 无 OS 级沙箱——后者与 ADR-0003 同向（CodeBuddy 实际使用也未开沙箱），由 fresh worktree + 只读工具集兜底。pi 协议（0.84.3）仍在演进，本决策接受该风险，CodeBuddy 路径保留于 executor 接口缝后可回退。

## Considered Options

- **维持 CodeBuddy（不替换）**：schema 已实测钉实（#25）、#19 实现路径已铺。被否：可定制性弱，扩展能力绑定预览版 SDK，演进空间小。
- **双执行者**：可对照、可回退，但 MVP 双倍实现工作量；#26 已把「双执行者归一化层」划为 out of scope。被否（MVP）。
- **替换为 pi**：采纳。可定制性最强（CLI/RPC 形态编程定制）、配置隔离更彻底（`-nc`+`--no-approve` 可完全清空注入，CodeBuddy `--setting-sources` 做不到）、观测面不降反升；代价见上。
