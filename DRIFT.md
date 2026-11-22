# Drift

## Source lineage

Policy source: `abuzucom/agents` at `24f62e1c415313f1bc4bbd8cff30328ae6d69ae5`.
Pi reference: `abuzucom/pi` at `e4c75a73222ae2c72abb5f5314fa35ee8effc508`.
The `abuzucom/pi` repository no longer exists.
Pi runtime source: `earendil-works/pi` tag `v1.5.2` at `b4afdddf44e059c67ccf5097e5317d913521b470`.
`abuzucom/pi-neapple-pizza` uses an independent mirror without fork ancestry.
Substantial harness divergence requires a separate distribution.
Each revision identifies an inspected local commit.
No claim identifies the policy revision as the latest hosted revision.

## Decisions

| ID | Choice | Reason | Status |
|---|---|---|---|
| D001 | Agents policy overrides conflicting pi instructions. | Preserve approved authorization. | Included in this adoption |
| D002 | Adopt every hook and script in one transaction. | Prevent partial gate activation. | Included in this adoption |
| D003 | Keep pi architecture as a reference before import. | Preserve adoption-only scope. | Included in this adoption |
| D004 | Use native Git hook launchers with pinned PyYAML. | Reuse the approved checker dependency. | Included in this adoption |
| D005 | Require independent containment across channels. | Treat agent code as untrusted. | Planned |
| D006 | Preserve repeated security checks. | Detect changes between operations. | Planned for the harness |
| D007 | Unify tool and kernel decision auditing. | Correlate containment evidence. | Planned |
| D008 | Omit source-only policy orientation. | Avoid source-repository assumptions. | Included in this adoption |
| D009 | Preserve canonical source text with LF conversion. | Satisfy the canonical encoding requirement. | Included in this adoption |
| D010 | Require checks outside agent-writable policy files. | Contain autonomous execution by construction. | Planned |
| D026 | Import the pi runtime directly from `earendil-works/pi` `v1.5.2`. | The `abuzucom/pi` mirror no longer exists. | Implemented |
| D027 | Keep local `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, and `SECURITY.md`. | Preserve the adopted policy authority. | Implemented |
| D018 | Exclude upstream `.github/`, `.husky/`, and `.pi/`. | Keep upstream release automation, Husky hooks, and auto-loaded pi resources out of this repository. | Implemented |
| D019 | Keep the BSD `LICENSE` and reproduce the upstream MIT notice in `LICENSES/pi-MIT.txt`. | Preserve the upstream copyright and permission notice. | Implemented |
| D020 | Merge upstream ignore and attribute rules. | Keep pi build output untracked and pi sources tracked. | Implemented |
| D021 | Retain upstream exact dependency pins and `package-lock.json` unchanged. | Upstream pins every direct dependency and records integrity for every locked package. | Implemented |
| D022 | Remove the upstream `prepare` script and the `husky` dev dependency. | Husky rewrites `core.hooksPath` and bypasses the native policy hooks. | Implemented |
| D023 | Limit the Kubernetes values file name match to YAML extensions. | The name-only match protected source files such as `values.ts` and denied broad searches in the imported pi runtime. | Implemented |
| D024 | Exclude `apps/p2/test/p2/fetch.test.ts` from the import. | The file embeds a literal private key for a throwaway localhost certificate. Rule 8 forbids committing private key material. | Implemented |
| D025 | Retain runtime root in the eval and voice server containers. | The evaluator keeps root-only judge sources and isolates model tools by UID. The voice server writes model caches under `/models`. | Approved exception with future hardening review |
| D030 | Route pi tool calls through the canonical Python gates. | One classifier and one decision source serve every client. | Implemented |
| D031 | Load the pi adapter by path instead of adopting a `.pi` directory. | The upstream `.pi` resources stay out of this repository under D018. | Implemented |
| D032 | Adopt the condensed portable policy as `docs/portable-policy.md`. | A constrained client needs a policy that fits a small context budget. | Implemented |
| D033 | Keep the portable policy outside the assembled policy bundle. | The bundle carries every canonical rule and sits 2 bytes under its size cap. | Implemented |

## Planned harness boundaries

Treat the agent as capable, persistent untrusted code.
Apply containment across shell execution, tool calls, and network requests.
Cover code analysis, builds, security testing, data processing, and reports.

Escape threats include exfiltration, public disclosure, lateral movement,
host compromise, credential theft, destructive action, and resource abuse.
Prompt injection, model behavior, and harness defects can initiate these acts.

Allow only named tools and methods.
Validate parameters before using values or authorizing destinations.
Bound endpoints, request rates, payloads, results, worker concurrency, and queues.
Persist approval consumption and execution intent before execution.
Record tool denials and sensitive permitted calls with kernel decisions.
Use a tamper-evident audit trail outside agent control.
Return safe denial reasons to support compliant alternatives.

Repeated authorization, authentication, integrity, and freshness checks remain required.
Performance changes require evidence that every security check remains effective.
No cache may replace a required check against mutable security state.
No runtime implementation or containment claim applies to this adoption.

## Policy scope

Retain canonical gate decisions, imports, registrations, and test specifications.
Adapt the prose checker's two source-adopter document paths to the pi documents.
Match those paths in the synchronization workflow.
Keep every analyzer and failure condition active.
Apply three equivalent prose corrections in `AGENTS.md`.
Preserve the scope rule, protected path inventory, and client coverage limitation.
Tailor security-review documentation to this repository's adoption state.
Require LF for text files in `.gitattributes`.
Retain automatic binary detection and the canonical policy-file attributes.
Tailor project orientation, contribution examples, security examples, and handoff examples.
Retain upstream test specifications.
Existing task restrictions prohibit infrastructure access during adoption.
Do not invoke the source Cloudflare deployment exception for this task.

## Verification

Record activation, tests, launchers, integrity, and hosted checks separately.
Local files do not establish client trust or GitHub branch protection.
No harness containment claim applies before runtime implementation and native tests.

## Update review

Compare future source revisions against the recorded baseline.
Record each deliberate difference and verification result.
Classify incoming changes as adopt, adapt, reject, or defer.
Do not relax a gate to resolve an adoption block.

## Security remediation differences

- D011 removes check-run verdict deduplication from the review caller.
  Untrusted check writers cannot suppress the real model review through verdict text.
  Required-check provenance remains a separate GitHub control.
- D012 adds native adapters under every non-Claude pre-tool registration.
  The adapters invoke unchanged canonical shell, infrastructure, and consent gates.
  The adapters call canonical identity inspection for effective Git contexts.
  Native consent-required operations deny without a supported authorization path.
- D013 anchors native launchers to the enclosing Git root.
  Fixed launcher code uses a bounded ancestor list and separate hook arguments.
  Missing roots, missing scripts, and launch exceptions exit 2.
  Launcher checks exercise the exact registered commands from subdirectories.
- D014 requires Python 3.12 before activation path access.
  The installer retains Windows junction checks.
- D015 retains the original activation journal during remediation.
  A separate backup generation records current originals before publication.
- D028 runs every native launcher as `python -I -c`.
  Isolated mode drops the working directory and user site from `sys.path`.
  A planted `pathlib.py` or `json.py` cannot replace the launcher logic.
  `scripts/check_native_hook_launchers.py` rejects launchers without `-I`.
- D029 makes the native adapter deny tools it cannot inspect.
  Gemini `read_many_files` checks each `paths` and `include` entry as a read.
  Calls with more than 64 entries deny before any gate runs.
  Antigravity `view_file_outline` checks its path as a read.
  A fixed allowlist passes plan, todo, web search, and web fetch tools.
  MCP tools and new native tools deny until an adapter mapping exists.

The shared adoption and launcher checkers add native registration requirements.
The shared manifest retains every original entry.
Source provenance retains the immutable donor digests.
The local receipt records each deliberate source difference separately.
No change removes a gate, matcher, event, test assertion, or required security check.
The coupled client changes activate in one complete transaction.
- D016 adopts the `abuzucom/agents` `1835087` gate-integrity checker and workflow.
  A person must add the approval label after the latest head push.
  Path matching ignores case.
  A missing base checker requires the label and never runs head code.
  The workflow adds pinned `actions/github-script` v7.1.0 for timeline reads.
- D017 extends the protected path list with pi enforcement code.
  The list adds `tools/git_policy_hook.py`, `tools/git-hooks/`,
  `tools/adopt_agents_bundle.py`, `tools/bundle_transaction.py`, and
  `scripts/check_native_hook_launchers.py`.
  `tests/test_gate_pr_integrity_pi_paths.py` covers each added path.
  `shared-files.json` records the pi checker digest.
  The checker stays in the shared set to detect unrecorded edits.

## Pi runtime import

- D026 imports 4,250 upstream files with unchanged blobs and modes.
  Each package and app uses a dedicated snapshot commit.
- D020 anchors Python packaging and environment folders to the repository root.
  The unanchored patterns hid `packages/env` and other upstream sources.
  The merge omits the upstream `.claude/` entry.
  `.claude/settings.json` registers policy hooks.
- D020 retains CRLF for `*.bat`, `*.cmd`, and `*.ps1`.
  Windows command interpreters require CRLF in those scripts.
- D022 removes only the `husky` entries from `package-lock.json`.
  Every other lock entry keeps upstream bytes and the upstream `libc` fields.
- D023 narrows the Kubernetes values file name match to YAML extensions.
  The upstream `abuzucom/agents` change carries the same fix.
  The upstream pull request is draft PR 147.
- D024 excludes one upstream test file.
  The file embeds a literal private key.
  Rule 8 forbids committing private key material.
  The upstream file stays available in `earendil-works/pi`.
- D025 keeps runtime root in two upstream containers.
  The Rule 12 exception comment records the reason in each Dockerfile.
  The eval container preserves root-only evaluator sources and isolates model
  tools by UID.
  The voice server writes model caches under `/models`.
  The upstream `abuzucom/agents` policy allows an approved exception with future
  hardening review.
  A later hardening pass must run both containers as a non-root user.
- No runtime harness or containment claim applies to this import.

## Pi policy adapter

- D030 adds `hooks/pi_client_gate.py`.
  The adapter maps one pi tool call onto the canonical gate scripts.
  It runs `enforce_branch_name.py` for every call.
  It runs `enforce_git_identity.py` for every shell call.
  It runs `scripts/check_gate_adoption.py` before the other gates.
  A pi tool with no canonical inspection path denies.
- D030 adds `integrations/pi/agents-gate.ts`.
  The pi extension asks the adapter before every pi tool call.
  A denied call never reaches the operating system.
- D031 keeps the extension out of a `.pi` directory.
  The operator loads it with `pi -e integrations/pi/agents-gate.ts`.
- The adapter denies every act that a canonical gate would put to a human.
  The registered native clients deny those acts for the same reason.
- The pi gate shard runs alone with the resource timeout.
  Every decision spawns the canonical gates as separate processes.
- The adapter gates tool calls only.
  It does not bound the network, the process tree, or the filesystem.
  No harness containment claim applies to this adapter.

## Portable policy

- D032 adds `docs/portable-policy.md`.
  The document reproduces `abuzucom/portableops` `PORTABLE-5000.md` byte for byte.
  The upstream blob is `0ca740584bf023a337d55c714a2fe231ec5dd2ad` at 4,556 bytes.
  The copy carries 18 rules.
  The canonical policy in this repository carries 19 and adds the pi gate path.
  The portable copy omits the gate on state-changing GitHub CLI calls.
- D033 keeps the document outside the assembled bundle.
  The bundle carries every canonical rule and sits 2 bytes under its size cap.
  A constrained client selects the portable copy instead of the bundle.
- The prose checkers do not run on the portable copy.
  The document reproduces upstream text. The upstream text uses an enumeration
  style and a personal pronoun that the local style rules reject.
  The upstream license notice receives the same treatment.

## Upstream convergence

- Remove the Dependabot changelog companion to match `abuzucom/agents`
  commit `ee08521`. `docs/agents-adoption.json` and `plan/ADOPTION.md`
  keep the original adoption inventory unchanged.
