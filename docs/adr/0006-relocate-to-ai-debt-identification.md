# 重定位为 AI 技术债识别工具：六维引擎降级为失败模式判据

CogniCode 从「AI 原生程度打分工具」（动态测量驱动、六维度聚合出分）重定位为「AI 技术债识别与展示工具」。背景：AI 让写代码变便宜、瓶颈后移到验证与理解（[AI 开发痛点研究](../research/ai-dev-pain-points-synthesis.md)），且业界技术债体系的空档被双向印证——所有既有体系的利息受损者都是人类，无人以「下一个 agent 的实际表现」为判据（[债分类学研究](../research/debt-taxonomy.md)）。CogniCode 已有的六维度失败模式语言恰好是这个空档缺的判据语言，故转型不是推翻而是重定位。决定：

1. **债的定义**锚定「对 AI 不友好的债」：不归因谁写的，只看它是否会让下一个 agent 迷路、犯错或爆炸。收录判据只认 agent 失败形态，业界好实践不算数（防止 SonarQube 换皮）。
2. **六维度引擎的处置**：六维从「评分模型的聚合轴」降级为「债判据的失败模式词汇表」——每个债类型的判据以它引发哪类 agent 失败模式来论证（如 duplicate-code → 变更安全性+效率，flaky-test → 可诊断性）。CONTEXT.md 六维词条继续作为判断轴词汇表持有；动态测量主线（harness/生成/判卷/聚合/敏感性）随重定位失效并已删除（commit 3adda6f，~6.9K 行），archive/pre-relocation tag 保留可回溯；复用资产（符号提取、静态信号、模块深度判定协议、探测定位面）收缩进 scripts/ 服务于债检测。
3. **检测方法学**：两档——确定性档（可复现的脚本提取，工件落 `.cognicode/debt-scan/`）+ LLM 推断档（对确定性预筛的候选做判定，标置信度，一等公民）。证据等级语言（确证信号 vs 风险信号）贯穿报告。
4. **分类学**：七族 20 类型（A 结构 / B 测试 / C 文档与知识 / D 依赖与环境 / E 进程含 F 并入 / G 架构形状），类型清单与逐类型判据的权威在 [criteria/](../../cognicode-debt/criteria/)（判据文件 + 逐类型 rules 详解），分类学论证见 [debt-types.md](../research/debt-types.md)；收录与可检测性解耦，留册类型（dead-code、dep-stale、lockfile-drift、vendored-dep）记录捡回条件。
5. **首发形态**：skill 集合 `cognicode-debt`——单 skill 目录自包含，SKILL.md 只做编排协议，判据按族外置、扫描一族一子代理（免上下文污染）；管线 = 脚本确定性提取 → 分族子代理（证据包 16K 预算、单 JSON+置信度回传）→ 主会话单写手终写 DEBT.md。交付载体 = 按严重度排序的债项清单（位置 + 类型 + 为什么是债 + 修复建议），落盘仓库内 `DEBT.md`，可 diff、可追债项增减；重跑即销账（无状态字段，git 即审计）。CLI 降为脚本副产品。
6. **MVP 范围**：静态两档检测 + DEBT.md 清单。动态测量（跑真实 agent 做实证校验，如变异性测试 oracle、有效上下文校准）为二期，凭 DEBT.md 样例实战后的成本证据再启动。热力图/趋势等聚合视图后续。
7. **目标用户**：个人开发者与团队负责人双受众，首发文案以个人开发者为主。

本 ADR 只记录重定位决策本身；方法学细节的唯一权威分别是：术语表 [CONTEXT.md](../../CONTEXT.md)、判据 [criteria/](../../cognicode-debt/criteria/)、分类学与空档论证 [debt-types.md](../research/debt-types.md) / [debt-taxonomy.md](../research/debt-taxonomy.md)、skill 结构 [ADR-0006 决议出处 #42](https://github.com/asiazhang/cognicode/issues/42)。全链决策过程见 [Wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39) 及其已关子票。

## Consequences

- 动态测量主线的 ADR-0001（静动双测量聚合）整体失效；0002/0003/0005（判卷权、执行器配置、pi 执行者）随 harness 封存失效，仅作历史决策记录；0004（模块深度为归因信号）的精神延续——LLM 判定不产分、只做参考性输出，在债识别中体现为「LLM 推断标置信度、不伪装实锤」。
- 唯一真值原则（同一知识多份且未声明权威即债）升为全方法论判断原则，已入 CONTEXT.md；本 ADR 与 criteria/ 的分工是其自举——决策记录不复制判据内容。
- 新工作按此定位展开：MVP 剩余工作 = DEBT.md 样例（#43）+ skill 执行协议（SKILL.md 本体）；严重度跨族可比性、重复检测工具选型等留雾区，见地图「Not yet specified」。
