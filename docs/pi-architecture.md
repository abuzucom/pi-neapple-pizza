# Pi architecture reference

Source repository: `earendil-works/pi`.
Imported release: `v1.5.2` at `b4afdddf44e059c67ccf5097e5317d913521b470`.
`DRIFT.md` records the excluded upstream paths and local adaptations.

| Path | Responsibility |
|---|---|
| `packages/agent` | Agent core with transport abstraction and state management. |
| `packages/ai` | Unified model API and provider integrations. |
| `packages/chord` | Object runtime for apps across processes. |
| `packages/codemode` | Sandboxed JavaScript execution through injected tools. |
| `packages/coding-agent` | CLI, RPC, SDK, tools, extensions, and interactive modes. |
| `packages/durable` | Durable conversation, task, and document runtime. |
| `packages/env` | Remote execution environments for the durable runtime. |
| `packages/evals` | Model and harness evaluations. |
| `packages/mcp` | Model Context Protocol client. |
| `packages/schema` | JSON Schema validation without eval. |
| `packages/telemetry` | Typed telemetry contracts. |
| `packages/tui` | Terminal interface library. |
| `apps/p2` | Experimental durable UI prototype. |
| `apps/p3` | Design documents without a runtime package. |

CLI entry: `packages/coding-agent/src/cli.ts`.
RPC entry: `packages/coding-agent/src/rpc-entry.ts`.
Preserve exported APIs, CLI flags, tool schemas, extension events, and session formats.

## Reference commands

These commands require act-specific authorization.

- Install approved dependencies with `npm ci --ignore-scripts`.
- Build the packages with `npm run build`.
  The `packages/ai` build fetches live model catalog data.
- Inspect `npm run check` before execution.
  The command rewrites files through Biome.
  Run `node scripts/biome-check.mjs` without `--write` for a read-only check.
- Some `packages/ai` end-to-end tests read local provider credentials.
  Review the test targets before execution.
- Inspect `test.sh` before execution.
  The script recursively deletes its temporary tree.
  Script consent does not authorize destructive cleanup.

Canonical agents policy overrides conflicting pi agent guidance.
Do not substitute upstream convenience paths for adopted gates.
