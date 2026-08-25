# 合成任务生成管线（#20）

> 票：[实现合成基准任务生成管线](https://github.com/asiazhang/cognicode/issues/20)
> 前置：harness 执行层（#19）、静态信号提取（#18）、tree-sitter 底座（#18 comment_density）
> 分支：`prototype/pi-schema`

## 职责

三段式生成管线（#5 锁定）：**tree-sitter 解析 → LLM 模板合成 →
执行式验证过滤**，产出三类有效合成任务（检索/定位/修改）。

本层**只生成与过滤**，不执行任务、不判卷。判卷（F2P/P2P、位置匹配、
退出码五类 outcome）归 #21（verdict 层 + harness）。

## 模块

| 模块 | 职责 |
|---|---|
| `symbols.py` | **第一段**：tree-sitter 提取命名符号（函数/方法/类），语言无关、确定性 |
| `generation.py` | **第二段**：符号 → 三类任务（检索不带名 / 定位给症状 / 修改给描述），LLM 或确定性模板；生成配置独立固定（任务量/k 按 #6） |
| `verify.py` | **第三段**：执行式验证过滤——注入补丁可应用性（dry-run）+ 验收测试可注入性；砍掉无效实例 |
| `pipeline.py` | 三段式整合：符号 → 合成 → 过滤，修改类注入验收测试文件 |
| `llm.py` | `llm` 接口（生成配置独立固定）；offline / 失败走确定性模板 |

## 三段式

### 1. 符号提取（symbols.py）

- 解析范围：语言无关（Python/JS/TS/PHP/Go/Rust/Java/C/C++/C#/Ruby/Lua/
  Elixir/Kotlin/Swift/Bash 等，`tree-sitter-language-pack`）。
- 排除：测试文件（`tests/test/spec/__tests__`）、依赖与文档目录
  （`vendor/node_modules/docs/dist/build` 等）、隐藏路径——这些不是「被测代码」。
- 语法错误文件跳过（与 #18 comment_density 同策略）。
- 输出 `Symbol{kind: function|method|class, name, file, line}`；
  ground truth = `file::name`（符号级匹配，非行号，#5 锁定）。

### 2. 模板合成（generation.py）

三类任务（CONTEXT.md「合成任务」）：

| 类型 | 输入 | 验收 |
|---|---|---|
| 检索 | 符号描述（LLM 生成，**不带名**，语义→位置） | 符号级匹配 ground truth |
| 定位 | 失败症状（注入 bug 后，**不给答案**，症状→根因） | 对照注入点 |
| 修改 | 任务描述（描述→改动） | F2P/P2P 双闸 |

- **LLM 合成**：走 `llm` 接口（配置独立固定，`GenerationLLMConfig`）；
  LLM 失败（超时/拒答）→ 确定性模板兜底，不炸管线。
- **offline（Q17 降级）**：`llm=None` → 全部走确定性模板（不发请求）。
- **注入补丁**（bug 注入，SWE-smith 式）：在符号体内找第一个
  `return <表达式>` 行，替换为常量（按语言），生成 `-old/+new` diff 风格补丁。
  找不到可突变行 → 跳过该符号（不硬凑）。
- **任务量/k**（#6 锁定，`DEFAULT_COUNTS`/`GenerationConfig`）：
  检索 8 / 定位 8 / 修改 12；修改 k=5 / 检索定位 k=3。

### 3. 执行式验证过滤（verify.py）

- 检索：ground truth 存在即有效（题面不带名已由第二段保证）。
- 定位/修改：注入补丁在源码上**可应用**（`apply_injection` dry-run，
  不落盘）——过不了当场砍掉（SWE-bench 式「生成即验证」）。
- 修改：仓库有**既有测试目录**（`tests/test/spec/phpunit`）才能注入验收
  测试，否则不可判 F2P → 砍掉。
- **验收测试注入**（地图 Notes 锁定）：`cognicode_` 前缀 + 放既有测试
  目录，判 F2P（`cognicode_f2p_<符号>.py`）+ P2P 守护测试
  （`cognicode_guard_<符号>.py`，保证「改动前已绿」基线）。
- 过滤结果：`(kept, dropped)`，dropped 记录 `(task_id, 原因)` 进报告。

## CLI 接入

`cognicode scan <repo>`：
- 探测成功 → 生成任务（offline 走确定性模板），落盘
  `.cognicode/<run-id>/tasks.json`（counts + tasks + dropped）；
- 探测失败 → **任务生成降级跳过**（Q17：探测全灭 = 环境可用性低分信号，
  非评估失败），只出静态分；
- 首个生成任务作为演示任务执行（#19 链路验证）。

## 已知边界 / 真仓实测

- **tree-sitter-language-pack 0.26 的 `Node.start_point` 在特定 PHP 节点
  上访问会段错误**（本机实测 nbnbk 复现）：改用 `start_byte` + 源码计数
  行号（`src[:offset].count(b'\n') + 1`），确定性且稳定。
- nbnbk（pin 532bfdc）真仓冒烟：提取 10982 个符号（3 次一致）；
  生成 检索 8 + 定位 8 + 修改 12（#6 任务量）、0 砍；验收测试按约定
  注入 `tests/cognicode_*.py`。
- 修改类注入对象目前是「函数/方法体的第一个 return 行」；无 return 的
  符号（如只含副作用）跳过。注入形态扩展（表达式替换、逻辑反转）留
  #20 后续或新票。
- 判卷（F2P/P2P 真正跑测试、位置匹配判定）归 #21；本层只保证
  「生成出的实例可执行」。
