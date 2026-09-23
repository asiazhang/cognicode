# test-shape：测试形状债

> 判据权威来源：[B-testing.md](../B-testing.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[B 族：测试债](../B-testing.md) · 失败模式：变更安全性 · 预排：中

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 确证候选 + LLM 评估 | 确定性 + LLM | 未单列（import 私有符号 + mock 目标清单为 test-scan 中间产物，命中处采样进证据包） | private-touch 深度 × mock 内部依赖计数（组合） |

（一览表按族文件第 0 节概览 + 第 4 节正文誊写。shape 的检测结构是「确定性档产候选清单、LLM 档只做评估不做发现」——这个分工在 B 族里是独有的，见下文。）

## 规则陈述

这条规则说的是：**测试真的在测行为（真保护），但它越过公开接口直接焊死在实现的内部结构上**——import 私有符号、mock 内部协作对象、断言私有状态。B 族四分野里 shape 是「**真信号但焊死错误对象**」：测试质量本身没问题，问题在它把保护钉在了实现而非接口上。

为什么这对 agent 是债，而且是很阴险的一种：agent 做正确的事会受惩罚。agent 想把内部实现**深度化**（Ousterhout 意义上的：收窄接口、把复杂性藏进模块），这是提高代码质量的标准动作；但只要它动了被测试戳到的私有结构——哪怕行为完全不变——测试就红。红绿信号在撒谎：它说「行为坏了」，实际只是「结构变了」。被惩罚几次之后，agent（以及人）会**长期学会不重构**——红绿信号反向训练所有参与者避开内部改进。这是债里少见的「行为塑造」型利息：它不炸、不慢、不报错，它只是把整个仓库的重构肌肉慢慢废掉。

MVP 的检测面是**形状代理**（import 私有 / mock 内部这些静态可见的「焊点」），真正的「行为学习污染层」（测试如何反向塑造开发行为）需要动态验证，留二期。

## 信号与判定

### 私有符号定义（判「戳内部」的尺子）

**公开面声明优先，语言机制兜底**：

- **公开面声明优先**：模块若有显式导出声明（Python 的 `__all__`、TypeScript 的 `index.ts` 导出表），声明表就是公开面——不在表里的都是内部，**哪怕语言机制上它是公开的**（比如没有 `_` 前缀的函数没进 `__all__`）。
- **语言机制兜底**：没有显式声明时，落到语言约定——Python `_` 前缀、TypeScript/JS `#` 私有字段、Go 小写开头、Java package-private。

为什么声明优先：语言机制是「语法上能不能访问」，声明表是「设计上想不想让你访问」。债的判定关心后者——一个没进 `__all__` 的符号被测试 import，语法合法但设计意图上就是戳内部。

### mock 边界判定（判「mock 错对象」的尺子）

- mock **公开边界依赖**（网络服务、数据库接口、外部进程）= **正常测试实践，不判债**。测试不该真连生产 DB，这是对的做法，mock 它不是债。
- mock **内部协作对象**（同一个进程内的内部模块、内部类之间的协作）= **形状债信号**。内部协作是实现的血肉，mock 掉它等于测试在验证「我 mock 出来的假想协作方式」，而不是「真实协作方式下的行为」——实现重排协作关系（行为不变）测试就红。

分野的一句话：**mock 边界之外的东西是正常，mock 边界之内的东西是债**。边界 = 模块的公开面。

### 两档分工

- **确定性档**：从 test-scan 中间产物（B 族共享的一趟「测试→源」扫描）取两类清单——**import 私有符号清单**（测试文件 import 了哪些私有符号）和 **mock 目标清单**（测试 mock 了哪些对象）。确定性档只产这两张清单，不做任何判罪。
- **LLM 档 = 候选评估器**：**不做 shape 的独立发现**——不是让 LLM 全仓找形状债（那会失控），而是只对确定性档筛出的候选判「**是否真的焊死结构**」，标置信度。为什么要 LLM 评估这一步：import 私有符号有灰色地带——比如测试文件里 `from x import _make_test_config` 是仓库自己的测试工厂约定，不构成对生产结构的焊死；评估器负责把这类「语法上命中、语义上是惯例」的候选过滤掉。

### rubric

主轴 = **private-touch 深度 × mock 内部依赖计数**（组合）。为什么组合两个维度：单一维度都失真——只有 private-touch 深度（戳得深）看不到「mock 内部协作把实现关系冻结」的形态，只有 mock 计数看不到「戳到了多深的私有结构」。深度 × 数量共同刻画「焊死的牢固程度」。

## 实例

### 正例 1：import 私有符号 + 断言私有状态

```python
# src/inventory/service.py
__all__ = ["InventoryService", "reserve"]          # 公开面声明

class InventoryService:
    def _recompute_holdings(self): ...              # 内部方法，不在 __all__ 面
    _cache: dict                                    # 内部状态

# tests/test_inventory.py
from src.inventory.service import InventoryService, reserve
from src.inventory.service import _recompute_holdings   # ← 焊点：import 私有符号

def test_after_transfer():
    svc = InventoryService()
    reserve(svc, sku="A", qty=3)
    _recompute_holdings(svc)                         # ← 测试直接调内部方法编排
    assert svc._cache["A"] == {"held": 3, "available": 7}   # ← 断言私有状态
```

- 【信号档】确定性档·import 私有符号清单命中（`_recompute_holdings` 不在 `__all__`，公开面声明优先规则判定为私有）→ LLM 档评估「是否真的焊死结构」，置信度 0.86：测试不但调内部方法，还断言 `_cache` 这个纯内部数据结构——把缓存的表示方式焊进了测试。
- 【证据等级】确证候选 + LLM 评估——「import 私有」是静态实锤，「焊死结构」的严重度由 LLM 评估标置信度。
- 【agent 失败形态】agent 把 `_cache` 从 dict 换成 LRU 结构（行为完全不变，纯深度化重构），4 个测试全红，红的原因全是 `svc._cache["A"]` 这类断言。agent 面前的选择：放弃重构（质量停滞），或者花时间改 4 个测试（重构成本翻倍，还被训练成「下次别碰这个模块」）。
- 预期 DEBT.md 报告行：

```markdown
### test-shape · tests/test_inventory.py · 置信度 0.86 · 提议带：中
- 信号：import 私有符号 _recompute_holdings（不在 __all__ 公开面）+ 私有状态断言 svc._cache 2 处
- 定位：test_after_transfer / test_reserve_recompute
- 提议修复：把测试迁移到接口上——reserve() 后通过公开查询接口断言可观测行为；_recompute_holdings 作为实现细节从测试移除
```

### 正例 2：mock 内部协作对象

```python
# src/order/pipeline.py —— 单进程流水线，三个内部阶段类
class _Validator: ...        # 内部协作对象
class _Pricer: ...

class OrderPipeline:
    def __init__(self): self._validator = _Validator(); self._pricer = _Pricer()

# tests/test_pipeline.py
from unittest.mock import patch

@patch("src.order.pipeline._Pricer")          # ← mock 内部协作对象（焊点）
def test_pipeline_total(MockPricer):
    MockPricer.return_value.price_for.return_value = 99.0
    pipeline = OrderPipeline()
    assert pipeline.total(order) == 99.0      # 测的是「我假想的 Pricer 行为」
```

- 【信号档】确定性档·mock 目标清单命中（mock 目标 `_Pricer` 是 `pipeline` 模块内部协作类，非公开边界依赖）→ LLM 档评估确认为形状债，置信度 0.79。
- 【证据等级】确证候选 + LLM 评估。
- 【agent 失败形态】agent 把 `_Pricer` 从 `OrderPipeline` 的构造中抽出去、改为按订单类型路由到两个 pricer（行为不变），`test_pipeline_total` 红了——但红的原因只是 mock 的注入路径失效，价格计算逻辑一行没动、也根本没被测到。agent 拿这个红信号当行为回归处理，往错误方向排查半天。
- 预期 DEBT.md 报告行：

```markdown
### test-shape · tests/test_pipeline.py · 置信度 0.79 · 提议带：中
- 信号：mock 内部协作对象 _Pricer（pipeline 模块内部类，非公开边界依赖）1 处
- 定位：test_pipeline_total
- 提议修复：改用真实 _Pricer + 公开边界 fixture（价格表输入），让测试验证路由后的真实价格行为
```

### 反例：mock 公开边界依赖 = 正常实践，不报

```python
# tests/test_shipping.py
from unittest.mock import patch

@patch("src.shipping.carrier.CarrierClient")   # ← mock 网络边界依赖（公开接口）
def test_create_label(CarrierClientMock):
    CarrierClientMock.return_value.create_label.return_value = Label(tracking="1Z999")
    svc = ShippingService(CarrierClientMock())
    assert svc.create_label(order).tracking == "1Z999"
```

mock 了很多东西，长得比正例 2 还「重」，但**不报 test-shape**。

为什么不报：族文件 mock 边界判定明确「**mock 公开边界依赖（网络/DB 接口）= 正常测试实践，不判债**」。`CarrierClient` 是一个跨网络边界的外部服务客户端——mock 它让测试不依赖真实物流商 API，这是测试金字塔里的标准做法；测试验证的仍然是 `ShippingService` 这个公开接口的真实行为（创建面单、返回追踪号）。shape 判据的分野不在「mock 没 mock」，而在 **mock 的对象在边界外还是边界内**：边界外（网络/DB/进程外）mock 是隔离，边界内（模块内部协作）mock 是焊死。防换皮：如果不做这个区分，「mock 数量多」就会被机械报债，把所有正当的测试隔离实践污名化，团队会得出「这套工具反 mock」的错误结论——它反对的只是 mock 错对象。

## 边界与相邻类型

- **implicit-contract**（E 族，最重要的边界）：族文件明确「**shape 判测试侧焊死错误对象（债在测试），implicit-contract 判被测接口侧未声明真实使用条件（债在接口）**」。分野在**债所在侧**：测试 import 私有符号，债在测试文件里，是 shape；接口缺「先 init 再用」的声明，债在源码接口上，是 implicit-contract。**同实例可多 slug 并挂**：一个测试既戳私有（shape）又其 setup 链展示了接口未声明的真实使用条件（implicit-contract 的锚点之一就是 test-scan 的 setup 链）——两行都报。
- **test-gap / test-rot / flaky-test**（同族四分野）：gap 无信号 / rot 假信号 / flaky 噪音信号 / shape **真信号但焊死错误对象**。shape 的测试质量是四者中最好的——信号真实、断言有效、稳定绿——它的问题只在保护钉的位置。修复动作因此不同：gap/rot/flaky 补修测试即可，**shape 必须把测试迁移到接口上，是重构**（族文件原话）。
- **misplaced-seam**（G 族）：都涉及「跨模块关系焊死」，但 shape 焊的是测试↔实现的关系（B 族，测试→源方向），misplaced-seam 焊的是模块↔模块的关系（共编辑提升度）。不相交。

## 讨论要点

- **「公开面声明优先」对无声明仓库的降级**：很多仓库从不写 `__all__`、也没 index.ts 导出表——全部落到语言机制兜底，Python 里大量「无 `_` 前缀但事实上是内部」的符号会漏检。是否引入「无声明仓库的默认口径」（如类公开方法之外全算内部）值得讨论，族文件未提。
- **LLM 评估器的判定标准不够具体**：族文件说 LLM 档判「是否真的焊死结构」并举例测试工厂约定，但「焊死」的操作性定义（改什么样的结构会红？）没有细化为可校验的问题。建议在二期用「真实重构 diff vs 测试红绿」的历史数据做校准（类似 rot 的变异校准思路）。
- **行为学习污染层的边界**：MVP 只测形状代理，但「形状债 → 团队不重构」的因果链本身没有被验证。如果后续实证发现形状代理与重构停滞的相关性弱，这个类型的预排（中）可能要重估。
- **私有符号判定的语言机制细节**：Go 的大小写、TypeScript 的 `#` 都清楚，但 JavaScript 模块**没有**任何语言私有机制——`_` 只是约定。token 表工程化时需要明确「无机制语言」的兜底规则（`_` 约定算不算），族文件未展开。
- **组合主轴的量化口径**：private-touch 深度（离散档位？连续值？）与 mock 计数如何组合（相乘？加权？）族文件未定——实现前需要一次定标，建议沿用严重度带提议「不终裁」原则先给粗粒度组合。
