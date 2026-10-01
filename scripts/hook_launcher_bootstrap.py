"""Authenticate the runtime before executing repository hook code."""
import hashlib
import json
import pathlib
import sys

HOOK_NAMES = ('reinject_agents_policy.py', 'enforce_gate_adoption.py',
              'enforce_branch_name.py', 'native_client_gate.py', 'require_consent.py',
              'enforce_git_identity.py', 'block_infrastructure_access.py',
              'block_destructive_bash.py', 'block_destructive_cmd.py', 'block_destructive_powershell.py')

try:
    if len(sys.argv) < 2 or sys.argv[1] not in HOOK_NAMES:
        raise ValueError('unsupported hook')
    root = next(path for path in (pathlib.Path.cwd(), *pathlib.Path.cwd().parents)
                if (path / '.git').exists()).resolve()
    path = root / 'scripts/runtime-integrity.json'
    if path.is_symlink():
        raise ValueError('linked manifest')
    with path.open('rb') as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576 or hashlib.sha256(raw).hexdigest() != APPROVED_DIGEST:
        raise ValueError('unapproved runtime')
    record = json.loads(raw)
    path = root / 'scripts/verified_hook_runtime.py'
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('escaped verifier')
    with path.open('rb') as stream:
        source = stream.read(65537)
    if len(source) > 65536 or hashlib.sha256(source).hexdigest() != record[path.relative_to(root).as_posix()]:
        raise ValueError('unapproved verifier')
    namespace = {'__name__': 'verified_hook_runtime', '__file__': str(path)}
    exec(compile(source, str(path), 'exec'), namespace)
    namespace['launch_verified'](root, record, sys.argv[1:])
except Exception:
    if len(sys.argv) > 1 and sys.argv[1] in HOOK_NAMES:
        print(json.dumps({'decision': 'deny', 'reason': 'Hook runtime verification failed'}))
    sys.stderr.write('Hook launch failed; restore the complete verified gate set.\n')
    sys.exit(2)
