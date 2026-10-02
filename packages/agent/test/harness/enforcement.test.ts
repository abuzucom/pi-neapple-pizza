import { describe, expect, it } from "vitest";
import { BACKGROUND_CONTEXT } from "../../src/harness/context.ts";
import {
	type AuditEvent,
	type AuditReceipt,
	type AuditSink,
	computePolicyDigest,
	createEnforcementKernel,
	type EnforcementPolicySource,
	type SecurityHost,
	type ToolEffectDescriptor,
} from "../../src/harness/enforcement.ts";

const context = BACKGROUND_CONTEXT;

class RecordingAuditSink implements AuditSink {
	readonly events: AuditEvent[] = [];
	fail = false;

	async append(event: AuditEvent): Promise<AuditReceipt> {
		if (this.fail) throw new Error("audit unavailable");
		this.events.push(event);
		return {
			sequence: this.events.length,
			recordDigest: `record-${this.events.length}`,
			mac: `mac-${this.events.length}`,
		};
	}
}

class RecordingSecurityHost implements SecurityHost {
	readonly requests: string[] = [];
	result: unknown = { content: [{ type: "text", text: "brokered" }] };

	async execute<TResult>(request: { toolName: string }): Promise<TResult> {
		this.requests.push(request.toolName);
		return this.result as TResult;
	}
}

function buildPolicy(): EnforcementPolicySource {
	return {
		schemaVersion: 1,
		revision: "reviewed-policy-1",
		expiresAt: "2099-01-01T00:00:00.000Z",
		limits: {
			maxConcurrent: 2,
			maxQueued: 2,
			maxCallsPerMinute: 10,
			maxRequestBytes: 4_096,
			maxResultBytes: 4_096,
		},
		tools: {
			read: { effects: ["filesystem"], methods: ["read"], pathRoots: [process.cwd()] },
			process: { effects: ["process"], methods: ["run"], executables: ["git"] },
			pure: { effects: ["pure"], methods: ["calculate"] },
		},
	};
}

function effect(overrides: Partial<ToolEffectDescriptor> = {}): ToolEffectDescriptor {
	return { kind: "pure", method: "calculate", sensitive: false, ...overrides };
}

function createKernel(audit = new RecordingAuditSink(), host = new RecordingSecurityHost()) {
	const source = buildPolicy();
	return {
		audit,
		host,
		kernel: createEnforcementKernel({
			policy: { ...source, digest: computePolicyDigest(source) },
			audit,
			host,
		}),
	};
}

describe("strict harness enforcement", () => {
	it("denies an unclassified tool before local execution", async () => {
		const { audit, kernel } = createKernel();
		let executed = false;

		await expect(
			kernel.run(
				{
					operationId: "operation-1",
					callId: "call-1",
					toolName: "pure",
					args: {},
				},
				async () => {
					executed = true;
					return "local";
				},
				context,
			),
		).rejects.toThrow("tool lacks a strict effect declaration");
		expect(executed).toBe(false);
		expect(audit.events.at(-1)?.decision).toBe("deny");
	});

	it("denies shell command strings before broker execution", async () => {
		const { host, kernel } = createKernel();

		await expect(
			kernel.run(
				{
					operationId: "operation-2",
					callId: "call-2",
					toolName: "process",
					args: { command: "git status" },
					effect: effect({ kind: "process", method: "run", commandShape: "shell" }),
				},
				async () => "local",
				context,
			),
		).rejects.toThrow("shell command strings are unavailable in strict mode");
		expect(host.requests).toEqual([]);
	});

	it("routes external effects through the broker without local execution", async () => {
		const { audit, host, kernel } = createKernel();
		let executed = false;

		const result = await kernel.run(
			{
				operationId: "operation-3",
				callId: "call-3",
				toolName: "read",
				args: { path: "README.md" },
				effect: effect({
					kind: "filesystem",
					method: "read",
					destinationArgument: "path",
					destinationType: "path",
				}),
			},
			async () => {
				executed = true;
				return "local";
			},
			context,
		);

		expect(result).toEqual(host.result);
		expect(executed).toBe(false);
		expect(host.requests).toEqual(["read"]);
		expect(audit.events.map((event) => event.phase)).toEqual(["intent", "completion"]);
	});

	it("stops before every effect when the audit sink fails", async () => {
		const audit = new RecordingAuditSink();
		audit.fail = true;
		const { host, kernel } = createKernel(audit);
		let executed = false;

		await expect(
			kernel.run(
				{
					operationId: "operation-4",
					callId: "call-4",
					toolName: "pure",
					args: {},
					effect: effect(),
				},
				async () => {
					executed = true;
					return "local";
				},
				context,
			),
		).rejects.toThrow("audit persistence failed before execution");
		expect(executed).toBe(false);
		expect(host.requests).toEqual([]);
	});
});
