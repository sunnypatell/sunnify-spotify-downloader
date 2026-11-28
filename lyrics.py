"""Lyrics lookup for downloaded tracks, backed by LRCLIB (https://lrclib.net).

LRCLIB is open and needs no API key. Only the unsynchronised text is used:
that is the text every tag format can carry (ID3 USLT, MP4 ©lyr, Vorbis
LYRICS). Artist and title leave the machine, which is why the lookup is an
opt-in setting and never runs by default.

The matching rules keep a wrong song's lyrics out of a file: the title must
equal the wanted one after loose normalisation, and the artist must equal it
or start with the same words. Without a usable match nothing is written.
"""

from __future__ import annotations

import logging
import re
import unicodedata

import requests

log = logging.getLogger("sunnify")

LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "Sunnify (https://github.com/sunnypatell/sunnify-spotify-downloader)"
REQUEST_TIMEOUT_S = 15

# Trailing bracketed additions that do not change the song. Others such as
# "(Part 2)" or "(Cover)" name a different piece and are kept.
_HARMLESS_WORDS = (
    "live",
    "remaster",
    "version",
    "edit",
    "mix",
    "mono",
    "stereo",
    "acoustic",
    "demo",
    "radio",
    "single",
    "album",
    "feat",
    "featuring",
    "ft",
)
_TRAILING_BRACKET = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")

SCORE_EXACT_ARTIST = 2
SCORE_PREFIX_ARTIST = 1


def _fold(text: str) -> str:
    """Lowercase and strip accents."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _is_harmless(group: str) -> bool:
    words = [w for w in re.split(r"[^a-z]+", _fold(group)) if w]
    return any(w.startswith(h) for w in words for h in _HARMLESS_WORDS)


def normalize(value: str) -> str:
    """Compare-friendly form: no case, accents, punctuation or harmless trailing brackets."""
    text = value or ""
    while True:
        match = _TRAILING_BRACKET.search(text)
        if match is None or not _is_harmless(match.group()):
            break
        text = text[: match.start()]
    kept = "".join(ch if ch.isalnum() or ch == " " else " " for ch in _fold(text))
    return " ".join(kept.split())


def same_title(left: str, right: str) -> bool:
    a, b = normalize(left), normalize(right)
    return bool(a) and a == b


def artist_score(wanted: str, found: str) -> int:
    """2 for an exact match, 1 when one name starts with the other word by word, else 0."""
    w, f = normalize(wanted), normalize(found)
    if not w or not f:
        return 0
    if w == f:
        return SCORE_EXACT_ARTIST
    w_words, f_words = w.split(), f.split()
    shared = min(len(w_words), len(f_words))
    return SCORE_PREFIX_ARTIST if w_words[:shared] == f_words[:shared] else 0


def _clean(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def best_match(entries: object, title: str, artist: str) -> str | None:
    """Lyrics text of the best LRCLIB entry for this song, or None.

    Entries come straight from the service, so anything that is not the
    expected shape is skipped rather than trusted. On equal artist scores
    the service's own ordering wins.
    """
    if not isinstance(entries, list):
        return None
    best_text, best_score = None, 0
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("instrumental") is True:
            continue
        plain = entry.get("plainLyrics")
        text = _clean(plain) if isinstance(plain, str) else ""
        found_title = entry.get("trackName") or entry.get("name") or ""
        found_artist = entry.get("artistName") or ""
        if not text or not isinstance(found_title, str) or not same_title(found_title, title):
            continue
        score = artist_score(artist, found_artist if isinstance(found_artist, str) else "")
        if score > best_score:
            best_text, best_score = text, score
    return best_text


def fetch_lyrics(title: str, artist: str, session: requests.Session | None = None) -> str | None:
    """Plain-text lyrics for a song, or None when none are found or the lookup fails.

    Never raises on network or service trouble: lyrics are an extra, and a
    failed lookup must not cost the user the tags or the download.
    """
    title, artist = (title or "").strip(), (artist or "").strip()
    # Without an artist, common titles like "Intro" would pull in other songs' lyrics.
    if not title or not artist:
        return None
    # Spotify joins several artists with commas; LRCLIB indexes the lead artist.
    lead_artist = artist.split(",")[0].strip()
    getter = session.get if session is not None else requests.get
    try:
        response = getter(
            LRCLIB_SEARCH_URL,
            params={"track_name": title, "artist_name": lead_artist},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_S,
        )
        if response.status_code != 200:
            log.debug("lyrics service answered %s for '%s'", response.status_code, title)
            return None
        return best_match(response.json(), title, lead_artist)
    except (requests.RequestException, ValueError) as exc:
        log.debug("lyrics lookup failed for '%s': %s", title, exc)
        return None
