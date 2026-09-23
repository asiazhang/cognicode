# flaky-test：脆弱测试

> 判据权威来源：[B-testing.md](../B-testing.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[B 族：测试债](../B-testing.md) · 失败模式：可诊断性 · 预排：中

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 全类型风险信号 | 确定性（静态反模式清单，7 项有界枚举） | 未单列（命中测试文件的相关行采样进证据包） | 反模式类别数（非计数） |

（一览表按族文件第 0 节概览 + 第 3 节正文誊写。「全类型风险信号档」是 flaky 的核心特征——即便是确定性档提取的静态反模式，证据等级也只有风险一档，见下文展开。）

## 规则陈述

这条规则说的是：**有些测试的通过与否是随机的**——同一份代码，这次跑绿、下次跑红，结果取决于时间、时区、并发时序、网络状态这些与被测行为无关的因素。B 族四分野里 flaky 是「**噪音信号**」：信号在响，但响的内容与代码质量无关。

对 agent 的伤害集中在**可诊断性**：agent 改完代码跑测试，红了。它的标准反应是「我改坏了，回滚或修复」。但如果这个红是 flaky 的——竞态、时区、依赖外部服务超时——agent 就会进入徒劳的调试循环：反复检查自己的 diff、找不到错误、再跑一遍又绿了。更糟的是反向场景：agent 改坏了代码，恰好一个 flaky 测试随机绿了，混在绿色里掩盖真失败。红绿信号一旦有了随机成分，agent 对**所有**测试结果的信任都会被污染——它无法区分「真红」和「噪音红」，失败归因这个 agent 最依赖的诊断动作被系统性破坏。

为什么要静态地抓 flaky：动态检测（反复重跑找随机性）理论上最准，但成本高、且随机的复现本身不确定。MVP 选择抓**静态反模式**——随机红绿的测试通常带着可识别的代码特征（裸 `sleep()`、无 seed 的随机数、直呼 `now()`），这些特征是确定可提取的。当然，命中反模式不等于真的会 flaky（这就是证据等级定为风险信号的原因），但反模式密度高的测试模块，随机红绿的概率显著偏高——报告的是「脆性候选」，不是定罪。

## 信号与判定

### 确定性档：7 项静态反模式清单（有界枚举）

族文件锁定 7 项，每语种一套框架级 token 表（Pytest/Jest/Mocha…）：

1. **`sleep()` 蒙眼等待**——等时间而非等条件：`sleep(2)` 赌外部操作 2 秒内完成，慢机器上必挂。
2. **随机数无 seed**——`random.random()` / `Math.random()` 裸用，每次运行数据不同，断言结果不可复现。
3. **时间依赖无注入**——被测代码或测试直接调用 `now()` / `new Date()`，行为随墙钟漂移（跨午夜、跨月末必挂）。
4. **时区/本地化依赖**——隐式依赖运行机器的 TZ / locale，CI 容器是 UTC、开发机是 +08:00，同一测试两边结果不同。
5. **测试间共享可变全局状态**——模块级可变对象被多个测试读写，测试结果依赖执行顺序（单跑绿、全量跑红）。
6. **`os.environ` / cwd 修改不恢复**——测试改了环境变量或工作目录不还原，污染后续测试。
7. **无 mock 的外部网络调用**——测试真连外网，网络抖动即红绿随机。

清单是**有界枚举**：语种/框架适配 = 换一套 token 表（比如 Jest 里等价物是 `jest.setTimeout` 滥用、`Date.now` 直呼），是工程边界不是判据边界——新增语言不重新讨论「什么是 flaky」，只翻译 token。动态重跑检测留二期。

### 证据等级：全类型风险信号档

族文件的明确要求：**所有 flaky 报告行必须标注「脆性候选，未动态验证」**。为什么连确定性档提取的信号也只是风险：静态特征只证明「写法有随机性风险」，不证明「这个测试真的曾经随机红绿」——`sleep(1)` 配一个本地内存服务可能从未挂过。真正的确证 oracle 是动态重跑（同 commit 跑 N 次看结果方差），那是二期的事。MVP 的报告语言必须诚实反映这一点：报的是「值得怀疑的候选」，不是「已确认的 flaky」。

### rubric 主轴 = 反模式类别数（非计数）

**用类别数不用命中计数**，与 test-rot 的「比例不用绝对数」同一逻辑：计数受模块规模效应影响——一个 900 个测试的模块扫出 40 处 `sleep()` 调用，数量吓人，但如果全集中在「等待外部 API」一类，那是一个待修的工程习惯问题；一个 50 个测试的模块同时命中 5 类反模式（sleep + 无 seed + 时间直呼 + 共享状态 + 环境变量不恢复），随机性的**来源维度**多得多的多，红绿结果实际上不可预测。主轴衡量的是「随机性有多少种独立的来源」，这才是对失败归因污染的烈度。

## 实例

### 正例 1：sleep 蒙眼等待 + 时间依赖无注入（两类命中）

```python
# tests/test_webhook.py
import time
from datetime import datetime
from src.webhook import dispatch

def test_dispatch_writes_audit_log():
    dispatch(order_event)                 # 异步写审计日志
    time.sleep(2)                          # 反模式①：赌 2 秒内写完
    assert audit_log.latest() is not None

def test_daily_rollup_excludes_today():
    cutoff = datetime.now()                # 反模式③：墙钟直呼，无注入
    rows = rollup(cutoff)
    assert rows[-1].date < cutoff.date()   # 23:59:59 后跑必挂
```

- 【信号档】确定性档·反模式清单第 ①③ 类命中（token 表模式匹配）。
- 【证据等级】风险信号——脆性候选，未动态验证。
- 【agent 失败形态】agent 改了 `dispatch` 的批量写入策略，跑 `test_dispatch_writes_audit_log`，红了；它花 15 分钟逐行检查自己的 diff，毫无收获，重跑一遍又绿了——从此它对审计日志相关的一切红信号降权，包括真红。`test_daily_rollup_excludes_today` 在 CI 的 UTC 容器上永远绿、在开发机的 +08:00 时区上每天 0:00–8:00 之间跑必红，agent 在本地复现 CI 失败时陷入「我这里明明是绿的」死循环。
- 预期 DEBT.md 报告行：

```markdown
### flaky-test · tests/test_webhook.py · 置信度 0.81 · 提议带：中
- 信号：反模式类别 2 类——sleep 蒙眼等待（1 处）+ 时间依赖无注入（1 处）——脆性候选，未动态验证
- 定位：test_dispatch_writes_audit_log / test_daily_rollup_excludes_today
- 提议修复：sleep 换轮询条件等待（asyncio.to_thread + 显式 readiness check）；now() 改注入 clock
```

### 正例 2：测试间共享可变全局状态

```python
# tests/test_cache.py
from src.cache import _registry           # 模块级可变 dict

def test_register_backend():
    _registry["pg"] = FakeBackend()        # 写了全局状态，不清理
    assert "pg" in list_backends()

def test_unregister_all():                # 依赖上一个测试先跑过
    clear_all()
    assert "pg" not in list_backends()     # 单独跑时 _registry 为空，断言对象不存在
```

- 【信号档】确定性档·反模式清单第 ⑤ 类命中（共享可变全局状态）。
- 【证据等级】风险信号——脆性候选，未动态验证。
- 【agent 失败形态】agent 给 `test_unregister_all` 加了一个前置断言，单独跑它时红了（`_registry` 是空的，前置条件由 `test_register_backend` 顺带建立）——agent 误判为「我的断言写错了」，浪费一轮来回；而 pytest `-p no:randomly` 关掉随机排序后同样的测试又全绿，agent 完全无法建立「改了什么 → 结果如何」的因果模型。
- 预期 DEBT.md 报告行：

```markdown
### flaky-test · tests/test_cache.py · 置信度 0.74 · 提议带：低
- 信号：反模式类别 1 类——测试间共享可变全局状态（_registry 读写，2 处）——脆性候选，未动态验证
- 定位：test_register_backend / test_unregister_all
- 提议修复：加 autouse fixture 在每个测试后恢复 _registry 快照
```

### 反例：非确定模式不误伤——确定性等待与注入时钟

```python
# tests/test_webhook_fixed.py
from src.clock import FixedClock

def test_dispatch_writes_audit_log():
    dispatch(order_event, clock=FixedClock("2024-02-01T10:00:00"))
    wait_until(lambda: audit_log.latest() is not None, timeout=5)  # 等条件，不是等时间
    assert audit_log.latest().event_id == order_event.id
```

`wait_until(..., timeout=5)` 里有超时参数、内部可能有 `sleep`，长得像反模式①，但**不报**。

为什么不报：族文件反模式①的定义是「**等时间而非等条件**」——`wait_until` 轮询的是就绪条件本身（`audit_log.latest() is not None`），超时只是兜底上限，这是处理异步操作的正确姿势。token 表的职责是把「裸 sleep 等待」和「条件轮询」区分开，判据的分野在于**等待的语义对象**（时间 vs 条件），不是文本里有没有时间函数。同理，注入的 `FixedClock` 不命中反模式③——③判的是**直呼** `now()`/`new Date()` 产生的隐式墙钟依赖，显式注入的时钟恰恰是修复手段。防换皮：如果把「代码里出现 sleep 字样」机械当判据，会把所有正确的异步测试实践一并报成 flaky，报告面被噪音淹没，真正蒙眼等待的债反而看不见。

## 边界与相邻类型

- **test-rot**（同族）：「绿得可疑」vs「红绿随机」。rot 的测试**稳定地**绿（断言烂、skip 堆叠），flaky 的测试**随机地**红绿。一个 catch-and-pass 测试永不失败，是 rot；一个竞态测试偶发失败，是 flaky。两者都污染失败归因，但机制相反：rot 制造假阴性（改坏了不红），flaky 制造假阳性（没改坏也红）——修复动作也相反（rot 修断言，flaky 消随机源）。
- **test-shape**（同族）：shape 焊死的是**结构**（测试与实现的耦合方式），信号本身是真实且确定的；flaky 的问题是**时序/环境随机性**，与耦合深度无关。同一个测试理论上可双挂（既戳内部又竞态），但典型场景互斥。
- **fidelity-debt**（E 族）：flaky 的红绿随机是**时间维度的不稳定**（同一环境不同时刻不同结果）；fidelity 是**环境维度的分叉**（替身环境稳定全绿、真实环境行为不同——结果是稳定的，只是保错了对象）。一个测试可以既 flaky（随机红）又跑在替身上（fidelity），多 slug 并挂。
- **test-gap**（同族）：方向相反（源→测试 vs 测试→源），基本无交叠。flaky 测试一定是被触达的，gap 只管零触达。

## 讨论要点

- **「未动态验证」限定语对报告可信度的影响**：全类型风险信号档意味着 flaky 的每一行都是候选。用户拿到报告后「哪个候选值得先修」缺少进一步的分辨手段（二期动态重跑才能给）。是否有 MVP 内的低成本近似（如只对 3 类以上命中的模块建议手动重跑 5 次）值得讨论。
- **反模式④ 时区/本地化依赖的 token 表难度**：①②③⑤⑥⑦ 都有清晰的 token 锚点，但「时区依赖」往往体现为**缺失**（没显式指定 TZ）而非出现——检测「隐式依赖运行环境」比检测「出现了某个 API 调用」难得多，token 表设计时可能发现这一项实际上做不到纯确定性提取，届时要么降级为 LLM 档候选，要么进雾区。族文件目前没讨论这个不对称。
- **类别数主轴的并列冲突**：命中 3 类各 1 处 vs 命中 2 类各 20 处，主轴上前者更重——「随机性来源多」真的恒比「单来源高频」更伤归因吗？高频单来源（比如 20 处裸 sleep）对 CI 稳定性的实际伤害可能更大。族文件的非计数选择防住了规模效应，但可能矫枉过正，建议 review 时看二期动态数据能否校准。
- **与 CI 配置的边界缺句**：反模式⑦「无 mock 的外部网络调用」——如果仓库本身就是一个网络库，集成测试真连本地回环/容器服务算不算「外部」？族文件未定义「外部」的边界（跨进程？跨容器？跨网络边界？），token 表工程化前需要先裁。
- **动态重跑二期的判定标准**：跑 N 次出现几次红算 flaky？N 取多少？二期设计时需要 statistical power 讨论，建议提前进 #50 系列票。
