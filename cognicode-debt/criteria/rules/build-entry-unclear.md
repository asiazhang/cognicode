# build-entry-unclear：构建入口不明

> 判据权威来源：[E-process.md](../E-process.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：E 进程债（[E-process.md](../E-process.md)，含原 F 族并入内容）· 失败模式：环境可用性（延迟轴仓库内部分同收）· 预排：高

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| E1：静态事实确证；E2：静态事实确证 + LLM 互斥裁定；E3：**风险信号 + 置信度**（断链嫌疑）；E4：静态线索 | 确定性（probe 复用）+ LLM（E2 互斥裁定、E3 断链嫌疑评估） | **验证回路环节级**——每条断链/矛盾锚定到具体声明文件；E1 全缺失为**仓库级单点置顶** | **冷启动阻断度**（复用 config-drift 主轴语言）：E1 ＞ E3 ＞ E2 ＞ E4 |

## 规则陈述

这条规则说的是：**agent 冷启动要跑起「构建 + 测试 + 本地运行」这条验证回路，第一步就是找到入口命令——而入口的证据链断了**。

人类的入口知识靠惯性维持：在这仓库干过的人手指记得 `make test`。agent 没有肌肉记忆，它靠**仓库里的声明**找入口——package.json 的 scripts、CI workflow、Makefile、agent 文档。判据的正式表述是「验证回路入口的证据链断裂」：从「我想跑测试」到「敲下正确命令」之间，agent 赖以推理的证据链在某一环断了。

四档信号对应证据链断掉的四种方式：E1 声明缺失（哪一环都没有）、E2 碎片化（有几环但互相打架）、E3 不可信（有一环但它在撒谎）、E4 绕远（链条通，但终点依赖外部系统）。这是 agent 冷启动失败的**第一大来源**（预排高的依据），也是「验证回路时间轴」视角的入口端——债的利息以 agent 的验证速度计价，找不到入口 = 验证速度为零。

范围收口（同 config-drift 先例）：判据只覆盖**验证回路**的入口——纯生产/部署路径的入口（怎么发布、怎么上线）没有 agent 失败形态，不报。另外 E4 把延迟轴的**仓库内部分**一并收进来：测试硬连 staging、没有本地 compose——「回路走不完」与「找不到入口」同属可启动性失败，这是 #53 的归类决策。

跑通验证（真的执行命令看结果）留二期与动态测量一起——skill 形态跑真命令有安全与时长约束，MVP 只做静态证据链。

## 信号与判定

四档信号：

| 档 | 信号 | 检测与证据等级 |
|---|---|---|
| **E1 声明缺失** | probe 定位面全空，仓库无任何构建/测试命令声明 | 静态事实确证 |
| **E2 声明碎片化** | 多源不一致（package.json 说 npm、CI 用 pnpm） | 静态事实确证；「不一致是否互斥」LLM 裁 |
| **E3 声明不可信** | 命令依赖隐式前置：引用不存在的 compose 文件、断链脚本路径、未声明 env | 静态线索法判**风险信号 + 置信度**——线索只证明断链嫌疑，不证明跑不通 |
| **E4 延迟绕远** | 测试硬连 staging、无本地 compose | 回路存在但走不完 |

- **E1**（确定性档）：复用 probe.py 探测定位面（只定位不执行，零改动可搬），探测产出从「成败判定」改为**证据链**。定位面全空 = 仓库级单点置顶实例（同 agent-doc-missing 概念层缺失置顶先例：知识的家没建 → 入口的家没建）。
- **E2**（确证 + LLM 裁）：多源声明不一致是静态事实（package.json 写 npm test、CI 里是 pnpm test——文件都在，比对即知）。但「不一致」≠「债」：有些不一致是等价的（npm run test 与 node_modules/.bin/jest 可能殊途同归），有些是互斥的（npm/pnpm 会装出不同的 node_modules 结构，静默污染环境）。LLM 裁互斥性——结构同 config-drift C2（值不同不自动判债，LLM 判是否互斥）。
- **E3**（风险 + 置信度，**最阴险**）：声明存在但撒谎——`npm run db:up` 背后是 `docker compose -f infra/pg.yml up`，而 `infra/pg.yml` 不存在。检测用静态线索法（doc-rot 断链态同款思路：声明里引用的目标做存在性比对）。证据等级必须压到**风险信号**：断链线索只证明「链条上有嫌疑」，不证明「跑不通」——也许脚本运行时会动态生成那个文件，也许 CI 有另一个环节补齐。线索是嫌疑不是实锤。
- **E4**：回路存在但走不完——测试套件硬连 staging 数据库（本地跑会全红或挂死）、没有本地 compose 让被测系统起来。E 族把它并入本类型（不重复挂 config-drift——compose 缺失信号已让渡到这边）。

**rubric 主轴 = 冷启动阻断度**（复用 config-drift 主轴语言）：E1（完全找不到入口）＞ E3（浪费尝试且污染归因——比 E2 更伤可诊断性）＞ E2（试错成本）＞ E4（能走完但慢）。

## 实例

### 正例 1：E1 声明缺失（仓库级置顶，确证）

```
仓库根目录清单：README.md, requirements.txt, src/, tests/, deploy/
probe 定位面探测结果：
- package.json / Makefile / Taskfile / justfile —— 均不存在
- .github/workflows/ —— 不存在（无 CI）
- AGENTS.md / CLAUDE.md —— 不存在（无 agent 文档声明命令）
- README.md —— 通篇是产品介绍，无任何「如何跑」章节
定位面全空。
```

- 【信号档】确定性档：probe.py 定位面探测（零执行，纯静态）。
- 【证据等级】静态事实确证（定位面全空是文件系统事实）。
- 【agent 失败形态】agent 冷启动第一问「怎么跑测试」没有任何答案源。它只能猜：`pytest`？`python -m unittest`？装没装 pytest？每次猜测都是一轮「装依赖 → 跑 → 炸 → 换猜」的循环——环境可用性失败的完全体，且没有报错能告诉它「你没找到正确入口，别猜了」。

```
DEBT.md 报告行（示意）
slug:          build-entry-unclear
location:      仓库根目录（probe 定位面全空——仓库级单点）
confidence:    高（确证：E1）
rationale:     无 package.json/Makefile/CI/agent 文档/README 命令声明，构建/测试入口零声明
fix_suggestion: 补 Makefile 或 package.json scripts 声明测试与构建入口；同步写进 agent 文档操作层
提议严重度带:   高（主轴：E1，冷启动完全阻断）
```

### 正例 2：E2 声明碎片化（确证 + LLM 互斥裁定）

```json
// package.json
"scripts": { "test": "npm run build && jest" }
```

```yaml
# .github/workflows/ci.yml
steps:
  - run: pnpm install
  - run: pnpm test
```

AGENTS.md 写着「使用 pnpm」。三个源：package.json 的脚本默认 npm 生态、CI 用 pnpm、agent 文档说 pnpm。

- 【信号档】确定性档：多源声明提取与比对（不一致是静态事实）；LLM 档裁互斥性。
- 【证据等级】不一致确证；互斥判定：本例 npm 与 pnpm 混用**互斥成立**（置信度高——两套工具写同一个 node_modules 会产生结构分叉）。
- 【agent 失败形态】agent 按 AGENTS.md 用 pnpm install 装好依赖，然后按 package.json 跑 `npm test`——npm 重新解析依赖树，静默改写 node_modules，测试跑的是另一棵依赖树的代码。或者反过来。**环境被污染但每个命令都「成功」**：失败形态不是炸，是行为不可解释——后续任何诡异测试失败都可能与这次混合安装有关，归因链从这里开始就断了。

```
slug:          build-entry-unclear
location:      package.json::scripts.test × .github/workflows/ci.yml（npm/pnpm 不一致）
confidence:    高（不一致确证；互斥 LLM 高置信）
rationale:     包管理器声明三源不一致，npm/pnpm 混用互斥（静默污染 node_modules）
fix_suggestion: 统一为 pnpm（CI 与 AGENTS.md 已一致），package.json 增加 packageManager 字段声明
提议严重度带:   中（主轴：E2，试错成本 + 环境污染风险）
```

### 正例 3：E3 声明不可信（风险 + 置信度，最阴险，重点展开）

```json
// package.json
"scripts": {
  "test": "npm run db:up && jest",
  "db:up": "docker compose -f infra/pg.yml up -d"
}
```

`infra/pg.yml` **不存在**（三个月前基建重组，compose 文件挪到了 `infra/local/docker-compose.yml`，package.json 没人更新）。另变体：`"pretest": "bash scripts/setup_test_db.sh"` 而该脚本已删除。

- 【信号档】静态线索法（doc-rot 断链态同款）：提取声明里的引用目标（文件路径、脚本路径、命令），做存在性比对——`infra/pg.yml` 检索空白。
- 【证据等级】**风险信号 + 置信度**——注意这里与 E1/E2 的等级差异：断链线索只证明「声明引用了不存在的东西」，不证明「跑不通」。反事实是存在的：也许 jest 的 globalSetup 会动态写出 pg.yml；也许 db:up 失败但 `&&` 后面……不，`&&` 会短路。静态扫描把这类运行时分支统统看不见，所以只能报嫌疑。
- 【agent 失败形态】这是四档里最阴险的：**声明存在，agent 不需要猜**——它满怀信心地跑 `npm test`，db:up 炸出一个 `no configuration file provided` 的 docker 报错。炸点与病因距离极远（报错来自 docker，病因在 package.json 的路径），agent 的归因被引向 docker/compose 层，开始检查 docker 安装、daemon 状态、compose 版本——每一项都合理，每一项都错。E1 让 agent 知道自己不知道（还能问），E3 让 agent 以为自己知道（连问都不问）——**浪费尝试且污染归因**，所以主轴排在 E2 之前。

```
slug:          build-entry-unclear
location:      package.json::scripts.db:up（引用 infra/pg.yml 断链）
confidence:    中（风险信号：E3 断链嫌疑，LLM 评估；未动态验证）
rationale:     测试入口声明存在，但其依赖的 compose 文件 infra/pg.yml 不存在（检索空白）
fix_suggestion: 更新 db:up 指向 infra/local/docker-compose.yml；或恢复 infra/pg.yml
提议严重度带:   高（主轴：E3，浪费尝试且污染归因——仅次于完全无声明）
```

### 正例 4：E4 延迟绕远（回路存在但走不完）

```python
# tests/integration/conftest.py
import os
STAGING_DB = "postgres://reader:***@staging-db.internal:5432/app"   # 硬连 staging
engine = create_engine(STAGING_DB)
```

仓库没有任何本地数据库方案（无 compose、无 devcontainer、无内存替身），integration 测试必须连通公司内网 staging 才能跑。

- 【信号档】确定性档静态线索：测试配置里的外部系统指纹（非 localhost 连接串）+ 无本地 compose。
- 【证据等级】静态线索（连接串存在、本地方案检索空白都是事实；「回路走不完」的结论依赖内网不可达的假设，故整体按线索级报告）。
- 【agent 失败形态】agent 找得到入口、命令也对，`pytest tests/integration` 挂在连接超时上——它以为是自己网络配置问题，重试、换 DNS、查代理……回路走不完与找不到入口同属可启动性失败：agent 拿不到验证反馈，改任何代码都无法自证。能走完但每一步都在烧时间与轮次。

```
slug:          build-entry-unclear
location:      tests/integration/conftest.py（硬连 staging，无本地 compose 替代）
confidence:    中（E4：外部系统指纹 + 本地方案检索空白）
fix_suggestion: 增加本地 compose（pg 服务）供 integration 测试使用，staging 串移入显式 profile
提议严重度带:   低（主轴：E4，能走完但慢——四档最轻）
```

### 反例：纯生产/部署路径入口（不报）

```yaml
# deploy/release.yml —— 发布流水线
steps:
  - run: ./scripts/publish_artifacts.sh   # 脚本存在
  - run: kubectl apply -f k8s/prod/       # 目录存在
```

假设 `publish_artifacts.sh` 或 `k8s/prod/` 某处断了链——形似 E3。但判据范围收口到**验证回路**（同 config-drift 先例）：这些声明的执行路径是「发布到生产」，agent 的验证回路（构建 + 测试 + 本地运行）不经过它们，断链没有 agent 失败形态，不报。防换皮对照：传统 CI lint / 构建健康检查会报所有流水线断链（运维视角）；本类型的判断轴是 agent 验证回路视角——发布链断不归这里管。（注意分寸：如果 `release.yml` 同时被 agent 文档声明为「跑测试的前置」而进入验证回路路径，那就回到 E2/E3 的判据面内了——收口收的是**路径**，不是文件名。）

## 边界与相邻类型

- **config-drift（D 族）**：同载可启动性轴，以**信号载体**分界——compose 缺失信号让渡本类型 E4（D 族明文「不重复挂」）：config-drift 判「配置键的可达性」（读取痕迹对撞六源），本类型判「入口声明的证据链」。同一场景两边的信号不同：E4 的「无本地 compose」是回路走不完的入口侧事实，config-drift C1 的「PG 连接键无源」是配置项侧事实——按信号载体各挂各的，E4 与 C1 不重复挂 compose 缺失这一个信号。
- **agent-doc-missing（C 族）**：入口命令写在 agent 文档里且过时/矛盾时，两边判据都可能命中——按信号语境分界：入口声明面的碎片化/断链归本类型（E2/E3），第一信源的其他断言（结构、概念）归它；build-entry 的「源」包括 package.json/CI/Makefile 等非 agent 文档载体，这是本类型独有的检测面（见 agent-doc-missing 详解文档讨论要点 4 的同一处待定音）。
- **doc-rot（C 族）**：E3 的静态线索法是 doc-rot 断链态的**同款思路**（引用目标存在性比对），但判据对象不同——doc-rot 判注释断言的误导（可解性），E3 判入口命令声明的断链（环境可用性）。同一个断链目标（文件不存在）在注释里被 doc-rot 报、在 scripts 声明里被 E3 报，各开各的实例。
- **monolith-file / implicit-contract / fidelity-debt（同族）**：E 族无族级共享中间层，四类型判据各自独立；唯一族级锚 = 本类型与延迟轴共享「冷启动到拿到验证反馈」的验证回路时间轴视角。
- **oral-tradition（C 族）**：痕迹在文件系统里（compose、CI、脚本、scripts 声明）归本类型，任何载体无痕迹归 oral-tradition——痕迹所在层分界（C 族显式排除句 + E 族 implicit-contract 一节的对应表述）。

## 讨论要点

1. **E3 的置信度语义**：族文件把 E3 定为「风险信号 + 置信度」，但断链事实本身（文件不存在）是确证的——风险的是「跑不通」这个推断。报告行的 confidence 表达哪一层（断链事实的确定性 vs 断链导致失败的推断强度）需要单写手定死，否则 E3 报告行会与 E1（同为「找不到东西」）的等级语言混淆。
2. **E4 的证据等级族文件未标注**：E1/E2 标了「静态事实确证」、E3 标了「风险信号」，E4 那一行的检测与证据等级栏只写了「回路存在但走不完」（誊写发现此缺句）。按「硬连 staging 是配置事实、走不完是推断」拆两层，建议对齐 E3 的写法补「静态线索 + 置信度」。本文件一览表按此理解填写，待族文件定音。
3. **E2 与 agent-doc-missing 冲突态的边界待定音**：agent 文档也是入口声明的「源」之一——同一份 AGENTS.md 与 CI 的命令矛盾，E2 说归它（入口声明面）、agent-doc-missing 冲突态说归它（第一信源）。E 族分野规则只写了与 config-drift 的让渡，没写与 C 族这条。需要 review 补互斥句或明确双挂。
4. **probe 定位面的清单封闭性**：probe.py 探测哪些位置（package.json? tox.ini? Cargo.toml? noxfile?）决定了 E1 的召回——「定位面全空」的结论依赖清单足够全。定位面清单的语种覆盖是工程边界，但应在 SKILL.md 里版本化，否则新语种仓库会误报 E1。
5. **E4 与 config-drift C1 的「不重复挂」边界**：D 族说「compose 缺失信号让渡 build-entry-unclear E4（不重复挂）」——但「本地 PG 起不来」场景里，config-drift 的正例（DATABASE_URL 读取 + 六源全无）与 E4（无本地 compose）经常同时成立、信号不同源（配置键 vs 基建文件）。到底是「同一失败形态只挂一个」还是「信号不同各挂各的」，两边族文件的表述有解释空间，建议裁决实例入库作为先例。
