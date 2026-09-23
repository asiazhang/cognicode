# fidelity-debt：保真度债

> 判据权威来源：[E-process.md](../E-process.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[E 族：进程债](../E-process.md) · 失败模式：环境可用性 + 变更安全性 · 预排：高（沿 test-rot 假保护同档）

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 确定性替身指纹（候选）+ LLM 保真差距评估（标置信度） | 确定性（替身指纹）+ LLM（保真差距） | **环境对级**（声明真实环境 × 实际测试替身，一对一个实例） | 假保护覆盖面 |

（一览表按族文件第 0 节概览 + 第 4 节正文誊写。fidelity-debt 是 #53 从 #52 雾区毕业的新生类型——验证回路「保真度轴」的类型化身，此前 20 类型清单里没有它的位置。证据等级一栏为正文归纳，E 族概览表无此列，见讨论要点。）

## 规则陈述

这条规则说的是：**测试全绿，但绿在替身上**。声明的真实环境是 PostgreSQL + Redis（compose 文件、CI services 段、配置模板都这么写），测试实际跑在 SQLite 内存 + fakeredis 上。测试本身质量很好——断言真实、覆盖充分、从不 flaky——它们**真实地**验证了「代码在 SQLite 上的行为」。债在于：全绿被（agent 和人）默认理解为「在真实环境也安全」，而这个推断是假的。这是 B 族四分野之外的**第五形态：信号真、环境假**。

对 agent 的伤害是**环境可用性 + 变更安全性**的双重打击：agent 的整个工作流建立在「跑绿 = 安全放行」上。它写一个使用了 PG 特有语法（`ON CONFLICT ... RETURNING`）的迁移，测试套件在 SQLite 上全绿——SQLite 静默忽略或别扭地兼容了这段逻辑——agent 放心提交，真实环境第一次跑这条迁移就炸。更隐蔽的是不炸的：PG 的序列化隔离、类型强制（`strict` 模式下空字符串进不了 `integer` 列）、migration 的锁行为，这些替身上全都「看起来能跑」，错的行为静默流进生产。

**判据的关键收口：分叉本身不报**。测试用替身是完全正当的工程实践（速度、隔离、成本），仓库里「声明的环境」与「测试的环境」不一致是常态。只有当**分叉 + 全绿证据同时在手**——即「全绿被当作真实环境也安全」的信号存在时——才报。没有全绿信号的分叉不是债，是配置事实；有分叉但测试常年红的也不是本类型的债（那是别的烂）。

## 信号与判定

### 声明面（从哪里知道真实环境是什么）

四个来源（**config-drift 六源子集，明确不含 README**——README 是 config-drift C3 的断言比对面，两类型分工）：

1. **compose 文件**（`docker-compose.yml` 的 services 段）；
2. **CI workflow 的 services 段**（`.github/workflows/*.yml` 里声明的 PG/Redis 容器）；
3. **配置模板连接串**（`.env.example`、config 模板里的 `postgres://...`）；
4. **agent 上下文文档**（AGENTS.md/CONTEXT.md 里写的环境要求）。

### 确定性档：替身指纹

在测试配置/fixture 里做模式匹配，识别替身环境的特征指纹：

- **SQLite 内存串**：`sqlite:///:memory:`、`create_engine("sqlite://")`；
- **testing.local host**：连接串指向测试专用域名而非声明的真实服务；
- **docker-compose.test.yml 独立环境**：测试用一份与生产 compose 不同的编排文件。

指纹命中 = 「测试在用替身」的静态事实。拿指纹命中的替身环境**对照声明面**，形成「环境对」候选：声明 PG（compose）× 实际 SQLite（fixture）。

### LLM 档：保真差距评估

对每个环境对，判「**真实环境的特有面，在替身上是否被绕过**」，标置信度。所谓特有面：PG 相对 SQLite 多出来的行为面——migration 引擎行为（SQLite 不跑 PG 的迁移校验）、并发语义（事务隔离级别、锁）、类型强制（strict 列类型）。替身绕过的特有面越广，「全绿 → 真实环境也安全」这个推断就越假。

### 证据等级与报告

替身指纹是确定性事实（确证「在用替身」），但「假保护」的成立依赖 LLM 对保真差距的评估——报告行标置信度，不伪装实锤。全绿持续提交数（这条全绿在 main 分支上存活了多少个提交）做**信号级标注**：全绿越久，假安全信号累积的「利息」越多，但信号级标注不进主轴。

### rubric

主轴 = **假保护覆盖面**：替身绕过的真实环境特有面越广，误导越深。族文件给了明确的梯度：**只有连接 ＜ 加 migration 行为 ＜ 再加并发/类型强制**。为什么用覆盖面不用「分叉距离」（PG vs SQLite 差多少）：一个只绕过连接层（替身连的是 testing 库的真 PG）的环境对，几乎没有假保护；一个连 migration + 并发 + 类型强制全绕过的环境对，等于测了一个想象中的数据库。覆盖面直接对应「agent 会在多少类改动上被误导」。

## 实例

### 正例 1：SQLite 替 PG，绕过 migration 与类型强制

```yaml
# docker-compose.yml（声明面 1：真实环境是 PG 15 + Redis）
services:
  db:
    image: postgres:15
    connection: postgres://app:${DB_PASSWORD}@db:5432/app
```

```python
# tests/conftest.py（替身指纹命中）
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")     # ← 指纹：SQLite 内存串
    Base.metadata.create_all(engine)                 # ← 直接建表，不走 alembic migration
    yield sessionmaker(engine)()
# 全绿证据：main 分支连续 214 个提交 CI 全绿，其中 31 个改动涉及
# migration 文件（.versions/*.py）——这些改动从未在 PG 上执行过
```

- 【信号档】确定性档·替身指纹（`sqlite:///:memory:`）× 声明面（compose 声明 postgres:15）→ LLM 档·保真差距评估：migration 行为被完全绕过（`create_all` 跳过 alembic）、PG 类型强制被绕过（SQLite 无 strict 列类型），置信度 0.87。
- 【证据等级】指纹确证（在用替身）+ 保真差距评估标置信度。
- 【agent 失败形态】agent 写一个新 migration：`ALTER TABLE orders ADD COLUMN tags jsonb NOT NULL DEFAULT '[]'`，顺手加一条 `ALTER COLUMN discount SET DATA TYPE numeric USING ...`（PG 特有语法）。conftest 用 `create_all` 建表，migration 文件**根本没被执行过**，测试全绿，agent 放行——生产环境跑 alembic 时 `USING` 子句在某个未测分支上抛语法错，部署卡死在半迁移状态。
- 预期 DEBT.md 报告行：

```markdown
### fidelity-debt · tests/conftest.py × docker-compose.yml · 置信度 0.87 · 提议带：高
- 环境对：声明 postgres:15（compose）× 实际 sqlite:///:memory:（conftest fixture）
- 保真差距：migration 行为完全绕过（create_all 直建）+ 类型强制绕过（SQLite 无 strict 列型）
- 信号级标注：全绿持续 214 提交，其中 31 个含 migration 改动未在 PG 上验证
- 提议修复：CI 加一档真 PG 服务的 migration 冒烟 job，或显式声明替身局限（DEBT.md 报告此行即为声明）
```

### 正例 2：独立 test compose 偏离声明的服务拓扑

```yaml
# docker-compose.yml（声明面：服务拓扑 = app + postgres + redis + minio）
services:
  app: ...
  postgres: ...
  redis: ...
  minio: ...            # 对象存储，声明为真实依赖
```

```yaml
# docker-compose.test.yml（指纹：独立测试编排文件）
services:
  app:
    environment:
      STORAGE_DRIVER: local-fs       # ← minio 被 local-fs 替换
      REDIS_URL: redis://test-redis  # ← 换成另一套 redis 配置
```

- 【信号档】确定性档·指纹命中（`docker-compose.test.yml` 独立环境 + 配置偏离）× 声明面（主 compose 声明 minio 依赖）→ LLM 档评估：对象存储行为（分片上传、签名 URL、ACL）在 local-fs 上全部绕过，置信度 0.78。
- 【证据等级】指纹确证 + 评估标置信度。
- 【agent 失败形态】agent 调整文件上传的分片逻辑，测试在 local-fs 上全绿（local-fs 没有分片语义，写入就是成功）；真实 minio 上分片顺序错误导致合并失败——而 agent 既没有跑过真 minio，也从绿信号里得不到任何警告。
- 预期 DEBT.md 报告行：

```markdown
### fidelity-debt · docker-compose.test.yml × docker-compose.yml · 置信度 0.78 · 提议带：中
- 环境对：声明 minio 对象存储（主 compose）× 实际 local-fs 驱动（test compose 的 STORAGE_DRIVER）
- 保真差距：对象存储特有面绕过——分片上传、签名 URL、ACL 均未验证
- 提议修复：test compose 增设 minio 服务档（仅集成 job 启用），分片上传路径走真 minio
```

### 反例：环境分叉存在但无全绿证据 / 无假安全信号，不报

```python
# 场景 A：仓库根本没有声明面——
# 没有 compose、CI 无 services 段、配置模板写的是 sqlite、agent 文档只字未提数据库。
# 测试用 sqlite:///:memory:（指纹命中），但四个声明源全部为空。

# 场景 B：分叉 + 显式声明局限——
# conftest.py 顶部注释：
#   本套件跑在 SQLite 上；migration 与 PG 特有行为由 CI 的
#   integration-pg job（.github/workflows/integration.yml services 段
#   起 postgres:15）覆盖，勿依据本套件结果判断 PG 行为。
# 且 CI 确实存在该 job。
```

场景 A：**不报**。判据要求「声明的真实环境与测试替身的**分叉**」——分叉是个差集概念，没有声明面就没有差集。「仓库不用 PG」不是债，是配置事实；如果连「应该用什么环境」这件事本身都不明，那是 build-entry-unclear / config-drift 的地盘，不是 fidelity 的。

场景 B：**不报**。分叉 + 全绿都在，但「全绿被当作真实环境也安全」的信号被**显式声明打破了**——conftest 的注释 + 真实存在的 PG 集成 job 构成了对替身局限的显式声明。这正是族文件给的第三种修复方向（「对齐环境**或显式声明替身局限**」）已经完成的形态。判据报的是「假保护」，局限被声明的保护不再是假的。

防换皮角度：如果不做「全绿 + 无声明」的收口，只要仓库用替身就报，这个类型就退化成「反 mock/反替身」的审美判断——而 mock 公开边界依赖是正常测试实践（test-shape 文档的同一分野）、用替身加速单测也是正当工程，全部被冤枉。

## 边界与相邻类型

**与 B 族三态的分野是本类型的核心边界**（族文件原文展开）：

- **test-gap**：**保护不存在**——没有任何测试覆盖该区域。修复 = **补测试**。
- **test-rot**：**保护虚假**——测试在但断言烂，不测东西。修复 = **修断言**。
- **fidelity-debt**：**保护是真的，但保的是替身不是本体**——测试质量没问题，环境是假的。修复 = **对齐环境或显式声明替身局限**。

三者修复动作完全不同，这是必须拆成三个 slug 的根本原因：gap 的报告行说「这里没测试」、rot 说「这些测试是假的」、fidelity 说「这些真测试绿在假环境上」。**同模块多 slug 可并挂**：一个模块可能同时有无覆盖区域（gap）、烂断言（rot）和替身环境（fidelity），三行并挂、各自修复、互不替代。

其他相邻类型：

- **test-shape**（B 族）：shape 的 mock 判定（mock 公开边界 = 正常实践）与本类型的替身判定精神一致，但层面不同——shape 判**单测内部** mock 的对象（边界内协作 vs 边界外依赖），fidelity 判**整套测试环境**与声明环境的分叉。一个 fixture 可以 mock 得完全正确（无 shape 债）却整体跑在替身上（有 fidelity 债）。
- **config-drift**（D 族）：声明面来源重叠（compose/CI/配置模板是 config-drift 六源子集），但分野在用途——config-drift 判**配置本身的矛盾/缺失**（C1 读而无源、C2 多源矛盾），fidelity 拿同一批声明源做**环境对的左边**（真实环境是什么）。README 的分工：fidelity 不用 README（那是 config-drift C3 断言比对面）。compose 文件缺失归 build-entry-unclear E4 / config-drift C1，不重复挂本类型。
- **build-entry-unclear**（同族）：验证回路三轴内的兄弟——可启动性（起不起得来，build-entry + config-drift）、保真度（跑起来了但在撒谎，**本类型**）、延迟（能走完但慢，build-entry 信号档）。同一份 compose 可以同时是「起不来」（build-entry E4）和「起来了但保真是替身」（本类型）的证据源，两行各报各轴。
- **flaky-test**（B 族）：fidelity 的结果是**稳定的**全绿（假得很稳定），flaky 是**随机**红绿。一个跑在替身上又偶发竞态的套件可双挂。

## 讨论要点

- **「全绿证据」的采集口径缺句**：判据要求「分叉 + 全绿证据同时在手」，但族文件没定义全绿怎么采（CI 历史？最近 N 次提交？main 分支专属？）——正例 1 的「214 个提交全绿」是我构造的呈现，工程上需要明确数据源（CI API？git 历史？）与窗口。
- **显式声明局限的判定标准**：反例场景 B 靠注释 + 集成 job 不报——但「声明」的门槛在哪？一行注释够吗？还是必须有真实存在的替代验证路径（PG job）？注释可以撒谎（doc-rot 的领域），族文件未讨论声明的可信度校验，这里与 C 族 doc-rot 有个未划的边界。
- **替身指纹表的语言/框架覆盖**：SQLite 串、testing.local host、test compose 是三个先例指纹，但替换形态无穷（fakeredis、testcontainers、monkeypatch 的环境变量、H2 替 MySQL……）——token 表的初始集合该多大、漏检一个新型替身的代价（漏报整类假保护）需要评估。
- **预排「沿 test-rot 假保护同档」的合理性**：fidelity 预排高、rot 预排高，但两者的证据结构不同（rot 有确证子档，fidelity 的判罪全靠 LLM 评估）——同预排是否意味着同严重度带？严重度带跨族可比性本来就是雾区（CONTEXT.md），这里是一个具体实例。
- **E 族概览表无证据等级列**：与 monolith-file 同一誊写问题，不重复展开；建议族文件统一补列或补说明。
- **新生类型的实证空白**：#53 自 #52 雾区毕业，尚无样例票校准（对比：test-rot 有多年社区认知）。第一轮真实扫描的假阳性率未知，「环境对」粒度在大仓库（几十个服务 × 多套 compose）下的报告膨胀风险需要观察。
