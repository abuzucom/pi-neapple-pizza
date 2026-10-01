"""Launch only registered gate entry points below the enclosing repository."""
import pathlib
import runpy
import sys

HOOK_NAMES = ('reinject_agents_policy.py', 'enforce_gate_adoption.py',
              'enforce_branch_name.py', 'native_client_gate.py')

try:
    if len(sys.argv) < 2:
        raise ValueError('hook argument is absent')
    hook_name = sys.argv[1]
    if hook_name not in HOOK_NAMES:
        raise ValueError('hook argument is unsupported')
    roots = (pathlib.Path.cwd(), *pathlib.Path.cwd().parents)
    root = next((path for path in roots if (path / '.git').exists()), None)
    if root is None:
        raise ValueError('repository root is absent')
    resolved_root = root.resolve()
    target = (resolved_root / 'hooks' / hook_name).resolve()
    if not target.is_relative_to(resolved_root):
        raise ValueError('hook target escapes the repository')
    if not target.is_file():
        raise ValueError('hook target is absent')
    sys.argv = [str(target), *sys.argv[2:]]
    runpy.run_path(str(target), run_name='__main__')
except Exception:
    sys.stderr.write('Hook launch failed; restore the complete verified gate set.\n')
    sys.exit(2)
