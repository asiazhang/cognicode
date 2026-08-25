"""任务生成管线（#20 三段式整合）。

tree-sitter 解析（symbols）→ LLM 模板合成（generation）→
执行式验证过滤（verify），产出三类有效任务（检索/定位/修改）。

修改类任务在验证通过后**注入验收测试文件**（`cognicode_` 前缀 + P2P
守护测试，放既有测试目录，地图 Notes 锁定）——这是 F2P/P2P 判卷的
物理载体（判卷逻辑归 #21）。

offline（llm=None）走确定性模板（Q17 降级）；LLM 失败同样兜底。
探测成功才调本管线（探测全灭 → 整体降级，只出静态分，见 Q17）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cognicode.generation import (
    DEFAULT_COUNTS,
    GenerationConfig,
    ModifyTask,
    generate_tasks,
)
from cognicode.symbols import extract_symbols
from cognicode.verify import (
    RealVerifier,
    VerificationConfig,
    verify_tasks,
    prepare_acceptance_files,
)


@dataclass(frozen=True)
class PipelineConfig:
    """管线配置（默认值按 #5/#6 锁定）。"""

    generation: GenerationConfig = GenerationConfig()
    verification: VerificationConfig = VerificationConfig()


def _apply_counts_and_ks(counts: dict | None, ks: dict | None) -> GenerationConfig:
    """把调用方给的 counts/ks 覆盖到默认配置（测试/调参入口）。"""
    c = GenerationConfig()
    return GenerationConfig(
        search_count=(counts or {}).get("search", c.search_count),
        locate_count=(counts or {}).get("locate", c.locate_count),
        modify_count=(counts or {}).get("modify", c.modify_count),
        k_search=(ks or {}).get("search", c.k_search),
        k_locate=(ks or {}).get("locate", c.k_locate),
        k_modify=(ks or {}).get("modify", c.k_modify),
        llm_model=c.llm_model,
    )


def generate_task_suite(
    repo: str | Path,
    *,
    llm=None,
    counts: dict[str, int] | None = None,
    ks: dict[str, int] | None = None,
    config: PipelineConfig | None = None,
) -> dict:
    """三段式生成任务套件（探测成功后才调用）。

    Args:
        repo: 仓库根目录。
        llm: 可选 LLM 客户端（LLMClient 协议）；None（offline）→ 确定性模板。
        counts: 任务量覆盖（默认 #6：search 8 / locate 8 / modify 12）。
        ks: 采样 k 覆盖（默认 #6：search 3 / locate 3 / modify 5）。
        config: 管线配置（默认 #5/#6 锁定）。

    Returns:
        {
          "search": [SearchTask...],
          "locate": [LocateTask...],
          "modify": [ModifyTask...],
          "dropped": [(task_id, reason)...],
        }
    """
    cfg = config or PipelineConfig()
    gen_cfg = _apply_counts_and_ks(counts, ks)

    root = Path(repo)
    symbols = extract_symbols(root)
    # 给符号补 root（注入补丁/验证需要读源码）
    from cognicode.symbols import Symbol

    symbols = [
        Symbol(kind=s.kind, name=s.name, file=s.file, line=s.line, root=str(root))
        for s in symbols
    ]

    tasks = generate_tasks(symbols, llm=llm, config=gen_cfg)
    verifier = RealVerifier(config=cfg.verification, root=root)
    kept, dropped = verify_tasks(tasks, verifier=verifier, root=root)

    # 修改类：验证通过后注入验收测试文件（F2P + P2P 守护）
    test_dir = _first_test_dir(root, cfg.verification)
    for t in kept:
        if isinstance(t, ModifyTask):
            if test_dir is None:
                # 无测试目录的修改类任务无法判 F2P → 砍掉（记录）
                dropped.append((t.id, "仓库无既有测试目录，修改类任务不可判卷"))
                continue
            files = prepare_acceptance_files(root, t, test_dir.name, cfg.verification)
            if files is None:
                dropped.append((t.id, "验收测试注入失败"))
                continue
            # 记录注入的文件（判卷消费）
            object.__setattr__(
                t,
                "acceptance_files",
                [str(f.relative_to(root)) for f in files],
            )
            object.__setattr__(
                t,
                "guard_files",
                [str(f.relative_to(root)) for f in files if "guard" in f.name],
            )

    # 按类别分组（保持顺序）
    suite = {"search": [], "locate": [], "modify": []}
    for t in kept:
        if t.kind in suite:
            suite[t.kind].append(t)
    suite["dropped"] = dropped
    return suite


def _first_test_dir(root: Path, cfg: VerificationConfig) -> Path | None:
    """定位既有测试目录（地图 Notes：验收测试放既有测试目录）。"""
    for name in cfg.test_dirs:
        d = root / name
        if d.is_dir():
            return d
    return None
