"""Tests for the 3.0 additions below the window: translations, history, lyrics."""

from __future__ import annotations

import json
import os
import re
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
import requests

from sunnify import history, i18n, lyrics
from sunnify.lyrics import Lyrics


def _fields(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", text))


class TestTranslations:
    def test_both_languages_carry_every_key(self):
        assert set(i18n.EN) == set(i18n.MS)

    @pytest.mark.parametrize("key", sorted(i18n.EN))
    def test_placeholders_match_across_languages(self, key):
        """A translation that drops or renames {field} would show a raw brace."""
        assert _fields(i18n.MS[key]) == _fields(i18n.EN[key]), key

    def test_switching_language_changes_every_later_lookup(self):
        assert i18n.t("main.download") == "Download"
        i18n.set_language("ms")
        assert i18n.t("main.download") == "Muat turun"
        assert i18n.t("main.counter", done=3) == "Lagu dimuat turun 3"

    def test_unknown_language_and_key_never_crash(self):
        assert i18n.set_language("xx") == "en"
        assert i18n.t("no.such.key") == "no.such.key"
        # a missing field leaves the template rather than raising mid-download
        assert i18n.t("main.counter") == "Songs downloaded {done}"

    def test_missing_translation_falls_back_to_english(self, monkeypatch):
        monkeypatch.delitem(i18n.MS, "main.paste")
        i18n.set_language("ms")
        assert i18n.t("main.paste") == "Paste"

    @pytest.mark.parametrize(
        ("setting", "locale_name", "expected"),
        [
            ("en", "ms_MY", "en"),
            ("ms", "en_US", "ms"),
            ("auto", "ms_MY", "ms"),
            ("auto", "ms", "ms"),
            ("auto", "Malay_Malaysia.1252", "ms"),
            ("auto", "en_GB", "en"),
            ("auto", "id_ID", "en"),  # Indonesian is not Malay
            ("auto", "", "en"),
            (None, "ms_BN", "ms"),
        ],
    )
    def test_auto_follows_a_malay_locale(self, setting, locale_name, expected):
        assert i18n.resolve(setting, locale_name) == expected

    def test_engine_messages_follow_the_language(self):
        from sunnify.engine import MusicScraper

        scraper = MusicScraper()
        i18n.set_language("ms")
        msg = scraper._get_user_friendly_error(RuntimeError("no playable audio source"), "Lagu")
        assert msg == "'Lagu' tidak dijumpai di YouTube"

    def test_cli_output_stays_english_regardless_of_locale(self, monkeypatch):
        """The CLI never calls set_language, so a Malay system can't change its text."""
        import sunnify_cli as cli

        monkeypatch.setenv("LANG", "ms_MY.UTF-8")
        assert i18n.language() == "en"
        assert "download" in cli.build_parser().format_help()


class TestHistory:
    def test_records_newest_first(self):
        history.record(url="https://open.spotify.com/album/a", name="A", landed=3)
        history.record(url="https://open.spotify.com/album/b", name="B", landed=1, failed=1)
        entries = history.load()
        assert [e["name"] for e in entries] == ["B", "A"]
        assert entries[0]["status"] == "partial"
        assert entries[1]["status"] == "done"

    @pytest.mark.parametrize(
        ("landed", "failed", "stopped", "status"),
        [
            (5, 0, False, "done"),
            (5, 2, False, "partial"),
            (0, 4, False, "failed"),
            (0, 0, False, "done"),
            (3, 1, True, "stopped"),
        ],
    )
    def test_status_for(self, landed, failed, stopped, status):
        assert history.status_for(landed=landed, failed=failed, stopped=stopped) == status

    def test_caps_at_max_entries(self, monkeypatch):
        monkeypatch.setattr(history, "MAX_ENTRIES", 3)
        for i in range(5):
            history.record(url=f"https://open.spotify.com/track/{i}", name=str(i))
        assert [e["name"] for e in history.load()] == ["4", "3", "2"]

    def test_corrupt_or_foreign_file_reads_as_empty(self):
        path = history.history_path()
        for junk in ("not json", "[1, 2]", json.dumps({"entries": "nope"})):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(junk)
            assert history.load() == []

    def test_malformed_entries_are_dropped_not_fatal(self):
        with open(history.history_path(), "w", encoding="utf-8") as fh:
            json.dump(
                {"entries": [{"url": 5}, "x", {"url": "u", "landed": "2", "status": "??"}]}, fh
            )
        (only,) = history.load()
        assert only["url"] == "u" and only["landed"] == 2 and only["status"] == "done"

    def test_clear_forgets_everything(self):
        history.record(url="u")
        history.clear()
        assert history.load() == []
        history.clear()  # already gone: still fine

    def test_a_failed_write_is_logged_not_raised(self, monkeypatch):
        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr("sunnify.config.write_json_atomic", boom)
        assert history.record(url="u") is None


def _response(status, payload):
    r = MagicMock(status_code=status)
    r.json.return_value = payload
    return r


class TestLyricsLookup:
    RECORD: ClassVar[dict] = {
        "plainLyrics": "line one\nline two",
        "syncedLyrics": "[00:01.00] line one",
    }

    def test_exact_hit_prefers_synced(self):
        with patch("sunnify.lyrics.requests.get", return_value=_response(200, self.RECORD)) as get:
            found = lyrics.fetch_lyrics("Song", "Artist, Guest", "Album", 213.4)
        assert found.best == "[00:01.00] line one"
        params = get.call_args.kwargs["params"]
        assert params == {
            "track_name": "Song",
            "artist_name": "Artist",
            "album_name": "Album",
            "duration": 213,
        }
        assert get.call_args.kwargs["headers"]["User-Agent"].startswith("Sunnify/")

    def test_miss_falls_back_to_a_duration_checked_search(self):
        results = [
            {"duration": 263.0, "plainLyrics": "video edit"},
            {"duration": 201.0, "plainLyrics": "the album cut"},
        ]
        responses = [_response(404, {}), _response(200, results)]
        with patch("sunnify.lyrics.requests.get", side_effect=responses) as get:
            found = lyrics.fetch_lyrics("Blinding Lights - Remastered", "The Weeknd", "", 200)
        assert found.plain == "the album cut"
        assert get.call_args.kwargs["params"]["track_name"] == "Blinding Lights"

    def test_nothing_found_or_network_down_is_none(self):
        with patch(
            "sunnify.lyrics.requests.get", side_effect=[_response(404, {}), _response(200, [])]
        ):
            assert lyrics.fetch_lyrics("x", "y") is None
        with patch("sunnify.lyrics.requests.get", side_effect=requests.ConnectionError("offline")):
            assert lyrics.fetch_lyrics("x", "y") is None
        assert lyrics.fetch_lyrics("", "y") is None

    def test_instrumental_is_a_result_without_text(self):
        with patch(
            "sunnify.lyrics.requests.get", return_value=_response(200, {"instrumental": True})
        ):
            found = lyrics.fetch_lyrics("Intro", "Band")
        assert found.instrumental and found.best == ""

    def test_lrc_sidecar_only_for_synced(self, tmp_path):
        audio = tmp_path / "Song - Artist.mp3"
        assert lyrics.write_lrc_sidecar(str(audio), Lyrics(plain="words")) is None
        path = lyrics.write_lrc_sidecar(str(audio), Lyrics(synced="[00:01.00] hi"))
        assert path == str(tmp_path / "Song - Artist.lrc")
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == "[00:01.00] hi\n"


class TestLyricsInTags:
    """Real mutagen on fixture files: the frames players actually read."""

    @staticmethod
    def _mp3(path):
        from mutagen.id3 import ID3

        with open(path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 417)
        ID3().save(path)

    @staticmethod
    def _flac(path):
        import struct

        # same hand-built STREAMINFO-only file as TestFlacMetadata, no ffmpeg needed
        si = bytearray(34)
        si[0:2] = struct.pack(">H", 4096)
        si[2:4] = struct.pack(">H", 4096)
        si[10:18] = struct.pack(">Q", (44100 << 44) | (1 << 41) | (15 << 36))
        header = bytes([0x80]) + struct.pack(">I", 34)[1:]
        with open(path, "wb") as f:
            f.write(b"fLaC" + header + bytes(si))

    def test_mp3_gets_a_uslt_frame_in_v23(self, tmp_path):
        from mutagen.id3 import ID3

        from sunnify.tagging import _write_metadata_mp3

        path = str(tmp_path / "a.mp3")
        self._mp3(path)
        _write_metadata_mp3(path, {"title": "T", "lyricsText": "la la"}, None)
        tags = ID3(path)
        assert tags.version[:2] == (2, 3)
        assert tags.getall("USLT")[0].text == "la la"

    def test_flac_gets_a_lyrics_comment(self, tmp_path):
        from mutagen.flac import FLAC

        from sunnify.tagging import _write_metadata_flac

        path = str(tmp_path / "a.flac")
        self._flac(path)
        _write_metadata_flac(path, {"title": "T", "lyricsText": "la la"}, None)
        assert FLAC(path)["lyrics"] == ["la la"]

    def test_thread_fetches_only_when_asked(self, tmp_path):
        from sunnify.tagging import WritingMetaTagsThread

        path = str(tmp_path / "a.mp3")
        self._mp3(path)
        with (
            patch("sunnify.tagging.lrclib.fetch_lyrics") as fetch,
            patch("sunnify.tagging._fetch_cover_bytes", return_value=None),
        ):
            WritingMetaTagsThread({"title": "T", "lyrics": False}, path).run()
            fetch.assert_not_called()
            fetch.return_value = Lyrics(plain="p", synced="[00:00.50] s")
            WritingMetaTagsThread({"title": "T", "artists": "A", "lyrics": True}, path).run()
            fetch.assert_called_once()
        from mutagen.id3 import ID3

        assert ID3(path).getall("USLT")[0].text == "[00:00.50] s"
        assert os.path.exists(str(tmp_path / "a.lrc"))

    def test_untaggable_formats_still_get_the_sidecar(self, tmp_path):
        from sunnify.tagging import WritingMetaTagsThread

        path = str(tmp_path / "a.opus")
        open(path, "wb").close()
        thread = WritingMetaTagsThread({"title": "T", "artists": "A", "lyrics": True}, path)
        thread.tags_success = MagicMock()
        with patch(
            "sunnify.tagging.lrclib.fetch_lyrics", return_value=Lyrics(synced="[00:01.00] x")
        ):
            thread.run()
        thread.tags_success.emit.assert_called_once_with("Tags skipped (unsupported container)")
        assert os.path.exists(str(tmp_path / "a.lrc"))

    def test_engine_hands_the_flag_and_duration_to_the_tag_writer(self, tmp_path):
        from spotifydown_api import TrackInfo
        from sunnify.engine import MusicScraper

        scraper = MusicScraper(lyrics=True)
        scraper.add_song_meta = MagicMock()
        scraper.song_meta = MagicMock()
        scraper.count_updated = MagicMock()
        scraper.dlprogress_signal = MagicMock()
        track = TrackInfo(
            id="t1",
            title="Song",
            artists="Artist",
            album="Album",
            release_date="2024",
            cover_url="c",
            duration_ms=201_600,
            preview_url=None,
            raw={},
        )
        existing = tmp_path / "Song - Artist.mp3"
        existing.write_bytes(b"x")
        scraper._download_one_track(track, str(tmp_path), "", 1)
        meta = scraper.add_song_meta.emit.call_args[0][0]
        assert meta["lyrics"] is True and meta["duration"] == 202
