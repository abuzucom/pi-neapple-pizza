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
| D026 | Retain eval-container runtime root. | Preserve root-only evaluator sources and model-tool UID isolation. | Approved exception with future hardening review |
| D027 | Split imports across preparation, validation, and publication jobs. | Keep donor execution outside the write-token boundary. | Implemented |
| D028 | Bind apply publication to an immutable candidate bundle. | Detect base, patch, report, path, and approval changes before publication. | Implemented |
| D029 | Restrict OAuth discovery to exact configured origins. | Block credential URLs and unapproved metadata redirects or endpoints. | Implemented |
| D030 | Canonicalize filesystem and loader boundaries through real paths. | Reject symlink and junction escapes before host effects or module loading. | Implemented |
| D031 | Reject donor Python files under `scripts/` and bound Git blob reads. | Prevent module shadowing and memory exhaustion before content capture. | Implemented |
| D032 | Pin `brace-expansion` 5.0.12 through deterministic overrides. | Replace the vulnerable transitive resolution in every release lock. | Implemented |
| D033 | Run Linux build and security suites without secrets or write permissions. | Cover harness, OAuth, loader, eval, importer, and workflow boundaries. | Implemented |

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
- Root, coding-agent, and install-lock overrides retain `brace-expansion` 5.0.12.
- Donor Python files under `scripts/` stop the import as hard blockers.

## Import publication boundary

Preparation runs trusted base-branch importer code with read-only permissions.
Validation applies the immutable candidate without secrets or write permissions.
Publication receives write permissions through the protected environment.
Publication executes trusted base-branch Python code only.
Every checkout binds to the manual dispatch SHA and disables persisted credentials.
The candidate manifest binds the base SHA, donor SHA, approvals, and changed paths.
The candidate manifest records SHA-256 digests for each payload file.
Publication recomputes every digest before applying the binary patch.
The GitHub token enters only the trusted publication step.
Git push uses an ephemeral askpass helper without Git configuration changes.
Candidate validation rejects linked parent escapes and protected case variants.
Candidate validation rejects Python files under `scripts/` and unsafe entries.
Candidate validation enforces individual and aggregate file size limits.
Candidate patch capture stops before crossing its configured byte limit.
Workflow helpers route Git and GitHub calls through the explicit workspace.
Trusted GitHub workflow mode accepts exact read and draft creation shapes.
Publication requires the fixed repository origin and report body path.
Dependency installation remains report-only apply validation evidence.

OAuth discovery trusts the configured MCP server origin by default.
Explicit exact origins permit reviewed cross-origin discovery.
Manual redirect handling validates each destination and stops after three redirects.
Cached discovery metadata receives the same origin and endpoint validation.

Filesystem enforcement resolves relative destinations from the configured workspace.
Approved roots and existing destination parents receive realpath validation.
The broker receives the canonical destination.
Strict host loading rejects lexical and resolved workspace crossings.
Eval ownership traversal uses `lchownSync` and never follows model-created links.
Canonical argument encoding rejects cycles and excessive nesting.
Canonical argument encoding rejects non-JSON values and accessors.
Policy and approval freshness run again after intent persistence.

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

- D034 retains the generated Bedrock catalog as a tracked local runtime artifact.
  The imported provider module requires this JSON during offline builds.
  The catalog was hydrated on 2026-10-02 from configured model-data sources.
  SHA-256: `79c46943dee9438f321f5f5641d7a48805673bf5eb5d65dd4991f95753ef9d62`.
