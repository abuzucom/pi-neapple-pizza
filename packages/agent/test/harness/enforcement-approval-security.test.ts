import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { BACKGROUND_CONTEXT } from "../../src/harness/context.ts";
import {
	type ApprovalGrant,
	type AuditEvent,
	type AuditReceipt,
	type AuditSink,
	computePolicyDigest,
	createEnforcementKernel,
	type EnforcementPolicySource,
	type SecurityHost,
} from "../../src/harness/enforcement.ts";

class Audit implements AuditSink {
	async append(_event: AuditEvent): Promise<AuditReceipt> {
		return { sequence: 1, recordDigest: "record", mac: "mac" };
	}
}

class Host implements SecurityHost {
	async execute<TResult>(): Promise<TResult> {
		throw new Error("unexpected broker execution");
	}
}

function source(): EnforcementPolicySource {
	return {
		schemaVersion: 1,
		revision: "approval-policy",
		expiresAt: "2099-01-01T00:00:00.000Z",
		limits: {
			maxConcurrent: 1,
			maxQueued: 1,
			maxCallsPerMinute: 10,
			maxRequestBytes: 4_096,
			maxResultBytes: 4_096,
		},
		tools: {
			pure: { effects: ["pure"], methods: ["calculate"], approvalRequired: true },
		},
	};
}

function digestArguments(): string {
	return createHash("sha256").update("{}", "utf8").digest("hex");
}

function grant(policyDigest: string, overrides: Partial<ApprovalGrant> = {}): ApprovalGrant {
	return {
		id: "approval",
		operationId: "operation",
		callId: "call",
		argumentsDigest: digestArguments(),
		policyDigest,
		expiresAt: "2099-01-01T00:00:00.000Z",
		nonce: "nonce",
		...overrides,
	};
}

function request(approval: ApprovalGrant) {
	return {
		operationId: "operation",
		callId: "call",
		toolName: "pure",
		args: {},
		effect: { kind: "pure" as const, method: "calculate", sensitive: true },
		approval,
	};
}

describe("enforcement approval security", () => {
	it("rejects deeply nested and cyclic arguments before execution", async () => {
		const approvalPolicy = source();
		const policy: EnforcementPolicySource = {
			...approvalPolicy,
			tools: { pure: { effects: ["pure"], methods: ["calculate"] } },
		};
		const kernel = createEnforcementKernel({
			policy: { ...policy, digest: computePolicyDigest(policy) },
			audit: new Audit(),
			host: new Host(),
		});
		let nested: Record<string, unknown> = {};
		for (let depth = 0; depth < 65; depth += 1) nested = { nested };
		await expect(
			kernel.run(
				{ ...request(grant("unused")), args: nested as never, approval: undefined },
				async () => "local",
				BACKGROUND_CONTEXT,
			),
		).rejects.toMatchObject({ code: "invalid_arguments" });

		const cyclic: Record<string, unknown> = {};
		cyclic.self = cyclic;
		await expect(
			kernel.run(
				{ ...request(grant("unused")), args: cyclic as never, approval: undefined },
				async () => "local",
				BACKGROUND_CONTEXT,
			),
		).rejects.toMatchObject({ code: "invalid_arguments" });
	});

	it("rejects non-JSON arguments without invoking accessors", async () => {
		const approvalPolicy = source();
		const policy: EnforcementPolicySource = {
			...approvalPolicy,
			tools: { pure: { effects: ["pure"], methods: ["calculate"] } },
		};
		const kernel = createEnforcementKernel({
			policy: { ...policy, digest: computePolicyDigest(policy) },
			audit: new Audit(),
			host: new Host(),
		});
		let accessorCalls = 0;
		const accessorArguments: Record<string, unknown> = {};
		Object.defineProperty(accessorArguments, "value", {
			enumerable: true,
			get: () => {
				accessorCalls += 1;
				return "secret";
			},
		});
		for (const args of [{ value: Number.NaN }, { value: new Date() }, accessorArguments]) {
			await expect(
				kernel.run(
					{ ...request(grant("unused")), args: args as never, approval: undefined },
					async () => "local",
					BACKGROUND_CONTEXT,
				),
			).rejects.toMatchObject({ code: "invalid_arguments" });
		}
		expect(accessorCalls).toBe(0);
	});

	it("rejects approval argument and policy mismatches", async () => {
		const policy = source();
		const policyDigest = computePolicyDigest(policy);
		const kernel = createEnforcementKernel({
			policy: { ...policy, digest: policyDigest },
			audit: new Audit(),
			host: new Host(),
		});

		await expect(
			kernel.run(
				request(grant(policyDigest, { argumentsDigest: "0".repeat(64) })),
				async () => "local",
				BACKGROUND_CONTEXT,
			),
		).rejects.toMatchObject({ code: "approval_invalid" });
		await expect(
			kernel.run(request(grant("0".repeat(64))), async () => "local", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "approval_invalid" });
	});

	it("rejects expired approval grants", async () => {
		const policy = source();
		const policyDigest = computePolicyDigest(policy);
		const kernel = createEnforcementKernel({
			policy: { ...policy, digest: policyDigest },
			audit: new Audit(),
			host: new Host(),
			now: () => Date.parse("2026-01-01T00:00:00.000Z"),
		});
		const approval = grant(policyDigest, { expiresAt: "2025-12-31T23:59:59.000Z" });

		await expect(kernel.run(request(approval), async () => "local", BACKGROUND_CONTEXT)).rejects.toMatchObject({
			code: "approval_invalid",
		});
	});

	it("rejects a policy digest that does not bind canonical content", () => {
		const policy = source();
		expect(() =>
			createEnforcementKernel({
				policy: { ...policy, digest: "0".repeat(64) },
				audit: new Audit(),
				host: new Host(),
			}),
		).toThrow("policy digest does not match canonical content");
	});

	it("rechecks policy freshness after persisting execution intent", async () => {
		let currentTime = Date.parse("2026-01-01T00:00:00.000Z");
		let hostCalls = 0;
		const policy: EnforcementPolicySource = {
			...source(),
			expiresAt: "2026-01-01T00:00:00.010Z",
		};
		const policyDigest = computePolicyDigest(policy);
		const audit: AuditSink = {
			async append(event: AuditEvent): Promise<AuditReceipt> {
				if (event.phase === "intent") currentTime += 20;
				return { sequence: 1, recordDigest: "record", mac: "mac" };
			},
		};
		const host: SecurityHost = {
			async execute<TResult>(): Promise<TResult> {
				hostCalls += 1;
				return "unexpected" as TResult;
			},
		};
		const kernel = createEnforcementKernel({
			policy: { ...policy, digest: policyDigest },
			audit,
			host,
			now: () => currentTime,
		});

		await expect(
			kernel.run(request(grant(policyDigest)), async () => "local", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "policy_expired" });
		expect(hostCalls).toBe(0);
	});
});
