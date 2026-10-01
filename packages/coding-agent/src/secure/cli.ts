#!/usr/bin/env node

import { resolve } from "node:path";
import { loadExternalEnforcement } from "./load-enforcement.ts";
import { openMicro } from "./runtime/runtime.ts";
import { runMicroTui } from "./runtime/tui.ts";

function parseContinueFlag(arguments_: readonly string[]): boolean {
	if (arguments_.length === 0) return false;
	if (arguments_.length === 1 && ["--continue", "-c"].includes(arguments_[0]!)) return true;
	throw new Error("pi-secure accepts only --continue or -c");
}

const cwd = resolve(process.cwd());
const enforcement = await loadExternalEnforcement(cwd);
const micro = await openMicro({ cwd, continueSession: parseContinueFlag(process.argv.slice(2)), enforcement });
try {
	await runMicroTui(micro.view, micro.controller);
} finally {
	await micro.close();
}
