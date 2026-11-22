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
