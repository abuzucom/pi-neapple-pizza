import { createModels, fauxAssistantMessage, fauxProvider, fauxToolCall } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { describe, expect, it } from "vitest";
import { AgentHarness } from "../../src/harness/agent-harness.ts";
import { BACKGROUND_CONTEXT } from "../../src/harness/context.ts";
import {
	type ApprovedEnforcementPolicy,
	type AuditEvent,
	type AuditSink,
	computePolicyDigest,
	createEnforcementKernel,
	type SecurityHost,
} from "../../src/harness/enforcement.ts";
import { Harness as PicoHarness } from "../../src/harness/pico3/harness.ts";
import { MemoryStorage as PicoMemoryStorage } from "../../src/harness/pico3/memory.ts";
import type { ToolDeclaration, ToolResult } from "../../src/harness/pico3/types.ts";
import { MemoryStorage } from "../../src/harness/session/memory.ts";
import { StorageBackedSession } from "../../src/harness/session/session.ts";
import type { AgentHarnessTool } from "../../src/harness/types.ts";
import { fake, model } from "./pico3/helpers.ts";

const schema = Type.Object({ url: Type.String() });

function policy(): ApprovedEnforcementPolicy {
	const source = {
		schemaVersion: 1 as const,
		revision: "integration-v1",
		expiresAt: "2099-01-01T00:00:00.000Z",
		limits: {
			maxConcurrent: 2,
			maxQueued: 2,
			maxCallsPerMinute: 10,
			maxRequestBytes: 4096,
			maxResultBytes: 4096,
		},
		tools: {
			fetch: {
				effects: ["network" as const],
				methods: ["GET"],
				endpointOrigins: ["https://allowed.example"],
			},
		},
	};
	return { ...source, digest: computePolicyDigest(source) };
}

class RecordingAudit implements AuditSink {
	readonly events: AuditEvent[] = [];

	async append(event: AuditEvent) {
		this.events.push(event);
		return { sequence: this.events.length, recordDigest: "a".repeat(64), mac: "b".repeat(64) };
	}
}

class ResultHost implements SecurityHost {
	readonly calls: string[] = [];
	readonly result: unknown;

	constructor(result: unknown) {
		this.result = result;
	}

	async execute<TResult>(request: { toolName: string }): Promise<TResult> {
		this.calls.push(request.toolName);
		return this.result as TResult;
	}
}

describe("harness enforcement integration", () => {
	it("routes a legacy harness external effect through the broker", async () => {
		const session = new StorageBackedSession(
			{ id: "strict-legacy", createdAt: 1, storageVersion: 1 },
			new MemoryStorage(),
		);
		const provider = fauxProvider();
		provider.setResponses([
			fauxAssistantMessage([fauxToolCall("fetch", { url: "https://allowed.example/data" })], {
				stopReason: "toolUse",
			}),
			fauxAssistantMessage("complete"),
		]);
		const models = createModels();
		models.setProvider(provider.provider);
		let localCalls = 0;
		const tool: AgentHarnessTool<undefined, typeof schema> = {
			name: "fetch",
			label: "fetch",
			description: "fetch",
			parameters: schema,
			effect: {
				kind: "network",
				method: "GET",
				sensitive: true,
				destinationArgument: "url",
				destinationType: "url",
			},
			async execute() {
				localCalls += 1;
				return { content: [{ type: "text", text: "local" }], details: undefined };
			},
		};
		const host = new ResultHost({
			result: { content: [{ type: "text", text: "brokered" }], details: undefined },
			isError: false,
		});
		const audit = new RecordingAudit();
		const { harness } = await AgentHarness.create(
			{
				session,
				models,
				model: provider.getModel(),
				tools: [tool],
				enforcement: createEnforcementKernel({ policy: policy(), audit, host }),
			},
			BACKGROUND_CONTEXT,
		);
		try {
			const lane = await harness.lane("main", BACKGROUND_CONTEXT);
			const result = await lane.prompt("fetch", undefined, BACKGROUND_CONTEXT);
			expect(result).toMatchObject({ ok: true, value: { status: "completed" } });
			expect(localCalls).toBe(0);
			expect(host.calls).toEqual(["fetch"]);
			expect(audit.events.map((event) => event.phase)).toEqual(["intent", "completion"]);
		} finally {
			await harness.close(BACKGROUND_CONTEXT);
		}
	});

	it("routes a Pico3 external effect through the broker", async () => {
		let localCalls = 0;
		const declaration: ToolDeclaration<typeof schema> = {
			name: "fetch",
			description: "fetch",
			parameters: schema,
			effect: {
				kind: "network",
				method: "GET",
				sensitive: true,
				destinationArgument: "url",
				destinationType: "url",
			},
			async execute(): Promise<ToolResult> {
				localCalls += 1;
				return { content: [{ type: "text", text: "local" }] };
			},
		};
		const host = new ResultHost({ content: [{ type: "text", text: "brokered" }] });
		const audit = new RecordingAudit();
		const harness = await PicoHarness.open(
			new PicoMemoryStorage(),
			{
				models: fake({
					respond: (_messages, call) =>
						call === 0
							? { toolCalls: [{ name: "fetch", arguments: { url: "https://allowed.example/data" } }] }
							: { text: "complete" },
				}),
				tools: [declaration],
				root: { rewindable: { model, selectedTools: ["fetch"] } },
				enforcement: createEnforcementKernel({ policy: policy(), audit, host }),
			},
			BACKGROUND_CONTEXT,
		);
		try {
			harness.resume();
			const root = await harness.root(BACKGROUND_CONTEXT);
			await (await root.send({ content: "tool:fetch", whenBusy: "reject" }, BACKGROUND_CONTEXT)).wait(
				BACKGROUND_CONTEXT,
			);
			expect(localCalls).toBe(0);
			expect(host.calls).toEqual(["fetch"]);
			expect(audit.events.map((event) => event.phase)).toEqual(["intent", "completion"]);
		} finally {
			await harness.close(BACKGROUND_CONTEXT);
		}
	});
});
