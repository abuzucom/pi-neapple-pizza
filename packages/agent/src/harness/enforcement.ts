import { createHash, createHmac, randomUUID } from "node:crypto";
import { existsSync, realpathSync } from "node:fs";
import path from "node:path";
import type { Context } from "./context.ts";
import type { JsonValue } from "./session/types.ts";

export type EffectKind = "pure" | "filesystem" | "process" | "network" | "hosted" | "extension" | "mcp";

export interface ToolEffectDescriptor {
	readonly kind: EffectKind;
	readonly method: string;
	readonly sensitive: boolean;
	readonly commandShape?: "argv" | "shell";
	readonly destinationArgument?: string;
	readonly destinationType?: "path" | "url";
	readonly executableArgument?: string;
}

export interface EnforcementLimits {
	readonly maxConcurrent: number;
	readonly maxQueued: number;
	readonly maxCallsPerMinute: number;
	readonly maxRequestBytes: number;
	readonly maxResultBytes: number;
	readonly maxQueueWaitMs?: number;
}

export interface ToolPolicySource {
	readonly effects: EffectKind[];
	readonly methods: string[];
	readonly pathRoots?: string[];
	readonly endpointOrigins?: string[];
	readonly executables?: string[];
	readonly approvalRequired?: boolean;
}

export interface EnforcementPolicySource {
	readonly schemaVersion: 1;
	readonly revision: string;
	readonly expiresAt: string;
	readonly limits: EnforcementLimits;
	readonly tools: Record<string, ToolPolicySource>;
}

export interface ApprovedEnforcementPolicy extends EnforcementPolicySource {
	readonly digest: string;
}

export interface ApprovalGrant {
	readonly id: string;
	readonly operationId: string;
	readonly callId: string;
	readonly argumentsDigest: string;
	readonly policyDigest: string;
	readonly expiresAt: string;
	readonly nonce: string;
}

export interface EnforcementRequest {
	readonly operationId: string;
	readonly callId: string;
	readonly toolName: string;
	readonly args: Record<string, JsonValue>;
	readonly effect?: ToolEffectDescriptor;
	readonly approval?: ApprovalGrant;
}

export interface BrokerRequest extends EnforcementRequest {
	readonly argumentsDigest: string;
	readonly policyDigest: string;
	readonly policyRevision: string;
	readonly validatedDestination?: string;
}

export interface AuditEvent {
	readonly schemaVersion: 1;
	readonly eventId: string;
	readonly operationId: string;
	readonly callId: string;
	readonly toolName: string;
	readonly effect: EffectKind | "unclassified";
	readonly method: string | "unclassified";
	readonly sensitive: boolean;
	readonly argumentsDigest: string;
	readonly policyDigest: string;
	readonly policyRevision: string;
	readonly phase: "intent" | "denial" | "completion" | "failure";
	readonly decision: "allow" | "deny";
	readonly reasonCode: string;
	readonly occurredAt: string;
	readonly approvalId?: string;
}

export interface AuditReceipt {
	readonly sequence: number;
	readonly previousDigest?: string;
	readonly recordDigest: string;
	readonly mac: string;
}

export interface ChainedAuditRecord extends AuditReceipt {
	readonly event: AuditEvent;
}

export interface AuditRecordStore {
	/** Append the record and consume the grant in one durable transaction. */
	append(record: ChainedAuditRecord, approval: ApprovalGrant | undefined, context: Context): Promise<void>;
}

export interface MacChainedAuditSinkOptions {
	readonly key: Uint8Array;
	readonly store: AuditRecordStore;
	readonly initialReceipt?: AuditReceipt;
}

export interface AuditSink {
	/** Persist the event and atomically consume its approval grant when present. */
	append(event: AuditEvent, approval: ApprovalGrant | undefined, context: Context): Promise<AuditReceipt>;
}

/** Serialized SHA-256 record chain with a host-owned HMAC key. */
export class MacChainedAuditSink implements AuditSink {
	readonly integrity = "sha256-hmac-chain-v1" as const;
	private readonly key: Uint8Array;
	private readonly store: AuditRecordStore;
	private sequence: number;
	private previousDigest: string;
	private tail: Promise<void> = Promise.resolve();

	constructor(options: MacChainedAuditSinkOptions) {
		if (options.key.byteLength < 32) throw new RangeError("audit MAC key must contain at least 32 bytes");
		this.key = Uint8Array.from(options.key);
		this.store = options.store;
		this.sequence = options.initialReceipt?.sequence ?? 0;
		this.previousDigest = options.initialReceipt?.recordDigest ?? "0".repeat(64);
	}

	append(event: AuditEvent, approval: ApprovalGrant | undefined, context: Context): Promise<AuditReceipt> {
		const operation = this.tail.then(async () => {
			const sequence = this.sequence + 1;
			const previousDigest = this.previousDigest;
			const recordContent = canonicalJson({ event, previousDigest, sequence });
			const recordDigest = sha256(recordContent);
			const mac = createHmac("sha256", this.key).update(recordContent, "utf8").digest("hex");
			const record: ChainedAuditRecord = { event, sequence, previousDigest, recordDigest, mac };
			await this.store.append(record, approval, context);
			this.sequence = sequence;
			this.previousDigest = recordDigest;
			return record;
		});
		this.tail = operation.then(
			() => undefined,
			() => undefined,
		);
		return operation;
	}
}

export interface SecurityHost {
	/** Revalidate mutable security state and execute one named external effect. */
	execute<TResult>(request: BrokerRequest, receipt: AuditReceipt, context: Context): Promise<TResult>;
}

export interface ApprovalSource {
	/** Resolve one fresh grant for this exact operation and argument digest. */
	resolve(request: EnforcementRequest, context: Context): Promise<ApprovalGrant | undefined>;
}

export interface EnforcementKernelOptions {
	readonly policy: ApprovedEnforcementPolicy;
	readonly audit: AuditSink;
	readonly host: SecurityHost;
	readonly approvals?: ApprovalSource;
	readonly now?: () => number;
	readonly workingDirectory?: string;
}

interface CompiledToolPolicy {
	readonly effects: ReadonlySet<EffectKind>;
	readonly methods: ReadonlySet<string>;
	readonly pathRoots: readonly string[];
	readonly endpointOrigins: ReadonlySet<string>;
	readonly executables: ReadonlySet<string>;
	readonly approvalRequired: boolean;
}

interface CompiledPolicy {
	readonly source: ApprovedEnforcementPolicy;
	readonly expiresAt: number;
	readonly tools: ReadonlyMap<string, CompiledToolPolicy>;
}

interface QueueEntry {
	readonly key: symbol;
	readonly resolve: (release: () => void) => void;
	readonly reject: (error: Error) => void;
	readonly signal: AbortSignal | undefined;
	readonly abort: () => void;
	readonly timer: ReturnType<typeof setTimeout>;
}

interface CheckedRequest {
	readonly argumentsDigest: string;
	readonly validatedDestination?: string;
}

const DEFAULT_MAX_QUEUE_WAIT_MS = 30_000;
const MAX_CANONICAL_JSON_DEPTH = 64;
const CALL_TIME_COMPACTION_THRESHOLD = 1_024;
const CALL_RATE_WINDOW_MS = 60_000;

class PolicyViolation extends Error {
	readonly code: string;

	constructor(code: string, message: string) {
		super(message);
		this.name = "PolicyViolation";
		this.code = code;
	}
}

export class EnforcementDenied extends Error {
	readonly code: string;

	constructor(code: string, message: string) {
		super(message);
		this.name = "EnforcementDenied";
		this.code = code;
	}
}

function sortJsonArray(
	value: unknown[],
	depth: number,
	ancestors: Set<object>,
	omitUndefinedObjectProperties: boolean,
): unknown[] {
	const names = Object.getOwnPropertyNames(value);
	const keys = Object.keys(value);
	if (
		Object.getOwnPropertySymbols(value).length > 0 ||
		names.length !== value.length + 1 ||
		keys.length !== value.length
	) {
		throw new TypeError("canonical JSON array contains unsupported properties");
	}
	return keys.map((key, index) => {
		if (key !== String(index)) throw new TypeError("canonical JSON array is sparse");
		const descriptor = Object.getOwnPropertyDescriptor(value, key);
		if (descriptor === undefined || "get" in descriptor || "set" in descriptor) {
			throw new TypeError("canonical JSON must not contain accessors");
		}
		return sortJson(descriptor.value, depth + 1, ancestors, omitUndefinedObjectProperties);
	});
}

function sortJsonObject(
	value: object,
	depth: number,
	ancestors: Set<object>,
	omitUndefinedObjectProperties: boolean,
): Record<string, unknown> {
	const prototype = Object.getPrototypeOf(value);
	if (prototype !== Object.prototype && prototype !== null) {
		throw new TypeError("canonical JSON must contain plain objects");
	}
	const names = Object.getOwnPropertyNames(value);
	if (Object.getOwnPropertySymbols(value).length > 0 || Object.keys(value).length !== names.length) {
		throw new TypeError("canonical JSON object contains unsupported properties");
	}
	const entries = names
		.sort((left, right) => (left < right ? -1 : left > right ? 1 : 0))
		.flatMap((key) => {
			const descriptor = Object.getOwnPropertyDescriptor(value, key);
			if (descriptor === undefined || "get" in descriptor || "set" in descriptor) {
				throw new TypeError("canonical JSON must not contain accessors");
			}
			if (omitUndefinedObjectProperties && descriptor.value === undefined) return [];
			return [[key, sortJson(descriptor.value, depth + 1, ancestors, omitUndefinedObjectProperties)] as const];
		});
	return Object.fromEntries(entries);
}

function sortJson(
	value: unknown,
	depth = 0,
	ancestors = new Set<object>(),
	omitUndefinedObjectProperties = false,
): unknown {
	if (value === null || typeof value === "string" || typeof value === "boolean") return value;
	if (typeof value === "number") {
		if (!Number.isFinite(value)) throw new TypeError("canonical JSON number must be finite");
		return value;
	}
	if (typeof value !== "object") throw new TypeError("canonical JSON contains an unsupported value");
	if (depth >= MAX_CANONICAL_JSON_DEPTH) throw new TypeError("canonical JSON exceeds the nesting bound");
	if (ancestors.has(value)) throw new TypeError("canonical JSON contains a cycle");
	ancestors.add(value);
	try {
		return Array.isArray(value)
			? sortJsonArray(value, depth, ancestors, omitUndefinedObjectProperties)
			: sortJsonObject(value, depth, ancestors, omitUndefinedObjectProperties);
	} finally {
		ancestors.delete(value);
	}
}

function canonicalJson(value: unknown): string {
	const encoded = JSON.stringify(sortJson(value));
	if (encoded === undefined) throw new TypeError("value cannot be represented as canonical JSON");
	return encoded;
}

function canonicalResultJson(value: unknown): string {
	const encoded = JSON.stringify(sortJson(value, 0, new Set<object>(), true));
	if (encoded === undefined) throw new TypeError("result cannot be represented as canonical JSON");
	return encoded;
}

function cloneCanonicalArguments(value: unknown): Record<string, JsonValue> {
	const cloned: unknown = JSON.parse(canonicalJson(value));
	if (cloned === null || Array.isArray(cloned) || typeof cloned !== "object") {
		throw new TypeError("tool arguments must contain a JSON object");
	}
	return cloned as Record<string, JsonValue>;
}

function sha256(value: string): string {
	return createHash("sha256").update(value, "utf8").digest("hex");
}

export function computePolicyDigest(policy: EnforcementPolicySource): string {
	return sha256(canonicalJson(policy));
}

function requirePositiveInteger(value: number, name: string): void {
	if (!Number.isSafeInteger(value) || value <= 0) throw new RangeError(`${name} must be a positive safe integer`);
}

function validateIdentifier(value: string, name: string): void {
	if (value.length === 0 || value.length > 256 || /[\u0000-\u001f\u007f]/.test(value)) {
		throw new PolicyViolation("invalid_identifier", `${name} is invalid`);
	}
}

function canonicalizeFromExistingParent(value: string): string {
	let existing = value;
	const missingParts: string[] = [];
	while (!existsSync(existing)) {
		const parent = path.dirname(existing);
		if (parent === existing) throw new TypeError(`path has no existing parent: ${value}`);
		missingParts.unshift(path.basename(existing));
		existing = parent;
	}
	return path.join(realpathSync.native(existing), ...missingParts);
}

function isContained(root: string, candidate: string): boolean {
	const relation = path.relative(root, candidate);
	return relation === "" || (relation !== ".." && !relation.startsWith(`..${path.sep}`) && !path.isAbsolute(relation));
}

function compileToolPolicy(source: ToolPolicySource, workingDirectory: string): CompiledToolPolicy {
	if (source.effects.length === 0 || source.methods.length === 0) {
		throw new TypeError("tool policy effects and methods must not be empty");
	}
	const pathRoots = (source.pathRoots ?? []).map((root) => realpathSync.native(path.resolve(workingDirectory, root)));
	const endpointOrigins = new Set((source.endpointOrigins ?? []).map((origin) => new URL(origin).origin));
	return {
		effects: new Set(source.effects),
		methods: new Set(source.methods),
		pathRoots,
		endpointOrigins,
		executables: new Set(source.executables ?? []),
		approvalRequired: source.approvalRequired === true,
	};
}

function compilePolicy(policy: ApprovedEnforcementPolicy, workingDirectory: string): CompiledPolicy {
	if (policy.schemaVersion !== 1 || policy.revision.length === 0) throw new TypeError("policy metadata is invalid");
	const { limits } = policy;
	requirePositiveInteger(limits.maxConcurrent, "maxConcurrent");
	requirePositiveInteger(limits.maxQueued, "maxQueued");
	requirePositiveInteger(limits.maxCallsPerMinute, "maxCallsPerMinute");
	requirePositiveInteger(limits.maxRequestBytes, "maxRequestBytes");
	requirePositiveInteger(limits.maxResultBytes, "maxResultBytes");
	if (limits.maxQueueWaitMs !== undefined) requirePositiveInteger(limits.maxQueueWaitMs, "maxQueueWaitMs");
	const expiresAt = Date.parse(policy.expiresAt);
	if (!Number.isFinite(expiresAt)) throw new TypeError("policy expiration is invalid");
	const { digest, ...source } = policy;
	if (digest !== computePolicyDigest(source)) throw new TypeError("policy digest does not match canonical content");
	const tools = new Map<string, CompiledToolPolicy>();
	for (const [name, tool] of Object.entries(policy.tools)) {
		validateIdentifier(name, "policy tool name");
		tools.set(name, compileToolPolicy(tool, workingDirectory));
	}
	return { source: policy, expiresAt, tools };
}

function readArgument(request: EnforcementRequest, name: string): JsonValue {
	if (!Object.hasOwn(request.args, name))
		throw new PolicyViolation("missing_argument", `required argument ${name} is absent`);
	return request.args[name]!;
}

function validatePathDestination(value: JsonValue, roots: readonly string[], workingDirectory: string): string {
	if (typeof value !== "string") throw new PolicyViolation("invalid_destination", "path destination must be a string");
	const destination = canonicalizeFromExistingParent(path.resolve(workingDirectory, value));
	const allowed = roots.some((root) => isContained(root, destination));
	if (!allowed) throw new PolicyViolation("destination_denied", "path destination is outside approved roots");
	return destination;
}

function validateUrlDestination(value: JsonValue, origins: ReadonlySet<string>): void {
	if (typeof value !== "string") throw new PolicyViolation("invalid_destination", "URL destination must be a string");
	let destination: URL;
	try {
		destination = new URL(value);
	} catch {
		throw new PolicyViolation("invalid_destination", "URL destination is invalid");
	}
	if (destination.username || destination.password) {
		throw new PolicyViolation("invalid_destination", "URL destination must not contain credentials");
	}
	if (!origins.has(destination.origin)) {
		throw new PolicyViolation("destination_denied", "URL destination is not approved");
	}
}

function validateApproval(
	request: EnforcementRequest,
	digest: string,
	policy: ApprovedEnforcementPolicy,
	now: number,
): void {
	const approval = request.approval;
	if (approval === undefined) throw new PolicyViolation("approval_required", "an exact approval grant is required");
	const expiresAt = Date.parse(approval.expiresAt);
	if (
		approval.operationId !== request.operationId ||
		approval.callId !== request.callId ||
		approval.argumentsDigest !== digest ||
		approval.policyDigest !== policy.digest ||
		approval.nonce.length === 0 ||
		!Number.isFinite(expiresAt) ||
		expiresAt <= now
	) {
		throw new PolicyViolation("approval_invalid", "approval grant does not match the operation or remains stale");
	}
}

function validateEffect(
	request: EnforcementRequest,
	toolPolicy: CompiledToolPolicy,
	policy: ApprovedEnforcementPolicy,
	now: number,
	workingDirectory: string,
	argumentsDigest: string,
): CheckedRequest {
	const effect = request.effect;
	if (effect === undefined) throw new PolicyViolation("unclassified_tool", "tool lacks a strict effect declaration");
	if (!toolPolicy.effects.has(effect.kind) || !toolPolicy.methods.has(effect.method)) {
		throw new PolicyViolation("operation_denied", "tool effect or method is not approved");
	}
	if (effect.kind === "process" && effect.commandShape !== "argv") {
		throw new PolicyViolation("shell_string_denied", "shell command strings are unavailable in strict mode");
	}
	if (effect.executableArgument !== undefined) {
		const executable = readArgument(request, effect.executableArgument);
		if (typeof executable !== "string" || !toolPolicy.executables.has(executable)) {
			throw new PolicyViolation("executable_denied", "process executable is not approved");
		}
	}
	let validatedDestination: string | undefined;
	if (effect.destinationArgument !== undefined) {
		const destination = readArgument(request, effect.destinationArgument);
		if (effect.destinationType === "path") {
			validatedDestination = validatePathDestination(destination, toolPolicy.pathRoots, workingDirectory);
		} else if (effect.destinationType === "url") validateUrlDestination(destination, toolPolicy.endpointOrigins);
		else throw new PolicyViolation("invalid_destination", "destination type is absent");
	}
	if (toolPolicy.approvalRequired) validateApproval(request, argumentsDigest, policy, now);
	return { argumentsDigest, validatedDestination };
}

export class EnforcementKernel {
	private readonly compiled: CompiledPolicy;
	private readonly audit: AuditSink;
	private readonly host: SecurityHost;
	private readonly approvals: ApprovalSource | undefined;
	private readonly now: () => number;
	private readonly workingDirectory: string;
	private readonly queue = new Map<symbol, QueueEntry>();
	private readonly callTimes: number[] = [];
	private callTimesHead = 0;
	private readonly activeOperations = new Map<string, string>();
	private activeCount = 0;

	constructor(options: EnforcementKernelOptions) {
		this.workingDirectory = realpathSync.native(path.resolve(options.workingDirectory ?? process.cwd()));
		this.compiled = compilePolicy(options.policy, this.workingDirectory);
		this.audit = options.audit;
		this.host = options.host;
		this.approvals = options.approvals;
		this.now = options.now ?? Date.now;
	}

	get maxOutputBytes(): number {
		return this.compiled.source.limits.maxResultBytes;
	}

	assertOutputSize(value: unknown): void {
		this.checkResultSize(value);
	}

	async run<TResult>(
		request: EnforcementRequest,
		localPureEffect: () => Promise<TResult>,
		context: Context,
	): Promise<TResult> {
		let release: (() => void) | undefined;
		let resolvedRequest = request;
		let claimedOperation = false;
		try {
			if (request.approval === undefined && this.approvals !== undefined) {
				const approval = await this.approvals.resolve(request, context);
				if (approval !== undefined) resolvedRequest = { ...request, approval };
			}
			try {
				resolvedRequest = { ...resolvedRequest, args: cloneCanonicalArguments(resolvedRequest.args) };
			} catch (error) {
				if (error instanceof TypeError) {
					throw new PolicyViolation("invalid_arguments", "tool arguments are not bounded canonical JSON");
				}
				throw error;
			}
			const checked = this.checkRequest(resolvedRequest, true);
			this.claimOperation(resolvedRequest);
			claimedOperation = true;
			release = await this.acquire(context);
			const admitted = this.checkRequest(resolvedRequest, false);
			if (admitted.argumentsDigest !== checked.argumentsDigest) {
				throw new PolicyViolation("arguments_changed", "tool arguments changed while awaiting admission");
			}
			const intent = this.createEvent(resolvedRequest, admitted.argumentsDigest, "intent", "allow", "admitted");
			const receipt = await this.persistIntent(intent, resolvedRequest.approval, context);
			const execution = this.checkRequest(resolvedRequest, false);
			if (execution.argumentsDigest !== admitted.argumentsDigest) {
				throw new PolicyViolation("arguments_changed", "tool arguments changed before execution");
			}
			const brokerRequest = this.brokerRequest(resolvedRequest, execution);
			let result: TResult;
			try {
				result =
					resolvedRequest.effect?.kind === "pure"
						? await localPureEffect()
						: await this.host.execute<TResult>(brokerRequest, receipt, context);
				this.checkResultSize(result);
			} catch (error) {
				const failureCode = error instanceof EnforcementDenied ? error.code : "effect_failed";
				await this.persist(
					this.createEvent(resolvedRequest, admitted.argumentsDigest, "failure", "deny", failureCode),
					context,
				);
				throw error;
			}
			await this.persist(
				this.createEvent(resolvedRequest, admitted.argumentsDigest, "completion", "allow", "completed"),
				context,
			);
			return result;
		} catch (error) {
			if (error instanceof PolicyViolation) return this.deny(resolvedRequest, error, context);
			throw error;
		} finally {
			if (claimedOperation) {
				this.activeOperations.delete(`${resolvedRequest.operationId}\u0000${resolvedRequest.callId}`);
			}
			release?.();
		}
	}

	private checkRequest(request: EnforcementRequest, recordRate: boolean): CheckedRequest {
		validateIdentifier(request.operationId, "operation identifier");
		validateIdentifier(request.callId, "call identifier");
		validateIdentifier(request.toolName, "tool name");
		const now = this.now();
		if (now >= this.compiled.expiresAt) throw new PolicyViolation("policy_expired", "approved policy is stale");
		let encodedArguments: string;
		try {
			encodedArguments = canonicalJson(request.args);
		} catch (error) {
			if (error instanceof TypeError) {
				throw new PolicyViolation("invalid_arguments", "tool arguments are not bounded canonical JSON");
			}
			throw error;
		}
		const requestBytes = Buffer.byteLength(encodedArguments, "utf8");
		if (requestBytes > this.compiled.source.limits.maxRequestBytes) {
			throw new PolicyViolation("request_too_large", "tool arguments exceed the approved byte bound");
		}
		const toolPolicy = this.compiled.tools.get(request.toolName);
		if (toolPolicy === undefined) throw new PolicyViolation("tool_denied", "tool is absent from the approved policy");
		if (recordRate) this.checkRate(now);
		return validateEffect(
			request,
			toolPolicy,
			this.compiled.source,
			now,
			this.workingDirectory,
			sha256(encodedArguments),
		);
	}

	private checkRate(now: number): void {
		const windowStart = now - CALL_RATE_WINDOW_MS;
		while (this.callTimesHead < this.callTimes.length && this.callTimes[this.callTimesHead]! <= windowStart) {
			this.callTimesHead += 1;
		}
		const activeCallCount = this.callTimes.length - this.callTimesHead;
		if (activeCallCount >= this.compiled.source.limits.maxCallsPerMinute) {
			throw new PolicyViolation("rate_limited", "tool call rate exceeds the approved bound");
		}
		this.callTimes.push(now);
		if (
			this.callTimesHead >= CALL_TIME_COMPACTION_THRESHOLD &&
			this.callTimesHead >= this.callTimes.length - this.callTimesHead
		) {
			this.callTimes.splice(0, this.callTimesHead);
			this.callTimesHead = 0;
		}
	}

	private acquire(context: Context): Promise<() => void> {
		context.abortSignal?.throwIfAborted();
		if (this.activeCount < this.compiled.source.limits.maxConcurrent) {
			this.activeCount += 1;
			return Promise.resolve(() => this.release());
		}
		if (this.queue.size >= this.compiled.source.limits.maxQueued) {
			throw new PolicyViolation("queue_full", "tool queue exceeds the approved bound");
		}
		const key = Symbol("queued enforcement call");
		return new Promise((resolve, reject) => {
			const finish = (error: Error): void => {
				const entry = this.queue.get(key);
				if (entry === undefined) return;
				this.removeQueueEntry(entry);
				reject(error);
			};
			const abort = (): void => {
				const reason = context.abortSignal?.reason;
				finish(reason instanceof Error ? reason : new Error("tool call aborted while queued"));
			};
			const timer = setTimeout(() => {
				finish(new PolicyViolation("queue_timeout", "tool call exceeded the approved queue wait"));
			}, this.compiled.source.limits.maxQueueWaitMs ?? DEFAULT_MAX_QUEUE_WAIT_MS);
			const entry: QueueEntry = { key, resolve, reject, signal: context.abortSignal, abort, timer };
			this.queue.set(key, entry);
			context.abortSignal?.addEventListener("abort", abort, { once: true });
		});
	}

	private release(): void {
		const next = this.queue.values().next().value as QueueEntry | undefined;
		if (next !== undefined) {
			this.removeQueueEntry(next);
			next.resolve(() => this.release());
			return;
		}
		this.activeCount -= 1;
	}

	private removeQueueEntry(entry: QueueEntry): void {
		this.queue.delete(entry.key);
		clearTimeout(entry.timer);
		entry.signal?.removeEventListener("abort", entry.abort);
	}

	private claimOperation(request: EnforcementRequest): void {
		const key = `${request.operationId}\u0000${request.callId}`;
		if (this.activeOperations.has(key)) throw new PolicyViolation("duplicate_call", "tool call is already active");
		this.activeOperations.set(key, request.toolName);
	}

	private brokerRequest(request: EnforcementRequest, checked: CheckedRequest): BrokerRequest {
		let args = request.args;
		const destinationArgument = request.effect?.destinationArgument;
		if (checked.validatedDestination !== undefined && destinationArgument !== undefined) {
			args = { ...request.args, [destinationArgument]: checked.validatedDestination };
		}
		return {
			...request,
			args,
			argumentsDigest: checked.argumentsDigest,
			policyDigest: this.compiled.source.digest,
			policyRevision: this.compiled.source.revision,
			...(checked.validatedDestination === undefined ? {} : { validatedDestination: checked.validatedDestination }),
		};
	}

	private checkResultSize(result: unknown): void {
		const bytes = Buffer.byteLength(canonicalResultJson(result), "utf8");
		if (bytes > this.compiled.source.limits.maxResultBytes) {
			throw new EnforcementDenied("result_too_large", "tool result exceeds the approved byte bound");
		}
	}

	private createEvent(
		request: EnforcementRequest,
		argumentsDigest: string,
		phase: AuditEvent["phase"],
		decision: AuditEvent["decision"],
		reasonCode: string,
	): AuditEvent {
		return {
			schemaVersion: 1,
			eventId: randomUUID(),
			operationId: request.operationId,
			callId: request.callId,
			toolName: request.toolName,
			effect: request.effect?.kind ?? "unclassified",
			method: request.effect?.method ?? "unclassified",
			sensitive: request.effect?.sensitive ?? true,
			argumentsDigest,
			policyDigest: this.compiled.source.digest,
			policyRevision: this.compiled.source.revision,
			phase,
			decision,
			reasonCode,
			occurredAt: new Date(this.now()).toISOString(),
			...(request.approval === undefined ? {} : { approvalId: request.approval.id }),
		};
	}

	private async persistIntent(
		event: AuditEvent,
		approval: ApprovalGrant | undefined,
		context: Context,
	): Promise<AuditReceipt> {
		try {
			return await this.audit.append(event, approval, context);
		} catch {
			throw new EnforcementDenied("audit_unavailable", "audit persistence failed before execution");
		}
	}

	private async persist(event: AuditEvent, context: Context): Promise<AuditReceipt> {
		try {
			return await this.audit.append(event, undefined, context);
		} catch {
			throw new EnforcementDenied("audit_unavailable", "audit persistence failed after execution");
		}
	}

	private async deny(request: EnforcementRequest, violation: PolicyViolation, context: Context): Promise<never> {
		let argumentsDigest = "unavailable";
		try {
			argumentsDigest = sha256(canonicalJson(request.args));
		} catch (error) {
			if (!(error instanceof TypeError)) throw error;
		}
		const event = this.createEvent(request, argumentsDigest, "denial", "deny", violation.code);
		try {
			await this.audit.append(event, undefined, context);
		} catch {
			throw new EnforcementDenied("audit_unavailable", "audit persistence failed while recording denial");
		}
		throw new EnforcementDenied(violation.code, violation.message);
	}
}

export function createEnforcementKernel(options: EnforcementKernelOptions): EnforcementKernel {
	return new EnforcementKernel(options);
}
