import { readFile } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import {
	type ApprovedEnforcementPolicy,
	createEnforcementKernel,
	type EnforcementKernel,
} from "@earendil-works/pi-agent-core/harness/enforcement";
import { validateSecureHostModule } from "./host-module.ts";

const MAX_POLICY_BYTES = 1_048_576;

function requireExternalPath(value: string | undefined, name: string, workspace: string): string {
	if (value === undefined || !isAbsolute(value)) throw new Error(`${name} must name an absolute external path`);
	const normalized = resolve(value);
	const relation = relative(resolve(workspace), normalized);
	if (relation === "" || (!relation.startsWith("..") && !isAbsolute(relation))) {
		throw new Error(`${name} must remain outside the target workspace`);
	}
	return normalized;
}

async function loadPolicy(path: string): Promise<ApprovedEnforcementPolicy> {
	const content = await readFile(path);
	if (content.byteLength === 0 || content.byteLength > MAX_POLICY_BYTES) {
		throw new Error("strict policy file violates its byte bound");
	}
	const decoded = new TextDecoder("utf-8", { fatal: true }).decode(content);
	const parsed: unknown = JSON.parse(decoded);
	if (typeof parsed !== "object" || parsed === null) throw new Error("strict policy root must be an object");
	return parsed as ApprovedEnforcementPolicy;
}

/** Load strict policy and host capabilities from outside the target workspace. */
export async function loadExternalEnforcement(workspace: string): Promise<EnforcementKernel> {
	const policyPath = requireExternalPath(process.env.PI_SECURE_POLICY, "PI_SECURE_POLICY", workspace);
	const hostPath = requireExternalPath(process.env.PI_SECURE_HOST_MODULE, "PI_SECURE_HOST_MODULE", workspace);
	if (process.platform === "win32" && process.env.PI_SECURE_WINDOWS_SETUP_VALIDATED !== "1") {
		throw new Error("Windows strict startup requires validated one-time elevated sandbox setup");
	}
	const [policy, imported] = await Promise.all([loadPolicy(policyPath), import(pathToFileURL(hostPath).href)]);
	const external = validateSecureHostModule(imported.default);
	return createEnforcementKernel({
		policy,
		audit: external.audit,
		host: external.host,
		...(external.approvals === undefined ? {} : { approvals: external.approvals }),
	});
}
