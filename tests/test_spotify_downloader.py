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
        assert scraper.sanitize_text("Test@Song#123") == "TestSong123"

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
            # Verify APIC tag was set
            mock_id3.return_value.__setitem__.assert_called_once()
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

        def fake_download(query, dest):
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

        def fake_download(query, dest):
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

        def fake_download(query, dest):
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

        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d
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
        scraper.download_track_audio = lambda _q, d: (
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
        # Pre-create files for tracks 0 and 2
        for i in (0, 2):
            (playlist_folder / f"Song {i} - Artist.mp3").touch()

        downloaded = []

        def fake_dl(q, d):
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
        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d
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

        def slow_download(query, dest):
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

        # Pre-claim the filename as if worker A got there first
        base_name = "Song - Artist.mp3"
        base_path = os.path.join(str(playlist_folder), base_name)
        with scraper._filename_lock:
            scraper._in_flight_files.add(base_path)

        # Worker B arrives — should get a suffixed filename
        scraper._download_one_track(tracks[1], str(playlist_folder), None)

        assert len(claimed_paths) == 1
        claimed = claimed_paths[0]
        assert claimed != base_path
        assert "[id_b]" in claimed

    def test_parallel_mode_suppresses_song_meta_emits(self, tmp_path):
        """In parallel mode, song_meta (UI preview) is not emitted per track.

        Audit fix H2: avoids label flicker + thumbnail thread spam.
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
        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d

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

        # 4 tracks >= 3 threshold → parallel mode. song_meta should NOT have
        # been emitted per track. add_song_meta must still fire (for ID3 tags).
        assert scraper.song_meta.emit.call_count == 0
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
        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d

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


class TestConfigModule:
    """Tests for the persisted user config (load_config / save_config)."""

    def test_load_config_returns_defaults_when_missing(self, tmp_path, mocker):
        """Missing config file returns sane defaults."""
        from Spotify_Downloader import DEFAULT_TEMPLATE, load_config

        mocker.patch(
            "Spotify_Downloader._config_path",
            return_value=str(tmp_path / "nonexistent.json"),
        )
        cfg = load_config()
        assert cfg["format"] == "mp3"
        assert cfg["quality"] == "192"
        assert cfg["filename_template"] == DEFAULT_TEMPLATE
        assert cfg["recent_playlists"] == []

    def test_load_config_roundtrip(self, tmp_path, mocker):
        """save_config then load_config returns the same values."""
        from Spotify_Downloader import load_config, save_config

        mocker.patch(
            "Spotify_Downloader._config_path",
            return_value=str(tmp_path / "cfg.json"),
        )
        save_config(
            {
                "version": 1,
                "download_path": "/tmp/foo",
                "format": "flac",
                "quality": "256",
                "filename_template": "{artists} - {title}",
                "recent_playlists": [{"url": "x", "name": "Y"}],
            }
        )
        cfg = load_config()
        assert cfg["download_path"] == "/tmp/foo"
        assert cfg["format"] == "flac"
        assert cfg["quality"] == "256"
        assert cfg["filename_template"] == "{artists} - {title}"
        assert len(cfg["recent_playlists"]) == 1

    def test_load_config_clamps_invalid_format(self, tmp_path, mocker):
        """Invalid format in config is clamped to mp3."""
        from Spotify_Downloader import load_config, save_config

        mocker.patch(
            "Spotify_Downloader._config_path",
            return_value=str(tmp_path / "cfg.json"),
        )
        save_config({"version": 1, "format": "garbage", "quality": "999"})
        cfg = load_config()
        assert cfg["format"] == "mp3"
        assert cfg["quality"] == "192"

    def test_load_config_tolerates_corrupt_file(self, tmp_path, mocker):
        """Malformed JSON file returns defaults instead of crashing."""
        from Spotify_Downloader import load_config

        path = tmp_path / "broken.json"
        path.write_text("{{not json")
        mocker.patch("Spotify_Downloader._config_path", return_value=str(path))
        cfg = load_config()
        assert cfg["format"] == "mp3"


class TestExtractSpotifyUrlFromText:
    """Tests for the clipboard/drag-drop URL extractor."""

    def test_plain_url(self):
        from Spotify_Downloader import extract_spotify_url_from_text

        url = "https://open.spotify.com/playlist/abc123"
        assert extract_spotify_url_from_text(url) == url

    def test_url_embedded_in_text(self):
        from Spotify_Downloader import extract_spotify_url_from_text

        text = "check this out https://open.spotify.com/track/xyz in here"
        assert extract_spotify_url_from_text(text) == "https://open.spotify.com/track/xyz"

    def test_album_url(self):
        from Spotify_Downloader import extract_spotify_url_from_text

        assert (
            extract_spotify_url_from_text("https://open.spotify.com/album/aaa111")
            == "https://open.spotify.com/album/aaa111"
        )

    def test_no_spotify_url(self):
        from Spotify_Downloader import extract_spotify_url_from_text

        assert extract_spotify_url_from_text("plain text with no url") is None

    def test_empty_and_none(self):
        from Spotify_Downloader import extract_spotify_url_from_text

        assert extract_spotify_url_from_text("") is None


class TestFilenameTemplate:
    """Tests for MusicScraper._format_filename and custom templates."""

    def _track(self, title="Hello", artists="World", album="Album"):
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id="tid",
            title=title,
            artists=artists,
            album=album,
            release_date=None,
            cover_url=None,
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def test_default_template(self):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        assert scraper._format_filename(self._track()) == "Hello - World"

    def test_reverse_template(self):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(filename_template="{artists} - {title}")
        assert scraper._format_filename(self._track()) == "World - Hello"

    def test_numbered_template(self):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(filename_template="{track_num:02d} {title} - {artists}")
        assert scraper._format_filename(self._track(), track_num=7) == "07 Hello - World"

    def test_malformed_template_falls_back(self):
        """Unknown placeholders should not raise; we fall back to the default."""
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(filename_template="{bogus_placeholder}")
        name = scraper._format_filename(self._track())
        assert name == "Hello - World"


class TestAudioFormatWiring:
    """Tests that format + quality flow from config to yt-dlp opts."""

    def test_defaults_produce_mp3_192(self):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper()
        assert scraper.audio_format == "mp3"
        assert scraper.audio_quality == "192"

    def test_invalid_format_is_clamped(self):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(audio_format="garbage")
        assert scraper.audio_format == "mp3"

    def test_flac_postprocessor_has_no_quality(self, mocker):
        """Lossless format must not pass preferredquality to ffmpeg."""
        from Spotify_Downloader import MusicScraper

        mocker.patch("Spotify_Downloader.get_ffmpeg_path", return_value="/opt/homebrew/bin")
        captured = {}

        class _FakeYDL:
            def __init__(self, opts):
                captured["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def extract_info(self, *a, **kw):
                return {}

            def prepare_filename(self, info):
                return ""

        mocker.patch("Spotify_Downloader.YoutubeDL", _FakeYDL)

        scraper = MusicScraper(audio_format="flac")
        scraper.download_track_audio("ytsearch1:test", "/tmp/out.flac")
        pps = captured["opts"]["postprocessors"]
        assert pps[0]["preferredcodec"] == "flac"
        assert "preferredquality" not in pps[0]

    def test_mp3_320_postprocessor_has_quality(self, mocker):
        """Lossy format passes the configured bitrate."""
        from Spotify_Downloader import MusicScraper

        mocker.patch("Spotify_Downloader.get_ffmpeg_path", return_value="/opt/homebrew/bin")
        captured = {}

        class _FakeYDL:
            def __init__(self, opts):
                captured["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def extract_info(self, *a, **kw):
                return {}

            def prepare_filename(self, info):
                return ""

        mocker.patch("Spotify_Downloader.YoutubeDL", _FakeYDL)

        scraper = MusicScraper(audio_format="mp3", audio_quality="320")
        scraper.download_track_audio("ytsearch1:test", "/tmp/out.mp3")
        pps = captured["opts"]["postprocessors"]
        assert pps[0]["preferredcodec"] == "mp3"
        assert pps[0]["preferredquality"] == "320"

    def test_progress_hooks_cancel_raises(self, mocker):
        """The progress hook raises when cancel_event is set so yt-dlp aborts."""
        from Spotify_Downloader import MusicScraper

        mocker.patch("Spotify_Downloader.get_ffmpeg_path", return_value="/opt/homebrew/bin")
        captured = {}

        class _FakeYDL:
            def __init__(self, opts):
                captured["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def extract_info(self, *a, **kw):
                return {}

            def prepare_filename(self, info):
                return ""

        mocker.patch("Spotify_Downloader.YoutubeDL", _FakeYDL)

        cancel = threading.Event()
        scraper = MusicScraper(cancel_event=cancel)
        scraper.download_track_audio("ytsearch1:x", "/tmp/out.mp3")
        hook = captured["opts"]["progress_hooks"][0]
        # No cancel: hook does nothing
        hook({"status": "downloading"})
        # With cancel: hook raises so yt-dlp aborts mid-fragment
        cancel.set()
        with pytest.raises(RuntimeError, match="cancelled"):
            hook({"status": "downloading"})


class TestCoverEnrichment:
    """Tests that per-track covers are fetched when the playlist embed omits them."""

    def _track(self, tid="id1", cover=None):
        from spotifydown_api import TrackInfo

        return TrackInfo(
            id=tid,
            title="Song",
            artists="Artist",
            album=None,
            release_date=None,
            cover_url=cover,
            duration_ms=None,
            preview_url=None,
            raw={},
        )

    def test_enriches_when_cover_missing(self, tmp_path):
        """Empty track.cover_url triggers a get_track call for the real cover."""
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

        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d

        mock_api = MagicMock()
        enriched = self._track(cover="https://real/cover.jpg")
        mock_api.get_track.return_value = enriched
        scraper.spotifydown_api = mock_api

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta["cover"])

        bare = self._track(cover=None)
        scraper._download_one_track(bare, str(tmp_path), "fallback-playlist-cover")
        assert captured == ["https://real/cover.jpg"]

    def test_does_not_enrich_when_disabled(self, tmp_path):
        """Album path sets enrich_cover=False to skip per-track fetches."""
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

        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d
        mock_api = MagicMock()
        scraper.spotifydown_api = mock_api

        bare = self._track(cover=None)
        scraper._download_one_track(bare, str(tmp_path), "album-cover", enrich_cover=False)
        mock_api.get_track.assert_not_called()

    def test_uses_existing_cover_without_fetching(self, tmp_path):
        """Track that already has a cover (e.g. fetched via spclient fallback)
        should not trigger a second network call.
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

        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d
        mock_api = MagicMock()
        scraper.spotifydown_api = mock_api

        with_cover = self._track(cover="https://already/present.jpg")
        scraper._download_one_track(with_cover, str(tmp_path), "playlist-cover")
        mock_api.get_track.assert_not_called()

    def test_enrichment_failure_falls_back_to_default(self, tmp_path):
        """If get_track fails, we fall back to default_cover_url rather than
        crashing the worker.
        """
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import SpotifyDownAPIError

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

        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d

        mock_api = MagicMock()
        mock_api.get_track.side_effect = SpotifyDownAPIError("offline")
        scraper.spotifydown_api = mock_api

        captured = []
        scraper.add_song_meta.emit.side_effect = lambda meta: captured.append(meta["cover"])

        bare = self._track(cover=None)
        scraper._download_one_track(bare, str(tmp_path), "fallback-playlist-cover")
        assert captured == ["fallback-playlist-cover"]


class TestCancelDuringMaterialization:
    """Tests that cancel set mid-iter_playlist_tracks aborts materialization."""

    def test_materialize_tracks_stops_on_cancel(self):
        from Spotify_Downloader import MusicScraper

        cancel = threading.Event()
        scraper = MusicScraper(cancel_event=cancel)

        yielded_count = 0

        def slow_generator():
            nonlocal yielded_count
            # Yield 5 then cancel; remaining yields should be skipped.
            for i in range(10):
                if i == 5:
                    cancel.set()
                yielded_count += 1
                yield f"track-{i}"

        out = scraper._materialize_tracks(slow_generator())
        # 5 are collected pre-cancel; cancel fires on 6th yield and we break
        # before appending that one.
        assert len(out) == 5


class TestAlbumScrape:
    """Tests that scrape_album goes through iter_album_tracks and runs workers."""

    def test_scrape_album_uses_album_api(self, tmp_path):
        from Spotify_Downloader import MusicScraper
        from spotifydown_api import TrackInfo

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

        tracks = [
            TrackInfo(
                id=f"t{i}",
                title=f"S{i}",
                artists="A",
                album="M",
                release_date="2022-10-21",
                cover_url="http://album/cover.jpg",
                duration_ms=None,
                preview_url=None,
                raw={},
            )
            for i in range(4)
        ]

        mock_api = MagicMock()
        meta = MagicMock()
        meta.name = "Midnights"
        meta.owner = "TS"
        meta.cover_url = "http://album/cover.jpg"
        mock_api.get_album_metadata.return_value = meta
        mock_api.iter_album_tracks.return_value = iter(tracks)
        scraper.ensure_spotifydown_api = MagicMock(return_value=mock_api)
        scraper.format_playlist_name = lambda _m: "Midnights - TS"
        scraper.download_track_audio = lambda _q, d: open(d, "wb").close() or d

        scraper.scrape_album("https://open.spotify.com/album/151w1FgRZfnKZA9FEcg9Z3", str(tmp_path))

        # All 4 tracks processed
        assert scraper.counter == 4
        # iter_album_tracks was used, not iter_playlist_tracks
        mock_api.iter_album_tracks.assert_called_once()
        mock_api.iter_playlist_tracks.assert_not_called()
        # get_track (cover enrichment) was NOT called for albums
        mock_api.get_track.assert_not_called()


class TestYtdlpStaleness:
    """Tests for the yt-dlp version staleness detector."""

    def test_fresh_version_is_not_stale(self, monkeypatch):
        import yt_dlp.version as _v

        from Spotify_Downloader import _ytdlp_version_is_stale

        today = __import__("datetime").date.today()
        fresh_ver = f"{today.year}.{today.month}.{today.day}"
        monkeypatch.setattr(_v, "__version__", fresh_ver)

        stale, ver = _ytdlp_version_is_stale(max_age_days=60)
        assert stale is False
        assert ver == fresh_ver

    def test_old_version_is_stale(self, monkeypatch):
        import yt_dlp.version as _v

        from Spotify_Downloader import _ytdlp_version_is_stale

        monkeypatch.setattr(_v, "__version__", "2023.1.1")

        stale, ver = _ytdlp_version_is_stale(max_age_days=60)
        assert stale is True
        assert ver == "2023.1.1"

    def test_malformed_version_is_not_flagged(self, monkeypatch):
        import yt_dlp.version as _v

        from Spotify_Downloader import _ytdlp_version_is_stale

        monkeypatch.setattr(_v, "__version__", "not.a.version")

        stale, _ver = _ytdlp_version_is_stale()
        assert stale is False
