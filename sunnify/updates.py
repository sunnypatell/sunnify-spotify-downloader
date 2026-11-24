"""Background check for a newer GitHub release; never blocks or breaks launch."""

from __future__ import annotations

from urllib.parse import urlsplit

import requests
from PyQt6.QtCore import QThread

from sunnify.logs import log
from sunnify.qt import Signal

GITHUB_REPO = "sunnypatell/sunnify-spotify-downloader"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"


def _parse_version(s: str) -> tuple:
    """'v2.0.13' / '2.0.13' / '2.0.13-beta' -> (2, 0, 13). Stops at the first non-int part."""
    parts = []
    for chunk in (s or "").strip().lstrip("vV").split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            break
        parts.append(int(num))
    return tuple(parts)


def _is_newer_version(latest: str, current: str) -> bool:
    """True if latest is a strictly newer release than current (numeric, not lexical)."""
    lv, cv = _parse_version(latest), _parse_version(current)
    return bool(lv) and lv > cv


def _release_url(candidate) -> str:
    """The release page to open: GitHub's own https link, else our releases page.

    The toast hands this to the OS browser, so whatever the API response says
    must not be able to point it at another site or a local file."""
    if isinstance(candidate, str):
        parts = urlsplit(candidate)
        if parts.scheme == "https" and parts.netloc == "github.com":
            return candidate
    return _RELEASES_PAGE


def _check_for_update(current: str, timeout: int = 5):
    """Return (latest_version, release_url) if a newer release exists, else None.

    Fail-silent (returns None) on any network/parse error so launch is never
    blocked or crashed by the check.
    """
    try:
        r = requests.get(
            _LATEST_RELEASE_API,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code != 200:
            log.debug("update check: github api returned %s", r.status_code)
            return None
        data = r.json()
        tag = data.get("tag_name") or ""
        url = _release_url(data.get("html_url"))
        if _is_newer_version(tag, current):
            return (tag.lstrip("vV"), url)
        log.debug("update check: on latest (%s, newest %s)", current, tag or "?")
        return None
    except Exception as exc:  # network/parse must never disrupt launch
        log.debug("update check skipped: %s", exc)
        return None


class UpdateCheckThread(QThread):
    """Runs _check_for_update off the UI thread and signals if a release is newer."""

    update_available = Signal(str, str)  # (latest_version, release_url)

    def __init__(self, current_version: str):
        super().__init__()
        self._current = current_version

    def run(self):
        result = _check_for_update(self._current)
        if result:
            self.update_available.emit(result[0], result[1])
