import { lstatSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { setTreeOwnership } from "../docker/ownership.ts";

describe("evaluation ownership traversal", () => {
	it.runIf(process.platform !== "win32")("does not follow model-created symbolic links", () => {
		const root = mkdtempSync(join(tmpdir(), "pi-ownership-"));
		const outside = join(root, "outside.txt");
		const workspace = join(root, "workspace");
		writeFileSync(outside, "outside");
		writeFileSync(workspace, "workspace");
		const link = join(root, "model-link");
		symlinkSync(outside, link, "file");
		const before = lstatSync(outside);

		setTreeOwnership(link, process.getuid?.() ?? 0, process.getgid?.() ?? 0);

		const after = lstatSync(outside);
		expect(after.ctimeMs).toBe(before.ctimeMs);
	});
});
