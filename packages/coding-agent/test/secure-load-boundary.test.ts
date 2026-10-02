import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { resolveExternalRegularFile } from "../src/secure/load-enforcement.ts";

describe("strict host loading boundaries", () => {
	it("rejects a sibling-like name inside the workspace", () => {
		const root = mkdtempSync(join(tmpdir(), "pi-loader-"));
		const workspace = join(root, "work");
		mkdirSync(workspace);
		const candidate = join(workspace, "..host.mjs");
		writeFileSync(candidate, "export default {};");

		expect(() => resolveExternalRegularFile(candidate, "host", workspace)).toThrow(
			"must remain outside the target workspace",
		);
	});

	it("rejects an external link that resolves into the workspace", () => {
		const root = mkdtempSync(join(tmpdir(), "pi-loader-"));
		const workspace = join(root, "work");
		const external = join(root, "external");
		mkdirSync(workspace);
		mkdirSync(external);
		const target = join(workspace, "host");
		const candidate = join(external, "host");
		mkdirSync(target);
		symlinkSync(target, candidate, process.platform === "win32" ? "junction" : "dir");

		expect(() => resolveExternalRegularFile(candidate, "host", workspace)).toThrow(
			"must remain outside the target workspace",
		);
	});

	it("requires a regular external file", () => {
		const root = mkdtempSync(join(tmpdir(), "pi-loader-"));
		const workspace = join(root, "work");
		const candidate = join(root, "external");
		mkdirSync(workspace);
		mkdirSync(candidate);

		expect(() => resolveExternalRegularFile(candidate, "host", workspace)).toThrow(
			"must name a regular external file",
		);
	});
});
