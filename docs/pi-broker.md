# Pi policy broker

The pi client reaches the canonical gates through the broker in
`broker/pi_broker.py`. The broker runs outside the repository and holds three
things that a repository cannot hold safely.

## The pin

The pin records the digest of every gate file in the decision path and the
digest of the broker itself. The decision path holds the files under
`hooks/`, the broker, and the pi extension. The broker compares the recorded
digests and the recorded file set with the files on disk before every
decision. A gate that changed after the pin was written loses the decision
until a person pins the change again. A gate that the pin does not record
loses the decision as well.

The shared manifest holds the digest of every file that must stay identical
across the repositories that adopt these gates. The broker compares the files
on disk with that manifest as well.

An operator records the pin after an approved change to the decision path:

```text
python broker/pi_broker.py pin
```

The state directory holds the pin, the audit log, and the approvals. It
lives outside the repository. The tools that reach the repository cannot
reach the state directory. The broker creates the directory with
owner-only permissions, because the directory holds the approval tokens.
The operating system boundary that keeps an agent out of the state directory
belongs to the sandbox work and is not in place yet.

## The audit log

Every decision appends one line to `decisions.jsonl` in the state directory.
The line carries the request digest, the tool, the decision, the reason, and
the digest of the line before it. A record that was changed, removed, or
reordered breaks the chain, and the broker reports the break when it reads
the log.

The log records the ask that carried a question to the operator and the
decision that followed the approval. The approval token stays out of the log,
so the log never holds a secret.

The broker verifies the chain before every decision. A record that was
changed, removed, or reordered breaks the chain, and a log that lost its first
lines breaks it as well. A broken chain loses the decision.

## The approvals

A gate that needs an answer from the active human returns an ask. The broker
carries the ask to the client with the canonical consent text. The client
asks the operator, and the operator answers through the client interface,
which the agent cannot reach. The client then asks the broker to record an
approval for that request. The approval binds the digest of the request, and
the broker consumes it once.

An approval for one request never covers another. The broker matches the
token and the request digest together.

An agent with shell access can call the broker directly, so an approval
recorded outside the client is not proof of a human answer. The broker
records the approval and the decision either way, and the audit log shows
both. The operating system boundary that makes an approval unforgeable
belongs to the sandbox work.

## Commands

| Command | Effect |
|---|---|
| `pin` | Record the current digests of the decision path. |
| `decide` | Read one request on standard input and answer it. |
| `approve` | Read one request on standard input and record an approval for it. |
| `status` | Report the pin, the approvals, and the log. |

A request names the tool, the arguments, and the session directory. A request
without a tool is a session start.

```text
echo '{"tool":"bash","arguments":{"command":"echo hello"},"cwd":"/path"}' \
  | python broker/pi_broker.py decide
```

The answer names the decision, the reason, the canonical consent text when
the decision is an ask, and the digest of the request record.

## Decisions

| ID | Decision | Status |
|---|---|---|
| D005 | Require independent containment across channels | Implemented |
| D007 | Unify tool and kernel decision auditing | Implemented |
| D010 | Require checks outside agent-writable policy files | Implemented |

D006 lands with the broker. The broker repeats the pin check, the shared
manifest check, and the canonical gate run before every decision, so a change
between two calls loses the next decision.

The operating system boundary remains planned. An approval recorded outside
the client interface is not proof of a human answer until the boundary lands.
