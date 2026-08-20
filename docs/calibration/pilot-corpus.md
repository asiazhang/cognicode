# 试点校准仓库集（pilot corpus）

方法学开发期的固定试验对象，用于维度权重校准、任务难度校准、可复现性验证。所有仓库 **pin 到具体 commit**，校准迭代期间不随上游移动。

选集原则（见 [选定试点校准仓库集](https://github.com/asiazhang/cognicode/issues/9)）：CogniCode 的目标用户是「本地 CLI、个人开发者、普通乃至脏乱的真实仓库」，故校准集**不选精心维护的明星仓库**，全部选取真实写过但未精修的项目，重点覆盖分数分布最需要区分度的中低端区间；语言优先保证 tree-sitter 管线与基建假设的跨栈普适性；环境负担均衡（含 1 个构建链敌对席位检验 fail_env 降级路径）。

| # | 席位 | 仓库 | 语言/栈 | 规模 | Pin |
|---|------|------|---------|------|-----|
| 1 | Python 遗留（温和腐化） | https://github.com/Melissa-AI/Melissa-Core | Python 2/3 混合，2020 归档，★498 | ~175K 行 | `ea08ae5` |
| 2 | JS 前端遗留 | https://github.com/hqwlkj/umi-dva-antd-mobile | JS/TS（umi+dva，2019 生态），2022 归档 | ~33K 行 | `23048a9` |
| 3 | PHP 脏乱典型 | https://github.com/Fanli2012/nbnbk | PHP/ThinkPHP5，2019 停更 | ~18MB PHP | `532bfdc` |
| 4 | 环境敌对对照 | https://github.com/koreader/kindlepdfviewer | Lua + C 子模块，2013 归档 | ~356K 行 Lua | `c5beab2` |
| 5 | 不友好侧对照（自家，非公开） | https://git.woa.com/vstation/vstation | 内部平台仓库，多模块 | 大型 | `752fc11b`（master） |

## Pin 记录

校准期间如需移动 pin，只改本节，并在 issue #9 追加说明。

- **Melissa-Core**: `ea08ae5e3088360d3bddc40db72160697522b8f7`（master, 2026-08 快照核实）
- **umi-dva-antd-mobile**: `23048a94e2eda5e70286baa862a4d733f3efe7a7`（v3 分支 HEAD, 2026-08 快照核实）
- **nbnbk**: `532bfdc816d30f890f5ca3aec0921234b1d8051c`（master, 2026-08 快照核实）
- **kindlepdfviewer**: `c5beab2ded22d6bd480604c2bb87f3479d4b3b85`（master, 2026-08 快照核实）
- **vstation**: `752fc11bb3533037617561c5ce4e5f65d658caae`（master, 2026-08 快照核实）

## 席位说明

1. **Melissa-Core**：真实维护过的语音助手项目，有 tests/、CI 遗迹、文档齐全，但依赖已腐化——「文档好但环境温和跑不起来」的代表，压环境可用性维度中段。
2. **umi-dva-antd-mobile**：2019 年 node 工具链时代的业务脚手架（node-sass 一代），真实业务代码但构建链大概率已断——前端遗留栈代表。
3. **nbnbk**：教科书级真实脏乱：vendor/ 入库、私钥与证书入库、SQL dump 入库、中英混合注释、测试近无——目标用户画像的直接代理，预期综合低分席。
4. **kindlepdfviewer**：冷启动构建需 e-ink 设备交叉工具链——fail_env 降级路径的极限检验席，验证「探测失败是信号不是评估失败」的设计。
5. **vstation**：非公开内部仓库（仅记指针，不记内容摘要）。多模块大型真实平台仓库，做不友好侧对照与规模上限压力测试。

## 使用约定

- 任何校准运行必须记录所用 pin；跨轮比较必须同 pin。
- 席位增删/替换是方法学决策，走 issue；本文件只是清单。
