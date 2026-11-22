# Pi policy integration

The adopted policy gates the tool calls of Claude, Codex, Gemini, and
Antigravity. pi runs in this repository as an agent client, and no client
registration covers it.

`hooks/pi_client_gate.py` maps one pi tool call onto the canonical gate
scripts and reports the canonical decision.
`integrations/pi/agents-gate.ts` asks the adapter before every pi tool call
and blocks a denied call.

## Load the extension

The repository does not adopt a `.pi` directory. Load the extension by path.

```text
pi -e integrations/pi/agents-gate.ts
```

Set `PI_POLICY_PYTHON` when the interpreter is not named `python` on the path.

## Gate mapping

The pi client reaches the canonical gates through the broker in
`broker/pi_broker.py`.
The broker pins the decision path, records every decision outside the
repository, and consumes one approval per act.
See `docs/pi-broker.md` for the broker.

| pi tool | Canonical tool | Canonical gates |
|---|---|---|
| `bash` | `Bash` | `block_destructive_bash.py` |
| `powershell` | `PowerShell` | `block_destructive_powershell.py` |
| `read` | `Read` | `block_infrastructure_access.py` |
| `find` | `Glob` | `block_infrastructure_access.py` |
| `grep` | `Grep` | `block_infrastructure_access.py` |
| `ls` | `Glob` | `block_infrastructure_access.py` |
| `write` | `Write` | `block_infrastructure_access.py`, `require_consent.py` |
| `edit` | `Edit` | `block_infrastructure_access.py`, `require_consent.py` |

Every call runs `enforce_branch_name.py` before the gates in the table.
Every shell call runs `enforce_git_identity.py` as well.
Every call runs `scripts/check_gate_adoption.py` before the other gates.

A pi tool with no entry in the table has no canonical inspection path.
The adapter denies it.

The adapter rewrites the pi arguments into the canonical spelling before a
gate reads the request.
A pi `path` becomes the canonical `file_path`.
A pi `newText` becomes the canonical `new_string`.

## Session start

The session start runs `enforce_branch_name.py` and `enforce_git_identity.py`
with the `SessionStart` event.

A failed branch preflight denies the session.
The canonical recovery instruction travels with the decision.
The identity advisory travels as a warning.

## Coverage limits

- The adapter denies every act that a canonical gate would put to a human.
  The registered native clients deny those acts for the same reason.
- A tool registered by another extension has no inspection path.
  The adapter denies it until the mapping names it.
- The adapter runs the canonical gates as separate processes.
  A repository writer can change the adapter and the gates.
  Tamper resistance requires controls outside the repository.
- pi loads `AGENTS.md` as project context.
  The adapter reinjects no policy at compaction or subagent start.
  A compaction event therefore carries no policy reinjection.
- The adapter gates tool calls only.
  It does not bound the network, the process tree, or the filesystem.
