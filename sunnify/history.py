"""Past downloads, newest first, in history.json next to config.json.

Shared by the desktop app and the CLI. Best-effort like the config: a missing
or corrupt file reads as an empty history, and a failed write is logged, never
raised, because history must never be the reason a download reports failure.
"""

from __future__ import annotations

import json
import os
import threading
import time

from sunnify import config
from sunnify.logs import log

HISTORY_FILENAME = "history.json"
MAX_ENTRIES = 200
STATUSES = ("done", "partial", "failed", "stopped")

_lock = threading.Lock()


def history_path() -> str:
    return os.path.join(config._config_dir(), HISTORY_FILENAME)


def _number(value, kind):
    """kind(value) for a finite, non-negative number; 0 for anything else a hand-edit left."""
    if isinstance(value, bool):
        return kind(0)
    try:
        number = kind(float(value))
    except (TypeError, ValueError, OverflowError):
        return kind(0)
    return number if 0 <= number < float("inf") else kind(0)


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _clean(entry) -> dict | None:
    """A well-formed entry, or None; a corrupt file must never break the History view."""
    if not isinstance(entry, dict) or not _text(entry.get("url")):
        return None
    status = entry.get("status")
    return {
        "url": entry["url"],
        "kind": _text(entry.get("kind")),
        "name": _text(entry.get("name")),
        "folder": _text(entry.get("folder")),
        "started_at": _number(entry.get("started_at"), float),
        "finished_at": _number(entry.get("finished_at"), float),
        "landed": _number(entry.get("landed"), int),
        "failed": _number(entry.get("failed"), int),
        "status": status if status in STATUSES else "done",
    }


def load() -> list[dict]:
    """Every recorded download, newest first."""
    try:
        with open(history_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return [e for e in map(_clean, entries or []) if e]


def status_for(*, landed: int, failed: int, stopped: bool) -> str:
    if stopped:
        return "stopped"
    if failed and not landed:
        return "failed"
    return "partial" if failed else "done"


def record(
    *,
    url: str,
    kind: str = "",
    name: str = "",
    folder: str = "",
    started_at: float | None = None,
    landed: int = 0,
    failed: int = 0,
    stopped: bool = False,
) -> dict | None:
    """Add one finished run to the top of the history; returns the stored entry."""
    entry = _clean(
        {
            "url": url,
            "kind": kind,
            "name": name,
            "folder": folder,
            "started_at": started_at or time.time(),
            "finished_at": time.time(),
            "landed": landed,
            "failed": failed,
            "status": status_for(landed=landed, failed=failed, stopped=stopped),
        }
    )
    if entry is None:
        return None
    with _lock:
        entries = [entry, *load()]
        try:
            config.write_json_atomic(
                history_path(), {"version": 1, "entries": entries[:MAX_ENTRIES]}
            )
        except OSError as exc:
            log.warning("could not save history: %s", exc)
            return None
    return entry


def clear() -> None:
    with _lock:
        try:
            os.remove(history_path())
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("could not clear history: %s", exc)
