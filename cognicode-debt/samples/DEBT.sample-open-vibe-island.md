# DEBT.md — Open Island 技术债清单

> 本文件由 **cognicode-debt**（AI 技术债识别 skill）生成，请勿手工编辑——重跑扫描即刷新。
> 债的定义：对 AI 不友好的债——会让下一个编程 agent 迷路、犯错或爆炸的技术债。不归因谁写的。

- **扫描日期**: 2026-09-24
- **扫描基准**: `b50f87a`（2026-09-15）
- **检测档**: 确定性脚本提取 + LLM 推断（标置信度）
- **未覆盖族**: D 依赖与环境（无文件级配置声明面，macOS app 配置在 UserDefaults）、G 架构形状（粗检层间依赖干净，候选未过线）
- **销账**: 修复后重跑扫描，对应条目自动消失；本文件不带状态字段，git 历史 + diff 即审计轨迹

证据等级：**确证** = 可复现的静态实锤；**风险** = 静态反模式命中 / LLM 推断，未动态验证。

---

## 高

### doc-rot@AGENTS.md::worktree-links

**位置**: AGENTS.md:46, 51, 61
**类型**: 文档与知识债 — 文档腐烂（代理上下文文档通道）
**证据等级**: 确证（路径断链，确定性比对）
**置信度**: 高

**为什么是债**: AGENTS.md 作为 agent 的第一信源，其 worktree 工作流规则硬编码维护者本机绝对路径（`/Users/wangruobing/Personal/open-island`）。61 行链接 `[docs/worktree-workflow.md](/Users/wangruobing/...)` 在任何其他 clone 中点开即断；46/51 行使 sibling worktree 命名规则在所有非维护者环境不可执行。agent 读到规则却无法照做——文档主动误导（可导航性 + 环境可用性失败模式），失败信号是「链接 404 / 路径不存在」，与代码错误同形，归因被污染（可诊断性）。

**证据**: `AGENTS.md:61` `See [docs/worktree-workflow.md](/Users/wangruobing/Personal/open-island/docs/worktree-workflow.md)`；目标文档本体存在于仓库相对路径 `docs/worktree-workflow.md`。

**修复**: 61 行改为仓库相对链接 `docs/worktree-workflow.md`；46/51 行改为基于 clone 位置的相对推导（如 `<repo-parent>/open-island-<topic>`）；同步检查 docs/worktree-workflow.md 内是否同样硬编码。

---

### duplicate-code@docs-matrix::supported-agents

**位置**: README.md:51-107 · README.zh-CN.md:51-98 · docs/product.md:22-48（同一重复簇，三份副本）
**类型**: 结构债 — 重复代码（唯一真值违反，文本形态）
**证据等级**: 确证
**置信度**: 高

**为什么是债**: 支持矩阵（agent/terminal 支持状态）存在三份副本且已实际分叉——README 15 行、README.zh-CN 14 行、docs/product.md 11 行；Warp 状态直接矛盾（README「Full / 完整支持」vs product.md「Planned」）；Gemini hook 事件列表两份说法不一致。且两份代理文档对权威源各执一词：CLAUDE.md 称「README.md — that's the single source of truth」，AGENTS.md 称「Keep product scope in docs/product.md」。新增 agent 时（本项目高频事件）agent 依读到的不同文档改不同文件，改 A 忘 B 已实际发生（CodeBuddy/Grok 缺于 product.md）。同一知识多份且无权威声明——唯一真值原则最直接的违反（变更安全性 + 可导航性失败模式）。

**证据**: `AGENTS.md:65` vs `CLAUDE.md:63` 权威声明冲突；`docs/product.md:48` `| **Warp** | Planned |` vs `README.md:104` `| **Warp** | Full |`；README:53 「13 agents」含 Cursor/Grok Build，product.md 矩阵缺此二者。

**修复**: 人裁唯一权威源（product.md 或 README 二选一），两份代理文档统一指向它；其余副本改为生成或链接；立即补齐已分叉条目（product.md 补 Cursor/Grok Build、修正 Warp 状态，zh-CN 补 Claude Code Desktop App）。fork 配置句式（Qoder/Qwen/Factory/CodeBuddy ×3 文档 12 处重复，未分叉、低风险）随矩阵收敛自动消解，不单独立案。

---

### monolith-file@Sources/OpenIslandCore/BridgeServer.swift

**位置**: Sources/OpenIslandCore/BridgeServer.swift::BridgeServer（3226 行，~30K token）
**类型**: 进程债 — 巨石文件
**证据等级**: 确证
**置信度**: 高

**为什么是债**: 单 class 承载 socket 传输 + 命令分发 + **7 个 agent 的 hook 处理器家族**（handle*Hook + ensure*SessionExists + synchronize*JumpTarget/Metadata 四件套 ×7）+ 9 个 `Pending*` 待决状态字典 + Claude transcript 增量游标 + 双状态快照管理。agent 改任一 agent 的 hook 行为需同时掌握共享 pending 状态语义、localState/stateSnapshot 覆写约定（79-89 行注释自认非显然）、envelope 发送路径——典型修改需全读 30K token，直逼有效上下文参考线（效率 + 可导航性失败模式）；跨 agent 待决状态靠隐式约定维持，局部修改极易破坏其他 agent 的状态机（变更安全性）。

**证据**: `:5-104` Pending*/ClaudeTranscriptCursor 结构群；`:311` handle(_:) 分发；`:488/628/1037/1194/1313/1433/1668` 七个 handleXxxHook。

**修复**: 按 agent 拆分 handler（每 agent 一个 HookHandler 模块，Pending 状态聚合为显式类型），socket 传输与 hook 语义分层，分发器只留路由。

---

## 中

### duplicate-code@design/v6+v8-bundles::notch-logo-styles

**位置**: design/v6-bundle/ + design/v8-bundle/（跨簇重复 + 簇内多版本并存；副本：notch_v6_locked.jsx ×2、logos_v7.jsx ×2、styles_v3.css ×2 逐字相同，styles_v7.css 已分叉 332 vs 537 行）
**类型**: 结构债 — 重复代码（文本重复簇）
**证据等级**: 确证
**置信度**: 高

**为什么是债**: 同一设计知识（v6 锁定视觉 DNA）跨 bundle 双份副本，styles_v7.css 已静默分叉（v8 版追加 panel-head 样式 41 行）；v6-bundle 内 v3–v7 迭代版本并存且 README 无权威声明（v6-bundle/README.md 是通用 handoff 模板）。缓解信号：v8-bundle/README.md 有部分权威声明（「notch_v6_locked.jsx ← v6 source-of-truth」），但未覆盖 styles 分叉。agent 被要求改 v7 样式时无法判断改哪份；且生产脚本 `scripts/generate-v6-appicon.swift` 以 v6-bundle 的 logos_v7.jsx 为 app icon spec 来源——这是活引用不是纯归档（变更安全性失败模式）。

**证据**: MD5 确证逐字相同：notch_v6_locked.jsx 两份 `b654f7b5…`、logos_v7.jsx 两份 `3112f277…`、styles_v3.css 两份 `fd1bf176…`；styles_v7.css v6-bundle 332 行 vs v8-bundle 537 行（diff 追加 `/* Panel head — slim mode-switch row */` 起 41 行）；v6-bundle 内 notch_v6.jsx 与 notch_v6_locked.jsx diff exit=0。

**修复**: 抽 design/shared/ 存放锁定资产，两 bundle 改引用；v6-bundle/README.md 顶部补权威声明（superseded by v8）；删除逐字重复的 notch_v6.jsx；tmp/ 迭代截图入 .gitignore。

---

### duplicate-code@agent-docs::workflow-restatement

**位置**: CLAUDE.md:37-43 vs AGENTS.md:12-58（工作流重述分叉）
**类型**: 结构债 — 重复代码（唯一真值违反，语义层）
**证据等级**: 风险
**置信度**: 中

**为什么是债**: 同一工作流在两份代理文档中不完全一致重述，至少三处实质分叉：worktree 创建方式（EnterWorktree+local main vs sibling 路径+origin/main——分支基点为行为类断言且未声明哪份优先）、PR draft 政策（AGENTS.md 整段 vs CLAUDE.md 未提）、两份均未声明权威层级。并行多 agent 场景下不同 agent 产出不一致的分支/worktree 布局，集成时冲突且无法归因到文档分叉（变更安全性 + 可诊断性失败模式）。与 doc-rot@docs-matrix 同根（唯一真值），但载体是工作流知识而非数据矩阵，独立成簇。

**证据**: `CLAUDE.md:37` `branched off latest local main` vs `AGENTS.md:50` `Create new worktrees from origin/main`；`AGENTS.md:16-18` draft PR 政策 vs CLAUDE.md:39 无 draft 说明。

**修复**: 声明权威层级（如 CLAUDE.md 开头注明「完整权威工作协议见 AGENTS.md，冲突以它为准」，方向由人裁）；统一分支基点措辞；CLAUDE.md 的 Workflow 节改为摘要+指向。

---

### doc-rot@CLAUDE.md::key-files-entry

**位置**: CLAUDE.md:84
**类型**: 文档与知识债 — 文档腐烂（代理上下文文档通道，断链）
**证据等级**: 确证（路径断链，确定性比对）
**置信度**: 高

**为什么是债**: CLAUDE.md Key files 节断言 `Sources/OpenIslandHooks/main.swift — hook CLI entry`，该文件不存在；实际入口是 `Sources/OpenIslandHooks/OpenIslandHooksCLI.swift`（目录内唯一文件）。agent 按文档直取该路径会扑空，批量引用扫描时得出「入口缺失」错误结论（可导航性失败模式）。误导方向轴判轻：错误在同目录且唯一，一次 ls 即自愈。

**证据**: `CLAUDE.md:84` 原文；`ls Sources/OpenIslandHooks/` 仅返回 OpenIslandHooksCLI.swift。

**修复**: 改为 `Sources/OpenIslandHooks/OpenIslandHooksCLI.swift — hook CLI entry`。

---

### flaky-test@Tests/CodexSessionTrackingTests.swift::rollout-watcher-sleep

**位置**: Tests/OpenIslandCoreTests/CodexSessionTrackingTests.swift:919, 933, 1060, 1123 + Tests/OpenIslandAppTests/AppModelSessionListTests.swift:622
**类型**: 测试债 — 脆弱测试（sleep 蒙眼等待）
**证据等级**: 风险（脆性候选，未动态验证）
**置信度**: 高

**为什么是债**: 5 处蒙眼等待——append 文件行后 `Task.sleep(200ms)` 盲等 watcher（pollInterval 0.05s）消费完再继续，不等条件只等时间。CI 慢时 watcher 未消费即被 stop，`events.contains` 断言随机红——agent 会把时间性红绿误判为自己改坏了 rollout 追踪逻辑，失败归因被污染（可诊断性 + 变更安全性失败模式）。同文件的条件轮询（:460）、deadline 轮询（ClaudeUsageTests:602）、注入延迟模拟（:426）均判为测试自身节拍的合理等待，不计入。

**证据**: 四处 `try await Task.sleep(for: .milliseconds(200))` 后无消费确认即 append/stop；对照合理实现 `CodexAppServerLifecycleTests.swift:53` waitUntil(deadline:condition:) 现成可复用。

**修复**: 测试改为等条件（轮询 recorder.snapshot() 至断言条件满足），复用 waitUntil 模式或暴露事件回调计数。

---

### flaky-test@Tests/CodexAppServerTimeoutTests.swift::wall-clock-assertion

**位置**: Tests/OpenIslandCoreTests/CodexAppServerTimeoutTests.swift:21-33
**类型**: 测试债 — 脆弱测试（时间依赖无注入）
**证据等级**: 风险（脆性候选，未动态验证；有 git 旁证不入判据）
**置信度**: 高

**为什么是债**: `Date()` 起止断言真实墙钟调度延迟，把 CI 机器负载耦合进测试语义。git 旁证：提交 b3738b6（PR #702）刚因 CI 争抢把 elapsed 推到 2.0-2.4s（bound 2.0s）真实 flaky 过一次，放宽到 5s 治标未治本——墙钟依赖仍在，下次调度争抢还会红，agent 会误以为超时机制回归（可诊断性失败模式）。

**证据**: `:21/32` Date() 起止断言；git log b3738b6 "test: loosen CI timing bound"。

**修复**: 二分——保留宽松 smoke（elapsed < 10s 防挂死）+ 精确 fail-fast 断言改为注入 clock 的单元测试（ContinuousClock 注入）。

---

### implicit-contract@Sources/OpenIslandApp/HookInstallationCoordinator.swift::migrateIntentStoreIfNeeded

**位置**: Sources/OpenIslandApp/HookInstallationCoordinator.swift::migrateIntentStoreIfNeeded（契约痕迹 :944-948，唯一调用点 AppModel.swift:1689）
**类型**: 进程债 — 隐式契约
**证据等级**: 风险（存在性候选，全类型最弱档）
**置信度**: 高

**为什么是债**: 调用顺序不变量只存在于 doc 注释：「Must be called only after refreshAllHookStatusAndWait() has returned, otherwise every agent will be recorded as .untouched and legacy users will have their installed hooks **silently forgotten**」。签名无任何强制（非 async、无 precondition、无状态门）。agent 或新调用方在非 async 上下文直接调用可编译通过，静默产出错误 intent 记录——违反后果烈度 = 静默错结果，无崩溃无报错（变更安全性 + 可诊断性失败模式）。

**证据**: `HookInstallationCoordinator.swift:944-948` doc 注释原文；唯一正确调用 `AppModel.swift:1689-1698` 靠 Task 内 await 排序维持。

**修复**: 把前置条件变成签名——方法改为接收刷新后的状态快照参数，或内部自行 await 刷新 + precondition 门。

---

### monolith-file@Sources/OpenIslandApp/AppModel.swift

**位置**: Sources/OpenIslandApp/AppModel.swift::AppModel（1923 行，~20K token）
**类型**: 进程债 — 巨石文件
**证据等级**: 确证
**置信度**: 中

**为什么是债**: @Observable 上帝对象——聚合 6 个 coordinator、~40 个一行转发函数、state 的 didSet 三重隐式副作用（缓存失效 + bridge 快照推送 + 票据修剪）、外观持久化、排序派生。观察票据/缓存失效等不变量只存在于注释（52-77 行），会话相关修改需理解全链副作用才能安全动手（变更安全性 + 效率失败模式）。

**证据**: `:17` class 声明；`:52-58` didSet 三重副作用；`:57-77` 票据机制注释；`:183-224` 转发层。

**修复**: v6 派生（排序/分组/票据/闭岛标签）抽为独立 derivation 模块（纯函数化），转发层按域分文件。

---

### monolith-file@Sources/OpenIslandApp/ProcessMonitoringCoordinator.swift

**位置**: Sources/OpenIslandApp/ProcessMonitoringCoordinator.swift::ProcessMonitoringCoordinator（1600 行）
**类型**: 进程债 — 巨石文件
**证据等级**: 风险
**置信度**: 中

**为什么是债**: 进程 liveness 跟踪 + 5 个 agent 的 uniqueTracked*Session 家族（各自进程匹配与合成会话逻辑）+ TTY 认领 + 跨工具清洗。与 BridgeServer 同型的 per-agent 复制家族 + 共享 reconcile 语义；新增/修改某 agent 的匹配规则需理解主循环与其他 agent 匹配块的共享不变量，家族式复制使 diff 定位困难（效率 + 可导航性失败模式）。

**证据**: `:671/722/773/1016/1122` uniqueTracked{Grok,OpenCode,Gemini,Cursor,Claude}Session 五连；`:1210/1265` adoptProcessTTYs 双版本。

**修复**: per-agent 匹配抽统一协议/泛型骨架，agent 差异参数化。

---

### monolith-file@Sources/OpenIslandApp/HookInstallationCoordinator.swift

**位置**: Sources/OpenIslandApp/HookInstallationCoordinator.swift::HookInstallationCoordinator（1575 行）
**类型**: 进程债 — 巨石文件
**证据等级**: 风险
**置信度**: 中

**为什么是债**: ~12 个 agent 的 hook 安装/卸载/状态刷新 + intent store 迁移 + 健康检查自动修复 + hooks 二进制自更新 + Claude 配置目录管理。改某 agent 的安装逻辑需确认不破坏 intent store 迁移序与健康检查自动修复链（与安装状态共享字段），横切读面大（变更安全性 + 效率失败模式）。

**证据**: `:941-967` intent store 迁移内嵌 install 状态判定；`:519` 健康检查自修复；AppModel.swift:183-224 有 40 个纯转发侧面证明它是多域聚合点。

**修复**: intent store 迁移与健康检查抽独立类型；per-agent 安装参数化收敛。

---

### monolith-file@Sources/OpenIslandApp/Views/IslandPanelView.swift

**位置**: Sources/OpenIslandApp/Views/IslandPanelView.swift::IslandPanelView（2698 行，~26K token）
**类型**: 进程债 — 巨石文件
**证据等级**: 确证
**置信度**: 中

**为什么是债**: 单 SwiftUI View 内嵌开合表面挂载状态机（keepsOpenedSurfaceMounted/openedSurfaceMountGeneration/isPopping 四态联动 + mount 代数机制）与布局深度耦合。UI 微调局部性好，但改过渡/开合行为需重建 26K token 的状态机心智模型，回归面覆盖整个岛屿开合体验（效率 + 变更安全性失败模式）。同仓库对照：AppearanceSettingsPane.swift（1539 行）纯布局局部性好，按「大且必须全读才是罪」不报——本条成立靠的是状态机耦合不是行数。

**证据**: `:107-124` 挂载状态群；`:256` syncOpenedSurfaceMount。

**修复**: 挂载状态机抽为独立 @Observable 状态对象（可单测），View 只消费；opened/closed/transition 三段表面拆子文件。

---

### test-gap@OpenIslandCore::watch-and-installers

**位置**: OpenIslandCore 模块（WatchHTTPEndpoint、Gemini/Kimi/OpenCodePlugin InstallationManager、BridgeTransport、CursorSessionRegistry、TimedCache 等 11 文件）
**类型**: 测试债 — 测试缺口（模块级上卷）
**证据等级**: 确证（保护不存在，符号触达口径）
**置信度**: 高

**为什么是债**: 约 110/745 声明（~15%）零测试触达，且是结构性保护空洞而非规模效应：同构模块 ClaudeSessionRegistry/OpenCodeSessionRegistry 有专测而 CursorSessionRegistry 无；WatchHTTPEndpoint 500 行（配对码 120s TTL 过期、token 撤销、SSE 连接管理）零触达；三个安装管理器**直接写用户家目录配置文件**（settings.json 合并/备份/卸载恢复）却零保护；TimedCache 是 @unchecked Sendable 手写锁并发原语。agent 重构这些区域无法自证没炸（变更安全性 + 可诊断性失败模式）。

**证据**: grep 'WatchHTTPEndpoint|WatchPermissionEvent|GeminiHookInstallationManager|CursorSessionRegistry' Tests 全目录 0 命中；对照 ClaudeSessionRegistryTests.swift:11 存在；WatchHTTPEndpoint.swift:113-200 配对码 TTL。

**修复**: WatchHTTPEndpoint 配对码过期/重生补单测（Date 可注入）；安装管理器复用 Claude 侧 temp 目录模式；CursorSessionRegistry 抄 ClaudeSessionRegistryTests 往返；TimedCache 补 TTL 与并发 miss。

---

### test-gap@OpenIslandApp::coordinator-layer

**位置**: OpenIslandApp 模块 coordinator/服务层（TerminalJumpTargetResolver、SessionDiscoveryCoordinator、OverlayUICoordinator、CodexAppServerCoordinator、TerminalTextSender 等）
**类型**: 测试债 — 测试缺口（模块级上卷）
**证据等级**: 确证（保护不存在，符号触达口径）
**置信度**: 中（口径已知假阳性：AgentSession+Presentation 的行为已被间接覆盖）

**为什么是债**: 剔除合理无单测的纯 UI 文件后核心逻辑约 180/754 声明（~24%）零触达：TerminalJumpTargetResolver 848 行 AppleScript 快照解析、TerminalTextSender 的 tmux send-keys 注入是 agent 常改的终端集成热区，改一行无红绿反馈；CodexAppServerCoordinator 的通知→session 映射改错会**静默丢会话**（变更安全性失败模式）。

**证据**: grep 五个类型名 Tests 全目录 0 命中；对照同目录 TerminalJumpServiceTests 存在；AppModel.swift:72 为 SessionDiscoveryCoordinator 唯一挂载点。

**修复**: TerminalJumpTargetResolver 快照解析是纯数据变换，拆 parser 函数即可低成本补测；CodexAppServerCoordinator 参考 CodexAppServerLifecycleTests 的 Pipe 桩模式注入；TerminalTextSender.canReply 纯函数直接可测。

---

## 低

### build-entry-unclear@scripts/launch-dev-app.sh::tcc-prereq

**位置**: CLAUDE.md:38-40 + scripts/launch-dev-app.sh（E4 风险信号）
**类型**: 进程债 — 构建入口不明（验证回路人工前置）
**证据等级**: 风险
**置信度**: 中

**为什么是债**: AX 功能（precision jump/keystroke injection）的验证回路依赖一次性人工前置——setup-dev-signing.sh 签名 + 手动 TCC 授权，且 canonical 运行时（swift run）与 dev bundle 的 TCC 键不同。agent 无法自举该前置：验证 AX 特性时若误用裸 swift run 或 `open -na`，得到 stale bundle / TCC 拒绝的假阴性反馈，与「功能坏了」不可区分，归因被污染（环境可用性 + 可诊断性失败模式）。入口声明本身健康（文档链完整、脚本有自检提示），故判低。

**证据**: `CLAUDE.md:38-40` never-just-open-na 警示；launch-dev-app.sh 尾部 ad-hoc 签名检测分支。

**修复**: launch-dev-app.sh 的 ad-hoc 回退分支加机器可检测标记（artifact/exit code 语义）；CLAUDE.md canonical runtime 处一句话注明 AX 验证必须走 bundle 路径。

---

### oral-tradition@design/v6-bundle/README.md::handoff-template

**位置**: design/v6-bundle/README.md + design/ 目录整体
**类型**: 文档与知识债 — 口头传统（存在性候选）
**证据等级**: 风险（存在性候选，全类型最弱档）
**置信度**: 中

**为什么是债**: v6-bundle/README.md 是 Claude Design 通用 handoff 模板，零版本权威信息——哪些组件是锁定资产、v3–v7 哪个是当前真相、tmp/ 截图是否可删，这些「应知」只活在维护者脑子里。对照 v8-bundle/README.md 有明确 source-of-truth 声明（知识已外化的正例）。agent 在 design/ 下工作时须靠猜或全读（可导航性失败模式，踩坑概率中等）。

**证据**: v6-bundle/README.md 全文为通用模板（"This is a handoff bundle from Claude Design"）；v8-bundle/README.md:8-17 有权威声明作对照。

**修复**: 随 duplicate-code@design 簇一并处理——v6-bundle/README.md 顶部补权威声明后本条自动消解。

---

## 统计

| 族 | 类型 | 债项数 |
|---|---|---|
| A 结构 | duplicate-code | 3（含 1 簇并入矩阵修复） |
| B 测试 | test-gap / flaky-test | 2 / 2 |
| C 文档知识 | doc-rot / oral-tradition | 3 / 1 |
| E 进程 | monolith-file / implicit-contract / build-entry-unclear | 5 / 1 / 1 |
| D 依赖环境 · G 架构形状 | — | 0（无候选） |

高 3 · 中 12 · 低 2，共 17 项（含 2 项附于主项的子修复，独立计数 15）。
