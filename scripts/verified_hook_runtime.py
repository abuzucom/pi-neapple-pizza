"""Hold the activation lock across runtime verification and hook execution."""
import hashlib
import os
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_COUNT = 1024


def lock_windows_reader(stream) -> tuple:
    """Acquire a shared Windows byte-range lock compatible with the writer lock."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class Overlapped(ctypes.Structure):
        """Describe the synchronous byte-range offset used by LockFileEx."""
        _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                    ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                    ("hEvent", wintypes.HANDLE)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    acquire = kernel.LockFileEx
    acquire.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                        wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    acquire.restype = wintypes.BOOL
    release = kernel.UnlockFileEx
    release.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                        wintypes.DWORD, ctypes.POINTER(Overlapped)]
    release.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(stream.fileno())
    offset = Overlapped()
    if not acquire(handle, 1, 0, 1, 0, ctypes.byref(offset)):
        raise ctypes.WinError(ctypes.get_last_error())
    return release, handle, offset


def checked_path(root: Path, relative: str) -> Path:
    """Reject links and noncanonical paths before opening runtime artifacts."""
    if not isinstance(relative, str) or any(value in relative for value in ("\\", ":", "\0")):
        raise ValueError("invalid runtime path")
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("invalid runtime path")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink() or target.is_junction():
            raise ValueError("linked runtime artifact")
    if not target.resolve().is_relative_to(root):
        raise ValueError("runtime artifact escapes the approved root")
    return target


@contextmanager
def runtime_lock(root: Path):
    """Serialize runtime readers with complete bundle publication."""
    path = checked_path(root, ".gate-staging/activation.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            release, handle, offset = lock_windows_reader(stream)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                import ctypes
                if not release(handle, 0, 1, 0, ctypes.byref(offset)):
                    raise ctypes.WinError(ctypes.get_last_error())


def verify_runtime(root: Path, record: dict) -> None:
    """Verify every runtime input under the same activation lock."""
    if not isinstance(record, dict) or not 0 < len(record) <= MAX_ARTIFACT_COUNT:
        raise ValueError("invalid runtime inventory")
    for relative, expected in record.items():
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("invalid runtime digest")
        path = checked_path(root, relative)
        if not path.is_file():
            raise ValueError("runtime artifact is absent")
        with path.open("rb") as stream:
            raw = stream.read(MAX_ARTIFACT_BYTES + 1)
        if len(raw) > MAX_ARTIFACT_BYTES or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("runtime artifact differs from the approved generation")


def launch_verified(root: Path, record: dict, arguments: list[str]) -> None:
    """Execute one approved hook without exposing a mixed runtime generation."""
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required")
    with runtime_lock(root):
        verify_runtime(root, record)
        relative = "hooks/" + arguments[0]
        if relative not in record:
            raise ValueError("hook is absent from the approved runtime")
        target = checked_path(root, relative)
        sys.argv = [str(target), *arguments[1:]]
        runpy.run_path(str(target), run_name="__main__")
