# config-drift：配置漂移

> 判据权威来源：[D-dependency-env.md](../D-dependency-env.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：D 依赖与环境债（[D-dependency-env.md](../D-dependency-env.md)）· 失败模式：环境可用性 + 可诊断性 · 预排：中（D 族独苗）

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| C1：存在性确证（候选）+ LLM 路径评估器置信度；C2：三元组事实 + LLM 互斥裁定置信度；C3：双向比对 + 置信度 | 确定性（候选生成）+ LLM（路径评估器） | **配置项级** | **冷启动阻断度**（只锁方向）：无源必需键 ＞ 多源矛盾 ＞ 文档误导 |

D 族仅此一类覆盖（dep-stale / lockfile-drift 留册）。验证回路三轴（可启动性/保真度/延迟）中，本类型与 build-entry-unclear（E 族）共同承载**可启动性**轴。

## 规则陈述

这条规则说的是：**验证回路（构建 + 测试 + 本地运行）执行路径上被读的配置，agent 摸不到、也推不出来**。判据的正式表述：验证回路执行路径上的配置可达性。

先看这笔债的典型剧本：代码里 `os.environ["DATABASE_URL"]`——运行必需；这个值住在 `.env` 里，`.env` 被 gitignore（本来就该 ignore，里面有密钥）；新克隆仓库的 agent 冷启动跑测试，炸出一个 `KeyError: 'DATABASE_URL'`。关键在最后一步：**这个报错与「代码写错了」的报错长得一模一样**。病因（gitignore 掉的环境文件）对 agent 完全不可见，归因路径被系统性污染——agent 会去检查代码、检查依赖版本、检查语法，唯独没有一个报错提示它「你缺一份配置」。这就是两个失败模式的合谋：**环境可用性**（跑不起来）+ **可诊断性**（炸了也定位不了根因）。

判据最独特的设计是**两端夹检测**——因为病因本身不可见（被 ignore 的文件、只存在于人脑的值），无法直接观测「配置缺失」，只能从两端对撞：

- **一端是读取痕迹**：代码里 env 读取 + 显式配置文件键——这是「配置被需要」的证据；
- **另一端是可见配置源六项**：配置模板/默认值文件、CI workflow、agent 上下文文档、README 配置段、compose/基建文件等（六项以 CONTEXT.md / #52 决议 2 为准清点）——这是「配置在哪里有交代」的证据。

两端一撞：读取痕迹有、六源全无 → 实例。「本地 PG 起不来」的场景因此可表达：读取痕迹有 PG 连接配置、六源全无。

**路径收口为收录门槛**（这是防换皮的关键）：只有落在验证回路执行路径上被读的配置才进检测面。传统 config lint 报**所有**未定义键——那是人类运维视角（生产环境的配置也要管）；本类型只报验证回路路径上的——纯生产/部署路径的配置键**没有 agent 失败形态**（agent 不部署生产），不报。判断轴在具体案例上改变了结论：这是「别人说债、我们说不债」的实存案例。

## 信号与判定

三档信号：

| 档 | 检测 | 判定 |
|---|---|---|
| **C1 读而无源** | 确定性候选生成 + LLM 路径评估器 | 评估器判「是否在验证回路执行路径上」定收录，标置信度；**有默认值的读取不报** |
| **C2 多源矛盾** | 确定性档提取 (键, 值, 源) 三元组 | 值不同不自动判债，LLM 裁「同语义环境下是否互斥」；**同值多源不报** |
| **C3 文档配置断言** | README 等声称的配置 ↔ 代码读取事实双向比对 | 按失败模式落点裁：配置断言失败落点是环境可用性，归本类型不归 doc-rot |

- **C1**：确定性档提取「env 无默认值读取 + 显式配置文件键」作为一端，六源键提取作为另一端，对撞出「读而无源」候选（存在性确证级）；LLM 路径评估器再判该读取是否在验证回路执行路径上（同 test-shape 候选评估器结构），定收录并标置信度。**有默认值的读取不报**——有默认值就不炸，弱信号不占报告面。
- **C2**：确定性档把六源里同一键的 (键, 值, 源) 三元组全提出来。值不同≠债：localhost vs staging-db 是正当的环境差异；LLM 裁的是「同语义环境下是否互斥」——两个源在同一个语义环境里给出不能共存的值（如都声称是本地开发默认，一个 `DEBUG=1` 一个 `DEBUG=0`）才是矛盾。**同值多源不报**：多份同值的痛感是变更安全机制（改 A 忘 B），归 duplicate-code 家族，D 族不预支。
- **C3**：README 等声称「配置 X 的值是 Y / 需要设置 X」，与代码读取事实双向比对（代码读了 README 没说的 → 接 C1；README 说了但与读取要求不符 → 断言误导）。README 只划「配置断言」一个切面，长文档其他信号仍留雾区。

**实例粒度 = 配置项级**（每个键一个实例）。fix_suggestion 对 C1 无源候选**必须指出应补进六源中的哪一源**——不是泛泛的「补配置」，而是具体的「这个键应该出现在 .env.example（配置模板源）还是 CI workflow」。

## 实例

### 正例 1：C1 读而无源（冷启动直接炸）

```python
# src/db/session.py —— 验证回路路径上：conftest.py 会 import 本模块建表
engine = create_engine(os.environ["DATABASE_URL"])   # 无默认值读取
```

六源检索：`.env.example`（不存在）、CI workflow（只在 staging job 里设置了 DATABASE_URL，本地测试 job 无）、AGENTS.md（无配置段）、README（无配置段）、compose 文件（无）。**六源全无本地可达的值**。

- 【信号档】确定性档：读取痕迹提取 + 六源对撞，候选确证；LLM 路径评估器判「conftest 建表在测试执行路径上」→ 收录。
- 【证据等级】存在性确证（读取存在 + 源不存在都是客观事实）+ 评估器置信度高。
- 【agent 失败形态】agent 冷启动跑测试：`KeyError: 'DATABASE_URL'`。它与「代码 bug」同形——agent 开始读 session.py 找拼写错误、检查依赖、怀疑 Python 版本，每条归因路径都合理且都错。冷启动阻断 + 归因污染双杀，这是主轴上最重的一档。

```
DEBT.md 报告行（示意）
slug:          config-drift
location:      src/db/session.py::DATABASE_URL（配置项级）
confidence:    高（C1：读取存在 + 六源检索空白，评估器确认在测试执行路径上）
rationale:     无默认值 env 读取，验证回路必需，六源均未提供本地值
fix_suggestion: 补进配置模板源——.env.example 增加 DATABASE_URL=postgresql://localhost:5432/app（本地默认值）
提议严重度带:   高（主轴：无源必需键，直接炸）
```

### 正例 2：C2 多源矛盾（悄悄错，污染后续行为）

```yaml
# .env.example（配置模板源）
CACHE_TTL_SECONDS: 3600

# src/config/defaults.py（配置模板/默认值文件）
CACHE_TTL_SECONDS = 60
```

两个**同语义环境**（本地开发默认值）的源给出互斥值 3600 vs 60，未声明谁是权威。

- 【信号档】确定性档：(键, 值, 源) 三元组提取，值不同 → 候选；LLM 裁「同为本地默认语义环境、值互斥」→ 矛盾成立。
- 【证据等级】三元组事实确证 + 互斥判定置信度中（「同语义环境」是推断——也可能团队约定 defaults.py 是运行时权威、.env.example 只是摆设，这正是要 LLM 裁的）。
- 【agent 失败形态】agent 调试缓存不生效的问题：它读 `.env.example` 推断 TTL 是 1 小时，实际运行时 defaults.py 的 60 秒先生效——agent 的每一步推理都建立在错误前提上，且**不炸**（60 秒也是合法 TTL），它只是悄悄给出错误的诊断结论。矛盾比缺失更阴：缺失至少炸得响。

```
slug:          config-drift
location:      CACHE_TTL_SECONDS（.env.example × src/config/defaults.py）
confidence:    中（C2：互斥性为 LLM 裁定）
rationale:     同语义环境（本地默认）两源值 3600 vs 60 互斥，未声明权威
fix_suggestion: 声明权威源（建议 defaults.py），.env.example 删除该键或改为「见 defaults.py」
提议严重度带:   中（主轴：多源矛盾，悄悄错）
```

### 正例 3：C3 文档配置断言（排障绕路，通常不炸）

```markdown
# README.md「本地开发」一节
本地运行只需设置一个环境变量：APP_PORT=8080。
```

```python
# src/app.py
port = int(os.environ["APP_PORT"])
debug = os.environ["APP_DEBUG"]            # README 没提的必需键
workers = os.environ.get("APP_WORKERS", "4")
```

README 断言「只需 APP_PORT」，代码读取事实是还必需 `APP_DEBUG`——断言与读取事实矛盾（同时 APP_DEBUG 构成 C1 无源候选，两个信号各开实例）。

- 【信号档】确定性档：README 配置断言提取 ↔ 代码读取事实双向比对。
- 【证据等级】断言与读取事实都是确证；「断言误导」的严重度评估带置信度。
- 【agent 失败形态】agent 按文档只设了 APP_PORT，启动炸在 `APP_DEBUG` 上。比纯 C1 多绕一层：它**相信了文档**，先怀疑自己设错了端口/写法，折腾一圈才意识到文档漏了键。排障绕路是三档里最轻的痛，但每一次绕路都在烧 agent 的轮次预算与人的耐心。

```
slug:          config-drift
location:      README.md「本地开发」节 × src/app.py::APP_DEBUG
confidence:    高（C3：断言「只需 APP_PORT」与必需读取 APP_DEBUG 双向比对矛盾）
fix_suggestion: README 更新为完整必需键清单（APP_PORT、APP_DEBUG），或 .env.example 补全后 README 指向它
提议严重度带:   低（主轴：文档误导，排障绕路不直接炸）
```

### 反例 1：纯生产路径配置（不报）

```python
# src/deploy/reaper.py —— 只在生产部署的 cron Pod 里运行，验证回路不经过
prod_replica_count = os.environ["PROD_REPLICA_COUNT"]   # 六源检索：无
```

读取存在、六源也无值——形似 C1。但 LLM 路径评估器判：这个模块不在构建/测试/本地运行的执行路径上（没有任何测试 import 它，本地 dev server 不加载它）。**路径收口为收录门槛**：纯生产/部署路径的配置键无 agent 失败形态（agent 的验证回路永远不触达它），不报。防换皮对照：传统 config lint 会把它和 C1 一起报（运维视角：生产配置也要管）；本类型的判断轴是 agent 视角，在这里改变了结论。

### 反例 2：有默认值的读取（不报）

```python
log_level = os.environ.get("LOG_LEVEL", "INFO")          # 有默认值，不炸
feature_flags = os.environ.get("ENABLE_BETA", "false")   # 有默认值
```

即使六源全都没提 `LOG_LEVEL`，也不报——**有默认值的读取不报**（族文件 C1 明文）：它不会炸（环境可用性无损），最多是「不知道还能调」的弱信号，弱信号不占报告面。这条规则防止报告被海量低痛感候选淹没，把冷启动阻断度主轴的信号密度保住。

### 反例 3：CLI 参数不是配置（不收）

```python
parser.add_argument("--timeout", type=int, default=30)   # CLI 参数
TIMEOUT_FALLBACK = 30                                    # 代码内常量
```

族文件两端夹检测的读取端明文：**CLI 参数是接口不是环境前提、代码内常量不是配置，均不收**。道理：CLI 参数的值在每次调用时显式给出（agent 能从 `--help` 看到它，它是可发现的接口面）；代码内常量则根本不是「环境知识」——它就在代码里，agent 读得到。config-drift 专收那些「在代码之外、agent 看不见摸不着」的环境前提，这两者都不满足。

## 边界与相邻类型

- **build-entry-unclear（E 族）**：同载可启动性轴，以**信号载体**分界——compose 缺失信号让渡 build-entry-unclear E4（不重复挂）：config-drift 判「配置键的可达性」（读取痕迹对撞六源），E4 判「回路走不完」（测试硬连 staging、无本地 compose）。E 族对应规则明文。
- **doc-rot（C 族）**：C3 与 doc-rot 的分界 = **失败模式落点**：配置断言的失败落点是环境可用性（跑不起环境）归本类型；注释断言的失败落点是可解性（推理被误导）归 doc-rot。按失败模式裁、不按载体裁——README 的配置断言归本类型，同是 README 的其他长文档信号留雾区。
- **duplicate-code（A 族）**：C2 **同值多源不报**——多份同值配置的痛感是「改 A 忘 B」的变更安全机制，属 duplicate-code 家族的知识重复逻辑，本类型不预支（值矛盾才归 C2）。
- **fidelity-debt（E 族）**：那边的声明面是本类型六源的**子集**（不含 README——README 是 C3 的断言比对面），判的是环境分叉 + 全绿证据；本类型判配置可达性。同一份 compose 文件可同时是两边的检测对象，判据不同不互斥。
- **dep-stale / lockfile-drift（同族，留册）**：依赖版本类不检测不报告（web search 普及使 dep-stale 利息降级；lockfile 检测商品化且报错清晰）。

## 讨论要点

1. **六源清单的封闭性**：族文件说「⑥（六项以 CONTEXT.md / #52 决议 2 为准清点）」——第⑥项在族文件里没写出名字（誊写发现此处引用悬空，CONTEXT.md 验证回路词条也没有逐项列出六源）。六源是 C1/C3 的检索面，清单不封闭会导致召回漂移，建议 review 时把六项补全并锁版本。
2. **各语言 env 读取语法表留雾区**（族文件明示）：`os.environ` / `process.env` / `System.getenv` 的提取是 C1 的确定性前提，语法表是工程边界不是判据，但它的覆盖度直接决定 C1 召回率。
3. **「同语义环境」的裁定弹性**：C2 的 LLM 裁定（localhost vs staging-db 是正当差异）依赖对源文件语义的推断——.env.example 和 docker-compose.yml 是否一定「同为本地开发」？次主流源（Makefile 里的 export、devcontainer.json）归哪个语义环境？需要实例校准。
4. **C1 存在性确证与 LLM 收录的等级落差**：候选是确证级（读存在 + 源不存在都是事实），但收录与否取决于 LLM 路径评估器（判「是否在验证回路路径上」）——一个评估器误判会把确证候选整个丢掉。报告行的 confidence 应综合表达两层（事实层高、收录层中），格式需单写手定死。
5. **冷启动阻断度排序的边界情形**：主轴把「文档误导」排在最轻（通常不炸），但反例 3 的变体——README 给了**错误的值**（说 `APP_DEBUG=false` 而测试路径必须 true）会让 agent 走得更偏（它会反复用一个错的值跑）。C2 结构（断言值 vs 读取必需语义互斥）能否套在 C3 上，族文件未说死。
