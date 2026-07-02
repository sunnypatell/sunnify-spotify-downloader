"""Tests for Spotify_Downloader module."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
import requests


class TestGetFfmpegPath:
    """Tests for get_ffmpeg_path function."""

    def test_bundled_ffmpeg_macos(self, tmp_path):
        """Test bundled FFmpeg detection on macOS."""
        # Import the function
        from Spotify_Downloader import get_ffmpeg_path

        # Mock frozen attribute for PyInstaller
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(tmp_path), create=True),
            patch("sys.platform", "darwin"),
        ):
            # Create mock ffmpeg in bundled path
            ffmpeg_dir = tmp_path / "ffmpeg"
            ffmpeg_dir.mkdir()
            ffmpeg_path = ffmpeg_dir / "ffmpeg"
            ffmpeg_path.touch()

            result = get_ffmpeg_path()
            assert result == str(ffmpeg_dir)

    def test_bundled_ffmpeg_windows(self, tmp_path):
        """Test bundled FFmpeg detection on Windows."""
        from Spotify_Downloader import get_ffmpeg_path

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(tmp_path), create=True),
            patch("sys.platform", "win32"),
        ):
            ffmpeg_dir = tmp_path / "ffmpeg"
            ffmpeg_dir.mkdir()
            ffmpeg_path = ffmpeg_dir / "ffmpeg.exe"
            ffmpeg_path.touch()

            result = get_ffmpeg_path()
            assert result == str(ffmpeg_dir)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX path probe; os.path.join uses backslash on Windows so the "
        "exists() mock keyed on '/opt/homebrew/bin/ffmpeg' never matches",
    )
    def test_homebrew_ffmpeg(self, tmp_path):
        """Test homebrew FFmpeg detection."""
        from Spotify_Downloader import get_ffmpeg_path

        # Mock not frozen (running from source)
        with (
            patch.object(sys, "frozen", False, create=True),
            patch("sys.platform", "darwin"),
            patch("os.path.exists") as mock_exists,
        ):
            # Return True only for homebrew path
            def exists_side_effect(path):
                return path == "/opt/homebrew/bin/ffmpeg"

            mock_exists.side_effect = exists_side_effect

            result = get_ffmpeg_path()
            assert result == "/opt/homebrew/bin"

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX path probe; os.path.join uses backslash on Windows so the "
        "exists() mock keyed on '/usr/bin/ffmpeg' never matches",
    )
    def test_system_ffmpeg_linux(self, tmp_path):
        """Test system FFmpeg detection on Linux."""
        from Spotify_Downloader import get_ffmpeg_path

        with (
            patch.object(sys, "frozen", False, create=True),
            patch("sys.platform", "linux"),
            patch("os.path.exists") as mock_exists,
        ):

            def exists_side_effect(path):
                return path == "/usr/bin/ffmpeg"

            mock_exists.side_effect = exists_side_effect

            result = get_ffmpeg_path()
            assert result == "/usr/bin"

    def test_ffmpeg_in_path(self):
        """Test FFmpeg detection via PATH."""
        from Spotify_Downloader import get_ffmpeg_path

        with (
            patch.object(sys, "frozen", False, create=True),
            patch("os.path.exists", return_value=False),
            patch("shutil.which", return_value="/custom/path/ffmpeg"),
        ):
            result = get_ffmpeg_path()
            assert result == "/custom/path"

    def test_ffmpeg_not_found(self):
        """Test when FFmpeg is not found anywhere."""
        from Spotify_Downloader import get_ffmpeg_path

        with (
            patch.object(sys, "frozen", False, create=True),
            patch("os.path.exists", return_value=False),
            patch("shutil.which", return_value=None),
        ):
            result = get_ffmpeg_path()
            assert result is None


class TestMusicScraper:
    """Tests for MusicScraper class."""

    def test_sanitize_text(self):
        """Test text sanitization for filenames."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        assert scraper.sanitize_text("Hello World") == "Hello World"
        # ordinary punctuation is legal in filenames and kept verbatim
        assert scraper.sanitize_text("Test@Song#123") == "Test@Song#123"
        # accented/non-Latin titles must survive (special-char download bug)
        assert scraper.sanitize_text("MONTAGEM BAILÃO") == "MONTAGEM BAILÃO"
        # Windows-reserved characters are still stripped
        assert scraper.sanitize_text("A: B / C") == "A B C"

    def test_format_playlist_name(self):
        """Test playlist name formatting."""
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import PlaylistInfo

        scraper = MusicScraper()

        # With owner
        meta = PlaylistInfo(
            name="My Playlist",
            owner="Test User",
            description=None,
            cover_url=None,
        )
        result = scraper.format_playlist_name(meta)
        assert result == "My Playlist - Test User"

        # Without owner
        meta_no_owner = PlaylistInfo(
            name="Solo Playlist",
            owner=None,
            description=None,
            cover_url=None,
        )
        result = scraper.format_playlist_name(meta_no_owner)
        assert result == "Solo Playlist - Spotify"

    def test_prepare_playlist_folder(self, tmp_path):
        """Test playlist folder creation."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        base = str(tmp_path)

        result = scraper.prepare_playlist_folder(base, "Test Playlist")
        assert os.path.exists(result)
        assert "Test Playlist" in result

    def test_prepare_playlist_folder_sanitizes_name(self, tmp_path):
        """Test that folder names are sanitized."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        base = str(tmp_path)

        result = scraper.prepare_playlist_folder(base, "Test/Playlist:Name")
        assert os.path.exists(result)

    def test_prepare_playlist_folder_escapes_reserved_device_name(self, tmp_path):
        """A playlist named like a Windows reserved device name must not produce
        an uncreatable folder on Windows (CON -> _CON)."""
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import _RESERVED_DEVICE_NAMES

        result = MusicScraper().prepare_playlist_folder(str(tmp_path), "CON")
        assert os.path.basename(result).split(".")[0].upper() not in _RESERVED_DEVICE_NAMES
        assert os.path.isdir(result)

    def test_prepare_playlist_folder_keeps_unicode_and_punctuation(self, tmp_path):
        """Accented/non-Latin letters survive and punctuation is preserved now
        that folders use sanitize_filename (matches the track-file behavior)."""
        from Spotify_Downloader import MusicScraper

        result = MusicScraper().prepare_playlist_folder(str(tmp_path), "Café Mix - RØRY")
        assert os.path.basename(result) == "Café Mix - RØRY"
        assert os.path.isdir(result)

    def test_prepare_playlist_folder_reuses_legacy_folder(self, tmp_path):
        """Backward-compat: reuse a folder from the older ascii-only naming so
        the per-folder resume manifest isn't orphaned by the sanitizer switch."""
        from Spotify_Downloader import MusicScraper

        base = str(tmp_path)
        legacy = os.path.join(base, "My Mix  Owner")  # old build dropped the hyphen
        os.makedirs(legacy)
        open(os.path.join(legacy, ".sunnify-manifest.jsonl"), "w").close()

        result = MusicScraper().prepare_playlist_folder(base, "My Mix - Owner")
        assert result == legacy  # reused, didn't orphan the previous download

    def test_prepare_playlist_folder_escapes_superscript_device_name(self, tmp_path):
        """Windows reserves the superscript COM/LPT variants too (COM(1-3));
        a playlist named that must not produce an uncreatable folder."""
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import _RESERVED_DEVICE_NAMES

        result = MusicScraper().prepare_playlist_folder(str(tmp_path), "COM¹")
        assert os.path.basename(result).split(".")[0].upper() not in _RESERVED_DEVICE_NAMES
        assert os.path.isdir(result)
        # Special chars should be removed
        assert "/" not in os.path.basename(result)
        assert ":" not in os.path.basename(result)

    def test_returnSPOT_ID(self):
        """Test playlist ID extraction."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        url = "https://open.spotify.com/playlist/abc123xyz"
        assert scraper.returnSPOT_ID(url) == "abc123xyz"

    def test_increment_counter(self):
        """Test counter incrementing."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        assert scraper.counter == 0

        # Mock the signal emit
        scraper.count_updated = MagicMock()

        scraper.increment_counter()
        assert scraper.counter == 1
        scraper.count_updated.emit.assert_called_once_with(1)


class TestResumeManifest:
    """Tests for the resume manifest that skips already-downloaded tracks (#40)."""

    @staticmethod
    def _scraper():
        from Spotify_Downloader import MusicScraper

        return MusicScraper()

    def test_load_manifest_absent_returns_empty(self, tmp_path):
        """No manifest file means nothing to skip."""
        assert self._scraper()._load_manifest(str(tmp_path)) == set()

    def test_record_then_load_roundtrip(self, tmp_path):
        """Recorded tracks (whose files exist) come back as skip IDs."""
        folder = str(tmp_path)
        writer = self._scraper()
        writer._load_manifest(folder)  # arms _manifest_path
        (tmp_path / "a.mp3").write_bytes(b"x")
        (tmp_path / "b.mp3").write_bytes(b"x")
        writer._record_in_manifest("id_a", str(tmp_path / "a.mp3"))
        writer._record_in_manifest("id_b", str(tmp_path / "b.mp3"))

        assert self._scraper()._load_manifest(folder) == {"id_a", "id_b"}

    def test_load_prunes_missing_files(self, tmp_path):
        """A manifest entry whose file was deleted is not treated as done."""
        folder = str(tmp_path)
        writer = self._scraper()
        writer._load_manifest(folder)
        (tmp_path / "present.mp3").write_bytes(b"x")
        writer._record_in_manifest("present", str(tmp_path / "present.mp3"))
        writer._record_in_manifest("ghost", str(tmp_path / "ghost.mp3"))  # never created

        assert self._scraper()._load_manifest(folder) == {"present"}

    def test_record_without_manifest_path_is_noop(self, tmp_path):
        """Recording before a manifest is armed must not raise or write."""
        scraper = self._scraper()
        scraper._manifest_path = None
        scraper._record_in_manifest("id", str(tmp_path / "x.mp3"))
        assert self._scraper()._load_manifest(str(tmp_path)) == set()


class TestDownloadTrackAudioOpts:
    """Tests for yt-dlp performance options in download_track_audio."""

    def test_ydl_opts_include_retries(self):
        """Verify yt-dlp retries option is set."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        with (
            patch("Spotify_Downloader.get_ffmpeg_path", return_value="/usr/bin"),
            patch("Spotify_Downloader.YoutubeDL") as mock_ydl,
        ):
            mock_ydl.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info = MagicMock(return_value={"entries": []})
            with contextlib.suppress(Exception):
                scraper.download_track_audio("test query", "/tmp/test.mp3")
            call_args = mock_ydl.call_args
            opts = call_args[0][0] if call_args[0] else call_args[1]
            assert opts["retries"] == 5

    def test_ydl_opts_include_socket_timeout(self):
        """Verify yt-dlp socket_timeout is set."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        with (
            patch("Spotify_Downloader.get_ffmpeg_path", return_value="/usr/bin"),
            patch("Spotify_Downloader.YoutubeDL") as mock_ydl,
        ):
            mock_ydl.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            with contextlib.suppress(Exception):
                scraper.download_track_audio("test query", "/tmp/test.mp3")
            opts = mock_ydl.call_args[0][0]
            assert opts["socket_timeout"] == 15

    def test_ydl_opts_include_concurrent_fragments(self):
        """Verify yt-dlp concurrent_fragment_downloads is set."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        with (
            patch("Spotify_Downloader.get_ffmpeg_path", return_value="/usr/bin"),
            patch("Spotify_Downloader.YoutubeDL") as mock_ydl,
        ):
            mock_ydl.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            with contextlib.suppress(Exception):
                scraper.download_track_audio("test query", "/tmp/test.mp3")
            opts = mock_ydl.call_args[0][0]
            assert opts["concurrent_fragment_downloads"] == 4


class TestYoutubeMatchSelection:
    """Tests for duration-aware YouTube match selection.

    The top search hit is often the music video (extra intro/outro) which plays
    as a different recording than the Spotify track. Selection must steer to the
    candidate whose duration matches the Spotify track.
    """

    @staticmethod
    def _scraper():
        from Spotify_Downloader import MusicScraper

        return MusicScraper()

    def _patched(self, entries):
        candidates = {"entries": entries}
        ctx = patch("Spotify_Downloader.YoutubeDL")
        mock_ydl = ctx.start()
        mock_ydl.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info = MagicMock(return_value=candidates)
        return ctx

    def test_picks_duration_closest_not_top_hit(self):
        """With a known duration, the closest-length candidate wins over #1."""
        entries = [
            {"id": "musicvideo", "duration": 183, "title": "WAGWAN [MUSIC VIDEO]"},
            {"id": "audio", "duration": 127, "title": "Wagwan (Official Audio)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match("ytsearch5:wagwan", 127)
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=audio"

    def test_loose_match_off_rejects_cross_script(self):
        """Default (strict): a Latin Spotify title can't match a Greek-script
        YouTube title, so it returns None - the #52 wrong-audio safeguard holds."""
        entries = [
            {"id": "greek", "duration": 200, "title": "Στους 31 Δρόμους"},
            {"id": "other", "duration": 400, "title": "Κάτι Άλλο"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Stous 31 Dromous",
                200,
                expected_title="Stous 31 Dromous",
                expected_artists="Some Artist",
            )
        finally:
            ctx.stop()
        assert url is None

    def test_loose_match_on_recovers_cross_script(self):
        """Opt-in loose mode: recovers the duration-closest result when strict
        title/artist matching finds nothing (the cross-script i18n case)."""
        entries = [
            {"id": "greek", "duration": 200, "title": "Στους 31 Δρόμους"},
            {"id": "other", "duration": 400, "title": "Κάτι Άλλο"},
        ]
        scraper = self._scraper()
        scraper.loose_match = True
        ctx = self._patched(entries)
        try:
            url = scraper._select_youtube_match(
                "ytsearch5:Stous 31 Dromous",
                200,
                expected_title="Stous 31 Dromous",
                expected_artists="Some Artist",
            )
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=greek"  # duration-closest match

    def test_keeps_top_hit_when_its_duration_is_already_close(self):
        """No regression: a top hit within tolerance is kept even if another
        candidate is a hair closer (avoids preferring a same-length wrong edit)."""
        entries = [
            {"id": "official", "duration": 204, "title": "Song (Official Audio)"},
            {"id": "spedup", "duration": 200, "title": "Song (sped up)"},
        ]
        ctx = self._patched(entries)
        try:
            # expected 200s; top is 4s off (within 7s tolerance) so it stays
            url = self._scraper()._select_youtube_match("ytsearch5:song", 200)
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=official"

    def test_falls_back_to_first_without_expected_duration(self):
        """No known duration keeps the top available result (legacy behavior)."""
        entries = [
            {"id": "first", "duration": 183, "title": "A"},
            {"id": "second", "duration": 127, "title": "B"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match("ytsearch5:x", None)
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=first"

    def test_returns_none_on_no_results(self):
        """An empty search returns None so the caller can fall through / fail."""
        ctx = self._patched([])
        try:
            url = self._scraper()._select_youtube_match("ytsearch5:nothing", 200)
        finally:
            ctx.stop()
        assert url is None

    def test_rejects_wrong_song_by_right_artist_close_duration(self):
        """The Mi Gente / Mi Chico failure mode (closes #52).

        Spotify says `Mi Gente` by `DJ Goja` is 114.8s. YouTube's top hit
        for that search is `Dj Goja - Mi Chico` at 117s - same artist,
        almost identical duration, completely different song. The prior
        duration-only matcher trusted the top hit and shipped Mi Chico
        audio under Mi Gente metadata. With title-and-artist matching,
        Mi Chico fails the title test, no other candidate has both `Mi
        Gente` AND `DJ Goja` in its YouTube title, so we return None and
        the user gets a clear `not found` instead of wrong audio.
        """
        entries = [
            {"id": "michico", "duration": 117, "title": "Dj Goja - Mi Chico (Official Video)"},
            {"id": "remix", "duration": 126, "title": "Mi Gente Remix by SkywiinPROD"},
            {"id": "balvin", "duration": 192, "title": "J Balvin Mi Gente (Bass Boost)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Mi Gente DJ Goja audio",
                expected_duration_s=114.8,
                expected_title="Mi Gente",
                expected_artists="DJ Goja",
            )
        finally:
            ctx.stop()
        assert url is None

    def test_picks_artist_and_title_match_over_artist_only(self):
        """Given the title-match passes for several candidates, prefer the
        one that also has the artist in the YouTube title."""
        entries = [
            {"id": "remix", "duration": 200, "title": "Blinding Lights Remix (by SomeoneElse)"},
            {"id": "right", "duration": 200, "title": "The Weeknd - Blinding Lights (Official)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Blinding Lights The Weeknd audio",
                expected_duration_s=200,
                expected_title="Blinding Lights",
                expected_artists="The Weeknd",
            )
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=right"

    def test_youtube_artist_song_format_doesnt_get_split(self):
        """Regression for an intermediate bug: an early variant-strip in
        the normalizer split `The Weeknd - Blinding Lights` into just
        `The Weeknd` and lost the song name, killing every legitimate
        match. The fix only strips variants from the Spotify side.
        """
        entries = [
            {"id": "yt", "duration": 200, "title": "The Weeknd - Blinding Lights (Official Audio)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Blinding Lights The Weeknd audio",
                expected_duration_s=200,
                expected_title="Blinding Lights",
                expected_artists="The Weeknd",
            )
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=yt"

    def test_strips_spotify_variant_suffix(self):
        """Spotify ` - Remastered YYYY` / ` - Live` / etc. shouldn't keep
        legitimate YouTube uploads from matching."""
        entries = [
            {"id": "queen", "duration": 354, "title": "Queen - Bohemian Rhapsody (Official Video)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Bohemian Rhapsody Queen audio",
                expected_duration_s=354,
                expected_title="Bohemian Rhapsody - Remastered 2011",
                expected_artists="Queen",
            )
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=queen"

    def test_rejects_when_only_match_has_wildly_wrong_duration(self):
        """Even when title+artist both match, a candidate that's >30s off
        the Spotify duration is almost certainly a live cover or extended
        edit; shipping it would still corrupt the user's library."""
        entries = [
            {"id": "live", "duration": 500, "title": "Queen - Bohemian Rhapsody (Live Aid 1985)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Bohemian Rhapsody Queen audio",
                expected_duration_s=354,
                expected_title="Bohemian Rhapsody",
                expected_artists="Queen",
            )
        finally:
            ctx.stop()
        assert url is None

    def test_handles_collaboration_artists_via_any_match(self):
        """For tracks with multiple artists (Spotify `Artist A, Artist B`),
        ANY of the artists appearing in the YouTube title is sufficient
        - YouTube uploads often credit only the primary artist in the title."""
        entries = [
            {"id": "fonsi", "duration": 228, "title": "Luis Fonsi - Despacito (Audio)"},
        ]
        ctx = self._patched(entries)
        try:
            url = self._scraper()._select_youtube_match(
                "ytsearch5:Despacito Luis Fonsi audio",
                expected_duration_s=228,
                expected_title="Despacito",
                expected_artists="Luis Fonsi, Daddy Yankee",
            )
        finally:
            ctx.stop()
        assert url == "https://www.youtube.com/watch?v=fonsi"

    def test_normalize_strips_apostrophes_without_creating_word_breaks(self):
        """`I'm Yours` -> `im yours` (not `i m yours`) so it matches a YT
        upload titled `Jason Mraz - I'm Yours`."""
        from Spotify_Downloader import MusicScraper

        assert MusicScraper._normalize_title("I'm Yours") == "im yours"
        assert MusicScraper._normalize_title("Don't Stop Me Now") == "dont stop me now"

    def test_normalize_strips_diacritics(self):
        """Café -> cafe (NFKD); MONTAGEM BAILÃO -> montagem bailao."""
        from Spotify_Downloader import MusicScraper

        assert MusicScraper._normalize_title("Café") == "cafe"
        assert MusicScraper._normalize_title("MONTAGEM BAILÃO") == "montagem bailao"
        assert MusicScraper._normalize_title("Beyoncé") == "beyonce"


class TestDetectImageMime:
    """Tests for _detect_image_mime image-format sniffing (closes #46).

    Spotify currently serves JPEG cover art but the writer code now sniffs
    the magic bytes so a future content-type change does not silently
    produce broken APIC / covr / Picture frames mis-tagged as JPEG.
    """

    def test_jpeg_magic(self):
        from Spotify_Downloader import _detect_image_mime

        # JPEG: every variant starts with FF D8 FF (JFIF / Exif / SOI markers)
        assert _detect_image_mime(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"
        assert _detect_image_mime(b"\xff\xd8\xff\xdb") == "image/jpeg"

    def test_png_magic(self):
        from Spotify_Downloader import _detect_image_mime

        # PNG: 8-byte signature per W3C spec section 5.2
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _detect_image_mime(png) == "image/png"

    def test_unknown_falls_back_to_jpeg(self):
        from Spotify_Downloader import _detect_image_mime

        # Anything we can't identify (a future webp/avif response, say) is
        # claimed as jpeg so we still hand the writer *something* coherent.
        assert _detect_image_mime(b"RIFF\x00\x00\x00\x00WEBP") == "image/jpeg"
        assert _detect_image_mime(b"") == "image/jpeg"


class TestMp3MetadataIsV23:
    """End-to-end verification that mp3 metadata writes are v2.3-compliant.

    Real mutagen + real file, not mocks: we want to catch a regression where
    the format byte slips back to v2.4 or the APIC encoding goes back to
    UTF-8 (both of which are what was being shipped pre-2.0.8 and broke cover
    display on iTunes / Windows Media Player / car head-units).
    """

    @staticmethod
    def _minimal_mp3(path):
        # MPEG-1 Layer III frame: sync + valid header + 417 zero bytes
        # (same trick used by other tests). Not playable but mutagen treats
        # it as a real mp3 for tag-write purposes. Seed an empty ID3v2 tag
        # so EasyID3 has something to read (the production path is fine
        # because yt-dlp + FFmpeg always emit a TSSE tag, but a freshly-
        # constructed fixture file has no header).
        from mutagen.id3 import ID3

        with open(path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 417)
        empty = ID3()
        empty.save(path)

    def test_writes_id3v23_header(self, tmp_path):
        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "v23.mp3")
        self._minimal_mp3(path)
        _write_metadata_mp3(
            path,
            {"title": "T", "artists": "A", "album": "Al", "releaseDate": "2025", "trackNumber": 1},
            None,
        )

        # First 5 bytes of an ID3 tag are "ID3" + major + minor.
        # We want major=3 (v2.3), not the mutagen default 4 (v2.4).
        with open(path, "rb") as f:
            head = f.read(5)
        assert head[:3] == b"ID3"
        assert head[3] == 3, f"expected ID3v2.3, got v2.{head[3]}"

    def test_apic_frame_v23_encoding(self, tmp_path):
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "apic.mp3")
        self._minimal_mp3(path)
        # Real JPEG header so the writer's sniffer picks image/jpeg.
        cover = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        _write_metadata_mp3(
            path,
            {
                "title": "T",
                "artists": "A",
                "album": "Al",
                "releaseDate": "2025",
                "trackNumber": 1,
            },
            cover,
        )

        id3 = ID3(path)
        assert id3.version[1] == 3, f"expected v2.3, got v2.{id3.version[1]}"
        apics = id3.getall("APIC")
        assert len(apics) == 1, "exactly one APIC frame should be written"
        apic = apics[0]
        assert apic.mime == "image/jpeg"
        assert apic.type == 3  # Cover (front) per the v2.3 enum
        assert apic.desc == "Cover"
        assert len(apic.data) == len(cover)
        # v2.3 only defines encoding 0 (Latin-1) and 1 (UTF-16+BOM).
        # encoding 3 (UTF-8) is the v2.4-only value that the pre-2.0.8
        # code was writing and that older players reject.
        assert apic.encoding in (0, 1), f"encoding {apic.encoding} is not v2.3-legal"

    def test_unicode_text_frames_roundtrip(self, tmp_path):
        """Non-ASCII titles/artists must survive the v2.3 downgrade."""
        from mutagen.easyid3 import EasyID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "unicode.mp3")
        self._minimal_mp3(path)
        _write_metadata_mp3(
            path,
            {
                "title": "MONTAGEM BAILÃO",
                "artists": "Tëst Ãrtist",
                "album": "Ålbüm",
                "releaseDate": "2025",
                "trackNumber": 7,
            },
            None,
        )

        audio = EasyID3(path)
        assert audio["title"][0] == "MONTAGEM BAILÃO"
        assert audio["artist"][0] == "Tëst Ãrtist"
        assert audio["album"][0] == "Ålbüm"
        assert audio["tracknumber"][0] == "7"

    def test_png_cover_writes_image_png_mime(self, tmp_path):
        """A PNG-magic cover must produce APIC mime=image/png, not jpeg."""
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "png.mp3")
        self._minimal_mp3(path)
        cover = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        _write_metadata_mp3(
            path,
            {
                "title": "T",
                "artists": "A",
                "album": "Al",
                "releaseDate": "2025",
                "trackNumber": 1,
            },
            cover,
        )

        apic = ID3(path).getall("APIC")[0]
        assert apic.mime == "image/png"


class TestFlacMetadata:
    """FLAC cover embedding, with a focus on idempotency.

    mutagen's add_picture() appends, so re-tagging a FLAC that already has a
    cover would stack duplicate Picture blocks. The writer calls
    clear_pictures() first; these tests lock that in (mp3/m4a replace covers
    in place via frame HashKey / atom assignment, so only flac needed it).
    """

    @staticmethod
    def _minimal_flac(path):
        # 'fLaC' + a single STREAMINFO block (type 0, last-block flag set).
        # No audio frames; mutagen parses it for tag-write purposes. Built by
        # hand so the test has no ffmpeg dependency in CI.
        import struct

        si = bytearray(34)
        si[0:2] = struct.pack(">H", 4096)  # min blocksize
        si[2:4] = struct.pack(">H", 4096)  # max blocksize
        # sample_rate(20b)=44100 | channels-1(3b)=1 | bps-1(5b)=15 | total_samples(36b)=0
        si[10:18] = struct.pack(">Q", (44100 << 44) | (1 << 41) | (15 << 36) | 0)
        header = bytes([0x80]) + struct.pack(">I", 34)[1:]  # last-block, type 0, 24-bit len
        with open(path, "wb") as f:
            f.write(b"fLaC" + header + bytes(si))

    def test_single_write_embeds_one_cover_and_tags(self, tmp_path):
        from mutagen.flac import FLAC

        from Spotify_Downloader import _write_metadata_flac

        path = str(tmp_path / "one.flac")
        self._minimal_flac(path)
        cover = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        _write_metadata_flac(
            path,
            {
                "title": "Sæson",
                "artists": "Sigur Rós",
                "album": "( )",
                "releaseDate": "2002",
                "trackNumber": 4,
            },
            cover,
        )

        audio = FLAC(path)
        assert audio["title"][0] == "Sæson"
        assert audio["artist"][0] == "Sigur Rós"
        assert audio["tracknumber"][0] == "4"
        assert len(audio.pictures) == 1
        assert audio.pictures[0].type == 3  # front cover
        assert audio.pictures[0].mime == "image/jpeg"

    def test_retag_stays_at_one_cover(self, tmp_path):
        from mutagen.flac import FLAC

        from Spotify_Downloader import _write_metadata_flac

        path = str(tmp_path / "twice.flac")
        self._minimal_flac(path)
        cover = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        tags = {
            "title": "T",
            "artists": "A",
            "album": "Al",
            "releaseDate": "2025",
            "trackNumber": 1,
        }
        _write_metadata_flac(path, tags, cover)
        _write_metadata_flac(path, tags, cover)

        assert len(FLAC(path).pictures) == 1, "re-tag must not stack duplicate covers"

    def test_no_cover_writes_tags_without_picture(self, tmp_path):
        from mutagen.flac import FLAC

        from Spotify_Downloader import _write_metadata_flac

        path = str(tmp_path / "nocover.flac")
        self._minimal_flac(path)
        _write_metadata_flac(path, {"title": "T", "artists": "A"}, None)

        audio = FLAC(path)
        assert audio["title"][0] == "T"
        assert len(audio.pictures) == 0


class TestWritingMetaTagsThread:
    """Tests for WritingMetaTagsThread synchronous cover fetch."""

    def test_meta_tags_written_to_file(self, tmp_path):
        """Verify ID3 tags are written correctly."""
        from Spotify_Downloader import WritingMetaTagsThread

        # Create a minimal valid MP3 file for mutagen
        mp3_path = str(tmp_path / "test.mp3")
        # Write a minimal MP3 frame header so mutagen can parse it
        with open(mp3_path, "wb") as f:
            # Minimal MP3 frame: sync word + valid header + padding
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 417)

        tags = {
            "title": "Test Song",
            "artists": "Test Artist",
            "album": "Test Album",
            "releaseDate": "2024-01-01",
            "cover": "",
            "file": mp3_path,
        }

        thread = WritingMetaTagsThread(tags, mp3_path)
        # Mock the signal
        thread.tags_success = MagicMock()

        with patch("Spotify_Downloader.EasyID3") as mock_easy:
            mock_audio = MagicMock()
            mock_easy.return_value = mock_audio
            thread.run()
            mock_audio.__setitem__.assert_any_call("title", "Test Song")
            mock_audio.__setitem__.assert_any_call("artist", "Test Artist")
            mock_audio.__setitem__.assert_any_call("album", "Test Album")
            mock_audio.save.assert_called()
            thread.tags_success.emit.assert_called_once_with("Tags added successfully")

    def test_cover_art_fetched_synchronously(self):
        """Verify cover art is downloaded synchronously, not via nested QThread."""
        from Spotify_Downloader import WritingMetaTagsThread

        tags = {
            "title": "Test",
            "artists": "Artist",
            "album": "Album",
            "releaseDate": "2024",
            "cover": "https://example.com/cover.jpg",
            "file": "/tmp/test.mp3",
        }

        thread = WritingMetaTagsThread(tags, "/tmp/test.mp3")
        thread.tags_success = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\x89PNG\r\n\x1a\n"  # Fake image data

        with (
            patch("Spotify_Downloader.EasyID3") as mock_easy,
            patch("Spotify_Downloader.ID3") as mock_id3,
            patch("Spotify_Downloader.requests.get", return_value=mock_response) as mock_get,
        ):
            mock_easy.return_value = MagicMock()
            mock_id3.return_value = MagicMock()
            thread.run()

            # Verify synchronous requests.get was called (not DownloadCover QThread)
            mock_get.assert_called_once_with("https://example.com/cover.jpg", timeout=15)
            # Verify APIC frame was added via id3.add(APIC(...)) and the tag
            # was saved as v2.3 for max player compatibility (closes #46)
            mock_id3.return_value.add.assert_called_once()
            mock_id3.return_value.save.assert_called_with(v2_version=3)
            thread.tags_success.emit.assert_called_once_with("Tags added successfully")

    def test_cover_art_failure_does_not_crash(self):
        """Verify cover art failure is handled gracefully."""
        from Spotify_Downloader import WritingMetaTagsThread

        tags = {
            "title": "Test",
            "artists": "Artist",
            "album": "",
            "releaseDate": "",
            "cover": "https://example.com/bad-cover.jpg",
            "file": "/tmp/test.mp3",
        }

        thread = WritingMetaTagsThread(tags, "/tmp/test.mp3")
        thread.tags_success = MagicMock()

        with (
            patch("Spotify_Downloader.EasyID3") as mock_easy,
            patch(
                "Spotify_Downloader.requests.get",
                side_effect=requests.RequestException("timeout"),
            ),
        ):
            mock_easy.return_value = MagicMock()
            thread.run()
            # Should still emit success (tags were written, just cover failed)
            thread.tags_success.emit.assert_called_once_with("Tags added successfully")


class TestStopButtonCooperative:
    """Tests for cooperative stop button behavior."""

    def test_cancel_event_stops_playlist_iteration(self):
        """Verify cancel event halts playlist download loop."""
        from Spotify_Downloader import MusicScraper

        cancel_event = threading.Event()
        scraper = MusicScraper(cancel_event=cancel_event)

        # Set cancel before scraping
        cancel_event.set()
        assert scraper.is_cancelled() is True

    def test_scraper_thread_request_cancel(self):
        """Verify ScraperThread.request_cancel sets the event."""
        from Spotify_Downloader import ScraperThread

        thread = ScraperThread("https://open.spotify.com/playlist/abc123")
        assert not thread._cancel_event.is_set()
        thread.request_cancel()
        assert thread._cancel_event.is_set()


class TestScraperThread:
    """Tests for ScraperThread class."""

    def test_init_defaults(self):
        """Test ScraperThread initialization."""
        from Spotify_Downloader import ScraperThread

        thread = ScraperThread("https://open.spotify.com/playlist/abc123")
        assert thread.spotify_link == "https://open.spotify.com/playlist/abc123"
        assert "music" in thread.music_folder

    def test_init_custom_folder(self, tmp_path):
        """Test ScraperThread with custom folder."""
        from Spotify_Downloader import ScraperThread

        folder = str(tmp_path)
        thread = ScraperThread("https://open.spotify.com/playlist/abc123", folder)
        assert thread.music_folder == folder


class TestParallelDownloads:
    """Tests for parallel track download behavior (issue #34)."""

    def _make_track(self, tid, title, artists="Artist"):
        """Build a minimal TrackInfo-like object for tests."""
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id=tid,
            title=title,
            artists=artists,
            album=None,
            release_date=None,
            cover_url=None,
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def test_max_workers_default_is_four(self):
        """Default parallel worker count matches measured sweet spot."""
        from Spotify_Downloader import MusicScraper

        assert MusicScraper.MAX_WORKERS == 4

    def test_counter_increment_is_thread_safe(self):
        """Parallel increment_counter calls produce correct total with no races."""
        import concurrent.futures

        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        # Stub the signal so we don't need a QApplication for this test
        scraper.count_updated = MagicMock()

        iterations = 1000
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda _: scraper.increment_counter(), range(iterations)))

        assert scraper.counter == iterations

    def test_failed_tracks_append_is_thread_safe(self):
        """Parallel appends to _failed_tracks don't lose entries."""
        import concurrent.futures

        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()

        def append_one(i):
            with scraper._failed_lock:
                scraper._failed_tracks.append(f"track_{i}")

        n = 500
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(append_one, range(n)))

        assert len(scraper._failed_tracks) == n

    def test_small_playlist_stays_sequential(self, tmp_path):
        """Playlists under the parallel threshold (3 tracks) run on one thread."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(2)]
        seen_workers: set[str] = set()

        def fake_download(query, dest, **_kw):
            seen_workers.add(threading.current_thread().name)
            open(dest, "wb").close()
            return dest

        scraper.download_track_audio = fake_download
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc123", str(tmp_path))

        # All 2 downloads happened on the main test thread — no pool spawned
        assert seen_workers == {threading.current_thread().name}
        assert scraper._parallel_mode is False

    def test_parallel_playlist_uses_max_workers_threads(self, tmp_path):
        """Playlists >= threshold actually spawn MAX_WORKERS distinct threads."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(8)]
        seen_workers: set[str] = set()
        barrier = threading.Barrier(MusicScraper.MAX_WORKERS, timeout=5)

        def fake_download(query, dest, **_kw):
            seen_workers.add(threading.current_thread().name)
            # Block until MAX_WORKERS threads have arrived concurrently. Proves
            # the pool really spawned that many threads in parallel.
            with contextlib.suppress(threading.BrokenBarrierError):
                barrier.wait()
            open(dest, "wb").close()
            return dest

        scraper.download_track_audio = fake_download
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc123", str(tmp_path))

        # With 8 tracks and MAX_WORKERS=4, exactly 4 unique worker threads ran
        assert len(seen_workers) == MusicScraper.MAX_WORKERS
        # Main test thread did not participate in downloads (pool ran them all)
        assert threading.current_thread().name not in seen_workers

    def test_exception_in_one_worker_does_not_abort_others(self, tmp_path):
        """A failure on one track must not prevent other tracks from finishing."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(5)]
        completed = []

        def fake_download(query, dest, **_kw):
            if "Song 2" in query:
                raise RuntimeError("simulated yt-dlp failure")
            open(dest, "wb").close()
            completed.append(dest)
            return dest

        scraper.download_track_audio = fake_download
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc123", str(tmp_path))
        # 4 tracks downloaded, 1 failed
        assert len(completed) == 4
        assert "Song 2" in scraper._failed_tracks

    def test_generator_is_materialized_before_threading(self, tmp_path):
        """Generator is fully consumed on the main thread before worker submission."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        main_thread_id = threading.get_ident()
        iter_threads = []

        def recording_generator():
            for i in range(4):
                iter_threads.append(threading.get_ident())
                yield self._make_track(f"id{i}", f"Song {i}")

        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = recording_generator()
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))
        # Every yield should have come from the main thread (materialization)
        assert all(tid == main_thread_id for tid in iter_threads)
        assert len(iter_threads) == 4

    def test_cancel_before_threading_exits_early(self, tmp_path):
        """Cancel set before worker pool starts prevents any downloads."""
        from Spotify_Downloader import MusicScraper

        cancel_event = threading.Event()
        scraper = MusicScraper(cancel_event=cancel_event)
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(10)]

        downloads = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            downloads.append(d),
            open(d, "wb").close(),
            d,
        )[2]
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta

        def gen():
            yield from tracks

        mock_api.iter_playlist_tracks.return_value = gen()
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        cancel_event.set()  # Cancel before call
        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))
        # No downloads should have started
        assert len(downloads) == 0

    def test_existing_files_are_skipped_in_parallel_mode(self, tmp_path):
        """Already-downloaded tracks aren't re-downloaded when parallelism is on."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        playlist_folder = tmp_path / "T"
        playlist_folder.mkdir()

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(4)]
        # Pre-create files for tracks 0 and 2 (default include_track_number=False
        # keeps the historical `Title - Artist.mp3` shape)
        for i in (0, 2):
            (playlist_folder / f"Song {i} - Artist.mp3").touch()

        downloaded = []

        def fake_dl(q, d, **_kw):
            downloaded.append(d)
            open(d, "wb").close()
            return d

        scraper.download_track_audio = fake_dl
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"
        scraper.prepare_playlist_folder = lambda _base, _name: str(playlist_folder)

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))
        # Only tracks 1 and 3 should have triggered a download
        assert len(downloaded) == 2

    def test_state_resets_between_playlist_runs(self, tmp_path):
        """counter, _failed_tracks, and _in_flight_files clear on each scrape_playlist call.

        Audit fix H3: repeated use of the same MusicScraper must not carry
        stale counter or failure state.
        """
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        # Pre-populate with junk state as if a prior run left residue
        scraper.counter = 42
        scraper._failed_tracks = ["old_failure"]
        scraper._in_flight_files = {"/tmp/old_file.mp3"}

        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track("id1", "Song A")]
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))

        # Stale state must be gone; counter reflects only this run
        assert scraper.counter == 1
        assert "old_failure" not in scraper._failed_tracks
        assert "/tmp/old_file.mp3" not in scraper._in_flight_files

    def test_filename_collision_produces_unique_files(self, tmp_path):
        """Two tracks that sanitize to the same filename get unique paths.

        Audit fix M1: parallel downloads can't TOCTOU-race into the same file.
        """
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        # Simulate concurrent claim: first worker holds the filename, second
        # must get a suffixed path.
        playlist_folder = tmp_path / "T"
        playlist_folder.mkdir()

        tracks = [
            self._make_track("id_a", "Song", "Artist"),
            self._make_track("id_b", "Song", "Artist"),
        ]

        claimed_paths = []

        def slow_download(query, dest, **_kw):
            # Both workers hit this. Record which path each one claimed, then
            # create the file.
            claimed_paths.append(dest)
            open(dest, "wb").close()
            return dest

        scraper.download_track_audio = slow_download
        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"
        scraper.prepare_playlist_folder = lambda _base, _name: str(playlist_folder)

        # 2 tracks stays on sequential path; force parallel by calling
        # _download_one_track directly with both tracks from workers.
        scraper._parallel_mode = True
        scraper._total_tracks = 2

        # Pre-claim the filename as if worker A got there first.
        # Default include_track_number=False, so filenames keep the
        # historical `Title - Artist.mp3` shape.
        base_name = "Song - Artist.mp3"
        base_path = os.path.join(str(playlist_folder), base_name)
        with scraper._filename_lock:
            scraper._in_flight_files.add(base_path)

        # Worker B arrives - should get a suffixed filename
        scraper._download_one_track(tracks[1], str(playlist_folder), None)

        assert len(claimed_paths) == 1
        claimed = claimed_paths[0]
        assert claimed != base_path
        assert "[id_b]" in claimed

    def test_parallel_mode_emits_song_meta_per_track(self, tmp_path):
        """In parallel mode, song_meta IS emitted per track.

        Previously suppressed to avoid label flicker, but an empty Song
        Information panel looked like a bug. Now the label races between
        workers and shows whichever track most recently started, which is
        fine. add_song_meta still fires for ID3 tag writing.
        """
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(4)]
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))

        # 4 tracks >= 3 threshold, parallel mode. song_meta now emits per
        # track so the preview panel reflects active work. add_song_meta
        # still fires per track for ID3 tag writing.
        assert scraper.song_meta.emit.call_count == 4
        assert scraper.add_song_meta.emit.call_count == 4

    def test_parallel_mode_aggregate_progress_emits(self, tmp_path):
        """In parallel mode, dlprogress emits aggregate completion, not per-byte.

        Audit fix H1: progress bar can't jitter because we emit counter/total
        once per completion instead of per-worker per-byte.
        """
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

        tracks = [self._make_track(f"id{i}", f"Song {i}") for i in range(4)]
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "T"
        meta.owner = "O"
        meta.cover_url = None
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "T"

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))

        # Each completion should emit exactly one aggregate progress value.
        # Monotonically non-decreasing. Last value should be 100.
        emitted_values = [c.args[0] for c in scraper.dlprogress_signal.emit.call_args_list]
        assert len(emitted_values) == 4  # one per track
        assert emitted_values == sorted(emitted_values)  # monotonic
        assert emitted_values[-1] == 100


class TestMainWindow:
    """Tests for MainWindow class (limited - requires QApplication)."""

    def test_get_default_download_path_returns_string(self):
        """Test default download path is a string."""
        # This test is limited since MainWindow requires QApplication
        # Just test the logic would produce a valid path format
        home = os.path.expanduser("~")
        expected_contains = os.path.join(home, "Music", "Sunnify")
        # The path should be under user's home
        assert home in expected_contains


class TestCoverEnrichment:
    """Tests for per-track cover art enrichment (fixes #31).

    Playlist embed trackList does not include per-track cover urls; without
    enrichment every track would fall back to default_cover_url (the playlist
    cover) and end up with the same artwork. These tests lock in that the
    worker calls get_track when cover_url is missing, uses the enriched
    release_date too, and falls back gracefully on enrichment failure.
    """

    def _track(self, tid="id1", cover=None, release_date=None):
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id=tid,
            title="Song",
            artists="Artist",
            album=None,
            release_date=release_date,
            cover_url=cover,
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def _stub_scraper_signals(self, scraper):
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

    def test_missing_cover_triggers_enrichment(self, tmp_path):
        """Track with cover_url=None causes a get_track call for the real cover."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        self._stub_scraper_signals(scraper)
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        enriched = self._track(cover="https://real/cover.jpg", release_date="2024-06-01")
        mock_api.get_track.return_value = enriched
        scraper.spotifydown_api = mock_api

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta)

        scraper._download_one_track(
            self._track(cover=None), str(tmp_path), "fallback-playlist-cover"
        )
        assert captured[0]["cover"] == "https://real/cover.jpg"
        assert captured[0]["releaseDate"] == "2024-06-01"
        mock_api.get_track.assert_called_once_with("id1")

    def test_existing_cover_skips_enrichment(self, tmp_path):
        """Track that already has cover_url (e.g. spclient fallback path) does
        not trigger a second network call."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        self._stub_scraper_signals(scraper)
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        scraper.spotifydown_api = mock_api

        scraper._download_one_track(
            self._track(cover="https://already/present.jpg"),
            str(tmp_path),
            "fallback",
        )
        mock_api.get_track.assert_not_called()

    def test_enrichment_failure_falls_back_to_playlist_cover(self, tmp_path):
        """If get_track raises, the worker silently falls back to default_cover_url."""
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import SpotifyDownAPIError

        scraper = MusicScraper()
        self._stub_scraper_signals(scraper)
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        mock_api.get_track.side_effect = SpotifyDownAPIError("offline")
        scraper.spotifydown_api = mock_api

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta)

        scraper._download_one_track(
            self._track(cover=None), str(tmp_path), "playlist-cover-fallback"
        )
        assert captured[0]["cover"] == "playlist-cover-fallback"

    def test_no_enrichment_when_cancelled(self, tmp_path):
        """Cancel set before worker runs skips enrichment + download entirely."""
        from Spotify_Downloader import MusicScraper

        cancel = threading.Event()
        scraper = MusicScraper(cancel_event=cancel)
        self._stub_scraper_signals(scraper)
        scraper.download_track_audio = MagicMock()

        mock_api = MagicMock()
        scraper.spotifydown_api = mock_api

        cancel.set()
        result = scraper._download_one_track(self._track(cover=None), str(tmp_path), "fallback")
        assert result is None
        mock_api.get_track.assert_not_called()
        scraper.download_track_audio.assert_not_called()

    def test_enrichment_preserves_existing_release_date(self, tmp_path):
        """If the track already has release_date, enrichment shouldn't clobber it."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        self._stub_scraper_signals(scraper)
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        mock_api = MagicMock()
        enriched = self._track(cover="https://real/cover.jpg", release_date="2020-01-01")
        mock_api.get_track.return_value = enriched
        scraper.spotifydown_api = mock_api

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta)

        original = self._track(cover=None, release_date="2024-12-31")
        scraper._download_one_track(original, str(tmp_path), "fallback")
        assert captured[0]["releaseDate"] == "2024-12-31"


class TestTrackNumberMetadata:
    """Tests that track_num flows into song_meta and gets written to ID3."""

    def _track(self, tid="t1"):
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id=tid,
            title="Title",
            artists="Artist",
            album="Album",
            release_date="2024-01-01",
            cover_url="https://x/y.jpg",
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def test_track_num_in_song_meta(self, tmp_path):
        """_download_one_track threads track_num into the emitted song_meta."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())
        scraper.download_track_audio = lambda _q, d, **_kw: open(d, "wb").close() or d

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta)

        scraper._download_one_track(self._track(), str(tmp_path), "", track_num=7)
        assert captured[0]["trackNumber"] == 7

    def test_writingmetatagsthread_writes_tracknumber(self, tmp_path, mocker):
        """WritingMetaTagsThread writes trackNumber to ID3 when present."""
        from Spotify_Downloader import WritingMetaTagsThread

        # Mock EasyID3/ID3 so we can inspect what was written without a real mp3
        mock_easy = mocker.MagicMock()
        mocker.patch("Spotify_Downloader.EasyID3", return_value=mock_easy)
        mocker.patch(
            "Spotify_Downloader.requests.get",
            return_value=mocker.MagicMock(status_code=200, content=b""),
        )

        tags = {
            "title": "T",
            "artists": "A",
            "album": "Al",
            "releaseDate": "2024-05-01",
            "trackNumber": 5,
            "cover": "",
        }
        thread = WritingMetaTagsThread(tags, str(tmp_path / "fake.mp3"))
        thread.tags_success = MagicMock()
        thread.run()
        mock_easy.__setitem__.assert_any_call("tracknumber", "5")

    def test_writingmetatagsthread_skips_tracknumber_when_zero(self, tmp_path, mocker):
        """trackNumber=0 (unset) should not write a tag."""
        from Spotify_Downloader import WritingMetaTagsThread

        mock_easy = mocker.MagicMock()
        mocker.patch("Spotify_Downloader.EasyID3", return_value=mock_easy)
        mocker.patch(
            "Spotify_Downloader.requests.get",
            return_value=mocker.MagicMock(status_code=200, content=b""),
        )

        tags = {
            "title": "T",
            "artists": "A",
            "album": "",
            "releaseDate": "",
            "trackNumber": 0,
            "cover": "",
        }
        thread = WritingMetaTagsThread(tags, str(tmp_path / "fake.mp3"))
        thread.tags_success = MagicMock()
        thread.run()
        # Confirm tracknumber was NOT written
        calls = [c for c in mock_easy.__setitem__.call_args_list if c.args[0] == "tracknumber"]
        assert len(calls) == 0


class TestTrackNumberInFilename:
    """Tests for the include_track_number filename-prefix option.

    Filename order must match playlist order in file managers (which sort
    alphabetically). Zero-padding (`01.` not `1.`) is what makes that work
    past nine tracks, so both the primary and the collision-guard paths
    pad consistently.
    """

    def _track(self, tid="t1"):
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id=tid,
            title="Title",
            artists="Artist",
            album="Album",
            release_date="2024-01-01",
            cover_url=None,
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def _stub(self, scraper):
        for sig in (
            "song_meta",
            "add_song_meta",
            "dlprogress_signal",
            "Resetprogress_signal",
            "PlaylistID",
            "song_Album",
            "PlaylistCompleted",
            "error_signal",
            "count_updated",
        ):
            setattr(scraper, sig, MagicMock())

    def test_default_off_keeps_legacy_filename(self, tmp_path):
        """Default is opt-out: `Title - Artist.mp3`, same as before this feature."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        assert scraper.include_track_number is False
        self._stub(scraper)
        captured = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            (
                captured.append(d),
                open(d, "wb").close(),
            )
            and d
        )

        scraper._download_one_track(self._track(), str(tmp_path), "", track_num=3)
        assert captured[0].endswith("Title - Artist.mp3")
        assert "03." not in os.path.basename(captured[0])

    def test_enabled_writes_padded_prefix(self, tmp_path):
        """When the user opts in, filenames get the zero-padded `NN. ` prefix."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(include_track_number=True)
        self._stub(scraper)
        captured = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            (
                captured.append(d),
                open(d, "wb").close(),
            )
            and d
        )

        scraper._download_one_track(self._track(), str(tmp_path), "", track_num=3)
        assert captured[0].endswith("03. Title - Artist.mp3")

    def test_uses_track_position_over_enumerate_idx(self, tmp_path):
        """Regression for #51 - the scrape_playlist loop must use
        track.position (the canonical playlist position) over enumerate
        idx (the yield order). On >100-track playlists those diverge
        because spclient yields in HTTP-completion order; the bug was
        that filenames numbered 101+ matched yield-order not playlist
        order, so a file named '113. ON FIRE.mp3' was actually playlist
        position 112.
        """
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import TrackInfo

        # Simulate a 4-track yield where positions don't match enumerate
        # idx: yield-1 has position 4, yield-2 has position 1, etc.
        def trk(tid, position):
            return TrackInfo(
                id=tid,
                title=f"T{tid}",
                artists="A",
                album=None,
                release_date=None,
                cover_url=None,
                duration_ms=None,
                preview_url=None,
                raw={},
                position=position,
            )

        # Yield order != playlist order (the bug shape on >100 tracks).
        yielded_tracks = [
            trk("d", 4),
            trk("a", 1),
            trk("c", 3),
            trk("b", 2),
        ]

        scraper = MusicScraper(include_track_number=True)
        self._stub(scraper)
        captured = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            (
                captured.append(d),
                open(d, "wb").close(),
            )
            and d
        )

        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "PL"
        meta.owner = "O"
        meta.cover_url = None
        meta.track_count = 4
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(yielded_tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "PL"
        # Single-worker so the order is deterministic and the assertion
        # below maps cleanly to yield-order; the position assignment
        # logic under test is identical in the parallel branch (same
        # `_track_num_for` helper) so single-thread coverage is enough.
        scraper.MAX_WORKERS = 1
        scraper.prepare_playlist_folder = lambda _b, _n: str(tmp_path)

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))

        names = sorted(os.path.basename(p) for p in captured)
        # Each file's NN prefix must equal its track's *position*, not its
        # yield index. So track 'a' (yielded second, position 1) -> 01.;
        # track 'b' (yielded fourth, position 2) -> 02.; etc.
        assert names == [
            "01. Ta - A.mp3",
            "02. Tb - A.mp3",
            "03. Tc - A.mp3",
            "04. Td - A.mp3",
        ]

    def test_falls_back_to_enumerate_when_position_is_none(self, tmp_path):
        """If a track has no position (e.g. albums, very small playlists
        where TrackInfo wasn't stamped), the loop falls back to enumerate
        idx so we don't regress the existing behaviour for those cases."""
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import TrackInfo

        def trk(tid):
            return TrackInfo(
                id=tid,
                title=f"T{tid}",
                artists="A",
                album=None,
                release_date=None,
                cover_url=None,
                duration_ms=None,
                preview_url=None,
                raw={},
                # position deliberately left as None
            )

        yielded = [trk("x"), trk("y"), trk("z")]

        scraper = MusicScraper(include_track_number=True)
        self._stub(scraper)
        captured = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            (
                captured.append(d),
                open(d, "wb").close(),
            )
            and d
        )

        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "PL"
        meta.owner = "O"
        meta.cover_url = None
        meta.track_count = 3
        mock_api.get_playlist_metadata.return_value = meta
        mock_api.iter_playlist_tracks.return_value = iter(yielded)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "PL"
        scraper.MAX_WORKERS = 1
        scraper.prepare_playlist_folder = lambda _b, _n: str(tmp_path)

        scraper.scrape_playlist("https://open.spotify.com/playlist/abc", str(tmp_path))

        names = sorted(os.path.basename(p) for p in captured)
        # No track.position -> filename prefix equals enumerate idx.
        assert names == ["01. Tx - A.mp3", "02. Ty - A.mp3", "03. Tz - A.mp3"]

    def test_collision_path_pads_consistently(self, tmp_path):
        """When a name collides, the `[id]` suffix variant must also be `NN. `-padded.

        Without this, the same playlist mixes `03. Foo - Bar.mp3` with
        `3. Foo - Bar [id].mp3`, which sorts wrong and looks broken.
        """
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(include_track_number=True)
        self._stub(scraper)
        # Pretend the primary name is already claimed by a sibling worker
        primary = str(tmp_path / "03. Title - Artist.mp3")
        scraper._in_flight_files.add(primary)
        captured = []
        scraper.download_track_audio = lambda _q, d, **_kw: (
            (
                captured.append(d),
                open(d, "wb").close(),
            )
            and d
        )

        scraper._download_one_track(self._track(tid="abc"), str(tmp_path), "", track_num=3)
        assert captured[0].endswith("03. Title - Artist [abc].mp3")

    def test_non_bool_config_falls_back_to_default(self):
        """Bool validation in load_config must reject non-bool values (defensive)."""
        from Spotify_Downloader import load_config

        # We can't easily exercise the file path here, but the validation
        # branch itself is small enough to exercise via construction:
        scraper_cls_args = ["yes", "no", 1, 0, "true", None]
        from Spotify_Downloader import MusicScraper

        for v in scraper_cls_args:
            s = MusicScraper(include_track_number=v)
            assert isinstance(s.include_track_number, bool)
        # And load_config returns a defaults dict; sanity-check the bool key
        cfg = load_config()
        assert isinstance(cfg["include_track_number"], bool)


class TestSettingsDialog:
    """Construction tests for the Settings dialog.

    These exist because the dialog mixes QHBoxLayout (download-folder row)
    with QWidget (the rest), and a single forgotten `addLayout` vs
    `addWidget` dispatch crashes on open. Headless construction is enough
    to catch the regression class because QFormLayout / QVBoxLayout do
    their type-checking at addRow/addWidget time.
    """

    def test_opens_with_default_config(self, qapp):
        from Spotify_Downloader import SettingsDialog

        # Same shape as load_config()'s defaults dict.
        cfg = {
            "download_path": None,
            "format": "mp3",
            "quality": "192",
            "include_track_number": False,
        }
        dlg = SettingsDialog(None, cfg)
        # If construction got past the layout assembly, the bug class
        # (QHBoxLayout passed to addWidget) cannot fire.
        assert dlg.sizeHint().width() > 0

    def test_opens_with_track_number_on_and_lossless_format(self, qapp):
        """Cover the cells the default-config test doesn't hit: every combo
        of the on/off track-number toggle x lossy/lossless format gets a
        slightly different rendering pass (the lossless branch disables
        the bitrate combo)."""
        from Spotify_Downloader import SettingsDialog

        for cfg in (
            {
                "download_path": "/tmp",
                "format": "flac",
                "quality": "320",
                "include_track_number": True,
            },
            {
                "download_path": "/tmp",
                "format": "wav",
                "quality": "256",
                "include_track_number": False,
            },
            {
                "download_path": "/tmp",
                "format": "m4a",
                "quality": "128",
                "include_track_number": True,
            },
            {
                "download_path": "/tmp",
                "format": "opus",
                "quality": "192",
                "include_track_number": False,
            },
        ):
            dlg = SettingsDialog(None, cfg)
            assert dlg.sizeHint().width() > 0, f"size hint should be positive for {cfg}"

    def test_result_config_round_trips_every_key(self, qapp):
        """The dialog's result_config() must return every key load_config()
        produced, so saving doesn't drop the new include_track_number key."""
        from Spotify_Downloader import SettingsDialog

        cfg = {
            "download_path": "/tmp/sunnify-music",
            "format": "m4a",
            "quality": "256",
            "include_track_number": True,
        }
        dlg = SettingsDialog(None, cfg)
        out = dlg.result_config()
        assert out["format"] == "m4a"
        assert out["quality"] == "256"
        assert out["include_track_number"] is True
        assert out["download_path"] == "/tmp/sunnify-music"


class TestLogging:
    """Tests for the per-user logging setup."""

    def test_log_dir_macos(self, tmp_path):
        from Spotify_Downloader import _log_dir

        with (
            patch("sys.platform", "darwin"),
            patch("os.path.expanduser", return_value=str(tmp_path)),
        ):
            assert _log_dir() == os.path.join(str(tmp_path), "Library", "Logs", "Sunnify")

    def test_log_dir_windows(self, tmp_path):
        from Spotify_Downloader import _log_dir

        with (
            patch("sys.platform", "win32"),
            patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}),
        ):
            assert _log_dir() == os.path.join(str(tmp_path), "Sunnify", "logs")

    def test_log_dir_linux_xdg(self, tmp_path):
        from Spotify_Downloader import _log_dir

        with (
            patch("sys.platform", "linux"),
            patch.dict(os.environ, {"XDG_STATE_HOME": str(tmp_path)}),
        ):
            assert _log_dir() == os.path.join(str(tmp_path), "sunnify", "logs")

    def test_setup_logging_writes_session_header_and_is_idempotent(self, tmp_path):
        import Spotify_Downloader as S

        log_path = str(tmp_path / "sunnify.log")
        with patch.object(S, "log_file_path", return_value=log_path):
            try:
                p1 = S.setup_logging()
                p2 = S.setup_logging()  # second call must not double-attach
                assert p1 == p2 == log_path
                handlers = [h for h in S.log.handlers if getattr(h, "_sunnify", False)]
                assert len(handlers) == 1
                S.log.info("probe-line")
                for h in handlers:
                    h.flush()
                content = (tmp_path / "sunnify.log").read_text(encoding="utf-8")
                assert "sunnify session start" in content
                assert "probe-line" in content
            finally:
                # don't leak the file handler into other tests
                for h in [h for h in S.log.handlers if getattr(h, "_sunnify", False)]:
                    h.close()
                    S.log.removeHandler(h)

    @staticmethod
    def _teardown_logging(S, prev_hook=None, prev_thook=None):
        if prev_hook is not None:
            sys.excepthook = prev_hook
        if prev_thook is not None:
            threading.excepthook = prev_thook
        for h in [h for h in S.log.handlers if getattr(h, "_sunnify", False)]:
            h.close()
            S.log.removeHandler(h)

    def test_crash_handlers_are_installed(self, tmp_path):
        import faulthandler

        import Spotify_Downloader as S

        prev_hook, prev_thook = sys.excepthook, threading.excepthook
        with patch.object(S, "log_file_path", return_value=str(tmp_path / "sunnify.log")):
            try:
                S.setup_logging()
                assert sys.excepthook is S._log_excepthook
                assert threading.excepthook is S._thread_excepthook
                assert faulthandler.is_enabled()
                assert (tmp_path / "crash.log").exists()  # sibling of sunnify.log
            finally:
                self._teardown_logging(S, prev_hook, prev_thook)

    def test_uncaught_exception_is_logged(self, tmp_path):
        import Spotify_Downloader as S

        prev_hook, prev_thook = sys.excepthook, threading.excepthook
        with patch.object(S, "log_file_path", return_value=str(tmp_path / "sunnify.log")):
            try:
                S.setup_logging()
                try:
                    raise RuntimeError("kaboom-test")
                except RuntimeError:
                    with patch("sys.stderr", None):  # skip the noisy default hook
                        sys.excepthook(*sys.exc_info())
                for h in [h for h in S.log.handlers if getattr(h, "_sunnify", False)]:
                    h.flush()
                content = (tmp_path / "sunnify.log").read_text(encoding="utf-8")
                assert "CRITICAL" in content
                assert "uncaught exception" in content
                assert "kaboom-test" in content
                assert "Traceback" in content
            finally:
                self._teardown_logging(S, prev_hook, prev_thook)

    def test_track_download_failure_is_logged(self, tmp_path):
        from types import SimpleNamespace

        import Spotify_Downloader as S

        with patch.object(S, "log_file_path", return_value=str(tmp_path / "sunnify.log")):
            try:
                S.setup_logging()
                scraper = S.MusicScraper()
                track = SimpleNamespace(
                    title="Some Song",
                    artists="Some Artist",
                    id="xyz",
                    cover_url="",
                    release_date="",
                    duration_ms=200000,
                    album="Alb",
                )
                with patch.object(
                    scraper, "download_track_audio", side_effect=Exception("yt failed")
                ):
                    ret = scraper._download_one_track(track, str(tmp_path), "http://c", track_num=1)
                assert ret == "Some Song"  # failed track surfaced to caller
                for h in [h for h in S.log.handlers if getattr(h, "_sunnify", False)]:
                    h.flush()
                content = (tmp_path / "sunnify.log").read_text(encoding="utf-8")
                assert "WARNING" in content
                assert "track failed" in content
                assert "Some Song" in content
                assert "yt failed" in content  # the real underlying error, surfaced
            finally:
                self._teardown_logging(S)

    def test_silent_download_failure_logs_real_reason(self, tmp_path):
        """The ignoreerrors blind spot: a download that produces no file WITHOUT
        raising must still record yt-dlp's real reason, not a generic message."""
        import Spotify_Downloader as S

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, url, download=False):
                if not download:  # the search
                    return {"entries": [{"id": "v1", "title": "Song X Artist Y", "duration": 100}]}
                # the download: report to yt-dlp's logger, produce no file, don't raise
                lg = self.opts.get("logger")
                if lg:
                    lg.error("ERROR: [youtube] v1: Sign in to confirm you're not a bot")
                return None

        scraper = S.MusicScraper()
        with (
            patch.object(S, "log_file_path", return_value=str(tmp_path / "sunnify.log")),
            patch.object(S, "get_ffmpeg_path", return_value=str(tmp_path)),
        ):
            try:
                S.setup_logging()
                with patch.object(S, "YoutubeDL", FakeYDL), pytest.raises(RuntimeError):
                    scraper.download_track_audio(
                        "Song X Artist Y",
                        str(tmp_path / "out.mp3"),
                        expected_duration_s=100,
                        expected_title="Song X",
                        expected_artists="Artist Y",
                    )
                for h in [h for h in S.log.handlers if getattr(h, "_sunnify", False)]:
                    h.flush()
                content = (tmp_path / "sunnify.log").read_text(encoding="utf-8")
                assert "produced no file" in content
                # the REAL cause is captured, not hidden by ignoreerrors
                assert "Sign in to confirm you're not a bot" in content
            finally:
                self._teardown_logging(S)


class TestUpdateCheck:
    """Version comparison + the GitHub release check that drives the update toast."""

    def test_parse_version_variants(self):
        from Spotify_Downloader import _parse_version

        assert _parse_version("2.0.13") == (2, 0, 13)
        assert _parse_version("v2.0.13") == (2, 0, 13)
        assert _parse_version("2.0.13-beta") == (2, 0, 13)
        assert _parse_version("garbage") == ()
        assert _parse_version("") == ()

    @pytest.mark.parametrize(
        "latest,current,expected",
        [
            ("2.0.13", "2.0.12", True),  # normal upgrade
            ("v2.0.13", "2.0.12", True),  # v-prefixed tag
            ("2.0.12", "2.0.12", False),  # same -> no toast
            ("2.0.12", "2.0.13", False),  # dev ahead of release
            ("2.1.0", "2.0.99", True),  # minor bump
            ("2.0.2", "2.0.10", False),  # numeric, not lexical (2 < 10)
            ("2.0.10", "2.0.2", True),
            ("garbage", "2.0.12", False),  # malformed tag -> no crash, no toast
            ("", "2.0.12", False),
        ],
    )
    def test_is_newer_version(self, latest, current, expected):
        from Spotify_Downloader import _is_newer_version

        assert _is_newer_version(latest, current) is expected

    def test_check_for_update_returns_tuple_when_newer(self):
        from Spotify_Downloader import _check_for_update

        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "tag_name": "v2.0.13",
            "html_url": "https://github.com/x/releases/tag/v2.0.13",
        }
        with patch("Spotify_Downloader.requests.get", return_value=resp):
            assert _check_for_update("2.0.12") == (
                "2.0.13",
                "https://github.com/x/releases/tag/v2.0.13",
            )

    def test_check_for_update_none_when_same(self):
        from Spotify_Downloader import _check_for_update

        resp = MagicMock(status_code=200)
        resp.json.return_value = {"tag_name": "v2.0.12", "html_url": "u"}
        with patch("Spotify_Downloader.requests.get", return_value=resp):
            assert _check_for_update("2.0.12") is None

    def test_check_for_update_none_on_non_200(self):
        from Spotify_Downloader import _check_for_update

        resp = MagicMock(status_code=403)
        with patch("Spotify_Downloader.requests.get", return_value=resp):
            assert _check_for_update("2.0.12") is None

    def test_check_for_update_fail_silent_on_exception(self):
        from Spotify_Downloader import _check_for_update

        with patch(
            "Spotify_Downloader.requests.get", side_effect=requests.ConnectionError("offline")
        ):
            assert _check_for_update("2.0.12") is None  # no raise

    def test_check_for_update_falls_back_to_releases_page_url(self):
        from Spotify_Downloader import _RELEASES_PAGE, _check_for_update

        resp = MagicMock(status_code=200)
        resp.json.return_value = {"tag_name": "v9.9.9"}  # no html_url
        with patch("Spotify_Downloader.requests.get", return_value=resp):
            result = _check_for_update("2.0.12")
        assert result == ("9.9.9", _RELEASES_PAGE)

    @staticmethod
    @contextlib.contextmanager
    def _capture_sunnify_logs():
        """Capture the 'sunnify' logger directly (it sets propagate=False after
        setup_logging, so pytest's root-attached caplog can't see it)."""
        import io
        import logging

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("sunnify")
        prev_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            yield buf
        finally:
            logger.removeHandler(handler)
            logger.setLevel(prev_level)

    def test_logs_when_on_latest(self):
        from Spotify_Downloader import _check_for_update

        resp = MagicMock(status_code=200)
        resp.json.return_value = {"tag_name": "v2.0.12", "html_url": "u"}
        with (
            self._capture_sunnify_logs() as buf,
            patch("Spotify_Downloader.requests.get", return_value=resp),
        ):
            _check_for_update("2.0.12")
        assert "on latest" in buf.getvalue()

    def test_logs_github_non_200(self):
        from Spotify_Downloader import _check_for_update

        resp = MagicMock(status_code=403)
        with (
            self._capture_sunnify_logs() as buf,
            patch("Spotify_Downloader.requests.get", return_value=resp),
        ):
            _check_for_update("2.0.12")
        assert "403" in buf.getvalue()

    def test_logs_skipped_on_network_error(self):
        from Spotify_Downloader import _check_for_update

        with (
            self._capture_sunnify_logs() as buf,
            patch("Spotify_Downloader.requests.get", side_effect=requests.ConnectionError("x")),
        ):
            _check_for_update("2.0.12")
        assert "update check skipped" in buf.getvalue()


class TestStarPrompt:
    """One-time 'star the repo' ask after the first successful download.

    Contract: fires at most once per install, only when the finished run
    actually landed >=1 track, never after a cancelled run, and the config
    flag persists BEFORE the dialog opens so a crash mid-dialog can never
    re-prompt."""

    def _window(self, *, shown=False, counter=1, cancelled=False):
        """Bare MainWindow (no Qt UI construction) with just the state the
        gating slot reads - same bare-instance trick check_api_status.py uses."""
        import threading
        from types import SimpleNamespace

        from Spotify_Downloader import MainWindow

        win = MainWindow.__new__(MainWindow)
        win._config = {"star_prompt_shown": shown}
        win._cancel_event = threading.Event()
        if cancelled:
            win._cancel_event.set()
        win.scraper_thread = SimpleNamespace(scraper=SimpleNamespace(counter=counter))
        return win

    def _run_slot(self, win, calls):
        import Spotify_Downloader as sd

        class _Recorder:
            def __init__(self, parent):
                calls.append("shown")

            def exec_(self):
                return 0

        with (
            patch.object(sd, "StarPromptNotifier", _Recorder),
            patch.object(sd, "save_config", lambda _cfg: calls.append("saved")),
        ):
            sd.MainWindow._maybe_show_star_prompt(win, "Download Complete!")

    def test_shows_once_then_never_again(self):
        """First successful run prompts; the persisted flag silences every
        run after it."""
        calls = []
        win = self._window()
        self._run_slot(win, calls)
        assert "shown" in calls
        assert win._config["star_prompt_shown"] is True
        self._run_slot(win, calls)
        assert calls.count("shown") == 1

    def test_skipped_when_nothing_downloaded(self):
        """A run that landed zero tracks (all failed / not found) must not
        beg for a star - the user got nothing."""
        calls = []
        win = self._window(counter=0)
        self._run_slot(win, calls)
        assert calls == []
        assert win._config["star_prompt_shown"] is False

    def test_skipped_on_cancelled_run(self):
        """Prompting right after the user hit Stop reads as nagging, even if
        some tracks landed first; the next successful run asks instead."""
        calls = []
        win = self._window(counter=5, cancelled=True)
        self._run_slot(win, calls)
        assert calls == []
        assert win._config["star_prompt_shown"] is False

    def test_flag_persists_before_dialog_opens(self):
        """save_config must run before the dialog constructs, so a crash or
        force-quit mid-dialog can never make it prompt twice."""
        calls = []
        self._run_slot(self._window(), calls)
        assert calls == ["saved", "shown"]

    def test_config_defaults_and_non_bool_coercion(self, tmp_path):
        """Missing file defaults star_prompt_shown to False; a corrupted
        non-bool value coerces back to False instead of crashing or
        permanently silencing the prompt."""
        import json

        from Spotify_Downloader import load_config

        cfg_file = tmp_path / "config.json"
        with patch("Spotify_Downloader._config_path", return_value=str(cfg_file)):
            assert load_config()["star_prompt_shown"] is False
            cfg_file.write_text(json.dumps({"star_prompt_shown": "yes"}))
            assert load_config()["star_prompt_shown"] is False
            cfg_file.write_text(json.dumps({"star_prompt_shown": True}))
            assert load_config()["star_prompt_shown"] is True

    def test_notifier_constructs_and_targets_repo(self, qapp):
        """Headless construction is enough to catch layout assembly crashes
        (same rationale as TestSettingsDialog); the CTA must point at the
        repo page, not the releases page."""
        from Spotify_Downloader import GITHUB_REPO, StarPromptNotifier

        dlg = StarPromptNotifier(None)
        assert dlg.sizeHint().width() > 0
        assert dlg._url == f"https://github.com/{GITHUB_REPO}"
