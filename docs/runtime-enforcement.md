# Runtime enforcement

The legacy harness and Pico3 harness accept an optional enforcement kernel.
Compatibility mode omits the kernel and preserves upstream behavior.
Strict mode requires a compiled approved policy and a host-owned audit sink.
Strict mode also requires a host-owned effect broker.

## Decision path

The harness performs these steps for every tool call:

1. Persist durable harness intent.
2. Resolve a fresh approval grant from the host when configured.
3. Validate the policy revision and expiration.
4. Validate the tool name and effect classification.
5. Validate the method and destination.
6. Validate process argument shape and executable policy.
7. Enforce request, rate, concurrency, and queue bounds.
8. Persist approval consumption and execution intent atomically.
9. Execute pure work locally or route external work to the host broker.
10. Enforce the result byte bound.
11. Persist completion evidence.

Recovery re-enters the same decision path.
Authorization and freshness checks run again.
The kernel caches only immutable compiled policy tables.

## Effect boundary

Strict tools declare one effect descriptor.
Missing descriptors receive an `unclassified_tool` denial.
Process effects require an argument-vector declaration.
Shell command strings receive a `shell_string_denied` denial.
Filesystem, process, network, hosted service, extension, and MCP effects reach the host broker.
Pure effects can execute inside the harness after admission.

The broker revalidates mutable security state immediately before execution.
The broker owns credentials and isolated workers.
The broker must keep grants outside unauthorized worker boundaries.
The broker must return bounded structured results.

## Audit boundary

Strict startup requires an audit sink.
The sink records denials and permitted calls.
The sink atomically consumes an approval with the matching intent record.
Audit receipts contain a SHA-256 record digest and a host-generated MAC.
Audit persistence failure blocks execution.

## Strict entrypoint

`pi-secure` uses the Pico3 coding-agent path.
Set `PI_SECURE_POLICY` to an absolute policy file outside the target workspace.
Set `PI_SECURE_HOST_MODULE` to an absolute module file outside the target workspace.
The module default export supplies these fields:

- `audit`
- `host`
- optional `approvals`
- `sandboxRuntimeVersion` with exact value `0.0.77`
- `validatedPlatforms` containing the current Node platform

Windows also requires `PI_SECURE_WINDOWS_SETUP_VALIDATED=1`.
Set the variable only after the one-time elevated sandbox setup passes native validation.
Repository code makes no Windows containment claim without that evidence.

## Policy shape

The approved policy includes a canonical SHA-256 digest.
The policy defines exact tools and methods.
The policy defines path roots and endpoint origins.
The policy defines approved executables.
The policy defines approval requirements.
The policy defines request, result, rate, worker, and queue bounds.

Policy expiration blocks every strict call.
Digest mismatch blocks strict startup.
