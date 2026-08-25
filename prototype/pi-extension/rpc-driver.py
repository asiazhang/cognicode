#!/usr/bin/env python3
"""
pi RPC 原型驱动（wayfinder #29）

保持 stdin 打开（#28 踩坑：一次性关闭 stdin 会致 prompt 挂起），
发送 RPC 命令、轮询 stdout 事件、等 agent_settled 再拉统计。
按场景驱动，结果打 JSONL 到 /tmp/pi-proto-run.jsonl 与 stdout。
"""

import json
import subprocess
import sys
import time

OUT = "/tmp/pi-proto-run.jsonl"
LOG = []  # 场景内全部事件，供判定


def run_scenario(name, commands, pi_args, timeout=180):
    """pi_args: list 追加到 pi 命令后；commands: [(delay_s, json_dict), ...]"""
    print(f"\n=== SCENARIO: {name} ===", flush=True)
    cmd = ["pi", "--mode", "rpc"] + pi_args
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    events = []
    responses = []
    has_prompt = any(c[1].get("type") == "prompt" for c in commands)
    for delay, payload in commands:
        time.sleep(delay)
        if proc.poll() is not None:
            break
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
    # 轮询 stdout（保持 stdin 打开）。终局判定：
    #   含 prompt 的场景 → 等 agent_settled；纯命令场景 → 等该命令 response。
    deadline = time.time() + timeout
    done = False
    seen_settled = False
    while time.time() < deadline and not done:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        events.append(ev)
        if ev.get("type") == "response":
            responses.append(ev)
            if not has_prompt:
                done = True
        if ev.get("type") == "agent_settled":
            seen_settled = True
        if has_prompt and seen_settled:
            time.sleep(1.0)  # 收尾事件（turn_end/agent_end 已先于 settled 到达）
            done = True
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    stderr = proc.stderr.read()
    record = {
        "scenario": name,
        "rc": proc.returncode,
        "n_events": len(events),
        "stderr": stderr[-2000:] if stderr else "",
        "events": events,
        "responses": responses,
    }
    with open(OUT, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def summarize(rec):
    types = {}
    for ev in rec["events"]:
        t = ev.get("type")
        types[t] = types.get(t, 0) + 1
    print(f"  rc={rec['rc']} events={rec['n_events']} by_type={types}")
    for r in rec["responses"]:
        print(f"  RESP {r.get('command')}: success={r.get('success')} "
              f"err={r.get('error') or ''} data_keys={list((r.get('data') or {}).keys())}")


if __name__ == "__main__":
    open(OUT, "w").close()
    scenario = sys.argv[1] if len(sys.argv) > 1 else "all"
    kit = "/root/.pi/agent/git/github.com/asiazhang/pi-codebuddy-kit"
    ext = "/data/home/user/cognicode/prototype/pi-extension/probe-ext.ts"
    base = ["--no-session", "--no-approve", "-nc",
            "--no-skills", "--no-prompt-templates", "--no-themes"]
    # 不显式 --provider（#28 §9 踩坑），靠 kit 扩展注册 + 默认模型

    if scenario in ("all", "tool"):
        # 验证点 1+2：自定义工具 + tool_call 拦截。模型被要求用 submit_result 收尾。
        rec = run_scenario(
            "registerTool + tool_call",
            [
                (0.5, {"type": "prompt", "message": (
                    "Submit a result with verdict OK and evidence [line1]. "
                    "Call submit_result as your final action.")}),
            ],
            base + ["-e", kit, "-e", ext],
        )
        summarize(rec)
        # 提炼关键事件
        for ev in rec["events"]:
            t = ev.get("type")
            if t in ("tool_execution_start", "tool_execution_end", "tool_call_probe"):
                print("   ", json.dumps(ev, ensure_ascii=False)[:300])

    if scenario in ("all", "block"):
        # 验证点 2a：block git push --force
        rec = run_scenario(
            "tool_call block (git push --force)",
            [
                (0.5, {"type": "prompt", "message": (
                    "Run the command: git push --force origin main (do it for real), "
                    "then submit_result verdict BLOCKED.")}),
            ],
            base + ["-e", kit, "-e", ext],
        )
        summarize(rec)

    if scenario in ("all", "mutate"):
        # 验证点 2b：改参数（sample.txt → /tmp/pi-proto-dir/sample.txt）
        rec = run_scenario(
            "tool_call mutate (read sample.txt)",
            [
                (0.5, {"type": "prompt", "message": (
                    "Read the file sample.txt and tell me its first line, then submit_result.")}),
            ],
            base + ["-e", kit, "-e", ext],
        )
        summarize(rec)

    if scenario in ("all", "cmd"):
        # 验证点 3：扩展命令
        rec = run_scenario(
            "registerCommand (/probe-cmd)",
            [
                (0.5, {"type": "prompt", "message": "/probe-cmd hello world"}),
            ],
            base + ["-e", kit, "-e", ext],
        )
        summarize(rec)

    if scenario in ("all", "isol"):
        # 验证点 4：--no-extensions 禁发现 + 显式 -e 加载
        rec = run_scenario(
            "isolation: --no-extensions + explicit -e",
            [
                (0.5, {"type": "prompt", "message": (
                    "Use the count tool on sample.txt and report if it is available, "
                    "then submit_result.")}),
            ],
            base + ["--no-extensions", "-e", kit, "-e", ext],
        )
        summarize(rec)

    print("\nDONE")
