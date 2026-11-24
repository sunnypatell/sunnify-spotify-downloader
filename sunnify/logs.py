"""Session logging and crash forensics: the only diagnostics a user can send us."""

from __future__ import annotations

import atexit
import contextlib
import faulthandler
import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler

from sunnify import __version__, tools

# Module logger. Stays a no-op (no handlers) until setup_logging() runs at
# startup, so importing this module in tests stays silent and writes nothing.
log = logging.getLogger("sunnify")


def _log_excepthook(exc_type, exc, tb):
    """Route uncaught main-thread exceptions to the log before the default handler."""
    # ctrl+c and an intentional sys.exit() are clean exits, not crashes
    if not issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        with contextlib.suppress(Exception):
            log.critical("uncaught exception", exc_info=(exc_type, exc, tb))
    if sys.stderr is not None:  # windowed builds have no stderr to write to
        sys.__excepthook__(exc_type, exc, tb)


def _thread_excepthook(args):
    """Same, for python threads; qt threads log inside their own run()."""
    if issubclass(args.exc_type, SystemExit):
        return
    with contextlib.suppress(Exception):
        log.critical(
            "uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )


def _install_crash_handlers() -> None:
    """Make every abnormal exit land in the log; logging is our only diagnostic."""
    sys.excepthook = _log_excepthook
    threading.excepthook = _thread_excepthook
    # faulthandler catches native crashes (qt/ffmpeg segfaults) excepthook can't;
    # crash.log sits next to sunnify.log and stays open for the process lifetime.
    with contextlib.suppress(Exception):
        crash_path = os.path.join(os.path.dirname(log_file_path()), "crash.log")
        faulthandler.enable(open(crash_path, "a"))  # noqa: SIM115
    atexit.register(lambda: log.info("==== sunnify session end ===="))


def _log_dir() -> str:
    """Return the per-user log directory path (does not create it).

    Pure path computation, no filesystem side effects, so callers that only
    need the string (e.g. a settings tooltip) don't create stray folders;
    setup_logging() and _open_logs() create the dir when they actually use it.

    Uses each platform's conventional spot for app logs (not config), so the
    files are where a user (or a support request) would expect them:
      windows -> %LOCALAPPDATA%\\Sunnify\\logs
      macOS   -> ~/Library/Logs/Sunnify
      linux   -> $XDG_STATE_HOME/sunnify/logs (defaults to ~/.local/state)
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "Sunnify", "logs")
    elif sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Sunnify")
    else:
        base = os.environ.get(
            "XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state")
        )
        path = os.path.join(base, "sunnify", "logs")
    return path


def log_file_path() -> str:
    """Absolute path of the current log file (used by the 'open logs' action)."""
    return os.path.join(_log_dir(), "sunnify.log")


class _SessionLogHandler(RotatingFileHandler):
    """The session log's handler; the marker lets setup_logging run exactly once."""

    _sunnify = True


def setup_logging() -> str:
    """Configure file logging once; return the log file path.

    Rotating handler caps disk use at ~6MB total (1MB x 5 backups) so logs are
    diagnostic, never bloat. Idempotent: safe to call more than once. The line
    format is deliberately dense (timestamp, level, function:line) so a single
    log pasted into an issue is enough to pinpoint where a download went wrong.
    A session header records the environment every launch.
    """
    if any(getattr(h, "_sunnify", False) for h in log.handlers):
        return log_file_path()

    path = log_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = _SessionLogHandler(
        path, maxBytes=1_000_000, backupCount=5, encoding="utf-8", delay=True
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # default INFO stays lean (scales with failures, not track count); set
    # SUNNIFY_DEBUG=1 to get the full per-track + yt-dlp trail for hard cases.
    level = logging.DEBUG if os.environ.get("SUNNIFY_DEBUG") else logging.INFO
    log.setLevel(level)
    log.addHandler(handler)
    log.propagate = False

    try:
        ytdlp_ver = __import__("yt_dlp").version.__version__
    except Exception:
        ytdlp_ver = "?"
    log.info("==== sunnify session start ====")
    log.info(
        "version=%s platform=%s python=%s yt-dlp=%s",
        __version__,
        f"{sys.platform}-{platform.machine()}",
        platform.python_version(),
        ytdlp_ver,
    )
    log.info("ffmpeg=%s", tools.get_ffmpeg_path() or "(not found)")
    log.info("logs=%s level=%s", path, logging.getLevelName(level))
    _install_crash_handlers()
    return path
