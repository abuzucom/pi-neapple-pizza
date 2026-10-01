import type { ApprovalSource, SecurityHost } from "@earendil-works/pi-agent-core/harness/enforcement";
import { MacChainedAuditSink } from "@earendil-works/pi-agent-core/harness/enforcement";

/** Host-owned enforcement components loaded from outside the target workspace. */
export interface SecureHostModule {
	readonly audit: MacChainedAuditSink;
	readonly host: SecurityHost;
	readonly approvals?: ApprovalSource;
	readonly sandboxRuntimeVersion: "0.0.77";
	readonly validatedPlatforms: readonly NodeJS.Platform[];
}

/** Validate the external module contract before strict startup. */
export function validateSecureHostModule(value: unknown): SecureHostModule {
	if (typeof value !== "object" || value === null) throw new TypeError("secure host module must export an object");
	const candidate = value as Partial<SecureHostModule>;
	if (
		!(candidate.audit instanceof MacChainedAuditSink) ||
		typeof candidate.host?.execute !== "function" ||
		candidate.sandboxRuntimeVersion !== "0.0.77" ||
		!Array.isArray(candidate.validatedPlatforms) ||
		!candidate.validatedPlatforms.includes(process.platform)
	) {
		throw new TypeError("secure host module lacks the required broker, audit sink, or platform validation");
	}
	if (candidate.approvals !== undefined && typeof candidate.approvals.resolve !== "function") {
		throw new TypeError("secure host approval source is invalid");
	}
	return candidate as SecureHostModule;
}
