/**
 * CogniCode 测量隔离扩展（#19 实现，随 cognicode 包发布）。
 *
 * 一次 `-e` 加载承担三件事（与 pi-schema.md §6 / ADR-0003 对齐）：
 *
 * 1. **max-turns 早停**（#6 锁定 50 轮）：turn_start 计数；达上限后
 *    下一个 tool_call 返回 {block, reason, terminate: true} 早停整批
 *    （FINDINGS.md 2c 实测机制）；纯文本回复兜底用 sendMessage 提示停止。
 * 2. **只读工具门**（测量纯净性二次保险）：--harness-read-only 开启时
 *    禁 write/edit/patch + bash 写命令（检索/定位类任务用）；
 *    修改/修复类任务不开（agent 必须能写，判卷靠 diff）。
 * 3. **submit_result 工具**（ADR-0002 约定交卷格式，不进判卷）：
 *    结构化收尾（terminate: true），供检索/定位类任务自报告。
 *
 * 配置经环境变量传入（PiExecutor 子进程 env 注入）：
 *   HARNESS_MAX_TURNS=<n>   轮次上限（默认 50）
 *   HARNESS_READ_ONLY=1     只读门开
 *   HARNESS_NO_SUBMIT=1     不注册 submit_result
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
	// 配置经环境变量传入（PiExecutor 子进程 env 注入）。
	// 不用 registerFlag/getFlag：RPC 长驻模式下 getFlag 读不到 CLI flag
	// （实测 pi 0.84.3，flag 解析仅对 -p 单发/CLI 形态生效）。
	const maxTurns = Number(process.env.HARNESS_MAX_TURNS) || 50;
	const readOnly = process.env.HARNESS_READ_ONLY === "1";
	const registerSubmit = process.env.HARNESS_NO_SUBMIT !== "1";

	let turnCount = 0;

	// ---------- max-turns 早停 ----------
	// 语义：轮次 = LLM 调用轮（turn_start 计数，含工具轮与总结轮，
	// 对齐 #6 num_turns 口径）。达上限后：
	//   - 若模型继续调工具 → tool_call 里 block+terminate 早停
	//   - 若模型纯文本总结收尾 → 已是最后动作，正常结束（不拦）
	pi.on("turn_start", () => {
		turnCount += 1;
	});

	pi.on("tool_call", (_event, ctx) => {
		// 1) max-turns：已超限 → 拦下一切工具调用并早停
		if (turnCount > maxTurns) {
			return {
				block: true,
				reason: `harness: max-turns(${maxTurns}) 已超限`,
				terminate: true,
			};
		}

		// 2) 只读门（readOnly=true）：禁写工具
		if (readOnly) {
			const WRITE_TOOLS = new Set(["write", "edit", "patch", "notebook_edit"]);
			if (WRITE_TOOLS.has(_event.toolName)) {
				return {
					block: true,
					reason: `harness: 只读模式禁止 ${_event.toolName}`,
				};
			}
			if (_event.toolName === "bash") {
				const cmd = (_event.input as { command?: string }).command ?? "";
				if (!isReadOnlyBash(cmd)) {
					return {
						block: true,
						reason: `harness: 只读模式禁止写命令: ${cmd.slice(0, 80)}`,
					};
				}
			}
		}

		return undefined;
	});

	// ---------- submit_result（可选，结构化交卷） ----------
	if (registerSubmit) {
		pi.registerTool({
			name: "submit_result",
			label: "Submit Result",
			description:
				"提交最终结构化结果。检索/定位类任务用它交卷（verdict + evidence）；" +
				"这是约定的交卷格式，对错判定由评测方客观判定，本工具仅记录你的结论。",
			parameters: Type.Object({
				verdict: Type.String({ description: "你的结论（如定位到的文件路径）" }),
				evidence: Type.Array(Type.String(), { description: "证据行（文件:行号 或 关键片段）" }),
			}),
			async execute(_toolCallId, params) {
				return {
					content: [{ type: "text", text: `submitted: ${params.verdict}` }],
					details: { verdict: params.verdict, evidence: params.evidence },
					terminate: true,
				};
			},
		});
	}
}

/** 判断 bash 命令是否只读（非破坏性）。 */
function isReadOnlyBash(cmd: string): boolean {
	const trimmed = cmd.trim();
	if (!trimmed) return true;
	// 管道/重定向组合：保守拦（检索/定位不需要）
	if (/>|>>|\|/.test(trimmed)) {
		return false;
	}
	const first = trimmed.split(/\s+/)[0] ?? "";
	const READONLY = new Set([
		"ls", "cat", "head", "tail", "grep", "rg", "find", "pwd", "echo",
		"git", "php", "python", "node", "npm", "composer", "make",
		"wc", "sort", "uniq", "cut", "sed", "awk", "diff",
	]);
	if (!READONLY.has(first)) return false;
	// git 子命令白名单（只读）
	if (first === "git") {
		const sub = trimmed.split(/\s+/)[1] ?? "";
		const GIT_READONLY = new Set([
			"status", "diff", "log", "show", "grep", "ls-files", "ls-tree",
			"rev-parse", "branch", "tag", "blame", "stash", "remote",
		]);
		return GIT_READONLY.has(sub);
	}
	return true;
}
