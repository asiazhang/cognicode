# bug 注入为主的任务源与 harness 唯一判卷权

CogniCode 的修改/修复类任务采用 bug 注入（SWE-smith 式）而非 commit 挖掘（R2E-Gym 式）：注入式在 tree-sitter 层可泛化、不依赖仓库 PR 历史（冷启动仓库可用）、注入物必须被既有测试抓住而令 F2P 天然成立；commit 挖掘对新仓库/squash 历史不可用且抽取质量难控，故不进首发。判卷上，尽管 CodeBuddy/Claude Code/Codex 均支持 `--json-schema` 结构化自报告，CogniCode 仍把对错判定权完全交给 harness 侧客观判定（位置匹配/测试红绿/退出码），自报告仅约定交卷格式：自报告内容入判定会引入「模型说服力」噪声，违背分数稳定的硬需求。

## Considered Options

- **commit 挖掘任务源**：任务更真实，但冷启动仓库不可用、跨语言抽取质量难控。被否（首发）。
- **agent 自报告参与判定**：实现最省（不用建客观判定），但模型可能「说对了做错了」或反之，分数稳定性不可保。被否。
