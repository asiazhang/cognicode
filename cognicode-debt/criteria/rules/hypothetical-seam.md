# hypothetical-seam：伪 seam 债

> 判据权威来源：[G-architecture-shape.md](../G-architecture-shape.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[G 族：架构形状债](../G-architecture-shape.md) · 失败模式：效率 + 可导航性 · 预排：中

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 全类型风险信号档 + LLM 置信度（**低置信不报**） | 确定性（实现计数，只产事实不判罪）+ LLM（一问定罪） | **抽象符号级**（每个单实现抽象一个实例） | **假信号误导烈度**（多读一层 ＜ 因假接口面放弃直接修改 ＜ 基于换实现假设做出错误方案） |

实现计数（=1）是收录条件，不做排序维度。

## 规则陈述

这条规则说的是：**一个只有一个实现的抽象**——interface、abstract class、protocol——它声称「这里可以换实现」，但仓库语境内从不存在第二条被真实需求驱动的实现路径。「可换」是假信号。对 agent 的伤害不是炸，而是**浪费与误导**：agent 先读接口签名、再跳到唯一实现，接口这层抽象知识是纯开销（穿越成本）；更重的形态是 agent 为遵守假接口面放弃直接修改，或者干脆**基于「换实现」的假设做出错误方案**——为不存在的灵活性设计了半天。

为什么这对 agent 是债：抽象的价值主张是「屏蔽变化」，但 agent 无法从代码本身分辨「真会变」和「从没变过也不会变」。单实现抽象把「可换」这个承诺印在类型系统里——对 agent 来说这是最高置信度的信号，比注释还硬（注释会撒谎，interface 是结构承诺）。假承诺 + 高置信信号源 = 系统性误导。传统审查会说「过度设计，YAGNI」——那是**品味判断**（也许人家就是要防御性设计呢）；本类型的判据是 agent 的实际失败形态：**在假抽象上的无效穿越与错误规划**，判断轴必须在案例上改变结论。

## 信号与判定

### 确定性档（实现计数，只产事实）

- 口径 = **公开抽象符号 + 实现计数**：interface / abstract class / protocol / typeclass / Go interface 的实现类计数，token 表按语种列抽象声明形态（新语种 = 新增 token 表，工程边界不是判据）。
- 候选线 = **恰好 1 个实现**。
- **不设存活时间门槛**（git 生存期分析进雾区，同 test-rot 留先例）：新写的接口和五年单实现的接口在确定性档眼里一样。
- 确定性档只产「单实现抽象」事实清单，**不判罪**——单实现本身不是罪（也许第二个实现下个月就来），判罪需要 LLM 档。

### LLM 档（一问定罪）

- 问一个问题：**「仓库语境内是否存在第二条被真实需求驱动的实现路径」**，标置信度。
- **低置信不报**——问不出来就放过去，宁可漏报不误报（这与其他类型「候选+置信度」的处理不同：本类型判罪端点收敛在一问上）。
- **新生接口豁免由 LLM 档承担**（因为不设存活时间门槛）：评估器判断「接口刚建、第二实现在路上」的语境信号。
- 与 shallow-module 不共用 LLM 判定内容（那边是成本核算，这边是定罪一问），只共用协议骨架。

## 实例

### 正例 1：经典 one-adapter（数据源抽象）

```python
# src/storage/interface.py
class Storage(Protocol):
    def get(self, key: str) -> bytes: ...
    def put(self, key: str, val: bytes) -> None: ...

# src/storage/s3_adapter.py —— 全仓库唯一实现，已存在 4 年
class S3Storage:
    def get(self, key): return self._s3.get_object(Bucket=b, Key=key)["Body"].read()
    def put(self, key, val): self._s3.put_object(Bucket=b, Key=key, Body=val)

# 全部调用方
#   src/backup/job.py:   storage = S3Storage(...)   # 直接实例化，从不通过类型注解约束
#   src/media/cache.py:  storage = S3Storage(...)
```

- 【信号档】确定性档：`Storage` protocol 实现计数 = 1 → 单实现抽象候选；LLM 档一问：「仓库内是否有第二条被真实需求驱动的实现路径？」——没有任何 mock 之外的候选实现、没有任何注解只依赖 `Storage` 而非 `S3Storage` 的调用方、无配置切换点，置信度 0.85（确有测试 fake，但那是测试替身不是「被真实需求驱动的实现」）。
- 【证据等级】风险信号档 + 置信度。
- 【agent 失败形态】agent 接到「给 get 加缓存层」任务：读到 `Storage` protocol，推断「必须保持接口契约，所有实现都要改」——先通读 interface.py 和 s3_adapter.py 两层（穿越成本）；再因为「还有别的实现吗？」检索全仓 15 分钟；最后把缓存写成 `CachedStorage(Storage)` 包一层以「不破坏可换性」——为一个不存在的第二实现支付了全部设计与实现税。
- 预期 DEBT.md 报告行：

```markdown
### hypothetical-seam · src/storage/interface.py::Storage · 置信度 0.85 · 提议带：中
- 信号：实现计数 = 1（S3Storage，4 年唯一实现）
- 评估：仓库内无第二条被真实需求驱动的实现路径，调用方全部直接实例化具体类
- 失败形态：agent 为遵守假接口面放弃直接修改 / 基于换实现假设设计缓存方案
- 建议：移除抽象（直用 S3Storage），或等第二个实现出现再抽象
```

### 正例 2：迁移半途的「预言式」接口（假信号更烈）

```typescript
// src/notify/channel.ts —— 「以后要支持短信」预言的接口
export interface NotificationChannel {
  send(to: string, body: string): Promise<void>;
}

// src/notify/email_channel.ts —— 唯一实现
export class EmailChannel implements NotificationChannel { ... }
```

- 【信号档】确定性档：实现计数 = 1；LLM 档一问：代码注释里的「TODO: SMS」是预言不是需求——没有任何调用短信的代码路径、issue、配置位，置信度 0.75。
- 【agent 失败形态】比正例 1 更烈：注释「TODO: SMS」给了 agent 一个**文档级的假信号**，agent 规划「新增 SmsChannel 实现 NotificationChannel」为正确路径——基于换实现假设做出的方案本身就是被这笔债塑造的。这个例子同时提醒：agent-doc-missing/doc-rot 不适用（注释没有说错事实，它只是预言了不存在的需求）。
- 预期报告行：`hypothetical-seam · src/notify/channel.ts::NotificationChannel · 置信度 0.75 · 提议带：中`，rationale 注明预言信号来源。

### 反例：测试替身不计入（不报）

```python
# src/queue/interface.py
class TaskQueue(Protocol):
    def enqueue(self, task: Task) -> None: ...

# src/queue/redis_queue.py      # 生产实现
# src/queue/celery_queue.py     # 第二个生产实现：高吞吐场景的真实需求（配置位 queue.backend 切换）
# tests/fakes/in_memory_queue.py # 测试替身（不算）
```

**为什么不报**：实现计数虽然是「2 个 + 1 个 fake」，但真正的判罪点是「是否存在**被真实需求驱动的**实现路径」——redis 与 celery 两个生产实现由配置位真实切换，抽象的「可换」承诺被兑现。判据的口径是「公开抽象符号 + 实现计数」的候选线（恰好 1 个实现），本例确定性档根本不产候选——若某仓库只数到 1 个生产实现 + 若干 fake，LLM 一问负责把「fake 算不算」判掉：fake 是 test-scan 语境里的替身（见 fidelity-debt），不是实现路径。

## 边界与相邻类型

- **shallow-module（常并挂）**：接口 + 唯一实现往往同时是薄壳转发层。同实例**多 slug 并挂**（#49 先例），但主轴与修复建议不同：shallow = 合并/加深，hypothetical = 移除抽象或等第二个实现出现再抽象——报告读者看两个 slug 各取所需（「这层又薄又是假的」）。
- **fidelity-debt**：单实现抽象的「唯一实现」如果是测试替身（如只有 InMemory 实现而生产实现另有其物），那是环境保真度问题，归 E 族 fidelity-debt，不归本类型。
- **naming-debt**：接口名起得再自大（`UniversalStorageProviderFactory`）也是检索问题；本类型只关心「可换」承诺的真伪。

## 讨论要点

- **「被真实需求驱动」的判定边界**：issue 里的计划算不算？废弃代码里的第二实现（如被删掉的 SmsChannel）算不算？LLM 一问的 prompt 设计需要把这些边界写清，否则置信度会漂——评审时值得过一遍正反例。
- **低置信不报的单向门**：本类型是全分类学里唯一「低置信直接不报」（而非降档报告）的类型——这是「宁漏勿误」的取舍，若样例票发现漏报率高，此门是否放宽需要重议。
- **git 生存期分析在雾区**：不设存活时间门槛意味着新接口（合理）和老接口（更可能是伪）同等对待，全靠 LLM 豁免——成本与准确率的权衡留给技术选型。
