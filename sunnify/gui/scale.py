"""Whole-window scaling (#122) and the relaunch a new size needs."""

from __future__ import annotations

import os
import sys

from sunnify.config import SUPPORTED_UI_SCALES
from sunnify.logs import log

# the frameless card is a fixed composition; this is its size in logical pixels
WINDOW_W, WINDOW_H = 750, 500

_UI_SCALE_ENV = "QT_SCALE_FACTOR"
_ui_scale_env_is_ours = False


def apply_ui_scale(scale: str) -> None:
    """Size the whole window, fonts included, from the saved setting.

    Qt reads QT_SCALE_FACTOR once, before QApplication exists, and multiplies
    it onto the system's scaling, so a change needs a relaunch. A value already
    in the environment wins, which is Qt's own convention.
    ref: https://doc.qt.io/qt-6/highdpi.html#environment-variable-reference
    """
    global _ui_scale_env_is_ours
    if os.environ.get(_UI_SCALE_ENV):
        log.info("ui scale: %s=%s from the environment", _UI_SCALE_ENV, os.environ[_UI_SCALE_ENV])
        return
    if scale not in SUPPORTED_UI_SCALES or scale == "100":
        return
    os.environ[_UI_SCALE_ENV] = f"{int(scale) / 100:g}"
    _ui_scale_env_is_ours = True
    log.info("ui scale: %s%%", scale)


def _current_ui_factor() -> float:
    """The factor this process runs at, 1 when none is set."""
    try:
        return float(os.environ.get(_UI_SCALE_ENV) or 1) or 1.0
    except ValueError:
        return 1.0


def _relaunch_command() -> tuple[str, list[str]]:
    """This same app, started again: the frozen binary, or python on the script."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    return sys.executable, [os.path.abspath(sys.argv[0])]


def relaunch_app() -> bool:
    """Start a fresh, detached instance of the app; the caller quits this one."""
    from PyQt6.QtCore import QProcess, QProcessEnvironment

    program, args = _relaunch_command()
    proc = QProcess()
    proc.setProgram(program)
    proc.setArguments(args)
    proc.setWorkingDirectory(os.getcwd())
    env = QProcessEnvironment.systemEnvironment()
    # the factor this process set for itself must not pin the next one to it
    if _ui_scale_env_is_ours:
        env.remove(_UI_SCALE_ENV)
    if getattr(sys, "frozen", False):
        # a onefile build spawned from itself is a worker sharing the parent's unpacked
        # files, which the parent deletes on exit; this makes it a fresh instance instead
        # ref: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
        env.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")
        # the bootloader put its unpack dir first on the library path; hand back the original
        for key in ("LD_LIBRARY_PATH", "LIBPATH"):
            if env.contains(f"{key}_ORIG"):
                env.insert(key, env.value(f"{key}_ORIG"))
            else:
                env.remove(key)
    proc.setProcessEnvironment(env)
    ok, _pid = proc.startDetached()
    if not ok:
        log.warning("relaunch failed: %s %s", program, args)
    return ok
