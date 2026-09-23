# E 族判据：进程债（含 F 族并入；build-entry-unclear / monolith-file / implicit-contract / fidelity-debt）

> Part of [Wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39) · 来源：[#53](https://github.com/asiazhang/cognicode/issues/53) 判据细则 + [#40](https://github.com/asiazhang/cognicode/issues/40) 类型清单 + [debt-types.md](../../docs/research/debt-types.md)
> 本文件是 E 族（含原 F 族独立内容）分族子代理的完整作业指令。跨族共享约定（证据包 16K 预算、回传 JSON schema、严重度带定档流程）见 [SKILL.md](../SKILL.md)，此处不重复。

> 逐类型人类向详解（含实例）见 [rules/](rules/)：build-entry-unclear · monolith-file · implicit-contract · fidelity-debt
## 0. 族概览与 F 族归位

原 F 族（版本控制债）独立内容不足：`zombie-branch` 已出册（#40）、`vendored-dep` 留册一行带过（下文第 5 节），按 #42「留册类型族内一行带过」精神并入本文件，不单独成文。

| slug | 名称 | 覆盖 | 检测档 | rubric 主轴 | 预排 |
|---|---|---|---|---|---|
| `build-entry-unclear` | 构建入口不明 | 覆盖 | 确定性（probe 复用）+ LLM | 冷启动阻断度 | 高 |
| `monolith-file` | 巨石文件 | 覆盖 | 确定性（体量五元组）+ LLM（局部性） | 单次典型修改的上下文占比 | 高 |
| `implicit-contract` | 隐式契约 | 覆盖 | 确定性（双锚点痕迹）+ LLM（评估器） | 违反后果烈度 | 高 |
| `fidelity-debt` | 保真度债 | 覆盖 | 确定性（替身指纹）+ LLM（保真差距） | 假保护覆盖面 | 高 |
| `vendored-dep` | Vendored 依赖（F 族） | **留册不覆盖** | — | — | 中 |

**族结构：无族级共享中间层**。四类型判据各自独立，不造框架；唯一族级判据锚 = build-entry-unclear 与延迟轴共享「agent 冷启动到拿到验证反馈」的验证回路时间轴视角。新语种/生态适配沿用 B 族先例（token 表是工程边界不是判据）。

## 1. build-entry-unclear

### 判据

= **验证回路入口的证据链断裂**（环境可用性）。判据范围收口到验证回路（同 config-drift 先例，纯生产/部署路径入口无 agent 失败形态不报）。延迟轴仓库内部分（测试硬连 staging、无本地 compose）同收——回路走不完与找不到入口同属可启动性失败。

### 四档信号

| 档 | 信号 | 检测与证据等级 |
|---|---|---|
| **E1 声明缺失** | probe 定位面全空，仓库无任何构建/测试命令声明 | 静态事实确证 |
| **E2 声明碎片化** | 多源不一致（package.json 说 npm、CI 用 pnpm） | 静态事实确证；「不一致是否互斥」LLM 裁（同 config-drift C2 结构——npm/pnpm 不一致可能装出错环境静默污染，不只是浪费尝试） |
| **E3 声明不可信** | 命令依赖隐式前置：引用不存在的 compose 文件、断链脚本路径、未声明 env（最阴险，声明存在但撒谎） | 静态线索法（doc-rot 断链态同款思路）判**风险信号 + 置信度**——线索只证明断链嫌疑，不证明跑不通 |
| **E4 延迟绕远** | 测试硬连 staging、无本地 compose | 回路存在但走不完 |

跑通验证留二期与动态测量一起（skill 形态跑真命令有安全与时长约束）。

### 两档分工

- **确定性档**：复用 probe.py 探测定位面（零改动可搬），产出从成败判定改为**证据链**。
- **LLM 档**：E2 互斥裁定、E3 断链嫌疑评估。

### 实例粒度

验证回路环节级——每条断链/矛盾锚定到具体声明文件；E1 全缺失为**仓库级单点置顶**（同 agent-doc-missing 概念层缺失置顶先例）。

### rubric

主轴 = **冷启动阻断度**（复用 config-drift 主轴语言）：E1 ＞ E3（浪费尝试且污染归因）＞ E2（试错成本）＞ E4（能走完但慢）。

## 2. monolith-file

### 判据

= **双层**：体量候选 + 修改局部性。失败形态：超出 agent 有效上下文，改一行要读五千行（效率 + 可导航性）。`code-smell` 的 agent 相关子集（超长函数/深嵌套/上帝类）并入。

### 两档分工

**确定性档（体量事实五元组）**：token 估算（字符 ≈ 4:1）、符号数、符号密度、最大函数长度、最大嵌套深度。候选线 = token 估算超中位 agent 有效预算参考线（**32K**——有效理解质量衰减远早于窗口上限；候选线不是判罪线）。排除 @generated / vendored / lockfile（与 duplicate-code 确定性档同口径）。

**LLM 档（修改局部性评估）**：module_depth.py 判定协议复用（收集→prompt→单 JSON→重试→丢弃），判「改一个典型任务需读的上下文量」。

### 防换皮

传统 lint 报「函数太长」（美学），本类型报「agent 改一处要读全文件」（失败形态）——高内聚巨文件传统报、我们不报。

### rubric

主轴 = **单次典型修改的上下文占比**（需读上下文量 ÷ 文件体量）：占比越高越严重；高内聚大文件占比低不报。体量五元组做信号级标注不进主轴（**大不是罪，大且必须全读才是**）。32K 参考线的精确校准留二期实证。

## 3. implicit-contract

### 判据（双锚点降配）

= **仓库痕迹与接口声明面的差集**——契约痕迹存在于代码/注释/测试但未外化到接口（签名/docstring/类型）。调用方依赖未声明的不变量（「先 init 再用」），代码上看不出来，炸了才知道（可解性 + 变更安全性）。

**双锚点**：

1. **文本痕迹**：注释 NOTE、防御检查报错、assert 消息中的契约语言（确定性模式匹配提取）。
2. **测试 setup 链**：挂 test-scan 中间产物便车（[B 族](B-testing.md)产出）——setup 链即「怎么用」的活示范，比对接口声明面差集。

**已砍锚点**：调用共现锚（「N 个调用方里 M 个先调 init」）不采——近调用图分析是重语言相关的真静态分析，破坏「token 表是工程边界」先例；且砍掉后与 oral-tradition 边界更干净（**痕迹所在层分界**：代码/测试/注释层 → implicit-contract；任何载体无痕迹 → oral-tradition）。

### 两档分工

- **确定性档**：双锚点痕迹提取。
- **LLM 档 = 候选评估器**：判「真实且未声明的不变量吗」，标置信度。

### 证据等级

**存在性候选**（与 oral-tradition 同级全类型最弱档）——静态档拿不到确证 oracle，运行时炸点是二期动态测量的天然确证。

### 与 test-shape 边界

shape 判**测试侧**焊死错误对象（债在测试），本类型判**被测接口侧**未声明真实使用条件（债在接口）——同实例可多 slug 并挂。

### rubric

主轴 = **违反后果烈度**：崩溃/数据损坏 ＞ 静默错结果 ＞ 性能劣化（存在性已最弱档，能拉开严重度的只剩真炸的时候有多疼）。

## 4. fidelity-debt

### 判据

= **声明的真实环境与测试实际替身环境的分叉 + 全绿证据同时在手**（分叉本身不报——只有「全绿被当作真实环境也安全」的信号存在时才报）。测试全绿但保的是替身不是本体（SQLite 替 PG 型环境级假保护），agent 在假安全信号下放行真实环境的破坏（环境可用性 + 变更安全性）。#53 自 #52 雾区毕业的新生类型，预排高沿 test-rot 假保护同档。

### 检测

- **声明面**：compose 文件、CI workflow services 段、配置模板连接串、agent 上下文文档（config-drift 六源子集，**不含 README**——那是 C3 断言比对面）。
- **确定性档·替身识别**：测试配置/fixture 里的替身指纹（SQLite 内存串、testing.local host、docker-compose.test.yml 独立环境）。
- **LLM 档·保真差距评估**：判真实环境特有面（PG 的 migration/并发/类型强制）在替身上是否被绕过，标置信度。

### 与 B 族三态分界（族内分野核心）

test-gap **保护不存在** / test-rot **保护虚假**（断言烂）/ fidelity **保护是真的但保的是替身不是本体**（环境虚假）——同模块多 slug 并挂，修复建议不同：补测试 / 修断言 / 对齐环境或显式声明替身局限。

### 实例粒度

**环境对级**：声明真实环境 × 实际测试替身，一对一个实例。

### rubric

主轴 = **假保护覆盖面**（替身绕过的真实环境特有面越广误导越深：只有连接 ＜ 加 migration 行为 ＜ 再加并发/类型强制）；全绿持续提交数做信号级标注。

## 5. 留册汇总

| slug | 为何不覆盖 | 捡回条件 |
|---|---|---|
| `vendored-dep` | 低频类型；惯例 vendor（Go/composer/cargo）不是债；「无标记即债 + 已改证据升档」状态阶梯设计稿存 [#53](https://github.com/asiazhang/cognicode/issues/53) 票内 | DEBT.md 样例票或二期实证发现 vendor 误改高频痛感 |

## 6. 子代理执行协议

- **候选来源**：确定性档 = probe 证据链（E1–E4 静态事实）、体量五元组（monolith）、双锚点痕迹提取（implicit-contract）、替身指纹（fidelity）；LLM 档 = E2 互斥裁定 + E3 断链嫌疑、修改局部性评估（monolith）、候选评估器（implicit-contract）、保真差距评估（fidelity）。
- **中间产物消费**：implicit-contract 的测试 setup 链锚点消费 **test-scan**（B 族产出，见 [B-testing.md](B-testing.md)）；monolith 的 LLM 档复用 module_depth.py 判定协议（收集→prompt→单 JSON→重试→丢弃）；E1 探测复用 probe.py 定位面（只定位不执行）。
- **族内分野规则**：fidelity 与 B 族三态的分野见第 4 节（信号真环境假 vs 信号本身的问题）；implicit-contract 与 oral-tradition 以痕迹所在层分界、与 test-shape 以债所在侧分界；build-entry-unclear 与 config-drift 以信号载体分界（compose 缺失归 E4 不重复挂 C1）。
- **证据包组装**：E2/E3 附声明原文与矛盾/断链证据；monolith 附五元组 + LLM 局部性判定输入；implicit-contract 附痕迹原文与接口声明面差集；fidelity 附声明面与替身指纹对照，总量 16K 预算内，超预算降采样并在 rationale 声明。
- **输出 schema**：`{slug, location, confidence, rationale, fix_suggestion}` + 提议严重度带（沿各类型主轴方向提议，不终裁）。
- **语种扩展**：新语种/生态 = 新增 token 表（工程边界不是判据）。
