"""One writer per playlist folder, across every desktop window and terminal."""

from __future__ import annotations

import contextlib
import os
import sys
import time

LOCK_FILENAME = ".sunnify.lock"


class FolderLockedError(RuntimeError):
    """Another live sunnify process is writing to this folder."""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_file_pid(path: str) -> int | None:
    with contextlib.suppress(OSError, ValueError), open(path, encoding="utf-8") as fh:
        return int(fh.read().strip())
    return None


def read_lock_pid(folder: str) -> int | None:
    """Pid of the live process holding folder's lock, or None."""
    pid = _lock_file_pid(os.path.join(folder, LOCK_FILENAME))
    return pid if pid is not None and _pid_alive(pid) else None


# a lock with no pid yet is a process mid-claim, not a stale lock, until it's this old
_LOCK_CLAIM_GRACE_S = 5


@contextlib.contextmanager
def folder_lock(folder: str):
    """Hold folder for this process; a lock left by a dead process is claimed."""
    path = os.path.join(folder, LOCK_FILENAME)
    for _ in range(2):
        try:
            # O_EXCL makes the claim atomic, so two processes starting together can't both win
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            holder = _lock_file_pid(path)
            if holder is not None and holder != os.getpid() and _pid_alive(holder):
                raise FolderLockedError(
                    f"another Sunnify download (pid {holder}) is already writing to {folder}; "
                    f"if none is running, delete {LOCK_FILENAME} there"
                ) from None
            if holder is None:
                with contextlib.suppress(OSError):
                    if time.time() - os.path.getmtime(path) < _LOCK_CLAIM_GRACE_S:
                        raise FolderLockedError(
                            f"another Sunnify download is already writing to {folder}"
                        ) from None
            with contextlib.suppress(OSError):
                os.remove(path)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        break
    else:
        raise FolderLockedError(f"another Sunnify download is already writing to {folder}")
    try:
        yield
    finally:
        if read_lock_pid(folder) == os.getpid():
            with contextlib.suppress(OSError):
                os.remove(path)
