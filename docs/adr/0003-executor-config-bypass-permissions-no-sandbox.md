# 测量用执行者配置：bypassPermissions 全自动 + 无 OS 级沙箱

CogniCode 动态测量让真实编程 agent（无头 CLI）在被测仓库上执行合成基准任务。无头模式下不存在人类审批，若采用 `acceptEdits` 等受限权限模式，被拒的命令调用会产生大量假阴性——「权限被拒」是 harness 的伪影，不是仓库的属性；同理，OS 级沙箱（bubblewrap/Seatbelt）的网络隔离会令依赖安装、包管理器下载失败，直接污染环境可用性维度的测量（网络可达性属于被测物）。故票 #6 钉死执行者配置为：`bypassPermissions`/`-y` 全自动 + 不开 OS 沙箱，爆炸半径由 fresh git worktree（每次运行新建、harness 侧 `git diff` 收产物）隔离；配合模型版本精确钉死、`--max-turns 50`、配置来源收窄到空/仅内置、`--no-session-persistence`，共同满足分数稳定硬需求。安全代价由场景吸收：本地 CLI、个人开发者、被测对象是自己的仓库。

## Considered Options

- **受限权限模式（acceptEdits）**：更安全，但无头模式下命令被拒即任务失败，测到的是 harness 配置而非仓库 AI 原生程度。被否。
- **OS 级沙箱**：防越界写入与网络滥用，但网络隔离破坏冷启动构建的真实性，环境可用性测量失真。被否（风险改由 fresh worktree + 本地场景承担）。
