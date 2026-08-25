/**
 * pi 扩展层可定制性原型（wayfinder #29，prototype/pi-schema 分支）
 *
 * 目的：把 pi-customization.md §2.1 的「CLI/RPC 形态即可编程定制」从文档升级为实测。
 * 四个验证点：
 *   1. registerTool()：submit_result 工具（TypeBox schema + terminate 早停），
 *      RPC prompt 直接调用触发 → 结构化 JSON 结果。
 *   2. tool_call 事件拦截：block / 改参数 / terminate 三种行为，CLI 非交互形态可用。
 *   3. registerCommand()：/probe-cmd 扩展命令，经 RPC prompt "/probe-cmd" 触发。
 *   4. count 工具：验证 --no-extensions 禁发现但显式 -e 仍加载（隔离与定制不冲突）。
 *
 * THROWAWAY：仅供 #29 原型验证，不是产品代码。
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { appendFileSync } from "node:fs";

/** 原型事件日志：把每个被触发的 hook 记下来，供 RPC 采集端事后读取。 */
const LOG = "/tmp/pi-prototype-29.jsonl";
function log(entry: unknown) {
	try {
		appendFileSync(LOG, `${JSON.stringify(entry)}\n`);
	} catch {
		/* ignore */
	}
}

export default function (pi: ExtensionAPI) {
	// ---------- 验证点 2：tool_call 事件拦截（block / 改参数 / terminate） ----------
	pi.on("tool_call", (event, ctx) => {
		log({
			hook: "tool_call",
			toolName: event.toolName,
			toolCallId: event.toolCallId,
			input: event.input,
			mode: ctx.mode,
		});

		// 2a. block：拦截 bash 里的危险命令（模型安全层常先自拒 rm -rf /，
		//     用 git push --force 这类"合规但策略禁止"的命令测真实拦截）
		if (event.toolName === "bash") {
			const input = event.input as { command?: string };
			if (input.command?.includes("git push --force")) {
				return { block: true, reason: "prototype: blocked git push --force" };
			}
		}

		// 2b. 改参数：给 read 的 path 加前缀（原地改 event.input，生效于实际执行）
		if (event.toolName === "read") {
			const input = event.input as { path?: string };
			if (input.path === "sample.txt") {
				input.path = "/tmp/pi-proto-dir/sample.txt";
			}
		}

		// 2c. terminate：拦截 write 到 FORBIDDEN.md，terminate 早停整批
		if (event.toolName === "write") {
			const input = event.input as { path?: string };
			if (input.path?.endsWith("FORBIDDEN.md")) {
				return { block: true, reason: "prototype: terminated by policy", terminate: true };
			}
		}
	});

	// 额外：tool_result 钩子（验证「可改结果」面，轻量记录）
	pi.on("tool_result", (event, ctx) => {
		log({
			hook: "tool_result",
			toolName: event.toolName,
			toolCallId: event.toolCallId,
			isError: event.isError,
			mode: ctx.mode,
		});
	});

	// 记录 mode 语义：扩展在 CLI/RPC 形态下确实被加载并执行
	pi.on("session_start", (_event, ctx) => {
		log({ hook: "session_start", mode: ctx.mode, hasUI: ctx.hasUI });
	});

	// ---------- 验证点 3：registerCommand() ----------
	pi.registerCommand("probe-cmd", {
		description: "probe extension command for wayfinder #29",
		handler: async (args, ctx) => {
			const reply = `probe-cmd executed: args=${JSON.stringify(args ?? null)} mode=${ctx.mode}`;
			log({ hook: "command", name: "probe-cmd", args, mode: ctx.mode });
			// RPC 下 notify 是 fire-and-forget；handler 返回值经 RPC prompt 响应可见
			if (ctx.mode !== "rpc") ctx.ui.notify(reply, "info");
			return reply;
		},
	});

	// ---------- 验证点 1：registerTool()（terminate 早停 + 结构化输出） ----------
	pi.registerTool({
		name: "submit_result",
		label: "Submit Result",
		description:
			"Return a final structured verification result. Use this as your last action when asked to submit a result.",
		parameters: Type.Object({
			verdict: Type.String({ description: "verification verdict" }),
			evidence: Type.Array(Type.String(), { description: "evidence lines" }),
		}),
		async execute(_toolCallId, params) {
			return {
				content: [{ type: "text", text: `submitted: ${params.verdict}` }],
				details: { verdict: params.verdict, evidence: params.evidence },
				terminate: true,
			};
		},
	});

	// ---------- 验证点 4：count 工具（--no-extensions 下显式 -e 仍加载的探针） ----------
	pi.registerTool({
		name: "count",
		label: "Count",
		description: "Count the number of lines in the given file.",
		parameters: Type.Object({
			path: Type.String({ description: "file path" }),
		}),
		async execute(_toolCallId, params) {
			return { content: [{ type: "text", text: "count tool available" }] };
		},
	});
}
