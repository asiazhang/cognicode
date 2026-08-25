"""llm 接口单元测试（#20）。

验证：LLMClient 协议、PiLlmClient 从 RPC stdout 提取文本、
失败返回 None（不抛异常，调用方兜底）。期望值来自已知字面。
"""

import json

from cognicode.llm import (
    GenerationLLMConfig,
    PiLlmClient,
    TemplateLLM,
    _extract_last_text,
)


class TestExtractLastText:
    def test_returns_last_assistant_text(self):
        stdout = "\n".join([
            json.dumps({"type": "response", "command": "prompt", "success": True}),
            json.dumps({"type": "agent_start"}),
            json.dumps({"type": "message_start", "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "第一个"}],
            }}),
            json.dumps({"type": "message_start", "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "最终答案"}],
            }}),
            json.dumps({"type": "agent_settled"}),
        ])
        assert _extract_last_text(stdout) == "最终答案"

    def test_no_text_returns_none(self):
        assert _extract_last_text("") is None
        assert _extract_last_text('{"type": "agent_start"}\n') is None

    def test_user_messages_ignored(self):
        stdout = "\n".join([
            json.dumps({"type": "message_start", "message": {
                "role": "user", "content": [{"type": "text", "text": "用户输入"}],
            }}),
        ])
        assert _extract_last_text(stdout) is None


class TestPiLlmClient:
    def test_complete_failure_returns_none(self):
        """pi 调用失败（如命令不存在）→ None，不抛异常。"""
        client = PiLlmClient(pi_cmd=["/nonexistent/pi-xyz"])
        assert client.complete("hi") is None

    def test_config_pins_model(self):
        cfg = GenerationLLMConfig(model="tencent-copilot/glm-5.3-ioa", timeout_s=30)
        assert cfg.model == "tencent-copilot/glm-5.3-ioa"


class TestTemplateLLM:
    def test_returns_input_verbatim(self):
        t = TemplateLLM()
        assert t.complete("你好") == "你好"
