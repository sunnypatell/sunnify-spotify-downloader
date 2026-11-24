"""Tag + cover-art writers per container (ID3 v2.3, iTunes atoms, Vorbis comments)."""

from __future__ import annotations

import os

from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, USLT
from PyQt6.QtCore import QThread

from sunnify import lyrics as lrclib
from sunnify import net
from sunnify.i18n import t
from sunnify.logs import log
from sunnify.qt import Signal


def _fetch_cover_bytes(url: str) -> bytes | None:
    """Download cover image bytes (http(s) only, size-capped); None on any failure."""
    return net.fetch_bytes(url, timeout=15)


def _detect_image_mime(data: bytes) -> str:
    """Return the MIME string for image bytes, sniffed from magic numbers.

    Spotify currently serves JPEG covers; this function exists so a future
    switch to PNG (or a mid-flight content-type change) doesn't silently
    produce broken cover-art frames mis-tagged as JPEG.

    ref: JPEG magic ff d8 ff (any JFIF/Exif variant), per ISO/IEC 10918-1
    ref: PNG signature 89 50 4e 47 0d 0a 1a 0a, per W3C PNG spec section 5.2
    """
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"  # safe default; Spotify has served JPEG since 2015


def _write_metadata_mp3(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write ID3 tags + embedded cover art to an MP3.

    Tags and the APIC cover frame are written as ID3v2.3 with UTF-16 text
    encoding instead of mutagen's v2.4 / UTF-8 default. v2.3 + UTF-16 is the
    lowest common denominator that's understood by older iTunes, Windows
    Media Player, most car head-units, and stock Android players, none of
    which read v2.4 APIC frames reliably (closes #46).

    ref: ID3v2.3 spec section 3.3 (only encoding values $00 ISO-8859-1
         and $01 Unicode UTF-16+BOM are defined) https://id3.org/id3v2.3.0
    ref: ID3v2.4 spec adds $02 UTF-16BE and $03 UTF-8 (which is what
         mutagen writes by default) https://id3.org/id3v2.4.0-frames
    ref: mutagen `update_to_v23()` downgrades any UTF-8 frames to UTF-16
         before saving as v2.3 https://mutagen.readthedocs.io/en/latest/api/id3.html
    """
    audio = EasyID3(filename)
    audio["title"] = tags.get("title", "")
    audio["artist"] = tags.get("artists", "")
    audio["album"] = tags.get("album", "")
    audio["date"] = tags.get("releaseDate", "")
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    # EasyID3.save() defaults to v2.4 + UTF-8. Passing v2_version=3 tells
    # mutagen to downgrade text frames to a v2.3-allowed encoding (UTF-16
    # with BOM for non-ASCII, Latin-1 for ASCII) before writing.
    audio.save(v2_version=3)
    lyrics_text = tags.get("lyricsText") or ""
    if cover_bytes or lyrics_text:
        id3 = ID3(filename)
        if cover_bytes:
            mime = _detect_image_mime(cover_bytes)
            # encoding=1 (UTF-16+BOM) is the only Unicode encoding v2.3 defines.
            # type=3 is "Cover (front)" per the v2.3 APIC enum.
            id3.add(APIC(encoding=1, mime=mime, type=3, desc="Cover", data=cover_bytes))
        if lyrics_text:
            # USLT exists in v2.3 as-is; "XXX" is the spec's unknown-language code
            id3.setall("USLT", [USLT(encoding=1, lang="XXX", desc="", text=lyrics_text)])
        id3.update_to_v23()
        id3.save(v2_version=3)


def _write_metadata_m4a(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write iTunes atom tags + embedded cover art to an M4A/MP4.

    iTunes atoms (`covr`, `\xa9nam`, etc.) are a stable, version-less spec
    used by every MP4-aware player. The only knob worth getting right is
    the cover-art image format, which we sniff so a future PNG cover from
    Spotify doesn't get mis-tagged as JPEG.

    ref: mutagen MP4Tags atom keys (`\xa9nam`/`\xa9ART`/`\xa9alb`/`\xa9day`/
         `trkn`/`covr`) and MP4Cover.FORMAT_JPEG/PNG, which is the spec we
         write against https://mutagen.readthedocs.io/en/latest/api/mp4.html
    """
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(filename)
    audio["\xa9nam"] = tags.get("title", "")
    audio["\xa9ART"] = tags.get("artists", "")
    audio["\xa9alb"] = tags.get("album", "")
    date = tags.get("releaseDate", "")
    if date:
        audio["\xa9day"] = date
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["trkn"] = [(int(track_num), 0)]
    if cover_bytes:
        mime = _detect_image_mime(cover_bytes)
        fmt = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover_bytes, imageformat=fmt)]
    if tags.get("lyricsText"):
        audio["©lyr"] = tags["lyricsText"]
    audio.save()


def _write_metadata_flac(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write Vorbis comments + embedded cover art to a FLAC.

    FLAC's Picture block carries an explicit MIME string, so we sniff the
    image type and pass it through. Vorbis comments are always UTF-8 and
    universally supported, so nothing else is version-sensitive here.

    ref: FLAC METADATA_BLOCK_PICTURE format spec
         https://xiph.org/flac/format.html#metadata_block_picture
    """
    from mutagen.flac import FLAC, Picture

    audio = FLAC(filename)
    audio["title"] = tags.get("title", "")
    audio["artist"] = tags.get("artists", "")
    audio["album"] = tags.get("album", "")
    date = tags.get("releaseDate", "")
    if date:
        audio["date"] = date
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    if cover_bytes:
        # add_picture() appends; clear first so a re-tag doesn't stack duplicate covers
        audio.clear_pictures()
        pic = Picture()
        pic.type = 3  # Front cover
        pic.mime = _detect_image_mime(cover_bytes)
        pic.desc = "Cover"
        pic.data = cover_bytes
        audio.add_picture(pic)
    if tags.get("lyricsText"):
        audio["lyrics"] = tags["lyricsText"]
    audio.save()


_METADATA_WRITERS = {
    ".mp3": _write_metadata_mp3,
    ".m4a": _write_metadata_m4a,
    ".flac": _write_metadata_flac,
}


class WritingMetaTagsThread(QThread):
    tags_success = Signal(str)

    def __init__(self, tags, filename):
        super().__init__()
        self.tags = tags
        self.filename = filename

    def run(self):
        """Write tags + cover art synchronously, dispatching on file extension.

        Each container uses a different tag system (ID3 for mp3, iTunes atoms
        for m4a, Vorbis comments for flac). Opus/WAV are skipped with a log
        line; those formats have limited or no standard cover-art story that
        would repay the extra dependency surface for this project's scope.
        With lyrics on, a synced .lrc lands next to every format, opus/wav too.
        """
        try:
            log.info("writing tags: %s", self.filename)
            ext = os.path.splitext(self.filename)[1].lower()
            writer = _METADATA_WRITERS.get(ext)
            tags = dict(self.tags)
            if tags.get("lyrics"):
                found = lrclib.fetch_lyrics(
                    tags.get("title", ""),
                    tags.get("artists", ""),
                    tags.get("album", ""),
                    tags.get("duration") or 0,
                )
                if found and found.best:
                    tags["lyricsText"] = found.best
                    lrclib.write_lrc_sidecar(self.filename, found)
                log.debug("lyrics for %r: %s", tags.get("title"), "found" if found else "none")
            if writer is None:
                self.tags_success.emit(t("tags.skipped"))
                return

            cover_bytes = _fetch_cover_bytes(tags.get("cover", ""))
            writer(self.filename, tags, cover_bytes)
            self.tags_success.emit(t("tags.done"))
        except Exception:
            log.error("tag write failed: %s", self.filename, exc_info=True)
