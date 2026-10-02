import { describe, expect, it } from "vitest";
import { BACKGROUND_CONTEXT } from "../../src/harness/context.ts";
import {
	type ApprovalGrant,
	type AuditEvent,
	type AuditRecordStore,
	type ChainedAuditRecord,
	MacChainedAuditSink,
} from "../../src/harness/enforcement.ts";

const context = BACKGROUND_CONTEXT;

function event(eventId: string): AuditEvent {
	return {
		schemaVersion: 1,
		eventId,
		operationId: "operation",
		callId: "call",
		toolName: "read",
		effect: "filesystem",
		method: "read",
		sensitive: false,
		argumentsDigest: "a".repeat(64),
		policyDigest: "b".repeat(64),
		policyRevision: "revision",
		phase: "intent",
		decision: "allow",
		reasonCode: "admitted",
		occurredAt: "2026-10-01T00:00:00.000Z",
	};
}

describe("MacChainedAuditSink", () => {
	it("serializes records and carries approval consumption into the durable append", async () => {
		const records: ChainedAuditRecord[] = [];
		const approvals: Array<ApprovalGrant | undefined> = [];
		const store: AuditRecordStore = {
			async append(record, approval) {
				records.push(record);
				approvals.push(approval);
			},
		};
		const approval: ApprovalGrant = {
			id: "approval",
			operationId: "operation",
			callId: "call",
			argumentsDigest: "a".repeat(64),
			policyDigest: "b".repeat(64),
			expiresAt: "2026-10-02T00:00:00.000Z",
			nonce: "nonce",
		};
		const sink = new MacChainedAuditSink({ key: new Uint8Array(32).fill(7), store });

		const [first, second] = await Promise.all([
			sink.append(event("first"), approval, context),
			sink.append(event("second"), undefined, context),
		]);

		expect(first.sequence).toBe(1);
		expect(second.sequence).toBe(2);
		expect(second.previousDigest).toBe(first.recordDigest);
		expect(first.mac).toMatch(/^[0-9a-f]{64}$/);
		expect(second.mac).not.toBe(first.mac);
		expect(records).toHaveLength(2);
		expect(approvals).toEqual([approval, undefined]);
	});

	it("rejects short MAC keys before any record can be written", () => {
		const store: AuditRecordStore = { append: async () => undefined };
		expect(() => new MacChainedAuditSink({ key: new Uint8Array(31), store })).toThrow(
			"audit MAC key must contain at least 32 bytes",
		);
	});
});
