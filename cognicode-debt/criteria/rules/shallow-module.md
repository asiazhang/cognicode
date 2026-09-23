# shallow-module：浅模块债

> 判据权威来源：[G-architecture-shape.md](../G-architecture-shape.md) · 详解文档供人类讨论，子代理执行口径以族文件为准
> 所属族：[G 族：架构形状债](../G-architecture-shape.md) · 失败模式：效率 + 可导航性 · 预排：高

## 一览

| 证据等级 | 检测档 | 实例粒度 | rubric 主轴 |
|---|---|---|---|
| 全类型风险信号档 + LLM 置信度（「架构候选」） | 确定性（薄壳三元组）+ LLM（穿越成本评估，复用 module_depth.py 判定协议） | **模块级**（连续 shallow 模块相邻呈现加链标注，不合并） | **上下文性价比**（等量行为理解的穿越成本，越高越严重） |

接口面宽度做信号级标注，不进主轴。

## 规则陈述

这条规则说的是：**agent 须穿过多层薄壳才凑出等量行为理解**。一个模块如果自己不藏行为、只做转发（pass-through 薄壳），它对 agent 的贡献是零，但每次穿越都要付读它的成本。三层这样的薄壳叠起来，agent 为了理解底层到底做了什么，要打开 3 个「没什么可看」的文件——这就是**上下文性价比债**：花的 token 和推理是真金白银，换到的信息增量趋近于零。

为什么这对 agent 是债：人类工程师浏览代码有模式识别兜底，扫一眼转发层就知道「这层没事，往下走」；agent 每一层都要认真读、认真建模，薄壳层是纯税。更阴险的是**可导航性**的损失：agent 检索「某个行为在哪」时，名字命中的往往是薄壳层，它得再跳一次才能找到真实现——索引与目标之间隔了一层税。

**与 monolith-file 互为镜像**：巨石文件是「一个东西大得读不完」，浅模块是「太多薄层，每层都没东西」。两者共用「上下文」语言但方向相反——monolith 主轴是上下文占比高（改一处要读全文件），shallow 主轴是性价比低（读了等于没读）。高内聚的深目录树**不是债**：每层都真藏行为（每层 deep）时，嵌套只是可导航成本。

**判罪条件是双因子，缺一不报**：

1. **薄**——pass-through 占比高（这一层主要是转发，没藏行为）；
2. **性价比损失**——穿越 N 层的读取/推理成本，与把同等行为摊平一层相比有明显溢价。

高内聚薄层不报（薄但每层都贡献信息增量，穿越是值得的）——与「高内聚巨文件不报」对称。

## 信号与判定

**确定性档（薄壳事实三元组）**：每个模块产三个数——pass-through 比例（转发调用占该模块全部逻辑的比例）、接口面宽度（公开符号数）、行为量指标（模块自身的行为贡献）。候选线以 **pass-through 比例为主锚**：转发占比高 = 这一层没藏行为，纯中转。确定性档只产事实，**不判罪**。

**LLM 档（穿越成本评估）**：复用 module_depth.py 判定协议（收集→prompt→单 JSON→重试→丢弃），判「agent 凑出对底层行为的理解需打开几层、每层贡献多少信息增量」，标置信度。这一步是双因子的第二因子：pass-through 高只证明「薄」，LLM 评估整个穿越链后才能证明「性价比损失」。

**阈值论证义务**（判据文件原文要求）：报实例的依据是「穿越这 N 层花费的读取/推理成本，与把同等行为摊平一层相比的溢价」——**逐实例在报告行陈述这个溢价**，不是拍脑袋常数。阈值数值留雾区进技术选型。

**证据等级**：全类型风险信号档——「架构候选，LLM 判定标置信度」。架构形状没有运行时确证 oracle（连二期动态测量都难确证「抽象是假的」），这是 G 族的共同底色。

## 实例

### 正例 1：三层转发税（API → Service → Repository 全薄）

```python
# src/users/api.py
def get_user(user_id: str) -> User:
    return user_service.get_user(user_id)        # ← 纯转发

# src/users/service.py
def get_user(user_id: str) -> User:
    return user_repository.find_by_id(user_id)   # ← 纯转发

# src/users/repository.py
def find_by_id(user_id: str) -> User:
    row = db.execute("SELECT * FROM users WHERE id = ?", user_id)
    return User(**row)                            # ← 行为只在这一层
```

- 【信号档】确定性档：api.py pass-through 比例 ≈ 1.0、service.py ≈ 1.0，接口面宽度各 5 个符号，行为量 ≈ 0 → 薄壳候选；LLM 档评估：凑出「查一个用户到底发生了什么」需打开 3 层，前 2 层信息增量 ≈ 0，置信度 0.9。
- 【证据等级】风险信号档（架构候选）+ LLM 置信度。
- 【agent 失败形态】agent 排查「用户查询为什么慢」：先打开 api.py——只有一行转发；跳 service.py——还是一行转发；跳 repository.py 才见到 SQL。三层目录 3 次 seek，其中 2 次是纯税；若它只读前两层就下结论「逻辑很简单，没問題」，结论还是错的。
- 预期 DEBT.md 报告行：

```markdown
### shallow-module · src/users/（api.py → service.py）· 置信度 0.9 · 提议带：中
- 信号：pass-through 1.0 / 1.0，穿越 3 层仅 1 层有信息增量
- 定位：api.get_user / service.get_user 转发链
- 溢价陈述：等量行为（单条查询）摊平一层 = 1 次读取；现状 = 3 次
- 建议：api 层直连 repository，或 service 层吸收真实业务逻辑
- 链标注：与 repository.py 相邻呈现（连续 shallow 链的末端）
```

### 正例 2：薄壳 + 接口面过宽（信息增量低的「门面」）

```python
# src/billing/gateway.py —— 12 个公开方法，全部一行转发到两个内部模块
def charge(order): return _stripe_adapter.charge(order)
def refund(tx):    return _stripe_adapter.refund(tx)
def invoice(order): return _ledger.invoice(order)
# ……其余 9 个同构
```

- 【信号档】确定性档：pass-through ≈ 1.0，接口面宽度 12（宽），行为量 ≈ 0 → 薄壳候选；LLM 档：12 个签名读一遍 = 0 信息增量（签名与转发目标一一对应，可直接推断），置信度 0.85。
- 【证据等级】风险信号档 + 置信度。
- 【agent 失败形态】agent 想改「退款要加审计日志」：读 gateway.py 12 个方法确认退款入口（宽接口面 = 检索面大），再跳 `_stripe_adapter` 才发现真正的退款逻辑；gateway 层的 12 行阅读对定位零贡献。
- 预期报告行：`shallow-module · src/billing/gateway.py · 置信度 0.85 · 提议带：中`，信号栏含接口面宽度 12（信号级标注，不进主轴）。

### 反例：薄但每层都藏行为（高内聚分层，不报）

```python
# src/pipeline/parse.py
def parse(raw: bytes) -> Ast:
    tokens = _lex(raw)           # 300 行词法逻辑，处理 5 种边界编码
    return _to_ast(tokens)       # 200 行语法树构建，处理 3 种语法糖

# src/pipeline/optimize.py
def optimize(ast: Ast) -> Ast:   # 独立职责：400 行优化 pass，可独立测试
    ...
```

**为什么不报**：两层都不是 pass-through（各自藏了数百行真行为），pass-through 比例低，确定性档根本不产候选——即使目录树很深，「深目录树本身不是债：每层都真藏行为时，嵌套只是可导航成本」（判据文件第 1 节镜像分野）。这正是「薄 + 性价比损失双因子缺一不报」的前半个因子在起作用。

## 边界与相邻类型

- **monolith-file（镜像，不并挂）**：机制相反——薄 vs 巨。同一模块不会同时是 shallow-module 和 monolith-file；但一个仓库可以两种债都有（不同模块）。
- **hypothetical-seam（常并挂）**：单实现抽象往往同时是薄壳（接口 + 唯一实现 = 经典转发层）。同实例可**多 slug 并挂**，但主轴与修复建议不同：shallow = 合并/加深，hypothetical = 移除抽象或等第二个实现出现再抽象。报告里两个 slug 挂同一位置，各自的 rationale 说各自的账。
- **naming-debt**：薄壳层的转发函数命名再差也不归本类型管——检索误导归 A 族。

## 讨论要点

- **阈值数值未定**：pass-through 比例候选线、穿越成本溢价阈值都留雾区进技术选型（判据文件明示「不是拍脑袋常数」，要求逐实例陈述溢价）——评审时可以讨论：溢价陈述用什么单位（读取次数？token 估算？）才够具体又不伪精确。
- **pass-through 比例的测量口径**：一行转发是 pass-through，那两行（转发 + 参数重排）算不算？三元组里「行为量指标」的定义在技术选型时需要收紧。
- **接口面宽度进信号级标注不进主轴**——是否合理？宽而薄的门面（正例 2）直觉上比窄而薄更烦，但 rubric 只锁了性价比主轴，评审时可议。
