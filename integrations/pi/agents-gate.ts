/**
 * Route pi tool calls through the canonical policy gates.
 *
 * The adopted policy registers gates for Claude, Codex, Gemini, and
 * Antigravity. pi runs in this repository as an agent client, and no
 * registration covers it. This extension closes that gap by asking the
 * Python adapter in `hooks/pi_client_gate.py` for a decision before every
 * pi tool call runs.
 *
 * The extension holds no policy of its own. It forwards the call, reads the
 * canonical decision, and blocks the call when the gate denies it. A gate
 * that cannot run, or a decision that cannot be read, denies the call.
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
const GATE_SCRIPT = join(ROOT, "hooks", "pi_client_gate.py");
const GATE_TIMEOUT_MS = 120000;
const MAX_OUTPUT_CHARACTERS = 1048576;
const MAX_DIAGNOSTIC_CHARACTERS = 4096;
const DEFAULT_PYTHON = "python";

export interface GateDecision {
	decision: "allow" | "deny";
	reason?: string;
	context?: string;
	warning?: string;
}

function pythonExecutable(): string {
	return process.env.PI_POLICY_PYTHON || DEFAULT_PYTHON;
}

/**
 * Ask the canonical adapter for one decision.
 *
 * The adapter runs the unchanged canonical gates and reports their verdict.
 * Every failure path denies, because a call the policy cannot clear must
 * not reach the operating system.
 */
export function runPolicyGate(event: "tool" | "session", request: Record<string, unknown>): Promise<GateDecision> {
	return new Promise<GateDecision>((resolve) => {
		const child = spawn(pythonExecutable(), ["-E", "-s", GATE_SCRIPT, "--event", event], {
			cwd: ROOT,
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let diagnostics = "";
		let settled = false;
		const finish = (decision: GateDecision): void => {
			if (settled) {
				return;
			}
			settled = true;
			clearTimeout(timer);
			resolve(decision);
		};
		const timer = setTimeout(() => {
			child.kill();
			finish({ decision: "deny", reason: "the policy gate did not answer within the time bound" });
		}, GATE_TIMEOUT_MS);
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk: string) => {
			stdout += chunk;
			if (stdout.length > MAX_OUTPUT_CHARACTERS) {
				child.kill();
				finish({ decision: "deny", reason: "the policy gate response exceeded the inspection bound" });
			}
		});
		child.stderr.setEncoding("utf8");
		child.stderr.on("data", (chunk: string) => {
			diagnostics = (diagnostics + chunk).slice(0, MAX_DIAGNOSTIC_CHARACTERS);
		});
		child.on("error", (error: Error) => {
			finish({ decision: "deny", reason: `the policy gate could not run: ${error.message}` });
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
					reason: detail || `the policy gate returned no readable decision (exit ${code})`,
				});
				return;
			}
			finish(parsed);
		});
		child.stdin.on("error", () => {
			// The gate can exit before reading the request.
		});
		child.stdin.end(JSON.stringify(request));
	});
}

function parseDecision(stdout: string): GateDecision | undefined {
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
	const candidate = parsed as GateDecision;
	if (candidate.decision !== "allow" && candidate.decision !== "deny") {
		return undefined;
	}
	return candidate;
}

function denialText(decision: GateDecision): string {
	return [decision.reason, decision.context].filter((part) => Boolean(part)).join("\n\n");
}

/**
 * Register the pi gate adapter.
 *
 * The session start reports the branch preflight and the identity advisory.
 * Every tool call asks the adapter for a decision, and a denial blocks the
 * call before it reaches the operating system.
 */
export default function agentsGate(pi: ExtensionAPI): void {
	pi.on("session_start", async (_event, ctx) => {
		const decision = await runPolicyGate("session", { cwd: ctx.cwd });
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
		const decision = await runPolicyGate("tool", {
			tool: event.toolName,
			arguments: event.input as Record<string, unknown>,
			cwd: ctx.cwd,
		});
		if (decision.decision === "deny") {
			return { block: true, reason: denialText(decision) || "the policy gate denied this call" };
		}
		return undefined;
	});
}
