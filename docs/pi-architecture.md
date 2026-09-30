# Pi architecture reference

Source repository: `abuzucom/pi`.
Inspected revision: `e4c75a73222ae2c72abb5f5314fa35ee8effc508`.
Original upstream: `earendil-works/pi`.

The packages below exist in the inspected source.
The packages do not exist in this repository yet.

| Package | Responsibility |
|---|---|
| `packages/agent` | Agent loop, durable harness, tools, sessions, and recovery. |
| `packages/ai` | Model requests and provider integrations. |
| `packages/coding-agent` | CLI, RPC, SDK, tools, extensions, and interactive modes. |
| `packages/chord` | Application composition and services. |
| `packages/tui` | Terminal interface. |
| `packages/telemetry` | Typed telemetry. |
| Protocol, client, server, and session backends | Transport and durable session support. |

CLI entry: `packages/coding-agent/src/cli.ts`.
RPC entry: `packages/coding-agent/src/rpc-entry.ts`.
Preserve exported APIs, CLI flags, tool schemas, extension events, and session formats.

## Reference commands

These commands require later source import and act-specific authorization.

- Install approved dependencies with `npm ci --ignore-scripts`.
- Run focused agent tests with the harness Vitest configuration.
- Use the faux provider for coding-agent suite tests.
- Run TUI tests with Node.
- Inspect `npm run check` before execution.
  The command rewrites files.
- Inspect `test.sh` before execution.
  The script recursively deletes its temporary tree.
  Script consent does not authorize destructive cleanup.

Canonical agents policy overrides conflicting pi agent guidance.
Do not substitute upstream convenience paths for adopted gates.
