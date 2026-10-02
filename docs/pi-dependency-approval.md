# Pi dependency approval

## Approval subject

Source repository: `abuzucom/pi`.
Source commit: `2bbfcca437c3aa5a21af1e4ee44ae7a051f953ad`.
Preview digest: `55019da5f17da192300bf8c8dd4e33b9ce74f0677c4f86666b6b2f0ac0ad60ee`.

The import pins every direct dependency exactly.
The lockfile pins transitive resolutions.
The import omits Husky 9.1.7 and the donor `prepare` script.

## Runtime and build dependencies

| Dependency | Exact version | Purpose | Alternative |
|---|---:|---|---|
| `@anthropic-ai/sandbox-runtime` | 0.0.77 | Isolate strict process effects across supported operating systems. | Require an external sandbox broker and deny local strict startup. |
| `@anthropic-ai/sdk` | 0.124.0 | Connect the AI package to Anthropic models. | Omit the Anthropic provider. |
| `@anthropic-ai/sdk` | 0.52.0 | Build the pinned custom-provider example. | Exclude that example. |
| `@aws-sdk/client-bedrock-runtime` | 3.1127.0 | Connect the AI package to Amazon Bedrock. | Omit the Bedrock provider. |
| `@google/genai` | 2.21.0 | Connect the AI package to Google models. | Omit the Google provider. |
| `@smithy/node-http-handler` | 4.12.1 | Configure the Bedrock Node transport. | Use the SDK default with reduced proxy control. |
| `openai` | 7.19.0 | Connect the AI package to OpenAI-compatible models. | Omit the OpenAI provider. |
| `http-proxy-agent` | 9.1.0 | Route HTTP provider traffic through configured proxies. | Omit HTTP proxy support. |
| `https-proxy-agent` | 9.1.0 | Route HTTPS provider traffic through configured proxies. | Omit HTTPS proxy support. |
| `undici` | 8.10.2 | Supply Node HTTP client behavior for the coding agent. | Use built-in fetch with a compatibility change. |
| `partial-json` | 0.1.7 | Parse partial streamed JSON arguments. | Maintain a local streaming parser. |
| `typebox` | 1.3.27 | Define and validate tool and protocol schemas. | Maintain custom schema validation. |
| `yaml` | 2.9.0 | Parse YAML configuration and front matter. | Remove YAML inputs. |
| `diff` | 8.0.4 | Create and apply text edits and durable differences. | Maintain a local diff implementation. |
| `ignore` | 7.0.8 | Apply Git ignore syntax to repository traversal. | Maintain a local ignore parser. |
| `cross-spawn` | 7.0.6 | Preserve cross-platform child-process behavior. | Use Node spawn with added platform handling. |
| `quickjs-wasi` | 3.6.2 | Execute isolated code-mode JavaScript. | Disable code mode. |
| `isolated-vm` | 6.2.0 | Build the mobile handoff sandbox example. | Exclude that example. |
| `@earendil-works/gondolin` | 0.12.0 | Build the Gondolin isolation example. | Exclude that example. |
| `@silvia-odwyer/photon-node` | 0.3.4 | Resize images in the coding agent. | Remove image resizing. |
| `chalk` | 6.0.0 | Format terminal output. | Use uncolored terminal output. |
| `grok-mermaid` | 0.2.3 | Render Mermaid content. | Keep Mermaid as plain text. |
| `highlight.js` | 10.7.3 | Highlight exported source code. | Export unhighlighted source. |
| `hosted-git-info` | 9.0.3 | Parse hosted Git repository identifiers. | Maintain a restricted URL parser. |
| `jiti` | 2.7.0 | Load TypeScript and JavaScript extensions. | Require precompiled extensions. |
| `minimatch` | 10.2.6 | Match extension and tool path patterns. | Maintain a restricted glob matcher. |
| `proper-lockfile` | 4.1.2 | Coordinate coding-agent file access. | Implement platform-specific file locks. |
| `semver` | 7.8.5 | Compare package and extension versions. | Maintain a restricted version parser. |
| `marked` | 18.0.11 | Render Markdown in terminal and export paths. | Display plain Markdown. |
| `get-east-asian-width` | 1.6.0 | Measure terminal display widths. | Accept incorrect wide-character layout. |
| `@xterm/headless` | 5.5.0 | Test terminal rendering without a browser. | Maintain a terminal emulator fixture. |
| `canvas` | 3.2.3 | Test image paths in the AI package. | Skip those image tests. |
| `ms` | 2.1.3 | Support the dependency-bearing extension example. | Exclude that example. |
| `protobufjs` | 7.6.6 | Fix the transitive protocol implementation version. | Accept an unbounded transitive resolution. |

## Workspace dependencies

The import pins the following workspace packages to 0.99.1.
The harness change updates the synchronized affected package set to 0.100.0.
No external replacement preserves the imported package contracts.

- `@earendil-works/chord`
- `@earendil-works/pi-agent-core`
- `@earendil-works/pi-ai`
- `@earendil-works/pi-client`
- `@earendil-works/pi-codemode`
- `@earendil-works/pi-coding-agent`
- `@earendil-works/pi-mcp`
- `@earendil-works/pi-protocol`
- `@earendil-works/pi-server`
- `@earendil-works/pi-telemetry`
- `@earendil-works/pi-tui`

The plugin example retains exact peer version 0.84.4 for
`@earendil-works/chord` and `@earendil-works/pi-coding-agent`.

## Development dependencies

| Dependency | Exact version | Purpose | Alternative |
|---|---:|---|---|
| `@biomejs/biome` | 2.3.5 | Check formatting and lint TypeScript. | Maintain separate formatter and linter configurations. |
| `typescript` | 7.0.2 | Compile and type-check the workspace. | No compatible alternative preserves the TypeScript build. |
| `esbuild` | 0.28.2 | Bundle packages and Chord artifacts. | Use the TypeScript compiler without the current bundles. |
| `shx` | 0.4.0 | Run portable package scripts. | Duplicate scripts for each operating system. |
| `vitest` | 4.1.11 | Run package tests. | Port the imported tests to Node test. |
| `@vitest/coverage-v8` | 4.1.11 | Measure harness coverage. | Omit coverage measurement. |
| `@types/node` | 22.19.19 | Type Node APIs. | Maintain local declarations. |
| `@types/cross-spawn` | 6.0.6 | Type cross-spawn calls. | Maintain local declarations. |
| `@types/hosted-git-info` | 3.0.5 | Type hosted-git-info calls. | Maintain local declarations. |
| `@types/ms` | 2.1.0 | Type the extension example. | Exclude that example. |
| `@types/proper-lockfile` | 4.1.4 | Type file-lock calls. | Maintain local declarations. |
| `@types/semver` | 7.7.1 | Type semantic-version calls. | Maintain local declarations. |
| `@vitest-evals/core` | 0.15.0 | Define evaluation cases. | Remove the evaluation package. |
| `autoevals` | 0.3.0 | Supply evaluation scoring helpers. | Maintain local scoring helpers. |
| `vitest-evals` | 0.15.0 | Run evaluations through Vitest. | Maintain a separate evaluation runner. |

## Workflow dependencies

| Dependency | Immutable revision | Purpose | Alternative |
|---|---|---|---|
| `actions/setup-node` | `49933ea5288caeca8642d1e84afbd3f7d6820020` | Install the required Node 22 runtime in CI. | Use an unverified runner Node installation. |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | Retain bounded preview and conflict reports. | Keep reports only in the transient job log. |

`actions/checkout` retains the adopted pin
`11d5960a326750d5838078e36cf38b85af677262`.
