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
| D016 | Import the pi runtime directly from `earendil-works/pi` `v1.5.2`. | The `abuzucom/pi` mirror no longer exists. | Implemented |
| D017 | Keep local `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, and `SECURITY.md`. | Preserve the adopted policy authority. | Implemented |
| D018 | Exclude upstream `.github/`, `.husky/`, and `.pi/`. | Keep upstream release automation, Husky hooks, and auto-loaded pi resources out of this repository. | Implemented |
| D019 | Keep the BSD `LICENSE` and reproduce the upstream MIT notice in `LICENSES/pi-MIT.txt`. | Preserve the upstream copyright and permission notice. | Implemented |
| D020 | Merge upstream ignore and attribute rules. | Keep pi build output untracked and pi sources tracked. | Implemented |
| D021 | Retain upstream exact dependency pins and `package-lock.json` unchanged. | Upstream pins every direct dependency and records integrity for every locked package. | Implemented |
| D022 | Remove the upstream `prepare` script and the `husky` dev dependency. | Husky rewrites `core.hooksPath` and bypasses the native policy hooks. | Implemented |

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

The shared adoption and launcher checkers add native registration requirements.
The shared manifest retains every original entry.
Source provenance retains the immutable donor digests.
The local receipt records each deliberate source difference separately.
No change removes a gate, matcher, event, test assertion, or required security check.
The coupled client changes activate in one complete transaction.

## Pi runtime import

- D016 imports 4,250 upstream files with unchanged blobs and modes.
  Each package and app uses a dedicated snapshot commit.
- D020 anchors Python packaging and environment folders to the repository root.
  The unanchored patterns hid `packages/env` and other upstream sources.
  The merge omits the upstream `.claude/` entry.
  `.claude/settings.json` registers policy hooks.
- D020 retains CRLF for `*.bat`, `*.cmd`, and `*.ps1`.
  Windows command interpreters require CRLF in those scripts.
- D022 removes only the `husky` entries from `package-lock.json`.
  Every other lock entry keeps upstream bytes and the upstream `libc` fields.
- No runtime harness or containment claim applies to this import.

## Upstream convergence

- Remove the Dependabot changelog companion to match `abuzucom/agents`
  commit `ee08521`. `docs/agents-adoption.json` and `plan/ADOPTION.md`
  keep the original adoption inventory unchanged.
