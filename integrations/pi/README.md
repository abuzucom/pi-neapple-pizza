# pi policy adapter

`agents-gate.ts` is a pi extension. It routes every pi tool call through the
canonical policy gates in `hooks/pi_client_gate.py`.

The repository does not adopt a `.pi` directory. Load the extension by path.

```text
pi -e integrations/pi/agents-gate.ts
```

Set `PI_POLICY_PYTHON` when the Python interpreter is not named `python` on the
path.

See `docs/pi-policy.md` for the gate mapping and the coverage limits.
