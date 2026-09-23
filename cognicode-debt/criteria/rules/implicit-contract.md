# implicit-contract：隐式契约

> 判据权威来源：[E-process.md](../E-process.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[E 族：进程债](../E-process.md) · 失败模式：可解性 + 变更安全性 · 预排：高

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 存在性候选（全类型最弱档，与 oral-tradition 同级） | 确定性（双锚点痕迹）+ LLM（评估器） | 未单列（痕迹原文 + 接口声明面差集进证据包） | 违反后果烈度（崩溃/数据损坏 ＞ 静默错结果 ＞ 性能劣化） |

（一览表按族文件第 0 节概览 + 第 3 节正文誊写。「存在性候选」是全类型最弱的证据档——连债的存在都是推断——这是本类型所有设计约束的根源。）

## 规则陈述

这条规则说的是：**调用方依赖一些「接口上看不出来」的使用前提**——最经典的形态是「先 init 再用」：`QueryEngine.search()` 从签名到类型到 docstring 都没有告诉你，调用它之前必须先调一次 `QueryEngine.load_index()`，否则拿到的是空结果甚至空指针。这个前提是真实的（违反它真的会炸），但它没有外化到接口的任何声明位置——签名、参数类型、docstring、返回类型里都找不到。它存在于哪里？注释里的一句 NOTE、代码里一道防御性检查的报错文案、测试 setup 链的固定动作序列。**仓库痕迹与接口声明面之间有一个差集，这个差集就是隐式契约**。

为什么这对 agent 是债，而且伤在两个维度：

- **可解性**：agent 读接口（签名 + 类型 + docstring）推断「怎么用」——这是它理解代码的主路径。隐式契约恰好在这条主路径上**隐形**。agent 按 API 面貌写出的第一版调用，命中隐式前提的概率相当高；它只能靠炸了才知道（defensive check 的报错、或裸异常）。人类老员工脑子里有这份契约，agent 每次冷启动都没有。
- **变更安全性**：更阴险的方向——agent 改**提供方**代码时，不知道某个内部顺序是被外部依赖的不变量。它「简化」了 init 流程（比如把 `load_index` 合并进构造函数、或改成惰性加载），行为看起来完全正常，所有仓库内测试全绿——然后某个不知道在哪的调用方（甚至只在生产环境部署脚本里）炸了。契约没有声明，就没有变更时的检查对象。

族文件把这个类型设计成「**双锚点降配**」：MVP 只采两个便宜且确定的锚点，砍掉了最贵的那个（见下文）。这是全类型里证据最弱的一档，报告语言必须诚实——「存在性候选」，不是实锤。

## 信号与判定

### 双锚点（确定性档提取）

1. **文本痕迹**：注释 NOTE、防御检查的报错文案、assert 消息里的契约语言。这些是仓库里「有人说出了契约但没放对地方」的位置——确定性模式匹配可提取（关键词如「必须先」「requires」「先调用」「before using」等，token 表工程化）。
2. **测试 setup 链**：**挂 test-scan 中间产物的便车**（B 族产出的 per-test-file 结构化记录）。测试的 setup 链是「这个接口真实怎么用」的活示范——如果每个测试都在调 `search()` 之前先调 `load_index()`，这条顺序就是被依赖的隐式契约，哪怕没有任何文字写过它。比对接口声明面（签名/docstring/类型）的差集：setup 链里出现、声明面里没有的使用前提，就是候选。

两个锚点提取的都是「契约痕迹存在于仓库、但没外化到接口」的**差集证据**。

### 已砍锚点：调用共现（重要设计决策）

最初的第三个锚点设想是「调用共现」——「N 个调用方里 M 个先调 init」，从调用方的实际行为统计反推契约。族文件明确**砍掉**，理由有二：

- **成本与先例**：近调用图分析是重语言相关的真静态分析，每种语言一套完整工程——破坏「token 表是工程边界不是判据」的先例（新语种本应只翻译 token 表，不重写分析器）。
- **边界更干净**：调用共现是**零文字痕迹**也能发力的锚点，砍掉它之后，implicit-contract 与 oral-tradition 的分界变得干净（见反例）。

### 两档分工

- **确定性档**：双锚点痕迹提取，只产候选（痕迹原文 + 声明面差集）。
- **LLM 档 = 候选评估器**：判「这是**真实且未声明的不变量**吗」，标置信度。为什么需要评估：文本痕迹会误命中（注释里的「必须先」可能描述的是另一个函数的事）、setup 链的固定顺序可能是巧合而非前提（先 A 后 B 不代表 B 依赖 A）——评估器把「痕迹存在」升级为「契约存在」的判断。

### 证据等级：存在性候选

**全类型最弱档，与 oral-tradition 同级**。为什么这么弱：静态档拿不到确证 oracle——「违反这个前提会炸」只能运行时验证，MVP 的静态扫描连运行都不做。运行时炸点是二期动态测量的**天然确证 oracle**：跑测试时捕获的 `IllegalStateError: call load_index() first` 就是实锤。MVP 的报告行必须带存在性候选的限定语，rubric 才用「违反后果烈度」这种前瞻性的轴（见下）。

### rubric

主轴 = **违反后果烈度**：**崩溃/数据损坏 ＞ 静默错结果 ＞ 性能劣化**。为什么选这条轴：证据档已经是最弱的存在性候选，在「债多确定」的维度上没有可拉开的层次——能拉开严重度的只剩下「真炸的时候有多疼」。一个隐式契约如果违反后是静默错结果（比如没 init 就查、拿到空列表当真相用），比违反后立刻崩溃的更严重——崩溃至少立刻暴露，静默错结果会流到下游。

## 实例

### 正例 1：文本痕迹 + 声明面差集

```python
# src/search/engine.py
class QueryEngine:
    def load_index(self, path: str) -> None:
        """Load the index from disk."""
        ...

    def search(self, query: str) -> list[Hit]:
        """Search the loaded index."""
        # NOTE: caller must call load_index() before search(),
        # otherwise _index is None and we return empty results silently
        if self._index is None:
            return []          # ← 防御检查：静默吞掉未 init 的调用
        return self._index.query(query)
```

- 【信号档】确定性档·双锚点之文本痕迹（NOTE 注释 + 防御检查两处痕迹）→ LLM 档评估：契约真实（`_index` 确实是 search 的硬前提）、未声明（`search` 的签名/docstring/类型均未提及前提），置信度 0.88。
- 【证据等级】存在性候选——「违反会静默返回空结果」是 LLM 从代码语义读出的推断，未动态验证。
- 【agent 失败形态】使用侧：agent 读 `search` 的 docstring「Search the loaded index」，推断 index 加载是自动的或已由框架处理，直接调用——拿到空结果，且**没有报错**，把「无命中」当真相返回给上层。变更侧：agent 重构 QueryEngine 为惰性加载，删掉显式 `load_index`，所有单测（setup 链里都先 load）全绿——生产环境里一个不走的代码路径上的调用方开始静默返回空。
- 预期 DEBT.md 报告行：

```markdown
### implicit-contract · src/search/engine.py · 置信度 0.88 · 提议带：高
- 信号：文本痕迹——NOTE 注释 + 防御检查（未 init 静默返回空）2 处；接口声明面差集——search() 签名/docstring/类型均未声明「先 load_index」前提（存在性候选）
- 定位：QueryEngine.search / QueryEngine.load_index
- 提议修复：外化契约——search() 签名改为接收已加载的 Index 参数（类型即契约），或未 init 时显式 raise
```

### 正例 2：测试 setup 链锚点

```python
# src/auth/session.py
class SessionManager:
    def begin(self, user_id: str) -> None: ...
    def authorize(self, action: str) -> bool: ...
    # docstring 与类型签名均无任何先后顺序说明

# tests/test_auth.py —— test-scan setup 链记录
def test_authorize_checked_action():
    mgr = SessionManager()
    mgr.begin("u1")              # ← 每个测试都先调 begin
    assert mgr.authorize("delete") is True

def test_authorize_denied_action():
    mgr = SessionManager()
    mgr.begin("u1")              # ← 又是先 begin 再 authorize
    assert mgr.authorize("root-only") is False
# 仓库内 17 个测试，17 个都在 authorize 前先调 begin——顺序 100% 一致
```

- 【信号档】确定性档·双锚点之测试 setup 链（test-scan 记录的调用顺序：`authorize` 前 `begin` 出现率 17/17）→ 声明面差集比对（`authorize` 的签名与 docstring 零顺序说明）→ LLM 档评估：`authorize` 读取的会话状态由 `begin` 建立，顺序是真实前提，置信度 0.81。
- 【证据等级】存在性候选。
- 【agent 失败形态】agent 给 `authorize` 加一个新参数并顺手「清理」它对会话状态的隐式依赖（改为直接从 user_id 推权限），破坏了 `begin` 建立的会话上下文语义；仓库测试因为 setup 链恰好补了前置全绿，一个生产环境里先 begin 再 authorize 再读会话审计日志的调用方行为悄悄变了。
- 预期 DEBT.md 报告行：

```markdown
### implicit-contract · src/auth/session.py · 置信度 0.81 · 提议带：中
- 信号：测试 setup 链——authorize 前置 begin 出现率 17/17；声明面差集——签名/docstring 无顺序声明（存在性候选）
- 定位：SessionManager.authorize
- 提议修复：authorize() 显式返回/消费会话对象，把先后顺序变成类型依赖
```

### 反例：零文字痕迹场景，让渡 oral-tradition

```
场景：团队内部人人皆知「部署前要先跑 scripts/warm_cache.sh，
不然首页首访超时」——但这句话：
- 代码注释里没有；防御检查不存在（超时不报错，只是慢）；
- 测试 setup 链里也没有（测试用的 fixture 不经过冷缓存路径）；
- 部署文档提过一嘴，但那份文档三年前就没人更新了。

双锚点提取结果：文本痕迹 0 命中，setup 链 0 差集。
```

这**确实是一份真实存在的隐式知识**，agent 也确实会在这里栽跟头（不知道要预热缓存，部署后首访超时）。但**不报 implicit-contract**，让渡给 **oral-tradition**（口头传统，C 族）。

为什么不报：族文件的分界规则是「**痕迹所在层**」——implicit-contract 只收「痕迹在代码/测试/注释层」的场景（双锚点能提取到东西）；**任何载体无痕迹**的隐式知识归 oral-tradition（其判据锚定 agent 高触达外化载体的覆盖缺口）。这条分界为什么必须干净：如果 implicit-contract 也做「零痕迹推断」（比如靠调用共现反推），两个类型的检测面就会大面积重叠、同一份知识被报两次——这正是砍掉调用共现锚点的第二个理由。一句话：**有痕迹的隐式找 implicit-contract，无痕迹的隐式找 oral-tradition**。

## 边界与相邻类型

- **oral-tradition**（C 族）：如上反例——**痕迹所在层**是唯一分界。痕迹在代码注释/防御检查/测试 setup 链 → implicit-contract；零痕迹、只活在人脑和聊天记录里 → oral-tradition。两个类型的证据档同级（存在性候选），但锚点和修复方向完全不同：本类型外化到**接口**（签名/类型），oral-tradition 外化到 **agent 高触达载体**（agent 文档/领域模型文档）。
- **test-shape**（B 族）：族文件明确「**shape 判测试侧焊死错误对象（债在测试），implicit-contract 判被测接口侧未声明真实使用条件（债在接口）——同实例可多 slug 并挂**」。分野在**债所在侧**：正例 2 里，如果那些测试还直接 import 了 `_session_store` 私有符号（shape 的焊点），则同一批测试同时触发两个 slug——shape 报「测试焊死实现」，implicit-contract 报「接口未声明前提」，两行各自修复：shape 迁移测试到接口，implicit-contract 把前提声明进接口。两件事互不替代。
- **fidelity-debt**（同族）：都在「接口声明与真实之间存在落差」的谱系上，但 implicit-contract 的落差在**使用前提**（怎么调），fidelity 的落差在**测试环境**（测的是不是本体）。不相交。
- **misplaced-seam**（G 族）：都涉及「跨模块的隐式依赖」，但 seam 焊的是模块间编辑耦合（改 A 必须连着改 B），implicit-contract 是调用方对接口前提的依赖。如果「先 init 再用」的 init 在另一个模块，两类型可能同位置出现，但报的债不同。

## 讨论要点

- **文本痕迹 token 表的召回率**：NOTE/防御检查文案的写法千变万化（中文注释、拼音报错、没有 NOTE 字样的裸 `if self._index is None: raise`）——模式匹配锚点容易漏。族文件没有给 token 表的召回/精确目标，建议工程化时先在样例仓库跑一轮人工对照。
- **setup 链锚点的方向性歧义**：正例 2 用「17/17 一致」做信号，但测试 setup 链里 100% 的顺序未必都是契约——`mgr = SessionManager()` 也是 17/17 的第一步，显然不是隐式契约。LLM 评估器需要区分「编排惯性」与「真实前提」，这个判断本身缺少校准数据。族文件未提供评估器的问题模板。
- **差集的「声明面」范围**：签名/docstring/类型之外，`TypedDict` 的字段注释、`pyi` 存根、协议类算不算声明面？范围划宽了差集变小（漏报），划窄了候选变多（LLM 档成本上升）。族文件只列了「签名/docstring/类型」三样，边界模糊。
- **运行时炸点 oracle 的采集口径缺句**：族文件说「运行时炸点是二期动态测量的天然确证」，但没说炸点怎么映射回契约实例（一个 `IllegalStateError` 对应哪条候选？）——二期的映射协议需要设计。
- **rubric 与证据档的错位**：主轴「违反后果烈度」评估的也是 LLM 推断（「违反后大概率静默错结果」），两层推断叠乘——置信度的传播怎么算（相乘？取 min？）族文件未定义，报告行的置信度语义在双层推断下变得含混。
