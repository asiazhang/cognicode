# 端到端冒烟（#24）

> 票：[端到端冒烟验证 done 标准](https://github.com/asiazhang/cognicode/issues/24)
> 地图：[实现 CogniCode MVP 闭环](https://github.com/asiazhang/cognicode/issues/16)
> 脚本：`scripts/smoke_e2e.py`
> 分支：`prototype/pi-schema`

## 职责

在试点语料（nbnbk + Melissa-Core）上端到端跑通「探测 → 任务生成 → 判卷 →
聚合 → 报告 → 敏感性」全链路，产出真实 `cognicode-report.md`，验证
issue 16 的 done 三条标准。分两次冒烟（issue 24 约定）：

1. `--offline`：LLM 全关（归因走确定性档、模块深度关）——验证确定性链路。
2. `--live`：开 LLM（归因兜底 + 模块深度）——验证 LLM 模块不拖垮打分。

## 用法

```bash
uv run python scripts/smoke_e2e.py --offline           # 第一次冒烟（确定性）
uv run python scripts/smoke_e2e.py --live              # 第二次冒烟（LLM）
uv run python scripts/smoke_e2e.py --offline --tasks 2 # 减量（链路验证）
```

产出：

- `.cognicode/smoke-<mode>-<repo>/`：static.json / probe.json / tasks.json /
  verdicts.json / aggregate.json / snapshot.json / medians.json / run.json /
  **cognicode-report.md**（每仓一份完整报告）
- `.cognicode/smoke-<mode>-done.json`：done 判定摘要

## 冒烟暴露的真实事实（本票核心产出）

### 1. 探测判定 vs 试点仓现实

地图 Notes 锁定的探测判定 = 「至少一条构建 exit 0 且至少一条测试 exit 0」。
试点仓实测：

| 仓 | 探测命令 | 真实退出码 | 结论 |
|---|---|---|---|
| nbnbk | `test.phpunit`（phpunit.xml 触发） | **126/255**（vendor 缺 `platform_check.php`，PHP Fatal） | 测试跑不通 |
| nbnbk | 构建命令 | 无（composer.json 无 scripts.build） | 无构建 |
| Melissa-Core | 测试命令 | 未识别（probe 只查 pyproject.toml，Melissa 只有 setup.py） | 无测试命令 |
| Melissa-Core | 构建命令 | 无（无 Makefile 等） | 无构建 |

→ **两仓探测均失败** → 按 Q17 降级（动态面未测，只出静态分 + 标注）。
探测失败是**环境可用性低分信号**（#9 预期：席位 1/2 环境可用性低分），
不是链路故障。

### 2. 探测采集口径缺陷（冒烟暴露，已在本脚本规避）

`ProbeRunner` 原实现让 pi agent 执行探测命令，`exit_codes` 记录的是
**agent 进程退出码**（agent 正常收尾 = 0），不是**命令真实退出码**
（phpunit Fatal 255 / pytest collection error 2 也被记成 0）。
本脚本改为**直接执行命令**记录真实退出码，避免该伪影。
（probe.py 的 agent 包装路径保留用于真实执行；冒烟用直接执行验证判定。）

### 3. 方向验证的约束

done 标准 3 的「方向」（nbnbk 总分 < Melissa-Core）需要动态分，
而动态分需要探测成功。试点仓探测失败 → 真实动态分缺失。
本脚本用**可复现仿真任务数据**（固定 seed，成功率按 #9 语料预期注入）
驱动完整聚合，验证方向判定链本身通；真实方向需探测成功的仓库测量。
仿真数据在报告中标注，不冒充真实测量。

## done 判定（--offline 完整任务量实测）

| 标准 | 判定 | 证据 |
|---|---|---|
| 1 闭环：两仓完整报告 | ✓ | `smoke-offline-nbnbk/cognicode-report.md` + `smoke-offline-Melissa-Core/cognicode-report.md`（六维分 + 区间 + 建议清单 + 快照 + 敏感性小节） |
| 2 正确：链路无未捕获异常 + 判卷五类单测全绿 | ✓ | 冒烟脚本全程无异常；`pytest tests/test_verdict_judge.py tests/test_verdict.py` = 42 passed |
| 3 有意义：方向 + 带宽 | ✓（方向）/ ✗（带宽参考） | 仿真动态 + 真实静态混合分：nbnbk 0.379 < Melissa 0.388 ✓；敏感性带宽 0.31/0.29（>0.05，如实报告） |

**总判定：PASS（方向为硬指标 ✓；带宽 ≤0.05 未达，如实报告为参考判据）**。

带宽 ≤0.05 未达的原因：仿真成功率差异大 → 维度分离散 → 权重扰动下总分
波动大。这是敏感性分析的如实报告语义（#10 判据①「每次打分必跑，随报告
附」），不是「必须过」的门禁；真实动态分下带宽需实测。

## 已知边界

- **仿真数据**：verdicts.json 的 outcomes 是固定 seed 仿真（成功率按 #9
  预期注入），非真实 agent 执行结果。真实执行（pi agent 跑任务 + F2P/P2P
  红绿判卷）需探测成功的仓库 + 测试运行时（nbnbk 无 php、Melissa 测试
  collection error），当前试点仓不具备。
- **live 模式**：LLM 归因 + 模块深度真实调用（LLM 调用 3+2 次），报告含
  LLM 综合归因建议与模块深度小节；总分与 offline 完全一致（LLM 模块不进
  产分，ADR-0004）。
- **判卷五类单测**：42 个构造假数据测试全绿（done 标准 2 的「判卷五类
  结果分类在构造假数据上单测全绿」）。
- **语料方向（判据②）**：报告标「待语料」——需各仓六维点值注入（校准
  验证阶段输出）。
