/**
 * Exercise the pi extension against the policy broker.
 *
 * The test drives the extension the way pi does. It supplies a tool call and
 * a session directory, and it reads the block decision the extension returns.
 * The broker and the canonical gates run for real.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import agentsGate from "./agents-gate.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const BROKER = join(ROOT, "broker", "pi_broker.py");
const PYTHON = process.env.PI_POLICY_PYTHON || "python";

type ToolCallHandler = (event: unknown, ctx: unknown) => Promise<unknown>;

const state = mkdtempSync(join(tmpdir(), "pi-broker-test-"));
process.env.PI_BROKER_STATE = state;

test.after(() => {
	rmSync(state, { recursive: true, force: true });
});

function runGit(repository: string, ...arguments_: string[]): void {
	execFileSync("git", arguments_, { cwd: repository, stdio: "pipe" });
}

function createRepository(): string {
	const repository = mkdtempSync(join(tmpdir(), "pi-gate-"));
	runGit(repository, "init", "-q", "-b", "main");
	runGit(repository, "config", "user.name", "Test User");
	runGit(repository, "config", "user.email", "test@example.com");
	writeFileSync(join(repository, "README.md"), "# Fixture\n");
	runGit(repository, "add", "README.md");
	runGit(repository, "commit", "-q", "-m", "feat: add fixture");
	runGit(repository, "checkout", "-q", "-b", "feat/pi-adapter-test");
	return repository;
}

function pinBroker(): void {
	execFileSync(PYTHON, [BROKER, "pin"], { cwd: ROOT, stdio: "pipe" });
}

interface FakePi {
	on(name: string, handler: ToolCallHandler): void;
}

function registerExtension(): { handlers: Map<string, ToolCallHandler>; notifications: string[] } {
	const handlers = new Map<string, ToolCallHandler>();
	const notifications: string[] = [];
	const pi: FakePi = {
		on(name: string, handler: ToolCallHandler): void {
			handlers.set(name, handler);
		},
	};
	agentsGate(pi as unknown as ExtensionAPI);
	return { handlers, notifications };
}

function context(cwd: string, notifications: string[]): unknown {
	return {
		cwd,
		hasUI: true,
		ui: {
			notify: (message: string): void => {
				notifications.push(message);
			},
			confirm: async (): Promise<boolean> => true,
		},
	};
}

test("the extension blocks a destructive shell command", async () => {
	const repository = createRepository();
	pinBroker();
	const { handlers } = registerExtension();
	const handler = handlers.get("tool_call");
	assert.ok(handler);
	const result = await handler({ toolName: "bash", input: { command: "rm -rf /" } }, context(repository, []));
	assert.equal((result as { block?: boolean }).block, true);
});

test("the extension allows an ordinary shell command", async () => {
	const repository = createRepository();
	pinBroker();
	const { handlers } = registerExtension();
	const handler = handlers.get("tool_call");
	assert.ok(handler);
	const result = await handler({ toolName: "bash", input: { command: "echo hello" } }, context(repository, []));
	assert.equal(result, undefined);
});

test("the extension blocks a tool with no canonical inspection path", async () => {
	const repository = createRepository();
	pinBroker();
	const { handlers } = registerExtension();
	const handler = handlers.get("tool_call");
	assert.ok(handler);
	const result = await handler({ toolName: "web_search", input: { query: "anything" } }, context(repository, []));
	assert.equal((result as { block?: boolean }).block, true);
});

test("the session start reports a compliant branch", async () => {
	const repository = createRepository();
	pinBroker();
	const { handlers, notifications } = registerExtension();
	const handler = handlers.get("session_start");
	assert.ok(handler);
	await handler({ reason: "startup" }, context(repository, notifications));
	assert.deepEqual(notifications, []);
});
