# Pull request security review

The adopted workflow calls the `abuzucom/foucault` reusable security review.
The pinned Foucault revision defines the review architecture and trust boundary.
This document describes the pi-neapple-pizza wiring.

## What runs

`.github/workflows/security-review-pr.yml` responds to completion of `Immutable Compliance`.
The workflow resolves the pull request from the completed run's head.
The reusable workflow loads pinned `AUDIT.md` and sends a bounded review envelope.
It posts a fenced report and publishes a `security-review` check.

The reusable workflow and `audit_ref` use the same Foucault revision:
`62851df1ef177593adbb9e06b223f5a6dce66fc0`.
The source identifies release 3.3.10.
Keep the policy and runner pins aligned.
Obtain dependency-specific approval before changing either pin.
Record approved changes in `CHANGELOG.md` and `DRIFT.md`.

The adoption includes the pinned adapter files:

- `ci/build_pr_case.py`
- `ci/run_model_command.py`
- `ci/call_model.py`
- `ci/model_providers.json`
- `scripts/check_pr_review_response.py`

The reusable workflow validates report structure with the caller's checker.
Retain that checker under `scripts/`.
Foucault supplies `AUDIT.md` at runtime.

The caller sets `fail_on_block: true`.
A `BLOCK` or `NEEDS-HUMAN` verdict fails the check.

A pull request from a fork receives an explicit skip result and no provider
secret.

The `workflow_run` trigger executes default-branch caller code.
Initial adoption cannot establish the caller before the adoption merge.
GitHub must complete `Immutable Compliance` for the relevant head.
Locate the subsequent review under the default branch in Actions.

## Required repository secret

An active human must configure the provider secret.
Never place the secret in source, documentation, or handoff files.

The active provider profile in `ci/model_providers.json` is Ollama with
`kimi-k2.7-code`. The caller maps `secrets.OLLAMA_API_KEY` to the reusable
workflow's `MODEL_API_KEY`.

Configure `OLLAMA_API_KEY` through repository Actions secrets.

An absent provider secret prevents a successful live review.
Report unavailable provider configuration separately from review findings.
Local policy tests do not establish live provider availability.

Obtain approval before changing the provider profile or review execution scope.
Keep the profile and caller secret mapping aligned.
Provider endpoints remain allowlisted in the adapter.

## Adoption provenance

`docs/agents-adoption.json` records the policy source and local artifact digests.
`DRIFT.md` records pi-specific choices.
Source-repository adopter records do not establish this repository's registration.
No local test establishes server-side branch protection or client trust.

## Review eligibility

Completed check runs never suppress the model review.
Verdict text cannot establish workflow provenance.
Each eligible completion can invoke another review for the same head.
Concurrency remains bounded by the existing per-head workflow group.
Read-only default tokens do not prevent workflows from requesting broader permissions.
Required-check spoofing requires independent workflow provenance controls.
