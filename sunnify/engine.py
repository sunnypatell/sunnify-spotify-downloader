"""The download engine shared by the desktop app and the headless CLI."""

from __future__ import annotations

import concurrent.futures
import contextlib
import os
import re
import tempfile
import threading

import requests
from PyQt6.QtCore import QThread
from yt_dlp import YoutubeDL

from spotifydown_api import (
    ContentUnavailableError,
    ExtractionError,
    NetworkError,
    PlaylistClient,
    PlaylistInfo,
    RateLimitError,
    SpotifyDownAPIError,
    cap_filename,
    detect_spotify_url_type,
    sanitize_filename,
)
from sunnify import tools
from sunnify.config import SUPPORTED_FORMATS, SUPPORTED_QUALITIES, SUPPORTED_SAMPLE_RATES
from sunnify.i18n import t
from sunnify.locking import folder_lock
from sunnify.logs import log
from sunnify.qt import Signal

# Resume manifest: JSON-lines file per playlist folder recording landed tracks,
# so a rate-limited playlist finishes across sessions instead of restarting (#40).
MANIFEST_FILENAME = ".sunnify-manifest.jsonl"


class _YtdlpLog:
    """Bridge yt-dlp's own output into our log and remember the last error.

    With ignoreerrors=True a failed download won't raise, so capturing error()
    here is the only way to record *why* no audio file landed (bot-block vs
    unavailable vs format vs nsig). Routine yt-dlp chatter goes to our DEBUG so
    the default INFO log stays lean.
    """

    def __init__(self):
        self.last_error = None

    def debug(self, msg):
        log.debug("yt-dlp: %s", msg)

    info = debug

    def warning(self, msg):
        log.debug("yt-dlp warning: %s", msg)

    def error(self, msg):
        self.last_error = msg
        log.debug("yt-dlp error: %s", msg)


# Clients for the retry attempt, as a set rather than a preference list:
# android/ios expose streams the default path may not, and tv/web_safari
# supply an alternative URL when those return 403. The combination is what
# recovers a track - measured per client, each alone fails on videos the
# set handles, and yt-dlp's own defaults 403 on some of them too. Kept
# deliberately, not by inertia; validated below so a retired client can't
# rot into a hard failure, and exercised end to end by the youtube_retry
# check in scripts/check_api_status.py.
_RETRY_CLIENTS = ("android", "ios", "tv", "web_safari")


def _retry_player_clients() -> tuple[str, ...]:
    """_RETRY_CLIENTS filtered to the clients yt-dlp still ships.

    YouTube retires client names and yt-dlp follows; naming a dead one is a
    hard extractor error, so unknown names are dropped with a warning that
    says which. Everything dropping out means the retry falls back to
    yt-dlp's maintained defaults, which is degraded but never broken.
    """
    try:
        from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
    except Exception:
        # table moved: our names are still the best guess we have
        log.debug("yt-dlp client table not introspectable; using retry clients unvalidated")
        return _RETRY_CLIENTS
    live = tuple(name for name in _RETRY_CLIENTS if name in INNERTUBE_CLIENTS)
    retired = [name for name in _RETRY_CLIENTS if name not in INNERTUBE_CLIENTS]
    if retired:
        log.warning("retry clients no longer shipped by yt-dlp, dropped: %s", retired)
    if not live:
        log.warning("no retry clients survive; retry now uses yt-dlp's defaults")
    return live


class MusicScraper(QThread):
    PlaylistCompleted = Signal(str)
    PlaylistID = Signal(str)
    song_Album = Signal(str)
    song_meta = Signal(dict)
    add_song_meta = Signal(dict)
    count_updated = Signal(int)
    dlprogress_signal = Signal(int)
    Resetprogress_signal = Signal(int)
    resume_skipped = Signal(int)  # manifest-resumed tracks never reach song_meta
    error_signal = Signal(str)  # Signal for error messages to UI

    # Max concurrent track downloads. 4 is the measured sweet spot:
    # linear speedup through 4, diminishing returns past 6 (CPU-bound ffmpeg).
    MAX_WORKERS = 4

    def __init__(
        self,
        cancel_event: threading.Event | None = None,
        *,
        audio_format: str = "mp3",
        audio_quality: str = "192",
        include_track_number: bool = False,
        artist_first: bool = False,
        title_only: bool = False,
        sample_rate: str = "auto",
        loose_match: bool = False,
        cookies_file: str | None = None,
        lyrics: bool = False,
    ):
        super().__init__()
        self.counter = 0  # Initialize counter to zero
        self.session = requests.Session()
        self.spotifydown_api: PlaylistClient | None = None
        self._cancel_event = cancel_event or threading.Event()
        self._failed_tracks: list[str] = []  # Track failed downloads
        # Output options. audio_format must be a key of SUPPORTED_FORMATS;
        # audio_quality only applies to lossy formats (mp3/m4a/opus).
        self.audio_format = audio_format if audio_format in SUPPORTED_FORMATS else "mp3"
        self.audio_quality = audio_quality if audio_quality in SUPPORTED_QUALITIES else "192"
        self.include_track_number = bool(include_track_number)
        self.artist_first = bool(artist_first)
        self.title_only = bool(title_only)
        self.sample_rate = sample_rate if sample_rate in SUPPORTED_SAMPLE_RATES else "auto"
        # opt-in: when strict title/artist matching fails, fall back to the
        # duration-closest youtube result (recovers cross-script matches);
        # off by default so the wrong-audio safeguard (#52) stays the default.
        self.loose_match = bool(loose_match)
        # opt-in: the tag writer looks lyrics up on LRCLIB (sunnify.lyrics)
        self.lyrics = bool(lyrics)
        # where the last run wrote and what it was called, for history + "open folder"
        self.output_folder: str | None = None
        self.display_name = ""
        self.cookies_file = os.path.expanduser(cookies_file) if cookies_file else None
        self._cookies_text = None
        self._js_runtime = None
        if self.cookies_file:
            # read once here, on the caller's thread: loading redirects stderr
            try:
                self._cookies_text = tools._cookies_text(self.cookies_file)
                self._js_runtime = tools.find_js_runtime()
                log.info("youtube cookies: on, js runtime: %s", self._js_runtime)
            except Exception as exc:
                log.error("youtube cookies unreadable, running without them: %s", exc)
                self.cookies_file = None
        self._counter_lock = threading.Lock()
        self._failed_lock = threading.Lock()
        self._filename_lock = threading.Lock()
        self._manifest_lock = threading.Lock()
        self._manifest_path: str | None = None
        self._manifest_owners: dict[str, str] = {}
        # youtube blocks per-IP, so it hits every track at once; say it once
        # rather than 300 times, and say what it actually means
        self._network_blocked = False
        self._in_flight_files: set[str] = set()
        # Set to True during parallel playlist downloads so workers can suppress
        # per-track UI noise (label flicker, thumbnail spam, progress bar jitter)
        # that only makes sense for a single active download.
        self._parallel_mode = False
        self._total_tracks = 0

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_event.is_set()

    @contextlib.contextmanager
    def _youtube(self, opts: dict):
        """YoutubeDL for one request, with the user's cookies when set."""
        if not self.cookies_file:
            # no js runtime: anonymous requests keep yt-dlp's js-less client set
            with YoutubeDL({**opts, "js_runtimes": {}}) as ydl:
                yield ydl
            return
        # yt-dlp rewrites its cookie file on close and workers run in parallel,
        # so each request gets a private copy and the user's file is only read
        fd, copy = tempfile.mkstemp(prefix="sunnify-cookies-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(self._cookies_text or "")
            name, path = self._js_runtime or ("deno", None)
            runtimes = {name: {"path": path}} if path else {name: {}}
            with YoutubeDL({**opts, "cookiefile": copy, "js_runtimes": runtimes}) as ydl:
                yield ydl
        finally:
            with contextlib.suppress(OSError):
                os.remove(copy)

    _BLOCK_MARKERS = ("sign in to confirm", "not a bot", "confirm you're not a bot")

    def _note_if_network_blocked(self, reason: str) -> None:
        """Emit one plain-language notice the first time YouTube gates us.

        The gate is applied to the whole network, so without this every track
        fails with its own generic message and the real cause never surfaces.
        """
        text = (reason or "").lower()
        if not any(m in text for m in self._BLOCK_MARKERS):
            return
        with self._failed_lock:
            if self._network_blocked:
                return
            self._network_blocked = True
        if self.cookies_file:
            log.error("youtube is gating this network even with cookies; they are likely stale")
            self.error_signal.emit(t("engine.cookies_stale"))
            return
        log.error("youtube is gating this network (bot check); downloads cannot proceed")
        self.error_signal.emit(t("engine.network_blocked"))

    def _get_user_friendly_error(self, error: Exception, track_title: str = "") -> str:
        """Convert exception to user-friendly error message."""
        if isinstance(error, RateLimitError):
            return t("engine.spotify_rate_limited")
        if isinstance(error, NetworkError):
            return t("engine.network_error")
        if isinstance(error, ContentUnavailableError):
            return str(error)
        if isinstance(error, ExtractionError):
            return t("engine.cannot_access", title=track_title)
        if any(m in str(error).lower() for m in self._BLOCK_MARKERS):
            return t("engine.youtube_blocked_track", title=track_title)
        if "HTTP Error 429" in str(error):
            return t("engine.youtube_rate_limited")
        error_text = str(error).lower()
        if (
            "no video formats" in error_text
            or "no playable audio source" in error_text
            or "unavailable" in error_text
        ):
            return t("engine.not_on_youtube", title=track_title)
        return t("engine.error", detail=str(error)[:50])

    def ensure_spotifydown_api(self):
        if self.spotifydown_api is None:
            self.spotifydown_api = PlaylistClient(session=self.session)
        return self.spotifydown_api

    def sanitize_text(self, text):
        """Sanitize text for filename usage."""
        return sanitize_filename(text, allow_spaces=True)

    def _compose_filename(self, sanitized_title, sanitized_artists, track_num=None, disambig=None):
        """Filename from the naming settings (#77, #91). Parts arrive
        sanitized, so composition can't change path safety. disambig is a
        track id appended when two tracks resolve to the same name."""
        if self.title_only:
            # a title that sanitizes to nothing falls back rather than yield ".mp3"
            stem = sanitized_title or sanitized_artists or "track"
        elif self.artist_first:
            stem = f"{sanitized_artists} - {sanitized_title}"
        else:
            stem = f"{sanitized_title} - {sanitized_artists}"
        if disambig:
            stem = f"{stem} [{disambig}]"
        fmt = self.audio_format if self.audio_format in SUPPORTED_FORMATS else "mp3"
        ext = SUPPORTED_FORMATS[fmt]["ext"]
        if self.include_track_number and track_num is not None:
            return f"{track_num:02d}. {stem}.{ext}"
        return f"{stem}.{ext}"

    def format_playlist_name(self, metadata: PlaylistInfo):
        owner = metadata.owner or "Spotify"
        return f"{metadata.name} - {owner}".strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        os.makedirs(base_folder, exist_ok=True)
        # Same cross-platform sanitizer as track files (windows reserved
        # chars/device names, posix rules - see sanitize_filename's doc refs).
        safe_name = sanitize_filename(playlist_name)
        if not safe_name or safe_name == "Unknown":
            safe_name = "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        # If the ascii-allowlist-era folder name ("Name  Owner") exists, keep
        # using it so re-runs resume there instead of orphaning the manifest (#40).
        legacy_name = "".join(
            ch for ch in playlist_name if ch.isalnum() or ch in (" ", "_")
        ).strip()
        legacy_folder = os.path.join(base_folder, legacy_name)
        if legacy_name and legacy_name != safe_name and os.path.isdir(legacy_folder):
            playlist_folder = legacy_folder
        try:
            os.makedirs(playlist_folder, exist_ok=True)
        except OSError:
            log.error("could not create playlist folder %r", playlist_folder, exc_info=True)
            raise
        return playlist_folder

    @staticmethod
    def _widen_search(search_query: str) -> str:
        """Search several YouTube results instead of only the top hit.

        A track's #1 result can be region-locked or removed; `ytsearch1`
        fails the whole download in that case (closes #42). Widening to
        `ytsearch5` lets yt-dlp skip unavailable results and download the
        first one that actually plays.
        """
        if search_query.startswith("ytsearch1:"):
            return "ytsearch5:" + search_query[len("ytsearch1:") :]
        return search_query

    @staticmethod
    def _simplify_search(search_query: str) -> str:
        """Strip parenthetical/bracketed qualifiers for a looser fallback.

        Hyper-specific titles (classical works like `(Wiegenlied, Op. 49,
        No. 4)`, tone tracks like `(528 Hz)`) can return zero YouTube
        matches. Dropping the qualifiers widens the net on a second attempt.
        Returns the original query unchanged if there is nothing to strip.
        """
        _, sep, terms = search_query.partition(":")
        if not sep:
            terms = search_query
        stripped = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", terms)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if not stripped or stripped == terms.strip():
            return search_query
        return f"ytsearch5:{stripped}"

    # Max spotify-vs-youtube length gap to count as the same recording; the
    # top hit is often the music video or an extended cut.
    _DURATION_TOLERANCE_S = 7

    # Wider bound for the title+duration combined check: right title but >30s
    # off means remix/live/extended - fail loudly rather than ship it.
    _DURATION_TOLERANCE_S_WIDE = 30

    @staticmethod
    def _normalize_title(s: str | None) -> str:
        """Lowercase, strip diacritics, drop bracketed segments + `feat./ft.`
        tails, collapse to word characters + spaces (any script). Used on
        BOTH sides of title comparison.

        Critically: this does NOT split on ` - ` because YouTube titles
        commonly use the `Artist - Song` convention; splitting would turn
        "The Weeknd - Blinding Lights" into just "The Weeknd" and lose the
        song name. Spotify-side variant stripping (`Title - Remastered`)
        is handled separately in `_spotify_title_core`.
        """
        if not s:
            return ""
        import unicodedata

        # NFKD + drop combining marks: "Café" -> "Cafe"
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
        s = s.lower()
        s = re.sub(r"\([^)]*\)", " ", s)  # "Hello (Remix)" -> "Hello "
        s = re.sub(r"\[[^\]]*\]", " ", s)  # "Hello [Edit]" -> "Hello "
        s = re.sub(r"\b(feat\.?|ft\.?)\s+.*$", "", s, flags=re.IGNORECASE)
        # Strip apostrophes BEFORE the general punctuation->space step so
        # "I'm" becomes "im" not "i m".
        s = s.replace("'", "").replace("\u2019", "")  # straight and curly
        # Keep letters/digits/marks from ANY script (#77). Category M is
        # load-bearing: indic/thai vowel signs are combining-class-0 marks,
        # and dropping them collapses distinct words ("दिल"/"दाल").
        s = "".join(
            ch if (ch.isspace() or unicodedata.category(ch)[0] in "LNM") else " " for ch in s
        )
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _spotify_title_core(s: str | None) -> str:
        """Drop the ` - Variant` suffix Spotify adds to differentiate releases.

        Examples:
            "Bohemian Rhapsody - Remastered 2011" -> "Bohemian Rhapsody"
            "Hello - Live"                        -> "Hello"
            "Sweet Disposition - Remix Edit"      -> "Sweet Disposition"
            "Take-Off"                            -> "Take-Off" (literal hyphen, no spaces)
            "Mi Gente"                            -> "Mi Gente"

        Only applied to the Spotify-side title before fuzzy comparison so
        a YouTube upload titled just "Bohemian Rhapsody" still matches.
        Don't apply this to YouTube titles - they use ` - ` for
        `Artist - Song` and the strip would lose the song name.
        """
        if not s:
            return ""
        return s.split(" - ", 1)[0]

    @classmethod
    def _title_plausibly_matches(cls, yt_title: str | None, expected_title: str | None) -> bool:
        """True when the YouTube candidate's title could reasonably be the
        Spotify track. The Spotify side gets its variant suffix dropped
        first so "Hello - Live" matches a plain "Hello" upload; the YouTube
        side is normalized as-is (its ` - ` is usually `Artist - Song`).
        Substring match for titles >= 4 chars, word-boundary match for
        shorter ones (so a single-letter song name like "i" doesn't match
        every YouTube video)."""
        yt = cls._normalize_title(yt_title)
        target = cls._normalize_title(cls._spotify_title_core(expected_title))
        if not target or not yt:
            return False
        if len(target) >= 4:
            return target in yt
        return target in yt.split()

    def _select_youtube_match(
        self, search_query, expected_duration_s, expected_title=None, expected_artists=None
    ):
        """Return the best YouTube watch URL for a search, or None.

        Selection policy (closes #52):
          1. Filter to candidates whose title plausibly matches the Spotify
             track title (substring / word match on a normalized form).
             Rules out the failure mode where YouTube's top hit is a
             DIFFERENT track by the SAME artist with a similar duration -
             e.g. searching "Mi Gente DJ Goja audio" returns "Dj Goja -
             Mi Chico" at the top, only ~2s off the real Mi Gente, and the
             prior pure-duration matcher would happily pick it and write
             Mi Gente metadata onto Mi Chico audio.
          2. Require an artist plausibly appearing in the YouTube title too,
             and return None if none does. Artists written only in non-latin
             script skip this gate, since YouTube usually romanizes them.
          3. Among the resulting pool, pick the duration-closest if duration
             is known, but reject the whole result if even the best
             candidate's duration is >30s off the Spotify track - that means
             the closest title-matching upload is a remix / live cover /
             extended edit, and shipping a 5-minute remix under a 2-minute
             track's metadata still corrupts the library.
          4. If no candidate's title passes, return None. The caller treats
             that as "not found on YouTube" - strictly better than shipping
             the wrong audio under the right cover. With loose_match on, the
             None of steps 2 and 4 becomes _loose_pick's duration-closest result.

        `expected_title` + `expected_artists` are optional so legacy callers
        that haven't been updated still work via the older trust-the-top-
        hit-unless-duration-is-clearly-off policy.
        """
        select_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "retries": 5,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 4,
        }
        log.debug(
            "yt search: query=%r title=%r artists=%r dur=%ss",
            search_query,
            expected_title,
            expected_artists,
            expected_duration_s,
        )
        try:
            with self._youtube(select_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
        except Exception as exc:
            # The single most useful log line for triage: a real exception here
            # (bot-challenge, SSL, network, region block) is otherwise invisible
            # because the caller only ever sees "not found on YouTube".
            log.warning("yt search raised %s: %s", type(exc).__name__, str(exc)[:300])
            return None
        entries = [e for e in (info or {}).get("entries", []) if e and e.get("id")]
        if not entries:
            # Empty results with no exception is the classic bot-block / rate-limit
            # / region signature. Distinct from "found results but filtered out".
            log.warning(
                "yt search returned 0 entries for %r (bot-block/network/region?)", search_query
            )
            return None
        log.debug("yt search returned %d entries", len(entries))

        if expected_title:
            title_ok = [
                e for e in entries if self._title_plausibly_matches(e.get("title"), expected_title)
            ]
            if not title_ok:
                log.info(
                    "title filter rejected all %d candidates for %r (e.g. %r)",
                    len(entries),
                    expected_title,
                    (entries[0].get("title") if entries else None),
                )
                if self.loose_match:
                    return self._loose_pick(entries, expected_duration_s)
                return None

            # Require an artist in the YouTube title alongside the song name:
            # rejects right-title-wrong-uploader remixes. Prefer not-found
            # over wrong audio (#52). Title-only when no artists are known.
            pool = title_ok
            if expected_artists:
                # Split on collaboration separators BEFORE normalizing -
                # normalization eats commas, which would collapse the
                # multi-artist string into one unmatchable token.
                raw_tokens = re.split(
                    r"[,&]+|\s+(?:feat\.?|ft\.?)\s+",
                    expected_artists,
                    flags=re.IGNORECASE,
                )
                artist_tokens = [self._normalize_title(t) for t in raw_tokens]
                artist_tokens = [t for t in artist_tokens if t]
                if artist_tokens:
                    pool = [
                        e
                        for e in title_ok
                        if any(
                            artist in self._normalize_title(e.get("title") or "")
                            for artist in artist_tokens
                        )
                    ]
                    if not pool and not any(re.search(r"[a-z0-9]", t) for t in artist_tokens):
                        # Native-script artists usually appear romanized on
                        # YouTube, so an all-non-latin token set would reject
                        # everything; fall back to title-only.
                        log.info(
                            "artist gate skipped: no latin token in %r, falling back to title-only",
                            expected_artists,
                        )
                        pool = title_ok
                    if not pool:
                        log.info(
                            "artist filter rejected all %d title-matches (artists=%r)",
                            len(title_ok),
                            expected_artists,
                        )
                        if self.loose_match:
                            return self._loose_pick(title_ok, expected_duration_s)
                        return None

            chosen = pool[0]
            if expected_duration_s:
                timed = [e for e in pool if e.get("duration")]
                if timed:
                    chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
                    # Right title+artist but wildly wrong duration = live
                    # cover / extended mix; still the wrong audio to ship.
                    off = abs(chosen["duration"] - expected_duration_s)
                    if off > self._DURATION_TOLERANCE_S_WIDE:
                        log.info(
                            "closest candidate duration off by %.0fs (>%ss), rejecting",
                            off,
                            self._DURATION_TOLERANCE_S_WIDE,
                        )
                        return None
            log.debug("selected youtube video %s", chosen["id"])
            return f"https://www.youtube.com/watch?v={chosen['id']}"

        # Legacy path - kept for any caller that hasn't been updated yet.
        chosen = entries[0]
        if expected_duration_s:
            top_duration = chosen.get("duration")
            top_off = top_duration is None or (
                abs(top_duration - expected_duration_s) > self._DURATION_TOLERANCE_S
            )
            if top_off:
                timed = [e for e in entries if e.get("duration")]
                if timed:
                    chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
        return f"https://www.youtube.com/watch?v={chosen['id']}"

    def _loose_pick(self, candidates, expected_duration_s):
        """Opt-in fallback (Settings: "use closest result if no match").

        When strict title/artist matching finds nothing, return the
        duration-closest candidate (or the top result if durations are
        missing). Recovers cross-script matches the ascii title filter can
        never make - e.g. a Latin Spotify title vs a Greek/Cyrillic/CJK
        youtube title. Trades the never-grab-the-wrong-audio guarantee for
        coverage, which is why the caller only reaches here when loose_match
        is on (off by default).
        """
        if not candidates:
            return None
        chosen = candidates[0]
        if expected_duration_s:
            timed = [e for e in candidates if e.get("duration")]
            if timed:
                chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
        log.warning("loose match (no confident title/artist match): selected %s", chosen["id"])
        return f"https://www.youtube.com/watch?v={chosen['id']}"

    def download_track_audio(
        self,
        search_query,
        destination,
        expected_duration_s=None,
        expected_title=None,
        expected_artists=None,
    ):
        # Check for FFmpeg first
        ffmpeg_path = tools.get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(f"FFmpeg not found! Install via: {tools.ffmpeg_install_hint()}")

        fmt = self.audio_format if self.audio_format in SUPPORTED_FORMATS else "mp3"
        ext = SUPPORTED_FORMATS[fmt]["ext"]
        is_lossy = SUPPORTED_FORMATS[fmt]["lossy"]

        base, _ = os.path.splitext(destination)
        # the stem carries Spotify's title and playlist name; yt-dlp would expand a
        # "%(uploader)s" in either into YouTube metadata, so every % stays literal
        output_template = base.replace("%", "%%") + ".%(ext)s"
        postprocessor = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": fmt,
        }
        if is_lossy:
            postprocessor["preferredquality"] = self.audio_quality

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "ffmpeg_location": ffmpeg_path,
            "retries": 5,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 4,
            "ignoreerrors": True,
            "postprocessors": [postprocessor],
        }
        if self.sample_rate != "auto" and fmt in ("mp3", "flac", "wav"):
            # "extractaudio" is the only key yt-dlp matches for this PP.
            # opus excluded (libopus is 48 kHz-only); m4a excluded (may
            # stream-copy aac, where ffmpeg silently drops -ar).
            ydl_opts["postprocessor_args"] = {"extractaudio": ["-ar", self.sample_rate]}

        expected_path = base + "." + ext

        # Widened query then a simplified fallback; success = an audio file
        # actually on disk, so an empty search fails loudly.
        queries = [self._widen_search(search_query)]
        fallback = self._simplify_search(search_query)
        if fallback not in queries:
            queries.append(fallback)

        # yt-dlp's maintained defaults first, then a different client family:
        # youtube bot-challenges per-IP and per-client, so a second family is
        # worth one retry. Never a pinned list - see _retry_player_clients.
        fallback_opts = dict(ydl_opts)
        retry_clients = _retry_player_clients()
        if retry_clients:
            fallback_opts["extractor_args"] = {"youtube": {"player_client": list(retry_clients)}}
        attempts = [("default", ydl_opts), ("fallback", fallback_opts)]

        for query in queries:
            video_url = self._select_youtube_match(
                query,
                expected_duration_s,
                expected_title=expected_title,
                expected_artists=expected_artists,
            )
            if not video_url:
                continue
            for label, opts in attempts:
                # per-attempt bridge captures yt-dlp's own error even when
                # ignoreerrors swallows it (no exception, no file)
                ytlog = _YtdlpLog()
                try:
                    with self._youtube({**opts, "logger": ytlog}) as ydl:
                        ydl.extract_info(video_url, download=True)
                except Exception as exc:
                    log.warning(
                        "download attempt (%s) failed for %s: %s",
                        label,
                        video_url,
                        str(exc)[:300],
                    )
                    self._note_if_network_blocked(str(exc))
                else:
                    if not os.path.exists(expected_path):
                        # the silent case: yt-dlp produced no file without
                        # raising; the bridge holds the real reason
                        reason = (ytlog.last_error or "no error reported by yt-dlp").strip()
                        log.warning(
                            "download attempt (%s) produced no file for %s: %s",
                            label,
                            video_url,
                            reason[:300],
                        )
                        self._note_if_network_blocked(reason)
                if os.path.exists(expected_path):
                    if label != "default":
                        log.info("recovered via %s player clients", label)
                    return expected_path

        log.debug("no playable audio landed for query set %r", queries)
        raise RuntimeError("no playable audio source found on YouTube for this track")

    def _download_one_track(self, track, playlist_folder_path, default_cover_url, track_num=0):
        """Download a single track. Runs inside a ThreadPoolExecutor worker.

        Returns None on success, the track title on failure (for _failed_tracks).
        Qt signals emitted here cross thread boundaries via queued connections,
        which is safe.

        In parallel mode (self._parallel_mode), per-track UI noise (song_meta
        preview, per-byte progress) is suppressed because those widgets are
        single-track and would flicker with N workers in flight. add_song_meta
        still fires so ID3 tags + cover art get written to every mp3.

        track_num (1-based) is passed through to song_meta so the ID3 TRCK
        frame can be populated for playlist ordering.
        """
        if self.is_cancelled():
            return None

        track_title = track.title
        artists = track.artists
        sanitized_title = self.sanitize_text(track_title)
        sanitized_artists = self.sanitize_text(artists)

        filename = self._compose_filename(sanitized_title, sanitized_artists, track_num)
        filepath = os.path.join(playlist_folder_path, cap_filename(filename))

        # Collision guard: distinct tracks can resolve to the same name
        # (always possible, likely under title_only), and parallel workers
        # racing os.path.exists would clobber each other. Claim under a lock;
        # if taken in-flight, on a case-folding filesystem, or on disk owned
        # by a different track per the manifest, suffix the track id.
        with self._filename_lock:
            claim = filepath.casefold()
            if claim in self._in_flight_files or self._file_belongs_to_other(filepath, track.id):
                log.info(
                    "filename collision: %r already claimed, suffixing track id %s",
                    os.path.basename(filepath),
                    track.id,
                )
                filename = self._compose_filename(
                    sanitized_title, sanitized_artists, track_num, disambig=track.id
                )
                filepath = os.path.join(playlist_folder_path, cap_filename(filename))
                claim = filepath.casefold()
            self._in_flight_files.add(claim)

        # Per-track enrichment: the playlist embed carries no per-track cover
        # url (the "all 300 songs have the same cover" report) and no album
        # at all (#104), so fetch /embed/track/{id} when any of them is
        # missing. ~100-300ms per track, overlapped by other workers in
        # parallel mode.
        cover_url = track.cover_url
        album_name = track.album or ""
        release_date = track.release_date or ""
        if (
            (not cover_url or not album_name or not release_date)
            and track.id
            and self.spotifydown_api is not None
            and not self.is_cancelled()
        ):
            try:
                enriched = self.spotifydown_api.get_track(track.id)
                if enriched:
                    if enriched.cover_url:
                        cover_url = enriched.cover_url
                    if not album_name and enriched.album:
                        album_name = enriched.album
                    if not release_date and enriched.release_date:
                        release_date = enriched.release_date
            except SpotifyDownAPIError as exc:
                log.debug("track enrichment failed for '%s': %s", track_title, exc)

        cover_url = cover_url or default_cover_url

        song_meta = self._song_meta(track, album_name, release_date, cover_url, filepath, track_num)

        # Preview panel shows whichever track most recently started; the
        # worker race is fine (better than a blank panel).
        self.song_meta.emit(dict(song_meta))

        try:
            if os.path.exists(filepath):
                self._record_in_manifest(track.id, filepath)
                self.add_song_meta.emit(song_meta)
                self._finish_track_ui(ok=True)
                return None

            search_query = f"ytsearch1:{track_title} {artists} audio"
            expected_dur = (track.duration_ms / 1000) if track.duration_ms else None
            try:
                final_path = self.download_track_audio(
                    search_query,
                    filepath,
                    expected_duration_s=expected_dur,
                    expected_title=track_title,
                    expected_artists=artists,
                )
            except Exception as error_status:
                error_msg = self._get_user_friendly_error(error_status, track_title)
                self.error_signal.emit(error_msg)
                # concise reason at WARNING (the per-attempt yt-dlp reason is
                # already logged above); full traceback only when verbose
                log.warning("track failed: '%s': %s", track_title, str(error_status)[:200])
                log.debug("track failure traceback for '%s'", track_title, exc_info=True)
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

            if not final_path or not os.path.exists(final_path):
                self.error_signal.emit(t("engine.track_failed", title=track_title))
                log.warning(
                    "track produced no audio file (no confident match or blocked): '%s'",
                    track_title,
                )
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

            self._record_in_manifest(track.id, final_path)
            song_meta["file"] = final_path
            self.add_song_meta.emit(song_meta)
            self._finish_track_ui(ok=True)
            return None
        finally:
            with self._filename_lock:
                self._in_flight_files.discard(filepath.casefold())

    def _song_meta(self, track, album, release_date, cover_url, filepath, track_num) -> dict:
        """The per-track payload the UI previews and the tag writer embeds."""
        duration_ms = getattr(track, "duration_ms", None)
        return {
            "title": track.title,
            "artists": track.artists,
            "album": album,
            "releaseDate": release_date,
            "cover": cover_url or "",
            "file": filepath,
            "trackNumber": track_num,
            # seconds; LRCLIB matches on it, and it tells two cuts of a song apart
            "duration": round(duration_ms / 1000) if isinstance(duration_ms, (int, float)) else 0,
            "lyrics": self.lyrics,
        }

    def _finish_track_ui(self, ok: bool) -> None:
        """Update counter + progress bar after a track completes or fails."""
        self.increment_counter()
        if self._parallel_mode and self._total_tracks > 0:
            # Aggregate progress across all workers: show how many tracks are
            # done as a percentage. Avoids the N-workers-jittering-one-bar
            # problem where per-byte emits from 4 downloads make the bar jump.
            pct = int(self.counter / self._total_tracks * 100)
            self.dlprogress_signal.emit(min(pct, 100))
        elif ok:
            self.dlprogress_signal.emit(100)

    def _load_manifest(self, folder: str) -> set:
        """Load the set of track IDs already downloaded into `folder`.

        The manifest is a JSON-lines file inside the folder; each line is a
        `{"id", "file"}` record. Entries whose file is missing are ignored so
        a track the user deleted re-downloads. Returns the set of valid IDs
        and arms `_manifest_path` for incremental appends during this run.
        """
        import json

        path = os.path.join(folder, MANIFEST_FILENAME)
        self._manifest_path = path
        self._manifest_owners = {}
        done: set[str] = set()
        if not os.path.exists(path):
            return done
        try:
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    track_id = record.get("id")
                    filename = record.get("file")
                    if track_id and filename and os.path.exists(os.path.join(folder, filename)):
                        done.add(track_id)
                        self._manifest_owners[filename.casefold()] = track_id
        except OSError:
            return set()
        return done

    def _file_belongs_to_other(self, filepath: str, track_id) -> bool:
        """True when a file already at this path is a different track's per
        the manifest - a title collision across runs, not a resume hit (#91).
        An unmapped existing file stays a resume hit so crash recovery
        (files present, manifest lost) keeps skipping instead of re-downloading."""
        if not track_id or not os.path.exists(filepath):
            return False
        owner = self._manifest_owners.get(os.path.basename(filepath).casefold())
        return owner is not None and owner != track_id

    def _record_in_manifest(self, track_id, filepath: str) -> None:
        """Append a completed track to the manifest (thread-safe).

        Append-only JSON-lines so recording a track is O(1) regardless of how
        large the playlist is. Failures are swallowed: the manifest is an
        optimization for resuming, never a hard dependency of a download.
        """
        if not track_id or not self._manifest_path:
            return
        import json

        record = json.dumps({"id": track_id, "file": os.path.basename(filepath)})
        with self._manifest_lock:
            # keep the ownership map live so a same-title track later in this
            # run suffixes instead of mistaking the finished file for its own
            self._manifest_owners.setdefault(os.path.basename(filepath).casefold(), track_id)
            try:
                with open(self._manifest_path, "a", encoding="utf-8") as handle:
                    handle.write(record + "\n")
            except OSError:
                pass

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        # Reset mutable state so repeat invocations on the same scraper
        # instance don't carry stale counters or failure lists.
        with self._counter_lock:
            self.counter = 0
        with self._failed_lock:
            self._failed_tracks.clear()
        with self._filename_lock:
            self._in_flight_files.clear()
        self._parallel_mode = False
        self._total_tracks = 0

        # A playlist or an album both flow through here. detect_spotify_url_type
        # returns ("playlist"|"album", id); albums reuse the same embed-parsing
        # path with the album embed endpoint (closes #38).
        content_type, playlist_id = detect_spotify_url_type(spotify_playlist_link)
        if content_type not in ("playlist", "album"):
            raise ValueError("Expected a playlist or album URL")
        self.PlaylistID.emit(playlist_id)

        # Bail before network work if stop was already clicked.
        if self.is_cancelled():
            self.PlaylistCompleted.emit(t("engine.cancelled"))
            return

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        metadata = spotify_api.get_playlist_metadata(playlist_id, content_type=content_type)
        playlist_display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(playlist_display_name)

        playlist_folder_path = self.prepare_playlist_folder(music_folder, playlist_display_name)
        self.output_folder = playlist_folder_path
        self.display_name = playlist_display_name
        with folder_lock(playlist_folder_path):
            # Resume support: skip tracks already downloaded in a previous run of
            # this folder before fetching their (rate-limited) metadata, so a huge
            # playlist can be finished across multiple sessions (closes #40).
            already_done = self._load_manifest(playlist_folder_path)
            if already_done:
                self.resume_skipped.emit(len(already_done))
                self.error_signal.emit(t("engine.resuming", count=len(already_done)))

            # Materialize the generator (not thread-safe; count also picks the
            # worker pool size). Cancel is checked between yields so huge
            # playlists abort mid-fetch instead of after the full window.
            expected_total = metadata.track_count or 0
            tracks: list = []
            for track in spotify_api.iter_playlist_tracks(
                playlist_id, content_type=content_type, skip_ids=already_done
            ):
                if self.is_cancelled():
                    break
                tracks.append(track)
                if expected_total and len(tracks) % 10 == 0:
                    self.error_signal.emit(
                        t("engine.fetching", done=len(tracks), total=expected_total)
                    )
            self._total_tracks = len(tracks)

            if self.is_cancelled():
                self.PlaylistCompleted.emit(t("engine.cancelled"))
                return

            self.Resetprogress_signal.emit(0)

            # Small playlists don't benefit from parallelism. Keep 1 worker for
            # playlists under 3 tracks to preserve the single-track UI feel.
            worker_count = 1 if len(tracks) < 3 else min(self.MAX_WORKERS, len(tracks))
            self._parallel_mode = worker_count > 1

            log.info(
                "%s scrape: name=%r id=%s tracks=%d (resume-skipped %d) mode=%s workers=%d fmt=%s/%s naming=%s",
                content_type,
                playlist_display_name,
                playlist_id,
                len(tracks),
                len(already_done),
                "parallel" if self._parallel_mode else "sequential",
                worker_count,
                self.audio_format,
                self.audio_quality,
                "title-only"
                if self.title_only
                else ("artist-first" if self.artist_first else "default"),
            )

            # Canonical playlist position over enumerate order: spclient yields
            # in http-completion order on >100-track playlists (#51). Enumerate
            # only for albums/small playlists, which arrive already ordered.
            def _track_num_for(track, idx):
                return track.position if getattr(track, "position", None) else idx

            if worker_count == 1:
                for idx, track in enumerate(tracks, start=1):
                    if self.is_cancelled():
                        break
                    # Reset the per-track progress bar at the top of each iteration
                    # so the single-track UI behaves the way it always has.
                    self.Resetprogress_signal.emit(0)
                    self._download_one_track(
                        track,
                        playlist_folder_path,
                        metadata.cover_url,
                        track_num=_track_num_for(track, idx),
                    )
            else:
                try:
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=worker_count
                    ) as executor:
                        futures = [
                            executor.submit(
                                self._download_one_track,
                                track,
                                playlist_folder_path,
                                metadata.cover_url,
                                _track_num_for(track, idx),
                            )
                            for idx, track in enumerate(tracks, start=1)
                        ]
                        for future in concurrent.futures.as_completed(futures):
                            if self.is_cancelled():
                                # Cancel remaining futures that haven't started
                                # yet. In-flight downloads check is_cancelled at
                                # their own top and return early.
                                for f in futures:
                                    f.cancel()
                                break
                            try:
                                future.result()
                            except Exception as exc:
                                # _download_one_track handles its own errors; this is
                                # only framework-level fallout (a worker crashed hard).
                                log.error("unexpected worker error", exc_info=exc)
                                self.error_signal.emit(t("engine.worker_error", error=exc))
                finally:
                    # Reset only after executor shutdown: in-flight workers that
                    # observed False mid-run would emit single-track UI signals.
                    self._parallel_mode = False

            if self.is_cancelled():
                log.info("scrape cancelled by user (%d done before cancel)", self.counter)
                self.PlaylistCompleted.emit(t("engine.cancelled"))
                return

            # Report completion with failed track count
            ok = max(self._total_tracks - len(self._failed_tracks), 0)
            if self._failed_tracks:
                log.info("scrape done: %d ok, %d failed", ok, len(self._failed_tracks))
                log.info("failed tracks: %s", " | ".join(self._failed_tracks))
                self.PlaylistCompleted.emit(
                    t("engine.done_with_failures", count=len(self._failed_tracks))
                )
            else:
                log.info("scrape done: %d ok, 0 failed", self._total_tracks)
                self.PlaylistCompleted.emit(t("engine.complete"))

    def scrape_track(self, spotify_track_link, music_folder):
        """Download a single track from Spotify."""
        url_type, track_id = detect_spotify_url_type(spotify_track_link)
        if url_type != "track":
            raise ValueError("Expected a track URL")

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        track = spotify_api.get_track(track_id)
        log.info(
            "single-track scrape: %r by %r id=%s fmt=%s/%s",
            track.title,
            track.artists,
            track_id,
            self.audio_format,
            self.audio_quality,
        )
        self.song_Album.emit(t("engine.single_track"))

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)
        self.output_folder = music_folder
        self.display_name = f"{track.title} - {track.artists}"

        self.Resetprogress_signal.emit(0)

        track_title = track.title
        artists = track.artists
        sanitized_title = self.sanitize_text(track_title)
        sanitized_artists = self.sanitize_text(artists)
        filename = self._compose_filename(sanitized_title, sanitized_artists)
        filepath = os.path.join(music_folder, cap_filename(filename))

        album_name = track.album or ""
        release_date = track.release_date or ""
        cover_url = track.cover_url

        song_meta = self._song_meta(track, album_name, release_date, cover_url, filepath, 1)

        self.song_meta.emit(dict(song_meta))

        if os.path.exists(filepath):
            self.add_song_meta.emit(song_meta)
            self.increment_counter()
            self.PlaylistCompleted.emit(t("engine.track_exists"))
            return

        # Download via YouTube search
        search_query = f"ytsearch1:{track_title} {artists} audio"
        expected_dur = (track.duration_ms / 1000) if track.duration_ms else None
        try:
            final_path = self.download_track_audio(
                search_query, filepath, expected_duration_s=expected_dur
            )
        except Exception as error_status:
            error_msg = self._get_user_friendly_error(error_status, track_title)
            log.error("single-track download failed: '%s'", track_title, exc_info=True)
            # record it: the CLI derives its failure count and exit code from
            # this list, and a silent single-track failure exited 0 with no file
            with self._failed_lock:
                self._failed_tracks.append(track_title)
            self.PlaylistCompleted.emit(error_msg)
            return

        if not final_path or not os.path.exists(final_path):
            log.warning("single-track produced no audio file: '%s'", track_title)
            with self._failed_lock:
                self._failed_tracks.append(track_title)
            self.PlaylistCompleted.emit(t("engine.no_audio"))
            return

        song_meta["file"] = final_path
        self.add_song_meta.emit(song_meta)
        self.increment_counter()
        self.dlprogress_signal.emit(100)
        self.PlaylistCompleted.emit(t("engine.complete"))

    def increment_counter(self):
        with self._counter_lock:
            self.counter += 1
            current = self.counter
        self.count_updated.emit(current)  # Emit the signal with the updated count


# Scraper Thread
class ScraperThread(QThread):
    progress_update = Signal(str)

    def __init__(
        self,
        spotify_link,
        music_folder=None,
        cancel_event: threading.Event | None = None,
        **scraper_opts,
    ):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        # MusicScraper's explicit signature validates the option names
        self.scraper = MusicScraper(cancel_event=self._cancel_event, **scraper_opts)

    def request_cancel(self):
        """Request cancellation of the download."""
        self._cancel_event.set()

    def run(self):
        self.progress_update.emit(t("engine.started"))
        try:
            # Detect URL type and handle accordingly
            url_type, _ = detect_spotify_url_type(self.spotify_link)
            if url_type == "track":
                self.scraper.scrape_track(self.spotify_link, self.music_folder)
            else:
                self.scraper.scrape_playlist(self.spotify_link, self.music_folder)
        except Exception as e:
            log.exception("scrape failed for %s", self.spotify_link)
            self.progress_update.emit(f"{e}")
