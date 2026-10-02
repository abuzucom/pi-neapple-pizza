import { realpathSync, statSync } from "node:fs";
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

function isContained(root: string, candidate: string): boolean {
	const relation = relative(root, candidate);
	return relation === "" || (!isAbsolute(relation) && relation !== ".." && !relation.startsWith(`..${pathSeparator}`));
}

const pathSeparator = process.platform === "win32" ? "\\" : "/";

/** Resolve one regular file while preserving the target workspace boundary. */
export function resolveExternalRegularFile(value: string | undefined, name: string, workspace: string): string {
	if (value === undefined || !isAbsolute(value)) throw new Error(`${name} must name an absolute external path`);
	const lexicalWorkspace = resolve(workspace);
	const lexicalCandidate = resolve(value);
	if (isContained(lexicalWorkspace, lexicalCandidate)) {
		throw new Error(`${name} must remain outside the target workspace`);
	}
	const resolvedWorkspace = realpathSync.native(lexicalWorkspace);
	const resolvedCandidate = realpathSync.native(lexicalCandidate);
	if (isContained(resolvedWorkspace, resolvedCandidate)) {
		throw new Error(`${name} must remain outside the target workspace`);
	}
	if (!statSync(resolvedCandidate).isFile()) throw new Error(`${name} must name a regular external file`);
	return resolvedCandidate;
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
	const policyPath = resolveExternalRegularFile(process.env.PI_SECURE_POLICY, "PI_SECURE_POLICY", workspace);
	const hostPath = resolveExternalRegularFile(process.env.PI_SECURE_HOST_MODULE, "PI_SECURE_HOST_MODULE", workspace);
	if (process.platform === "win32" && process.env.PI_SECURE_WINDOWS_SETUP_VALIDATED !== "1") {
		throw new Error("Windows strict startup requires validated one-time elevated sandbox setup");
	}
	const [policy, imported] = await Promise.all([loadPolicy(policyPath), import(pathToFileURL(hostPath).href)]);
	const external = validateSecureHostModule(imported.default);
	return createEnforcementKernel({
		policy,
		audit: external.audit,
		host: external.host,
		workingDirectory: workspace,
		...(external.approvals === undefined ? {} : { approvals: external.approvals }),
	});
}
