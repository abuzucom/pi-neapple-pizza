import { mkdirSync, mkdtempSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BACKGROUND_CONTEXT } from "../../src/harness/context.ts";
import {
	type AuditEvent,
	type AuditReceipt,
	type AuditSink,
	type BrokerRequest,
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
	request: BrokerRequest | undefined;

	async execute<TResult>(request: BrokerRequest): Promise<TResult> {
		this.request = request;
		return "ok" as TResult;
	}
}

function createFilesystemKernel(workingDirectory: string, root: string, host = new Host()) {
	const source: EnforcementPolicySource = {
		schemaVersion: 1,
		revision: "path-policy",
		expiresAt: "2099-01-01T00:00:00.000Z",
		limits: {
			maxConcurrent: 1,
			maxQueued: 1,
			maxCallsPerMinute: 10,
			maxRequestBytes: 4_096,
			maxResultBytes: 4_096,
		},
		tools: {
			write: { effects: ["filesystem"], methods: ["write"], pathRoots: [root] },
		},
	};
	return {
		host,
		kernel: createEnforcementKernel({
			policy: { ...source, digest: computePolicyDigest(source) },
			audit: new Audit(),
			host,
			workingDirectory,
		}),
	};
}

function request(destination: string) {
	return {
		operationId: "operation",
		callId: "call",
		toolName: "write",
		args: { path: destination },
		effect: {
			kind: "filesystem" as const,
			method: "write",
			sensitive: true,
			destinationArgument: "path",
			destinationType: "path" as const,
		},
	};
}

describe("enforcement path security", () => {
	it("rejects approved roots that do not exist", () => {
		const workspace = mkdtempSync(join(tmpdir(), "pi-enforcement-"));
		const missingRoot = join(workspace, "missing");

		expect(() => createFilesystemKernel(workspace, missingRoot)).toThrow();
	});

	it("resolves relative destinations from the configured working directory", async () => {
		const workspace = mkdtempSync(join(tmpdir(), "pi-enforcement-"));
		const approved = join(workspace, "approved");
		mkdirSync(approved);
		const { host, kernel } = createFilesystemKernel(workspace, approved);

		await expect(kernel.run(request("approved/output.txt"), async () => "local", BACKGROUND_CONTEXT)).resolves.toBe(
			"ok",
		);
		expect(host.request?.validatedDestination).toBe(join(approved, "output.txt"));
		expect(host.request?.args.path).toBe(join(approved, "output.txt"));
	});

	it("rejects a link escape through the deepest existing parent", async () => {
		const workspace = mkdtempSync(join(tmpdir(), "pi-enforcement-"));
		const approved = join(workspace, "approved");
		const outside = join(workspace, "outside");
		mkdirSync(approved);
		mkdirSync(outside);
		const link = join(approved, "escape");
		symlinkSync(outside, link, process.platform === "win32" ? "junction" : "dir");
		const { kernel } = createFilesystemKernel(workspace, approved);

		await expect(
			kernel.run(request("approved/escape/output.txt"), async () => "local", BACKGROUND_CONTEXT),
		).rejects.toMatchObject({ code: "destination_denied" });
	});

	it("uses UTF-16 code-unit ordering for canonical policy digests", () => {
		const original = String.prototype.localeCompare;
		String.prototype.localeCompare = () => {
			throw new Error("locale comparison used");
		};
		try {
			const first = computePolicyDigest({
				schemaVersion: 1,
				revision: "digest",
				expiresAt: "2099-01-01T00:00:00.000Z",
				limits: {
					maxConcurrent: 1,
					maxQueued: 1,
					maxCallsPerMinute: 1,
					maxRequestBytes: 1,
					maxResultBytes: 1,
				},
				tools: { "\uffff": { effects: ["pure"], methods: ["z"] }, a: { effects: ["pure"], methods: ["a"] } },
			});
			expect(first).toMatch(/^[0-9a-f]{64}$/);
		} finally {
			String.prototype.localeCompare = original;
		}
	});
});
