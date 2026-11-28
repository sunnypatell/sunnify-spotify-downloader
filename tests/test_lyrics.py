"""Tests for the opt-in lyrics lookup and its tag embedding.

The lyrics in these fixtures are invented; no network is touched.
"""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest
import requests

import lyrics as lyrics_mod
from lyrics import artist_score, best_match, fetch_lyrics, normalize, same_title

LYRICS = "first invented line\nsecond invented line"


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
            lyrics_mod.requests, "get", return_value=_response(payload=[_entry()])
        ) as get:
            result = fetch_lyrics("Song", "Band, Guest Artist")

        assert result == LYRICS
        _, kwargs = get.call_args
        assert kwargs["params"] == {"track_name": "Song", "artist_name": "Band"}
        assert "Sunnify" in kwargs["headers"]["User-Agent"]
        assert kwargs["timeout"] == lyrics_mod.REQUEST_TIMEOUT_S

    def test_no_artist_means_no_request(self):
        with patch.object(lyrics_mod.requests, "get") as get:
            assert fetch_lyrics("Intro", "") is None
            assert fetch_lyrics("", "Band") is None
        get.assert_not_called()

    def test_uses_given_session(self):
        session = MagicMock()
        session.get.return_value = _response(payload=[_entry()])
        assert fetch_lyrics("Song", "Band", session=session) == LYRICS

    @pytest.mark.parametrize("status", [404, 429, 500])
    def test_service_errors_return_none(self, status):
        with patch.object(lyrics_mod.requests, "get", return_value=_response(status=status)):
            assert fetch_lyrics("Song", "Band") is None

    @pytest.mark.parametrize("error", [requests.ConnectionError("down"), requests.Timeout()])
    def test_network_errors_return_none(self, error):
        with patch.object(lyrics_mod.requests, "get", side_effect=error):
            assert fetch_lyrics("Song", "Band") is None

    def test_unreadable_body_returns_none(self):
        resp = _response()
        resp.json.side_effect = ValueError("not json")
        with patch.object(lyrics_mod.requests, "get", return_value=resp):
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
