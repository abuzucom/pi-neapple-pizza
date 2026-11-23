/**
 * Route pi tool calls through the policy broker.
 *
 * The adopted policy registers gates for Claude, Codex, Gemini, and
 * Antigravity. pi runs in this repository as an agent client, and no
 * registration covers it. This extension closes that gap by asking the
 * broker in `broker/pi_broker.py` for a decision before every pi tool call
 * runs.
 *
 * The broker runs the unchanged canonical gates outside the repository. It
 * pins the digest of every gate in the decision path, records every decision
 * in an append-only log, and consumes one approval per act that a human
 * accepted.
 *
 * The extension holds no policy of its own. It forwards the call, reads the
 * decision, and blocks the call when the decision denies it. A decision that
 * needs an answer from a human reaches the operator through the client, and
 * the broker consumes the approval that follows.
 *
 * Load the extension without a project resource directory:
 *
 *     pi -e integrations/pi/agents-gate.ts
 *
 * The repository does not adopt a `.pi` directory, so the extension ships in
 * the repository tree and the operator names it on the command line.
 */
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const BROKER_SCRIPT = join(ROOT, "broker", "pi_broker.py");
const BROKER_TIMEOUT_MS = 120000;
const MAX_OUTPUT_CHARACTERS = 1048576;
const MAX_DIAGNOSTIC_CHARACTERS = 4096;
const DEFAULT_PYTHON = "python";
const MAX_DISPLAY_CHARACTERS = 2000;

export interface BrokerDecision {
	decision: "allow" | "deny" | "ask";
	reason?: string;
	context?: string;
	warning?: string;
	approval?: string;
	record?: string;
}

function pythonExecutable(): string {
	return process.env.PI_POLICY_PYTHON || DEFAULT_PYTHON;
}

/**
 * Ask the broker for one decision or one approval.
 *
 * The broker runs the canonical gates and records the outcome. Every
 * failure path denies, because a call the policy cannot clear must not reach
 * the operating system.
 */
export function runBroker(command: "decide" | "approve", request: Record<string, unknown>): Promise<BrokerDecision> {
	return new Promise<BrokerDecision>((resolve) => {
		const child = spawn(pythonExecutable(), ["-E", "-s", BROKER_SCRIPT, command], {
			cwd: ROOT,
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let diagnostics = "";
		let settled = false;
		const finish = (decision: BrokerDecision): void => {
			if (settled) {
				return;
			}
			settled = true;
			clearTimeout(timer);
			resolve(decision);
		};
		const timer = setTimeout(() => {
			child.kill();
			finish({ decision: "deny", reason: "the policy broker did not answer within the time bound" });
		}, BROKER_TIMEOUT_MS);
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk: string) => {
			stdout += chunk;
			if (stdout.length > MAX_OUTPUT_CHARACTERS) {
				child.kill();
				finish({ decision: "deny", reason: "the policy broker response exceeded the inspection bound" });
			}
		});
		child.stderr.setEncoding("utf8");
		child.stderr.on("data", (chunk: string) => {
			diagnostics = (diagnostics + chunk).slice(0, MAX_DIAGNOSTIC_CHARACTERS);
		});
		child.on("error", (error: Error) => {
			finish({ decision: "deny", reason: `the policy broker could not run: ${error.message}` });
		});
		child.on("close", (code: number | null) => {
			if (settled) {
				return;
			}
			const parsed = parseDecision(stdout);
			if (!parsed) {
				const detail = diagnostics.trim();
				finish({
					decision: "deny",
					reason: detail || `the policy broker returned no readable decision (exit ${code})`,
				});
				return;
			}
			finish(parsed);
		});
		child.stdin.on("error", () => {
			// The broker can exit before reading the request.
		});
		child.stdin.end(JSON.stringify(request));
	});
}

function parseDecision(stdout: string): BrokerDecision | undefined {
	const text = stdout.trim();
	if (!text) {
		return undefined;
	}
	let parsed: unknown;
	try {
		parsed = JSON.parse(text);
	} catch {
		return undefined;
	}
	if (!parsed || typeof parsed !== "object") {
		return undefined;
	}
	const candidate = parsed as BrokerDecision;
	if (candidate.decision !== "allow" && candidate.decision !== "deny" && candidate.decision !== "ask") {
		return undefined;
	}
	return candidate;
}

function denialText(decision: BrokerDecision): string {
	return [decision.reason, decision.context].filter((part) => Boolean(part)).join("\n\n");
}

/**
 * Reduce broker output to plain text before it reaches the interface.
 *
 * The broker echoes text that came from the tool arguments, so the
 * confirmation prompt must carry no control characters and no markup.
 */
function displayText(text: string): string {
	const bounded = text.slice(0, MAX_DISPLAY_CHARACTERS);
	return bounded.replace(/[\u0000-\u001f\u007f]/g, " ");
}

/**
 * Register the pi policy broker client.
 *
 * The session start reports the branch preflight and the identity advisory.
 * Every tool call asks the broker for a decision, and a denial blocks the
 * call before it reaches the operating system. A decision that needs an
 * answer from a human reaches the operator through the client, and the
 * broker consumes the approval that follows.
 */
export default function agentsGate(pi: ExtensionAPI): void {
	pi.on("session_start", async (_event, ctx) => {
		const decision = await runBroker("decide", { cwd: ctx.cwd });
		if (decision.decision === "deny") {
			if (ctx.hasUI) {
				ctx.ui.notify(`pi policy gate blocked this session.\n${denialText(decision)}`, "warning");
			}
			return;
		}
		if (decision.warning && ctx.hasUI) {
			ctx.ui.notify(decision.warning, "warning");
		}
	});

	pi.on("tool_call", async (event, ctx) => {
		const request = {
			tool: event.toolName,
			arguments: event.input as Record<string, unknown>,
			cwd: ctx.cwd,
		};
		const decision = await runBroker("decide", request);
		if (decision.decision === "allow") {
			return undefined;
		}
		if (decision.decision === "ask") {
			if (!ctx.hasUI) {
				return {
					block: true,
					reason: denialText(decision) || "the act needs an answer from the active human",
				};
			}
			const accepted = await ctx.ui.confirm(
				"The policy broker needs an answer from you",
				`Allow this act?\n\n${displayText(denialText(decision))}`,
			);
			if (!accepted) {
				return {
					block: true,
					reason: denialText(decision) || "the active human declined the act",
				};
			}
			const approval = await runBroker("approve", request);
			if (!approval.approval) {
				return {
					block: true,
					reason: "the policy broker recorded no approval for the act",
				};
			}
			const confirmed = await runBroker("decide", { ...request, approval: approval.approval });
			if (confirmed.decision === "allow") {
				return undefined;
			}
			return {
				block: true,
				reason: denialText(confirmed) || "the policy broker denied the approved act",
			};
		}
		return { block: true, reason: denialText(decision) || "the policy broker denied this call" };
	});
}
