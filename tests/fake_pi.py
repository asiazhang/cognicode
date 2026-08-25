#!/usr/bin/env python3
"""假 pi RPC 服务端（测试用，非产品代码）。

模拟 pi 0.84.3 `--mode rpc` 协议的子集（对齐 pi-schema.md §1.2 真实事件流）：
- stdin 读 JSON 命令（prompt / get_session_stats / get_state）
- stdout 发 JSONL 事件：response(prompt) → agent_start → turn_start/message_*/
  tool_execution_*（3 轮）→ agent_end → agent_settled → response(get_session_stats)
- 保持 stdin 打开（pi-schema.md §8 踩坑：一次性关闭 stdin 会致 prompt 挂起）

额外测试钩子（真实 pi 没有）：
- --sleep-before-response N：prompt 受理后睡 N 秒再发事件（测 timeout）
- --bad-flag：非零退出（测参数错误 exit 1）
- --turn-count N：发 N 轮（默认 3）
"""

import json
import os
import sys
import time

TURN_COUNT = 3


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    args = sys.argv[1:]
    if "--bad-flag" in args:
        sys.stderr.write("Error: Unknown option: --bad-flag\n")
        sys.exit(1)

    sleep_before = 0.0
    for a in args:
        if a == "--sleep-before-response":
            # 下一个参数是秒数
            pass
    if "--sleep-before-response" in args:
        idx = args.index("--sleep-before-response")
        try:
            sleep_before = float(args[idx + 1])
        except (IndexError, ValueError):
            sleep_before = 0.0

    turn_count = TURN_COUNT
    if "--turn-count" in args:
        idx = args.index("--turn-count")
        try:
            turn_count = int(args[idx + 1])
        except (IndexError, ValueError):
            pass

    # 每轮事件间隔（模拟真实流式，毫秒）；0 则立即发完
    inter_turn_ms = 5
    if "--inter-turn-ms" in args:
        idx = args.index("--inter-turn-ms")
        try:
            inter_turn_ms = int(args[idx + 1])
        except (IndexError, ValueError):
            pass
    inter_turn_s = inter_turn_ms / 1000.0

    cwd = os.getcwd()
    started = time.time()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except Exception:
            continue
        ctype = cmd.get("type")

        if ctype == "prompt":
            emit({"type": "response", "command": "prompt", "success": True})
            if sleep_before > 0:
                time.sleep(sleep_before)
                # 睡超后被 kill，不会再发事件
                continue
            # 事件流：对齐 pi-schema.md §1.2
            t0 = time.time()
            emit({"type": "agent_start"})
            for i in range(turn_count):
                time.sleep(inter_turn_s)
                emit({"type": "turn_start", "turnIndex": i, "timestamp": int(t0 * 1000) + i})
                emit({"type": "message_start", "message": {"role": "user", "content": []}})
                emit({"type": "message_end", "message": {"role": "user", "content": []}})
                emit({"type": "message_start", "message": {
                    "role": "assistant", "content": [], "usage": {
                        "input": 9085, "output": 15, "cacheRead": 0,
                        "cacheWrite": 0, "reasoning": 0, "totalTokens": 9100,
                    }, "stopReason": "stop", "timestamp": int(t0 * 1000) + i,
                }})
                emit({"type": "message_end", "message": {
                    "role": "assistant", "content": [{"type": "text", "text": f"turn {i}"}],
                    "usage": {
                        "input": 9085, "output": 15, "cacheRead": 0,
                        "cacheWrite": 0, "reasoning": 0, "totalTokens": 9100,
                    }, "stopReason": "stop", "timestamp": int(t0 * 1000) + i,
                }})
                emit({"type": "turn_end", "turnIndex": i,
                      "message": {"role": "assistant"}, "toolResults": []})
            emit({"type": "agent_end", "messages": [], "willRetry": False})
            emit({"type": "agent_settled", "timestamp": int(time.time() * 1000)})

        elif ctype == "get_session_stats":
            emit({
                "type": "response", "command": "get_session_stats", "success": True,
                "data": {
                    "sessionId": "fake-session",
                    "userMessages": 1, "assistantMessages": TURN_COUNT,
                    "toolCalls": 0, "toolResults": 0, "totalMessages": TURN_COUNT + 1,
                    "tokens": {
                        "input": 9085, "output": 15, "cacheRead": 0,
                        "cacheWrite": 0, "total": 9100,
                    },
                    "cost": 0,
                    "contextUsage": {"tokens": 9100, "contextWindow": 1000000, "percent": 0.91},
                    "cwd": cwd,
                },
            })

        elif ctype == "get_state":
            emit({
                "type": "response", "command": "get_state", "success": True,
                "data": {"cwd": cwd},
            })


if __name__ == "__main__":
    main()
