# Drift

## Source lineage

Policy source: `abuzucom/agents` at `24f62e1c415313f1bc4bbd8cff30328ae6d69ae5`.
Pi import source: `abuzucom/pi` at `2bbfcca437c3aa5a21af1e4ee44ae7a051f953ad`.
Original pi upstream: `earendil-works/pi`.
`abuzucom/pi` retains fork-mirror lineage.
`abuzucom/pi-neapple-pizza` uses an independent mirror.
Substantial harness divergence requires a separate distribution.
Both revisions identify inspected local commits.
No claim identifies either revision as the latest hosted revision.

## Decisions

| ID | Choice | Reason | Status |
|---|---|---|---|
| D001 | Agents policy overrides conflicting pi instructions. | Preserve approved authorization. | Included in this adoption |
| D002 | Adopt every hook and script in one transaction. | Prevent partial gate activation. | Included in this adoption |
| D003 | Keep pi architecture as a reference before import. | Preserve adoption-only scope. | Included in this adoption |
| D004 | Use native Git hook launchers with pinned PyYAML. | Reuse the approved checker dependency. | Included in this adoption |
| D005 | Require independent containment across channels. | Treat agent code as untrusted. | Implemented through the strict kernel and external host contract |
| D006 | Preserve repeated security checks. | Detect changes between operations. | Implemented for every strict tool call and replay |
| D007 | Unify tool and kernel decision auditing. | Correlate containment evidence. | Implemented through the required host-owned audit sink |
| D008 | Omit source-only policy orientation. | Avoid source-repository assumptions. | Included in this adoption |
| D009 | Preserve canonical source text with LF conversion. | Satisfy the canonical encoding requirement. | Included in this adoption |
| D010 | Require checks outside agent-writable policy files. | Contain autonomous execution by construction. | Implemented as a strict startup requirement |
| D016 | Preserve independent pi history. | Avoid fork ancestry for substantial runtime divergence. | Implemented |
| D017 | Exclude donor policy and publishing automation. | Preserve the adopted policy authority and release boundary. | Implemented |
| D018 | Remove donor Husky setup. | Preserve adopted native hooks without rewrite behavior. | Implemented |
| D019 | Pin dependency ranges and sandbox runtime 0.0.77. | Make imported execution inputs reviewable. | Implemented |
| D020 | Keep `pi` and add `pi-secure`. | Preserve compatibility while adding strict startup. | Implemented |
| D021 | Block strict Windows startup without native validation. | Avoid unsupported enforcement claims. | Implemented |
| D022 | Publish the Pico3 runtime under `secure/runtime`. | Keep `pi-secure` inside the supported package graph. | Implemented |
| D023 | Isolate traced workers and clean-root shards. | Preserve bounded Windows traces and fixture assumptions. | Implemented |
| D024 | Check forge command scope before owner lookup. | Avoid Git configuration reads for unrelated commands. | Implemented |
| D025 | Parallelize immutable import generation. | Bound independent hashing and local reads without changing approval order. | Implemented |

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
Strict runtime claims apply only when `pi-secure` completes external host validation.
Compatibility entrypoints carry no strict containment claim.

## Pi import exclusions

The import excludes these donor surfaces:

- Root `AGENTS.md` and synchronized policy files.
- `.pi/` project content.
- `.husky/` hooks.
- Issue automation.
- Publishing workflows.
- Repository governance workflows.
- Donor lockfiles and shrinkwrap files.

The import adapts these donor surfaces:

- Root and package dependency ranges become exact pins.
- Root Husky and `prepare` entries disappear.
- Sandbox runtime references use version 0.0.77.
- Root configuration merges through the importer allowlist.
- Product source remains separate from local enforcement additions.
- Experimental Pico3 imports retain compatibility re-exports.
- Release locks regenerate from the approved exact dependency graph.

`docs/pi-import.json` records the complete imported path set.
Each record contains the donor blob identifier and SHA-256 digests.

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
Harness containment claims require passing native tests and external host validation.

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
