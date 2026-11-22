# Changelog

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
