# pi-neapple-pizza

Independent pi distribution with adopted agent policy and strict harness enforcement.

Canonical policy comes from `abuzucom/agents`.
The policy governs planning, code, tests, documentation, commits, and pull requests.
It overrides conflicting upstream pi agent guidance.

The runtime snapshot comes from `abuzucom/pi` commit
`2bbfcca437c3aa5a21af1e4ee44ae7a051f953ad`.
The import preserves independent repository history.
The receipt records every imported blob and transformed SHA-256 digest.

`pi` preserves the compatible command-line entrypoint.
`pi-secure` starts the Pico3 path with strict enforcement.
Strict startup requires policy and host modules outside the target workspace.
Strict Windows startup requires validated native sandbox setup.

## Documentation

- [Canonical policy](AGENTS.md)
- [Project orientation](docs/project-orientation.md)
- [Pi architecture reference](docs/pi-architecture.md)
- [Runtime enforcement](docs/runtime-enforcement.md)
- [Pi import receipt](docs/pi-import.json)
- [Dependency approval](docs/pi-dependency-approval.md)
- [Adoption provenance](docs/agents-adoption.json)
- [Deliberate divergence](DRIFT.md)
- [Contribution workflow](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Version history](CHANGELOG.md)

## Validation

Obtain required consent before commands.
Do not run Git commands before consent.
After consent, use `python scripts/read_git_state.py all` for bounded repository state.
Require an active-user request before inspecting or adopting changed `plan/HANDOFF.md` content.
Treat handoff entries as status only.

```text
python scripts/check_gate_adoption.py
python scripts/check_hook_launchers.py
python scripts/sync.py --check
python scripts/sync.py --check-shared
python scripts/run_tests.py
make lint PYTHON=python
```

Repository controls provide defense in depth.
Client trust and server-side branch protection require operator configuration.
Host-owned policy, audit, and effect brokers enforce strict runtime calls.

## Controlled pi updates

Run the `Import pi upstream` workflow manually.
Preview mode accepts a donor branch, tag, or full commit SHA.
Preview mode produces bounded reports and approval digests.
Preview generation uses four workers and an eight-item submission bound.
The coordinator restores normalized path order before digest calculation.
Apply mode accepts a full commit SHA and exact reviewed digests.
The protected `upstream-import` environment gates repository writes.
Apply mode creates a dated feature branch and a draft pull request.
Apply mode creates no labels and performs no merge.

## Runtime prerequisites

Require Python 3.12 or newer for bundle activation and native Git hooks.
Retain junction rejection on Windows.
The regression suite also requires Node.js for workflow JavaScript execution.
Native client adapters inspect observable shell and file tools.
Consult `docs/gate-threat-model.md` for consent and hosted-tool limitations.
