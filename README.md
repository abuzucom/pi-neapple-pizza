# pi-neapple-pizza

Adopted agent policy for the independent pi-neapple-pizza distribution.

Canonical policy comes from `abuzucom/agents`.
The policy governs planning, code, tests, documentation, commits, and pull requests.
It overrides conflicting upstream pi agent guidance.

The repository currently contains policy, hooks, scripts, tests, and client registrations.
Pi runtime import and harness implementation require a later plan after adoption merge.

## Documentation

- [Canonical policy](AGENTS.md)
- [Project orientation](docs/project-orientation.md)
- [Pi architecture reference](docs/pi-architecture.md)
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
The future harness remains planned.

## Runtime prerequisites

Require Python 3.12 or newer for bundle activation and native Git hooks.
Retain junction rejection on Windows.
The regression suite also requires Node.js for workflow JavaScript execution.
Native client adapters inspect observable shell and file tools.
Consult `docs/gate-threat-model.md` for consent and hosted-tool limitations.

## Windows hook launchers

Configured hook launchers must execute real gates from a subdirectory.
`scripts/check_hook_launchers.py` verifies Claude, Codex, Gemini, and Antigravity.
Native launchers preserve fixed source bytes through quote-retaining argument parsing.
`scripts/hook_launcher_bootstrap.py` retains the readable bootstrap source.
Every gate, event, matcher, and authorization check remains active.
