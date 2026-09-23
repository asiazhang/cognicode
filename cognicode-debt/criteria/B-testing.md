# B 族判据：测试债（test-gap / test-rot / flaky-test / test-shape）

> Part of [Wayfinder 地图 #39](https://github.com/asiazhang/cognicode/issues/39) · 来源：[#50](https://github.com/asiazhang/cognicode/issues/50) 判据细则 + [#40](https://github.com/asiazhang/cognicode/issues/40) 类型清单 + [debt-types.md](../../docs/research/debt-types.md)
> 本文件是 B 族分族子代理的完整作业指令。跨族共享约定（证据包 16K 预算、回传 JSON schema、严重度带定档流程）见 [SKILL.md](../SKILL.md)，此处不重复。

## 0. 族概览

| slug | 名称 | 判断方向 | 证据等级 | 检测档 | rubric 主轴 | 预排 |
|---|---|---|---|---|---|---|
| `test-gap` | 测试缺口 | 源→测试 | 确证（保护不存在） | 确定性 | 裸露度 | 高 |
| `test-rot` | 测试腐烂 | 测试→源 | 确证 + 风险混合 | 混合 | 假保护率 | 高 |
| `flaky-test` | 脆弱测试 | 测试→源 | 全类型风险信号 | 确定性 | 反模式类别数 | 中 |
| `test-shape` | 测试形状债 | 测试→源 | 确证候选 + LLM 评估 | 确定性 + LLM | private-touch 深度 × mock 内部计数 | 中 |

**四类型分野（方向轴）**：gap 无信号、rot 假信号、flaky 噪音信号、shape 真信号但焊死错误对象。修复动作也不同：gap/rot/flaky 补修测试，shape 须把测试迁移到接口上（是重构）。

**证据等级语言（全 B 族统一）**：**确证信号**（实锤证据：保护不存在，如 skip 堆叠、无断言）vs **风险信号**（脆性候选：静态反模式命中，未动态验证）——A 族 exact/near 二分的 B 族镜像。flaky 全类型为风险信号档，报告行标注「脆性候选，未动态验证」。

**B 族与 E 族 fidelity-debt 的分野**：gap 无保护 / rot 假保护（断言烂）/ shape 真信号焊错对象——而 fidelity 是「信号真、环境假」（测试全绿但保的是替身不是本体），归 E 族，见 [E-process.md](E-process.md)。同模块多 slug 可并挂。

## 1. test-gap

### 判据

源→测试方向：改了没保护的区域，agent 无法自证没炸别处（变更安全性）。

### 检测（确定性档，新写提取器）

两层漏斗：

1. **文件级漏斗**：筛出无测试触达的文件。
2. **符号级精判**：对有触达文件做符号级判定（复用 symbols.py 既有资产）。

「测试触达」口径 = **符号触达**：被测符号名在测试文件文本中出现即可，不验证调用图（保守口径，确定可提取）。coverage 等动态覆盖数据 MVP 不含，选型留雾区。

### 实例粒度

每未触达符号一个实例；DEBT.md 报告**上卷到模块级一行**（gap 符号数 / 总符号数）。

### rubric

主轴 = **裸露度**（模块内 gap 符号比例）。

## 2. test-rot

### 判据

测试→源方向：假保护——测试在但不测东西，agent 以为安全其实没有（变更安全性 + 可诊断性）。

### 三层信号

1. **确定性层·skip 集中度**：模块内 skip 占测试函数比例超阈值（约 10%）。**用比例不用绝对数**——绝对数受模块规模效应影响，那是 monolith-file 的债不是 rot 的。
2. **确定性层·快照债堆叠**：快照文件计数 + 体量增长，纯文件系统计数。
3. **LLM 推断层·断言质量**：判「被测行为出错时测试会变红吗」——无断言、`assert result` 真值检查、catch-and-pass 均为候选，标置信度。

留雾区（MVP 不做）：快照-实现变更耦合、共编历史、断言 vs 实现过时对比（均需 git 历史或实现对照，成本高）。

**断言质量层的理论基准 = 变异性测试**：MVP 用 LLM 静态推断近似，报告必须标置信度，不得伪装实锤；二期变异性测试做确证 oracle + 校准数据。

**快照债边界**：rot 的快照信号是**时序信号**（堆叠增长），duplicate-code 的重复是**结构信号**——同一快照文件可同时挂两 slug。

### rubric

主轴 = **假保护率**（rot 信号数 / 测试函数总数）。

## 3. flaky-test

### 判据

测试→源方向：随机红绿，agent 误判自己改坏，污染失败归因（可诊断性）。

### 检测（确定性档：静态反模式清单，7 项有界枚举）

1. `sleep()` 蒙眼等待（等时间而非等条件）
2. 随机数无 seed
3. 时间依赖无注入（`now()` / `new Date()` 直接调用）
4. 时区/本地化依赖
5. 测试间共享可变全局状态
6. `os.environ` / cwd 修改不恢复
7. 无 mock 的外部网络调用

清单**有界枚举**，每语种一套框架级 token 表（Pytest/Jest/Mocha…）；新增语种 = 新增 token 表，是工程边界不是判据。动态重跑检测留二期。

### 证据等级

全类型**风险信号档**（脆性候选，未动态验证），报告行必须标注。

### rubric

主轴 = **反模式类别数**（非计数——计数受模块规模效应影响）。

## 4. test-shape

### 判据

测试→源方向：真保护焊死错误对象——测试绕过接口直戳内部，agent 的深度化重构被惩罚（红绿信号撒谎），长期学会不重构（变更安全性）。

### 私有符号定义

**公开面声明优先**（`__all__` / index.ts 导出表），语言机制兜底（`_` 前缀 / `#` 字段 / Go 大小写 / Java package-private）。

### mock 边界判定

- mock **公开边界依赖**（网络/DB 接口）= 正常测试实践，**不判债**。
- mock **内部协作对象** = 形状债信号。

### 两档分工

- **确定性档**：import 私有符号清单 + mock 目标清单（test-scan 中间产物）。
- **LLM 档 = 候选评估器**：不做 shape 独立发现，只对确定性候选判「是否真的焊死结构」，标置信度。

行为学习污染层留二期动态验证。MVP 检测面为形状代理。

### 与 E 族 implicit-contract 边界

shape 判**测试侧**焊死错误对象，implicit-contract 判**被测接口侧**未声明真实使用条件——同实例可多 slug 并挂。

### rubric

主轴 = **private-touch 深度 × mock 内部依赖计数**（组合）。

## 5. 留册汇总

B 族无留册类型（四类型 MVP 全覆盖）。

## 6. 子代理执行协议

- **候选来源**：确定性档 = gap 符号触达提取（文件级漏斗）、rot 的 skip 集中度 + 快照堆叠、flaky 反模式清单、shape 的 import 私有 + mock 内部目标提取；LLM 档 = rot 断言质量（能变红吗，标置信度）+ shape 候选评估器。
- **共享中间产物口径（test-scan）**：一趟「测试→源」扫描产 per-test-file 结构化记录——测试函数计数、skip 标记、断言形态统计、import 私有符号清单、mock 目标清单——作为 rot/flaky/shape 的共享中间层。**E 族 implicit-contract 的测试 setup 链锚点消费同一工件**（见 E-process.md），本族子代理负责其产出完整、字段不缺。工件落 `.cognicode/debt-scan/`，由 SKILL.md 管线编排；本族消费时不重复扫描。
- **证据包组装**：gap 上卷前的符号级明细、rot/flaky/shape 命中测试文件的相关行采样，总量 16K 预算内，超预算降采样并在 rationale 声明。
- **输出 schema**：`{slug, location, confidence, rationale, fix_suggestion}` + 提议严重度带（沿各类型主轴方向提议，不终裁）。
- **语种扩展**：新语种 = 新增一套语言适配（test-scan）+ 一套框架 token 表（flaky），均为工程边界不是判据。
