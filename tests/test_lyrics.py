"""Tests for the opt-in lyrics lookup and its tag embedding.

The lyrics in these fixtures are invented; no network is touched.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

import lyrics as lyrics_mod
from lyrics import artist_score, best_match, fetch_lyrics, normalize, same_title
from Spotify_Downloader import SETTINGS

LYRICS = "first invented line\nsecond invented line"


@pytest.fixture(autouse=True)
def _no_real_network():
    """A test that forgets to stub the lyrics service must fail, not call lrclib.net."""
    with patch.object(
        lyrics_mod._session, "get", side_effect=AssertionError("real network call in a test")
    ):
        yield


def _entry(title="Song", artist="Band", text=LYRICS, **extra):
    return {"trackName": title, "artistName": artist, "plainLyrics": text, **extra}


class TestNormalize:
    def test_ignores_case_accents_and_punctuation(self):
        assert normalize("Sigur Rós – Glósóli!") == normalize("sigur ros glosoli")

    @pytest.mark.parametrize(
        "suffix", [" (Live)", " [Remastered 2011]", " (Radio Edit)", " (feat. Someone)"]
    )
    def test_drops_harmless_trailing_brackets(self, suffix):
        assert same_title("Song" + suffix, "Song")

    @pytest.mark.parametrize("suffix", [" (Part 2)", " (Cover)", " (Instrumental)"])
    def test_keeps_brackets_that_name_another_piece(self, suffix):
        assert not same_title("Song" + suffix, "Song")

    @pytest.mark.parametrize(
        "title",
        ["Song - Live", "Song - Remastered 2011", "Song - 2011 Remaster", "Song - Radio Edit"],
    )
    def test_drops_spotify_dash_tail(self, title):
        assert same_title(title, "Song")

    @pytest.mark.parametrize("title", ["Song - Part 2", "Song - Reprise", "Song (Radio Gaga)"])
    def test_keeps_dash_tail_and_brackets_with_other_words(self, title):
        assert not same_title(title, "Song")

    @pytest.mark.parametrize("word", ["Democracy", "Mixtape", "Lively", "Editorial"])
    def test_harmless_words_match_whole_words_not_prefixes(self, word):
        assert not same_title(f"Song ({word})", "Song")

    @pytest.mark.parametrize(
        "addition",
        ["(Live at Wembley 1986)", "(feat. Someone Else)", "- Live in Berlin", "[Original Mix]"],
    )
    def test_live_and_feat_openers_cover_any_trailing_text(self, addition):
        assert same_title(f"Song {addition}", "Song")

    def test_a_routine_word_inside_another_phrase_is_not_enough(self):
        assert not same_title("Song (Everybody Wants to Mix)", "Song")

    def test_hyphen_inside_a_name_is_not_a_tail(self):
        assert normalize("Jay-Z - Live") == "jay z"

    @pytest.mark.parametrize(
        ("left", "right"),
        [("दिल", "दाल"), ("が", "か"), ("สวัสดี", "สวสด"), ("안녕", "안뇽")],
    )
    def test_other_scripts_keep_their_marks(self, left, right):
        assert not same_title(left, right)

    def test_non_latin_titles_still_match_themselves(self):
        assert same_title("Привет (Live)", "привет")
        assert same_title("ありがとう", "ありがとう")

    def test_empty_titles_never_match(self):
        assert not same_title("", "")
        assert not same_title("(Live)", "")


class TestArtistScore:
    def test_exact_scores_two(self):
        assert artist_score("The Band", "the band") == 2

    def test_word_prefix_scores_one(self):
        assert artist_score("Band", "Band Live in Berlin") == 1

    def test_unrelated_and_substring_score_zero(self):
        assert artist_score("A", "Jemand anderes") == 0
        assert artist_score("Live", "Band Live in Berlin") == 0
        assert artist_score("", "Band") == 0


class TestBestMatch:
    def test_returns_text_of_matching_entry(self):
        assert best_match([_entry()], "Song", "Band") == LYRICS

    def test_wrong_title_or_artist_is_rejected(self):
        entries = [_entry(title="Other"), _entry(artist="Somebody Else")]
        assert best_match(entries, "Song", "Band") is None

    def test_skips_instrumental_and_empty_text(self):
        entries = [_entry(instrumental=True), _entry(text=""), _entry(text=None)]
        assert best_match(entries, "Song", "Band") is None

    def test_exact_artist_beats_prefix_artist(self):
        entries = [_entry(artist="Band Live in Berlin", text="prefix"), _entry(text="exact")]
        assert best_match(entries, "Song", "Band") == "exact"

    def test_first_of_equals_wins(self):
        entries = [_entry(text="one"), _entry(text="two")]
        assert best_match(entries, "Song", "Band") == "one"

    def test_normalises_line_endings(self):
        assert best_match([_entry(text="a\r\nb\rc\n")], "Song", "Band") == "a\nb\nc"

    @pytest.mark.parametrize("junk", [None, {}, "text", 7, [None, 3, "x", {"trackName": 5}]])
    def test_unexpected_shapes_do_not_raise(self, junk):
        assert best_match(junk, "Song", "Band") is None


def _response(status=200, payload=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else []
    return resp


class TestFetchLyrics:
    def test_queries_lead_artist_with_identifying_user_agent(self):
        with patch.object(
            lyrics_mod._session, "get", return_value=_response(payload=[_entry()])
        ) as get:
            result = fetch_lyrics("Song", "Band, Guest Artist")

        assert result == LYRICS
        _, kwargs = get.call_args
        assert kwargs["params"] == {"track_name": "Song", "artist_name": "Band"}
        assert "Sunnify" in kwargs["headers"]["User-Agent"]
        assert kwargs["timeout"] == lyrics_mod.REQUEST_TIMEOUT_S

    def test_searches_without_the_spotify_dash_tail(self):
        with patch.object(
            lyrics_mod._session, "get", return_value=_response(payload=[_entry()])
        ) as get:
            assert fetch_lyrics("Song - Remastered 2011", "Band") == LYRICS
        assert get.call_args.kwargs["params"]["track_name"] == "Song"

    def test_no_artist_means_no_request(self):
        with patch.object(lyrics_mod._session, "get") as get:
            assert fetch_lyrics("Intro", "") is None
            assert fetch_lyrics("", "Band") is None
        get.assert_not_called()

    @pytest.mark.parametrize("status", [404, 429, 500])
    def test_service_errors_return_none(self, status):
        with patch.object(lyrics_mod._session, "get", return_value=_response(status=status)):
            assert fetch_lyrics("Song", "Band") is None

    @pytest.mark.parametrize("error", [requests.ConnectionError("down"), requests.Timeout()])
    def test_network_errors_return_none(self, error):
        with patch.object(lyrics_mod._session, "get", side_effect=error):
            assert fetch_lyrics("Song", "Band") is None

    def test_unreadable_body_returns_none(self):
        resp = _response()
        resp.json.side_effect = ValueError("not json")
        with patch.object(lyrics_mod._session, "get", return_value=resp):
            assert fetch_lyrics("Song", "Band") is None


# --- tag embedding -------------------------------------------------------

TAGS = {"title": "Song", "artists": "Band", "album": "Al", "releaseDate": "2025", "trackNumber": 1}


def _minimal_mp3(path: str) -> None:
    from mutagen.id3 import ID3

    with open(path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00" + b"\x00" * 417)
    ID3().save(path)


def _minimal_flac(path: str) -> None:
    si = bytearray(34)
    si[0:2] = struct.pack(">H", 4096)
    si[2:4] = struct.pack(">H", 4096)
    si[10:18] = struct.pack(">Q", (44100 << 44) | (1 << 41) | (15 << 36) | 0)
    header = bytes([0x80]) + struct.pack(">I", 34)[1:]
    with open(path, "wb") as f:
        f.write(b"fLaC" + header + bytes(si))


class TestEmbedLyrics:
    def test_mp3_gets_uslt_frame_with_non_ascii_text(self, tmp_path):
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "l.mp3")
        _minimal_mp3(path)
        text = "Zeile eins\nZeile zwei – süß"
        _write_metadata_mp3(path, {**TAGS, "lyrics": text}, None)

        frames = ID3(path).getall("USLT")
        assert len(frames) == 1
        assert frames[0].text == text

    def test_mp3_retag_keeps_one_uslt_frame(self, tmp_path):
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "twice.mp3")
        _minimal_mp3(path)
        _write_metadata_mp3(path, {**TAGS, "lyrics": "old"}, None)
        _write_metadata_mp3(path, {**TAGS, "lyrics": "new"}, None)

        frames = ID3(path).getall("USLT")
        assert [f.text for f in frames] == ["new"]

    def test_mp3_without_lyrics_has_no_uslt_frame(self, tmp_path):
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "none.mp3")
        _minimal_mp3(path)
        _write_metadata_mp3(path, TAGS, None)
        assert ID3(path).getall("USLT") == []

    def test_mp3_lyrics_survive_with_cover(self, tmp_path):
        from mutagen.id3 import ID3

        from Spotify_Downloader import _write_metadata_mp3

        path = str(tmp_path / "cover.mp3")
        _minimal_mp3(path)
        cover = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        _write_metadata_mp3(path, {**TAGS, "lyrics": LYRICS}, cover)

        id3 = ID3(path)
        assert id3.getall("USLT")[0].text == LYRICS
        assert len(id3.getall("APIC")) == 1

    def test_flac_gets_lyrics_comment(self, tmp_path):
        from mutagen.flac import FLAC

        from Spotify_Downloader import _write_metadata_flac

        path = str(tmp_path / "l.flac")
        _minimal_flac(path)
        _write_metadata_flac(path, {**TAGS, "lyrics": LYRICS}, None)
        assert FLAC(path)["lyrics"] == [LYRICS]

    def test_m4a_writer_sets_lyr_atom(self, tmp_path):
        from Spotify_Downloader import _write_metadata_m4a

        audio = MagicMock()
        with patch("mutagen.mp4.MP4", return_value=audio):
            _write_metadata_m4a(str(tmp_path / "l.m4a"), {**TAGS, "lyrics": LYRICS}, None)

        audio.__setitem__.assert_any_call("\xa9lyr", LYRICS)
        audio.save.assert_called_once()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_m4a_real_file_roundtrip(tmp_path):
    from mutagen.mp4 import MP4

    from Spotify_Downloader import _write_metadata_m4a

    path = str(tmp_path / "real.m4a")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc",
            "-t",
            "0.2",
            "-c:a",
            "aac",
            path,
        ],
        check=True,
    )
    _write_metadata_m4a(path, {**TAGS, "lyrics": LYRICS}, None)
    assert MP4(path)["\xa9lyr"] == [LYRICS]


class TestTagThreadLookup:
    """WritingMetaTagsThread only goes online when the track asked for lyrics."""

    def _run(self, tags, tmp_path):
        from Spotify_Downloader import WritingMetaTagsThread

        path = str(tmp_path / "t.mp3")
        thread = WritingMetaTagsThread({**tags, "cover": ""}, path)
        writer = MagicMock()
        with (
            patch.dict("Spotify_Downloader._METADATA_WRITERS", {".mp3": writer}),
            patch("Spotify_Downloader.fetch_lyrics", return_value=LYRICS) as fetch,
        ):
            thread.run()
        return fetch, writer

    def test_no_lookup_by_default(self, tmp_path):
        fetch, writer = self._run(TAGS, tmp_path)
        fetch.assert_not_called()
        assert "lyrics" not in writer.call_args.args[1]

    def test_lookup_when_requested_passes_text_to_writer(self, tmp_path):
        fetch, writer = self._run({**TAGS, "wantLyrics": True}, tmp_path)
        fetch.assert_called_once_with("Song", "Band")
        assert writer.call_args.args[1]["lyrics"] == LYRICS

    @pytest.mark.parametrize("ext", [".opus", ".wav"])
    def test_formats_without_lyrics_never_go_online(self, tmp_path, ext):
        from Spotify_Downloader import WritingMetaTagsThread

        thread = WritingMetaTagsThread(
            {**TAGS, "cover": "", "wantLyrics": True}, str(tmp_path / f"t{ext}")
        )
        with patch("Spotify_Downloader.fetch_lyrics") as fetch:
            thread.run()
        fetch.assert_not_called()

    def test_failed_lookup_still_writes_tags(self, tmp_path):
        from Spotify_Downloader import WritingMetaTagsThread

        path = str(tmp_path / "t.mp3")
        thread = WritingMetaTagsThread({**TAGS, "cover": "", "wantLyrics": True}, path)
        writer = MagicMock()
        with (
            patch.dict("Spotify_Downloader._METADATA_WRITERS", {".mp3": writer}),
            patch("Spotify_Downloader.fetch_lyrics", return_value=None),
        ):
            thread.run()
        writer.assert_called_once()
        assert not writer.call_args.args[1]["lyrics"]


class TestSetting:
    def test_off_by_default_and_wired_to_scraper_and_cli(self):
        from Spotify_Downloader import SETTINGS, MusicScraper, scraper_kwargs_from

        setting = next(s for s in SETTINGS if s.key == "lyrics")
        assert setting.default is False
        assert setting.cli_flag == "--lyrics"
        assert MusicScraper().fetch_lyrics is False
        assert scraper_kwargs_from({"lyrics": True})["fetch_lyrics"] is True


class TestScraperAndCli:
    """The opt-in travels from setting to flag to the tag payload; off never asks for lyrics."""

    @staticmethod
    def _emitted_meta(tmp_path, *, fetch):
        from Spotify_Downloader import MusicScraper

        scraper = MusicScraper(fetch_lyrics=fetch)
        scraper.song_meta = MagicMock()
        scraper.add_song_meta = MagicMock()
        scraper.error_signal = MagicMock()
        scraper.count_updated = MagicMock()
        track = SimpleNamespace(
            id="id1",
            title="Song",
            artists="Band",
            album="Al",
            release_date="2025",
            cover_url="",
            duration_ms=1000,
        )

        def fake_download(_query, dest, **_kw):
            open(dest, "wb").close()
            return dest

        scraper.download_track_audio = fake_download
        scraper._download_one_track(track, str(tmp_path), None)
        return scraper.add_song_meta.emit.call_args.args[0]

    def test_payload_asks_for_lyrics_only_when_enabled(self, tmp_path):
        assert self._emitted_meta(tmp_path, fetch=True)["wantLyrics"] is True
        other = tmp_path / "off"
        other.mkdir()
        assert self._emitted_meta(other, fetch=False)["wantLyrics"] is False

    def _args(self, **kw):
        base = {s.cli_flag.lstrip("-").replace("-", "_"): None for s in SETTINGS if s.cli_flag}
        return SimpleNamespace(**{**base, **kw})

    @pytest.mark.parametrize(
        ("saved", "flag", "expected"),
        [(False, None, False), (True, None, True), (False, True, True), (True, False, False)],
    )
    def test_cli_flag_beats_saved_setting(self, saved, flag, expected):
        import threading

        import sunnify_cli as cli

        cfg = {s.key: s.default for s in SETTINGS}
        cfg["lyrics"] = saved
        scraper = cli._build_scraper(self._args(lyrics=flag), cfg, threading.Event())
        assert scraper.fetch_lyrics is expected


class TestSettingsDialogLyrics:
    @pytest.mark.parametrize("stored", [False, True])
    def test_checkbox_shows_and_returns_the_stored_value(self, qapp, stored):
        from Spotify_Downloader import SettingsDialog

        dlg = SettingsDialog(None, {"lyrics": stored})
        assert dlg._lyrics_cb.isChecked() is stored
        assert dlg.result_config()["lyrics"] is stored

    def test_toggling_the_checkbox_changes_the_result(self, qapp):
        from Spotify_Downloader import SettingsDialog

        dlg = SettingsDialog(None, {})
        assert dlg.result_config()["lyrics"] is False  # off by default
        dlg._lyrics_cb.setChecked(True)
        assert dlg.result_config()["lyrics"] is True

    def test_saved_value_survives_a_config_round_trip(self, tmp_path):
        import Spotify_Downloader as sd

        with patch.object(sd, "_config_path", return_value=str(tmp_path / "config.json")):
            sd.save_config({"lyrics": True})
            assert sd.load_config()["lyrics"] is True
            sd.save_config({"lyrics": "yes"})  # junk in the file falls back to the default
            assert sd.load_config()["lyrics"] is False
