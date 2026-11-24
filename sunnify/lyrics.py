"""Lyrics from LRCLIB (https://lrclib.net): free, open, no account or key.

Best-effort by design: a lookup that fails, times out, or finds nothing returns
None and the track is tagged without lyrics. Lyrics never fail a download.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests

from sunnify import __version__
from sunnify.logs import log

LRCLIB_GET = "https://lrclib.net/api/get"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
# LRCLIB asks clients to identify themselves so it can reach a misbehaving one
USER_AGENT = f"Sunnify/{__version__} (https://github.com/sunnypatell/sunnify-spotify-downloader)"
# a search hit further off than this is another cut of the song (video edit, live)
_DURATION_TOLERANCE_S = 5


@dataclass(frozen=True)
class Lyrics:
    plain: str = ""
    synced: str = ""  # LRC: "[mm:ss.xx] line" per line
    instrumental: bool = False

    @property
    def best(self) -> str:
        """Time-synced when available: players that understand LRC scroll it, others show text."""
        return self.synced or self.plain


def _primary_artist(artists: str) -> str:
    return re.split(r",|&|\s+(?:feat\.?|ft\.?)\s+", artists or "", maxsplit=1)[0].strip()


def _title_core(title: str) -> str:
    """'Song - Remastered 2011 (Live)' -> 'Song': Spotify's variant suffixes rarely match."""
    core = (title or "").split(" - ", 1)[0]
    core = re.sub(r"[\(\[].*?[\)\]]", " ", core)
    return re.sub(r"\s+", " ", core).strip()


def _from_record(record: dict) -> Lyrics | None:
    if not isinstance(record, dict):
        return None
    lyrics = Lyrics(
        plain=(record.get("plainLyrics") or "").strip(),
        synced=(record.get("syncedLyrics") or "").strip(),
        instrumental=bool(record.get("instrumental")),
    )
    return lyrics if (lyrics.best or lyrics.instrumental) else None


def fetch_lyrics(
    title: str,
    artists: str,
    album: str = "",
    duration_s: float = 0,
    *,
    session: requests.Session | None = None,
    timeout: float = 10,
) -> Lyrics | None:
    """Lyrics for a track, or None. Exact lookup first, then a duration-checked search."""
    artist = _primary_artist(artists)
    if not title or not artist:
        return None
    http = session or requests
    headers = {"User-Agent": USER_AGENT}

    params: dict[str, str | int] = {"track_name": title, "artist_name": artist}
    if album:
        params["album_name"] = album
    if duration_s:
        params["duration"] = round(duration_s)
    try:
        r = http.get(LRCLIB_GET, params=params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            found = _from_record(r.json())
            if found:
                return found
        elif r.status_code != 404:
            log.debug("lrclib get answered %s for %r", r.status_code, title)

        core = _title_core(title) or title
        r = http.get(
            LRCLIB_SEARCH,
            params={"track_name": core, "artist_name": artist},
            headers=headers,
            timeout=timeout,
        )
        if r.status_code != 200:
            log.debug("lrclib search answered %s for %r", r.status_code, core)
            return None
        results = r.json()
        for record in results if isinstance(results, list) else []:
            length = record.get("duration") if isinstance(record, dict) else None
            if (
                duration_s
                and isinstance(length, (int, float))
                and abs(length - duration_s) > _DURATION_TOLERANCE_S
            ):
                continue
            found = _from_record(record)
            if found:
                return found
    except (requests.RequestException, ValueError) as exc:
        log.debug("lrclib lookup failed for %r: %s", title, exc)
    return None


def write_lrc_sidecar(audio_path: str, lyrics: Lyrics) -> str | None:
    """Song.mp3 -> Song.lrc next to it, for players that only read sidecar files."""
    if not lyrics.synced:
        return None
    path = os.path.splitext(audio_path)[0] + ".lrc"
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(lyrics.synced + "\n")
    except OSError as exc:
        log.debug("could not write %s: %s", path, exc)
        return None
    return path
