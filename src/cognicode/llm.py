"""llm 接口（#20：LLM 合成走独立固定的 llm 接口）。

地图 Notes 锁定：LLM = tencent-copilot 网关（deepseek-v4-flash-ioa /
glm-5.3-ioa），抽 `llm` 接口；生成 / 判深度 / 归因三处各自 pin 模型、
配置独立固定（版本进可复现性元数据）。本模块实现生成用 LLM 客户端：

- `LLMClient` 协议：`complete(prompt, *, model) -> str | None`；
- `TemplateLLM`：确定性兜底实现（offline 用，不发网络请求）；
- `PiLlmClient`：真 LLM（经 pi RPC 网关，配置独立固定）；
- offline（llm=None）或 LLM 失败时，生成管线走确定性模板（Q17 降级）。

判深度（#23 归因）与归因（#15）各有自己的 llm 配置实例，不在本票。
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    """LLM 合成客户端协议：给定 prompt 返回文本；失败返回 None。"""

    def complete(self, prompt: str, *, model: str | None = None) -> str | None: ...


@dataclass(frozen=True)
class GenerationLLMConfig:
    """生成用 LLM 配置（独立固定，#5；改动需回 #5）。"""

    # 模型 pin（地图 Notes：生成 / 判深度 / 归因各自 pin）
    model: str = "tencent-copilot/deepseek-v4-flash-ioa"
    # 超时（生成单次调用）
    timeout_s: int = 60
    # 扩展与 provider 扩展路径（复用 pi-executor 的测量隔离扩展形态）
    ext_dir: str | Path | None = None


class TemplateLLM:
    """确定性兜底 LLM：不发请求，直接返回输入（供 offline / 测试）。

    实际上生成管线在 llm=None 时连 TemplateLLM 都不建（直接走确定性模板）；
    本类用于测试替身或「明确要一个无害 llm 对象」的场景。
    """

    def complete(self, prompt: str, *, model: str | None = None) -> str | None:
        return prompt


class PiLlmClient:
    """真 LLM 客户端：经 pi 网关调用（生成配置独立固定）。

    复用 pi executor 的测量隔离形态（--mode rpc + -e provider 扩展），
    但这是**生成侧**的独立配置：模型、超时与执行侧（#19 PiExecutor）
    各自 pin，互不影响（地图 Notes：配置独立固定）。
    """

    def __init__(
        self,
        config: GenerationLLMConfig | None = None,
        *,
        pi_cmd: list[str] | None = None,
    ) -> None:
        self.config = config or GenerationLLMConfig()
        self.pi_cmd = pi_cmd if pi_cmd is not None else ["pi"]

    def complete(self, prompt: str, *, model: str | None = None) -> str | None:
        """单次生成调用：返回模型文本；任何失败返回 None（调用方兜底）。"""
        model = model or self.config.model
        try:
            proc = subprocess.run(
                self.pi_cmd + [
                    "--mode", "rpc",
                    "--model", model,
                    "--no-session", "--no-approve", "-nc",
                    "--no-skills", "--no-prompt-templates", "--no-themes",
                ],
                input=json.dumps({"type": "prompt", "message": prompt}) + "\n",
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
            )
        except Exception:
            return None
        # 取最后一条 assistant 文本（简单解析：agent_settled 前的 message）
        return _extract_last_text(proc.stdout)


def _extract_last_text(stdout: str) -> str | None:
    """从 pi RPC stdout（JSONL）提取最后一条 assistant 文本；失败返回 None。"""
    last = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "message_start":
            msg = ev.get("message") or {}
            if msg.get("role") == "assistant":
                for block in msg.get("content") or []:
                    if block.get("type") == "text" and block.get("text"):
                        last = block["text"]
    return last
