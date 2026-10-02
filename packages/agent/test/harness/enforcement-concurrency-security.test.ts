import { describe, expect, it } from "vitest";
import { BACKGROUND_CONTEXT, withAbortSignal } from "../../src/harness/context.ts";
import {
	type AuditEvent,
	type AuditReceipt,
	type AuditSink,
	computePolicyDigest,
	createEnforcementKernel,
	type EnforcementLimits,
	type EnforcementPolicySource,
	type SecurityHost,
	type ToolEffectDescriptor,
} from "../../src/harness/enforcement.ts";

class Audit implements AuditSink {
	readonly events: AuditEvent[] = [];

	async append(event: AuditEvent): Promise<AuditReceipt> {
		this.events.push(event);
		return {
			sequence: this.events.length,
			recordDigest: `record-${this.events.length}`,
			mac: `mac-${this.events.length}`,
		};
	}
}

class Host implements SecurityHost {
	async execute<TResult>(): Promise<TResult> {
		throw new Error("unexpected broker execution");
	}
}

function deferred(): {
	readonly promise: Promise<void>;
	readonly resolve: () => void;
} {
	let resolvePromise: (() => void) | undefined;
	const promise = new Promise<void>((resolve) => {
		resolvePromise = resolve;
	});
	return {
		promise,
		resolve: () => resolvePromise?.(),
	};
}

function limits(overrides: Partial<EnforcementLimits> = {}): EnforcementLimits {
	return {
		maxConcurrent: 1,
		maxQueued: 2,
		maxCallsPerMinute: 20,
		maxRequestBytes: 4_096,
		maxResultBytes: 4_096,
		...overrides,
	};
}

function policy(
	limitOverrides: Partial<EnforcementLimits> = {},
	expiresAt = "2099-01-01T00:00:00.000Z",
): EnforcementPolicySource {
	return {
		schemaVersion: 1,
		revision: "reviewed-policy-1",
		expiresAt,
		limits: limits(limitOverrides),
		tools: {
			pure: { effects: ["pure"], methods: ["calculate"] },
		},
	};
}

function effect(): ToolEffectDescriptor {
	return { kind: "pure", method: "calculate", sensitive: false };
}

function request(operationId: string, callId: string) {
	return {
		operationId,
		callId,
		toolName: "pure",
		args: {},
		effect: effect(),
	};
}

function kernel(limitOverrides: Partial<EnforcementLimits> = {}, now: () => number = Date.now, expiresAt?: string) {
	const source = policy(limitOverrides, expiresAt);
	return createEnforcementKernel({
		policy: { ...source, digest: computePolicyDigest(source) },
		audit: new Audit(),
		host: new Host(),
		now,
	});
}

describe("enforcement concurrency security", () => {
	it("preserves the first owner across matching denied calls", async () => {
		const active = deferred();
		const enforcement = kernel();
		const first = enforcement.run(
			request("operation", "call"),
			async () => {
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);

		await expect(
			enforcement.run(request("operation", "call"), async () => "second", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "duplicate_call" });
		await expect(
			enforcement.run(request("operation", "call"), async () => "third", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "duplicate_call" });

		active.resolve();
		await expect(first).resolves.toBe("first");
		await expect(
			enforcement.run(request("operation", "call"), async () => "later", BACKGROUND_CONTEXT),
		).resolves.toBe("later");
	});

	it("does not release another call after a denied request", async () => {
		const active = deferred();
		const started = deferred();
		const enforcement = kernel({ maxQueued: 1 });
		const first = enforcement.run(
			request("operation-1", "call-1"),
			async () => {
				started.resolve();
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);
		await started.promise;
		const queued = enforcement.run(request("operation-2", "call-2"), async () => "queued", BACKGROUND_CONTEXT);

		await expect(
			enforcement.run(request("operation-3", "call-3"), async () => "denied", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "queue_full" });
		let queueCompleted = false;
		void queued.then(() => {
			queueCompleted = true;
		});
		await Promise.resolve();
		expect(queueCompleted).toBe(false);

		active.resolve();
		await expect(first).resolves.toBe("first");
		await expect(queued).resolves.toBe("queued");
	});

	it("does not release another call after a rate-limited request", async () => {
		const active = deferred();
		const started = deferred();
		const queuedStarted = deferred();
		const enforcement = kernel({ maxCallsPerMinute: 2 });
		const first = enforcement.run(
			request("operation-1", "call-1"),
			async () => {
				started.resolve();
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);
		await started.promise;
		const queued = enforcement.run(
			request("operation-2", "call-2"),
			async () => {
				queuedStarted.resolve();
				return "queued";
			},
			BACKGROUND_CONTEXT,
		);

		await expect(
			enforcement.run(request("operation-3", "call-3"), async () => "limited", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "rate_limited" });
		let admitted = false;
		void queuedStarted.promise.then(() => {
			admitted = true;
		});
		await Promise.resolve();
		expect(admitted).toBe(false);

		active.resolve();
		await expect(first).resolves.toBe("first");
		await expect(queued).resolves.toBe("queued");
	});

	it("removes an aborted queued call", async () => {
		const active = deferred();
		const enforcement = kernel();
		const first = enforcement.run(
			request("operation-1", "call-1"),
			async () => {
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);
		const controller = new AbortController();
		const queued = enforcement.run(
			request("operation-2", "call-2"),
			async () => "queued",
			withAbortSignal(controller.signal, BACKGROUND_CONTEXT),
		);

		controller.abort(new Error("caller stopped"));
		await expect(queued).rejects.toThrow("caller stopped");
		active.resolve();
		await expect(first).resolves.toBe("first");
		await expect(
			enforcement.run(request("operation-3", "call-3"), async () => "next", BACKGROUND_CONTEXT),
		).resolves.toBe("next");
	});

	it("rejects a queued call after its wait bound", async () => {
		const active = deferred();
		const enforcement = kernel({ maxQueueWaitMs: 10 });
		const first = enforcement.run(
			request("operation-1", "call-1"),
			async () => {
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);

		await expect(
			enforcement.run(request("operation-2", "call-2"), async () => "queued", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "queue_timeout" });
		active.resolve();
		await expect(first).resolves.toBe("first");
	});

	it("rechecks policy freshness after queue admission", async () => {
		let now = Date.parse("2026-01-01T00:00:00.000Z");
		const expiry = "2026-01-01T00:00:01.000Z";
		const active = deferred();
		const started = deferred();
		const enforcement = kernel({}, () => now, expiry);
		const first = enforcement.run(
			request("operation-1", "call-1"),
			async () => {
				started.resolve();
				await active.promise;
				return "first";
			},
			BACKGROUND_CONTEXT,
		);
		await started.promise;
		const queued = enforcement.run(request("operation-2", "call-2"), async () => "queued", BACKGROUND_CONTEXT);

		now += 2_000;
		active.resolve();
		await expect(first).resolves.toBe("first");
		await expect(queued).rejects.toMatchObject({ code: "policy_expired" });
	});
});
