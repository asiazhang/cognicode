# duplicate-code：重复代码

> 判据权威来源：[A-structural.md](../A-structural.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：A 结构债（[A-structural.md](../A-structural.md)）· 失败模式：变更安全性 + 效率 · 预排：高

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| exact / near：确定性工具事实（文本重复确证）；语义重复：LLM 判定 + 置信度 | 确定性（重复检测工具集成）+ LLM（语义重复发现） | **重复簇**：N 份副本 = 一个实例，簇内指定权威副本 | **分叉状态**（一维）：已分叉 ＞ 未分叉但无权威声明 |

（A 族文件未定义 B 族式的「确证 / 风险」证据等级语言，上表表述系从两档分工推导，见「讨论要点」。）

## 规则陈述

这条规则说的是：**同一份知识在仓库里存在多份，而且没有声明哪一份是权威的**。这是全方法论「唯一真值原则」（见根目录 CONTEXT.md 术语表）最直接的类型化身。

关键在判据的措辞：不是「有重复文本」，而是「知识存在多份且无权威声明」。两者的差别值得展开——

- 如果判据是「有重复文本」，那逐字复制一段工具函数就该报。但两份一模一样的副本，只要没有任何一份被声明为权威（注释、文档、目录约定都算声明），下一次修改就可能只改其中一份，「改 A 忘 B」随时发生。所以族文件明确说：**「改 A 忘 B」是利息而非本金**——分叉是这笔债的利息，本金是「知识多份且无权威声明」这个状态本身。哪怕今天两份还一字不差，只要处于这个状态，就构成债。
- 反过来，同一份知识存在多份、但声明了权威（例如「生成文件，勿手改，源头在 X」加生成标记），就不构成本类型的债。

为什么它是「对 AI 不友好的债」？agent 的失败形态有两条：

1. **变更安全性**：agent 接到「把这个函数的错误处理改成重试三次」的任务，用名字或语义检索只找到其中一份副本改了，测试恰好只覆盖那份——另一份副本继续旧行为，bug 由此产生。agent 事后无法归因，因为它压根不知道第二份副本存在。
2. **效率**：测试代码重复是重灾区——agent 写测试时无法复用既有样板，每次都从零写一遍近似结构，token 成本极高。所以族文件特别强调：**测试代码与产品代码同等优先级**，测试目录里的重复不是二等公民。

## 信号与判定

按两档分工：

**确定性档（重复检测工具集成，算法不自研）**

- 集成 jscpd / PMD CPD 类现成工具，产出**文本重复事实**。具体选型与 near 档阈值参数在雾区（见族文件与地图，不预设）。
- 重复事实分两档：**exact**（逐字相同）与 **near**（近重复，阈值由工具配置）。
- 扫描范围排除：vendored 目录、生成文件（`@generated` 标记）。
- **语言惯用样板不建白名单**——每个语种都有的 idiomatic boilerplate 由 LLM 语义档识别并标注降级，而不是在确定性档维护一份会腐烂的清单。

**LLM 档（语义重复发现）**

- 判「**同一知识、独立实现**」。文本相似度为零的语义重复是最危险的实例——两个函数用不同库、不同风格实现了同一条业务规则，任何文本级工具永远抓不到，只有语义档能发现。
- 扫描范围为**全仓**，不排除 vendored / 生成物——语义档判断的是知识重复，不是文本重复，vendor 里的知识副本同样构成「改 A 忘 B」风险。
- 对确定性档产出的 exact / near 候选做**语义复核**：语言惯用样板标注降级（不报或降档）。
- 输出标置信度。

**实例粒度与报告**

- 一个重复簇 = 一个实例，不管簇里有几份副本。簇内须指定**权威副本**（哪份是当前维护的真相），修复建议挂「其余副本向权威副本合并」。
- 报告行须能指出簇内各副本位置与权威副本。
- 其余维度做**信号级标注**，不进主轴：副本距离（不同模块 > 同文件，越远越危险）、语义重复 ≥ 文本重复（语义档命中比 exact 更危险）、副本数、变化频率。

**证据等级落点**：exact / near 由工具产出，是文本重复的客观事实（确证级）；语义重复是 LLM 判定，必须标置信度。已分叉簇（内容已不一致）是主轴上最严重的档位。

## 实例

### 正例 1：exact 重复 + 已分叉（主轴最严重档）

两处逐字起家的 `formatDuration`，后来各自被改过一次，已分叉：

```python
# src/utils/time.py
def format_duration(seconds: float) -> str:
    """把秒数格式化为 '1h 2m 3s' 样式。"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

# src/report/duration.py —— 半年前从这里复制走，上月有人单独改了这里：
def format_duration(seconds: float) -> str:
    """把秒数格式化为 '1h 2m 3s' 样式。"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"   # 改成了冒号风格，utils 那份没跟上
```

- 【信号档】确定性档 exact/near 命中（虽已小分叉，仍在 near 阈值内）。
- 【证据等级】文本重复事实确证 + 分叉状态确证（两份内容不一致是客观事实）。
- 【agent 失败形态】用户要求「时长统一用冒号风格」，agent 检索到 `utils/time.py` 那份改了，报告页继续输出 `1h 2m 3s` 风格——变更安全性失败，且 agent 无从知道还有第二份。

```
DEBT.md 报告行（示意）
slug:          duplicate-code
location:      src/report/duration.py::format_duration + src/utils/time.py::format_duration（权威副本待定，建议 utils）
confidence:    高
rationale:     exact 起源、已分叉（输出风格不一致），无任何权威声明
fix_suggestion: 其余副本向权威副本合并；权威副本进公共模块并声明
提议严重度带:   高（主轴：已分叉）
```

### 正例 2：near 重复（未分叉、无权威声明）

```python
# services/api/errors.py
def raise_if_missing(payload: dict, *keys: str) -> None:
    for k in keys:
        if k not in payload:
            raise ValidationError(f"missing field: {k}")

# services/cli/errors.py —— 同一知识第二份，字段名略改
def require_fields(data: dict, *names: str) -> None:
    for n in names:
        if n not in data:
            raise ValidationError(f"missing field: {n}")
```

- 【信号档】确定性档 near 命中。
- 【证据等级】near 事实确证；未分叉但无权威声明。
- 【agent 失败形态】agent 在 API 服务里要给校验错误加 i18n，只改了 `errors.py`；CLI 侧同需求第二次被提出时才发现另一份。未分叉时的痛感是潜在的分叉风险 + 双倍维护。

```
slug:          duplicate-code
location:      services/api/errors.py::raise_if_missing + services/cli/errors.py::require_fields（权威副本建议 api 侧）
confidence:    高
提议严重度带:   中（主轴：未分叉但无权威声明）
```

### 正例 3：语义重复（文本相似度为零，工具永远抓不到）

```python
# billing/retry.py
def charge_with_retry(order):
    for attempt in range(3):
        try:
            return gateway.charge(order.amount, idempotency_key=order.id)
        except GatewayTimeout:
            if attempt == 2:
                raise
            sleep(2 ** attempt)

# shipping/shipment.py —— 完全不同风格，实现同一条规则：
# 「对外部服务调用最多重试 3 次、指数退避、幂等键防重复执行」
class ShipmentDispatcher:
    def dispatch(self, parcel):
        key = f"ship:{parcel.tracking_no}"
        backoff = 1
        for _ in range(3):
            try:
                return self.carrier_api.send(parcel, idempotency_key=key)
            except CarrierUnavailable:
                backoff *= 2
                time.sleep(backoff)
        raise DispatchFailed(parcel.tracking_no)
```

- 【信号档】LLM 语义档全仓发现（确定性档零输出——文本相似度为零）。
- 【证据等级】LLM 判定，置信度中（「同一知识」是推断：重试次数、退避、幂等键三要素齐同）。
- 【agent 失败形态】需求「全局重试从 3 次改 5 次」：agent 只找到其中一处改了，另一处沉默地维持 3 次——变更安全性失败，且语义重复比文本重复更难被 agent 自己发现。

```
slug:          duplicate-code
location:      billing/retry.py::charge_with_retry + shipping/shipment.py::ShipmentDispatcher.dispatch（权威副本：billing 侧）
confidence:    中（语义重复，LLM 推断）
提议严重度带:   高（信号级标注：语义档命中 ≥ exact）
```

### 反例：语言惯用样板（降级不报）

```python
# tests/conftest.py 与 tests/unit/conftest.py 各有一段
@pytest.fixture
def sample_user():
    return User(name="Alice", email="alice@example.com")
```

两个 conftest 里有近似的 fixture 样板、Java 里成对的 getter/setter、Express 里结构雷同的路由注册块——这些是**语言的「方言」**，不是这个仓库的知识分叉。族文件明确不建白名单，由 LLM 语义档对确定性候选复核后**标注降级（不报或降档）**。理由：判据锚定的是「同一知识多份」，而惯用样板的内容由语言生态决定，任何仓库都长这样，报了全是噪音，会把真正的知识分叉淹没。防换皮地说：传统重复检测工具在这里会大量误报（工具视角），本类型的判据把它压掉（agent 失败形态视角——样板不会造成「改 A 忘 B」的知识分叉）。

## 边界与相邻类型

- **dead-code（同族，留册不覆盖）**：本族子代理不产 dead-code 实例，检测已商品化委托外部工具。重复簇里若混有死副本，死副本的事实不单独开实例。
- **naming-debt（同族）**：naming 判「检索索引失效」（名字误导），本类型判「知识多份」。确定性档的「重复符号名」信号走 naming-debt 的候选通道；只有当重复符号背后是重复知识时才落本类型。
- **test-rot 的快照信号（B 族）**：快照-实现的重复是**时序信号**（快照与实现共漂移），本类型是**结构信号**（同一知识多份静态存在）——同一快照文件可同时挂两 slug。
- **config-drift 的 C2 同值多源（D 族）**：D 族明文「同值多源不报（让渡 duplicate-code 家族）」——配置键多份同值的痛感是变更安全机制，归本类型的知识重复逻辑，D 族不预支。
- **多债并存**：同一位置同时命中其他族类型时多 slug 并挂，本类型不裁。
- **权威声明豁免**：`@generated` 生成物 + 「源头在 X」的声明 = 已声明权威，不构成本类型债（确定性档直接排除生成文件，语义档全仓扫描时以「是否声明权威」为分野）。

## 讨论要点

1. **工具选型与 near 阈值留雾区**（族文件明示不预设）：jscpd / PMD CPD 的阈值差异会显著改变 near 候选量，需在实跑中校准。
2. **A 族缺显式证据等级语言**：B/C/D/E 族都有「确证 / 风险 / 存在性候选」的等级语言，A 族文件没有对应表述。本文件一览表中的等级措辞是从「工具事实 vs LLM 推断」推导的，建议 review 时补一句定音。
3. **权威副本的指定依据缺句**：报告行须「簇内指定权威副本」，但族文件没说指定的判据（最近变更？有测试覆盖？被 import 更多？）。扫描子代理需要一个确定性的指定规则，否则两次扫描可能指定不同的权威副本，破坏 diff 稳定性。
4. **失败模式归属扩展**：debt-types.md 清单里 duplicate-code 失败模式只标「变更安全性」，A 族文件补了「效率」（测试重复 token 成本）——不算矛盾，但属于族文件对清单的有意扩展，值得确认口径一致。
5. **语义重复的置信度校准**：「同一知识」的判定没有静态 oracle，假阳性（两个相似但独立演化的实现）会直接把不相关代码绑进一个簇，修复建议「向权威合并」可能制造错误合并。是否需要「簇成员人工确认」的报告标注，留 review。
