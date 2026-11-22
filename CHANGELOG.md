# Changelog

## [0.3.2] (2026-11-20)

### Added

- Add `docs/portable-policy.md`.
  The document reproduces the `abuzucom/portableops` condensed policy byte
  for byte at blob `0ca740584bf023a337d55c714a2fe231ec5dd2ad`.
  A constrained client selects the copy instead of the assembled policy.

## [0.3.1] (2026-11-20)

### Changed

- Record the pi adapter decisions as D030 and D031.
  The runtime import records D016 through D025.
  The native launcher pull request records D028 and D029.

## [0.3.0] (2026-11-20)

### Added

- Add `hooks/pi_client_gate.py`.
  The adapter maps one pi tool call onto the unchanged canonical gate scripts
  and reports the canonical decision.
  Every call runs the branch gate, the adoption checker, and the gates for
  the tool.
  Every shell call runs the identity gate.
  A pi tool with no canonical inspection path denies.
- Add `integrations/pi/agents-gate.ts`.
  The pi extension asks the adapter before every pi tool call and blocks a
  denied call.
  The extension loads by path. The repository adopts no `.pi` directory.
- Add `docs/pi-policy.md`.
  The document records the gate mapping, the session behavior, and the
  coverage limits.
- Add `tests/test_pi_client_gate.py` and `integrations/pi/agents-gate.test.ts`.
  Both suites run the canonical gates for real.

### Changed

- Register the `pi` client in `hooks/enforce_branch_name.py`.
  The branch gate now accepts the pi client label and denies an ask the way
  the native clients deny it.
- Register the pi gate shard as a resource-heavy shard in
  `scripts/check_hook_coverage.py`.
  The shard spawns the canonical gates for every decision and runs alone with
  the resource timeout.
- Record the pi adapter limits in `hook-coverage-baseline.json` and
  `docs/gate-threat-model.md`.
- Extend the lint file list with `docs/pi-policy.md`.
- Extend the TypeScript and Biome file sets with the integration directory.

## [0.2.23] (2026-11-20)

### Fixed

- State in `CONTRIBUTING.md` that the pi runtime is present.
  The file still said the runtime had not entered this repository.

## [0.2.22] (2026-11-20)

### Fixed

- Merge main into the native launcher branch.
  The gate approval pull request landed after this branch started.
- Restore the 0.1.2 CHANGELOG section.
  The gate approval entry had absorbed it.

## [0.2.21] (2026-11-20)

### Security

- Run native hook launchers with `python -I` to ignore planted modules.
- Check every Gemini `read_many_files` path and include entry, up to 64.
- Deny native tool calls the gate cannot inspect.

## [0.2.19] (2026-11-19)

### Fixed

- Exclude `apps/p2/test/p2/fetch.test.ts` from the import.
  The file embeds a literal private key for a throwaway localhost certificate.
  Rule 8 forbids committing private key material.
- Record the Rule 12 exception for the eval and voice server containers.
  Both containers keep runtime root.
  The exception comment names the reason in each Dockerfile.

## [0.2.18] (2026-11-19)

### Fixed

- Limit the Kubernetes values file name match in `hooks/_gate_core.py` to YAML
  extensions. The gate protected any file whose name starts with `values-` or
  `values.`. A source file named `values.ts` carries no Kubernetes
  configuration, and its name reached the protected set. That denied broad
  searches in repositories holding such a file.
- Add `tests/test_infrastructure_values_scope.py`. The test covers the
  protected YAML names and the unprotected source names.

## [0.2.17] (2026-11-19)

### Documentation

- Describe the imported `earendil-works/pi` `v1.5.2` packages and apps in `docs/pi-architecture.md`.

## [0.2.16] (2026-11-19)

### Security

- Remove the upstream `prepare` script and the `husky` dev dependency.
  Husky rewrites `core.hooksPath` during dependency installation.
  The rewrite bypasses the native policy hooks.

## [0.2.15] (2026-11-19)

### Added

- Reproduce the upstream pi MIT notice in `LICENSES/pi-MIT.txt`.
  Reference the notice from `LICENSE`.
- Merge the upstream pi ignore and attribute rules.

### Fixed

- Anchor Python packaging and environment ignore patterns to the repository root.
  The unanchored patterns hid `packages/env` and other pi sources.

### Documentation

- Record `earendil-works/pi` `v1.5.2` as the pi runtime source in `DRIFT.md` and `README.md`.

## [0.2.14] (2026-11-19)

### Added

- Import the pi v1.5.2 `apps/p3` snapshot from `earendil-works/pi`.

## [0.2.13] (2026-11-19)

### Added

- Import the pi v1.5.2 `apps/p2` snapshot from `earendil-works/pi`.

## [0.2.12] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/tui` snapshot from `earendil-works/pi`.

## [0.2.11] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/telemetry` snapshot from `earendil-works/pi`.

## [0.2.10] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/schema` snapshot from `earendil-works/pi`.

## [0.2.9] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/mcp` snapshot from `earendil-works/pi`.

## [0.2.8] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/evals` snapshot from `earendil-works/pi`.

## [0.2.7] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/env` snapshot from `earendil-works/pi`.

## [0.2.6] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/durable` snapshot from `earendil-works/pi`.

## [0.2.5] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/coding-agent` snapshot from `earendil-works/pi`.

## [0.2.4] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/codemode` snapshot from `earendil-works/pi`.

## [0.2.3] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/chord` snapshot from `earendil-works/pi`.

## [0.2.2] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/ai` snapshot from `earendil-works/pi`.

## [0.2.1] (2026-11-19)

### Added

- Import the pi v1.5.2 `packages/agent` snapshot from `earendil-works/pi`.

## [0.2.0] (2026-11-19)

### Added

- Import the pi v1.5.2 root build configuration and scripts from `earendil-works/pi`.

## [0.1.3] (2026-10-14)

### Security

- Require a person to add the gate approval label after the latest push.
- Match protected gate paths without regard to case.
- Require the approval label when the base lacks the integrity checker.
- Protect imported scripts, policy files, and pi enforcement tools.

## [0.1.2] (2026-10-14)

### Removed

- Remove the Dependabot changelog companion workflow, script, and test.
  Upstream `abuzucom/agents` removed the same files in `ee08521`. The workflow token
  cannot read the `/user` endpoint that `scripts/trusted_gh.py` checks.
  Dependabot pull requests need manual changelog entries.

## [0.1.1] (2026-09-30)

### Security

- Remove spoofable check-run review suppression.
- Enforce canonical gates through native client payload adapters.
- Anchor registered hook launchers and verify subdirectory execution.
- Reject unsupported Python runtimes before activation access.
- Retain activation backups across independent transaction generations.
- Document client consent and hosted-tool coverage limits.

## [0.1.0] (2026-09-30)

### Added

- Adopt the complete agents policy, hooks, scripts, tests, and client registrations.
- Add native Git hook launchers and full-bundle activation verification.
- Add pi architecture references and tailored contributor examples.
- Record source provenance and deliberate divergence.

### Security

- Preserve canonical authorization gates and immutable dependency pins.
- Keep runtime harness containment pending post-merge planning.
