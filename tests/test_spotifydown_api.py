"""Tests for spotifydown_api module."""

from __future__ import annotations

import pytest

from spotifydown_api import (
    ExtractionError,
    PlaylistClient,
    PlaylistInfo,
    SpotifyEmbedAPI,
    TrackInfo,
    detect_spotify_url_type,
    extract_album_id,
    extract_playlist_id,
    extract_track_id,
    sanitize_filename,
)


class TestExtractPlaylistId:
    """Tests for extract_playlist_id function."""

    def test_valid_playlist_url(self):
        """Extract ID from standard playlist URL."""
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert extract_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_playlist_url_with_query_params(self):
        """Extract ID from URL with query parameters."""
        url = "https://open.spotify.com/playlist/abc123?si=xyz789"
        # Current implementation uses re.match which won't match query params
        # This tests current behavior - ID before query params
        assert extract_playlist_id(url) == "abc123"

    def test_invalid_url_raises_valueerror(self):
        """Invalid URLs should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify playlist URL"):
            extract_playlist_id("https://example.com/playlist/123")

    def test_track_url_raises_valueerror(self):
        """Track URLs should raise ValueError for playlist extraction."""
        with pytest.raises(ValueError, match="Invalid Spotify playlist URL"):
            extract_playlist_id("https://open.spotify.com/track/abc123")

    def test_album_url_raises_valueerror(self):
        """Album URLs should raise ValueError for playlist extraction."""
        with pytest.raises(ValueError, match="Invalid Spotify playlist URL"):
            extract_playlist_id("https://open.spotify.com/album/abc123")

    def test_empty_url_raises_valueerror(self):
        """Empty URL should raise ValueError."""
        with pytest.raises(ValueError):
            extract_playlist_id("")


class TestExtractAlbumId:
    """Tests for extract_album_id function."""

    def test_valid_album_url(self):
        """Extract ID from standard album URL."""
        url = "https://open.spotify.com/album/1JcLZljq8ADWNCdwVJKNID"
        assert extract_album_id(url) == "1JcLZljq8ADWNCdwVJKNID"

    def test_album_url_with_query_params(self):
        """Extract ID from album URL with trailing query params."""
        url = "https://open.spotify.com/album/abc123?si=xyz789"
        assert extract_album_id(url) == "abc123"

    def test_album_uri(self):
        """Extract ID from a spotify:album: URI."""
        assert extract_album_id("spotify:album:abc123") == "abc123"

    def test_playlist_url_raises_valueerror(self):
        """Playlist URLs should raise ValueError for album extraction."""
        with pytest.raises(ValueError, match="Invalid Spotify album URL"):
            extract_album_id("https://open.spotify.com/playlist/abc123")


class TestExtractTrackId:
    """Tests for extract_track_id function."""

    def test_valid_track_url(self):
        """Extract ID from standard track URL."""
        url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"
        assert extract_track_id(url) == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_invalid_url_raises_valueerror(self):
        """Invalid URLs should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify track URL"):
            extract_track_id("https://example.com/track/123")

    def test_playlist_url_raises_valueerror(self):
        """Playlist URLs should raise ValueError for track extraction."""
        with pytest.raises(ValueError, match="Invalid Spotify track URL"):
            extract_track_id("https://open.spotify.com/playlist/abc123")


class TestDetectSpotifyUrlType:
    """Tests for detect_spotify_url_type function."""

    def test_detect_playlist(self):
        """Detect playlist URL type."""
        url = "https://open.spotify.com/playlist/abc123"
        url_type, item_id = detect_spotify_url_type(url)
        assert url_type == "playlist"
        assert item_id == "abc123"

    def test_detect_track(self):
        """Detect track URL type."""
        url = "https://open.spotify.com/track/xyz789"
        url_type, item_id = detect_spotify_url_type(url)
        assert url_type == "track"
        assert item_id == "xyz789"

    def test_invalid_url_raises_valueerror(self):
        """Invalid URLs should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify URL"):
            detect_spotify_url_type("https://example.com/something")

    def test_detect_album(self):
        """Detect album URL type."""
        url = "https://open.spotify.com/album/1JcLZljq8ADWNCdwVJKNID"
        url_type, item_id = detect_spotify_url_type(url)
        assert url_type == "album"
        assert item_id == "1JcLZljq8ADWNCdwVJKNID"

    def test_detect_album_intl_and_query(self):
        """Detect album URL with locale prefix and trailing query params."""
        url = "https://open.spotify.com/intl-de/album/abc123?si=xyz"
        url_type, item_id = detect_spotify_url_type(url)
        assert url_type == "album"
        assert item_id == "abc123"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_sanitization(self):
        """Basic filename sanitization."""
        assert sanitize_filename("Hello World") == "Hello World"

    def test_removes_windows_reserved_chars(self):
        """Only the Windows-reserved characters are stripped (superset of mac/linux)."""
        assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"

    def test_keeps_ordinary_punctuation(self):
        """Non-reserved punctuation is legal on all platforms and kept verbatim."""
        assert sanitize_filename("P!nk - Sober (Remix) [Explicit] & more") == (
            "P!nk - Sober (Remix) [Explicit] & more"
        )

    def test_preserves_allowed_chars(self):
        """Allowed characters should be preserved."""
        assert sanitize_filename("file-name_123.mp3") == "file-name_123.mp3"

    def test_collapses_multiple_spaces(self):
        """Multiple spaces should be collapsed to one."""
        assert sanitize_filename("Hello    World") == "Hello World"

    def test_no_spaces_option(self):
        """Test allow_spaces=False."""
        result = sanitize_filename("Hello World", allow_spaces=False)
        assert result == "HelloWorld"

    def test_empty_or_reserved_only_returns_unknown(self):
        """Empty input, or input that is entirely reserved chars, returns 'Unknown'."""
        assert sanitize_filename("") == "Unknown"
        assert sanitize_filename('/\\:*?"<>|') == "Unknown"

    def test_unicode_preserved(self):
        """Accented and non-Latin characters must be kept (closes the special-char bug)."""
        assert sanitize_filename("MONTAGEM BAILÃO") == "MONTAGEM BAILÃO"
        assert sanitize_filename("Café ☕ Music") == "Café ☕ Music"
        assert sanitize_filename("Beyoncé") == "Beyoncé"
        assert sanitize_filename("日本語の歌") == "日本語の歌"
        assert sanitize_filename("Метель") == "Метель"

    def test_control_chars_removed(self):
        """Control characters (tab, newline, NUL) are stripped on all platforms."""
        assert sanitize_filename("tab\there\nnewline\x00nul") == "tabherenewlinenul"

    def test_trailing_and_leading_dots_spaces_trimmed(self):
        """Windows rejects trailing dots/spaces; a leading dot hides files on Unix."""
        assert sanitize_filename("trailing. ") == "trailing"
        assert sanitize_filename("...Baby One More Time") == "Baby One More Time"

    def test_windows_reserved_device_names_escaped(self):
        """DOS device names (CON, NUL, COM1, ...) are escaped, incl. with extension."""
        assert sanitize_filename("NUL") == "_NUL"
        assert sanitize_filename("con.mp3") == "_con.mp3"
        assert sanitize_filename("COM1") == "_COM1"
        assert sanitize_filename("LPT9.flac") == "_LPT9.flac"
        # superscript COM/LPT variants are reserved too (per the 2024 MS docs)
        assert sanitize_filename("COM¹") == "_COM¹"
        assert sanitize_filename("LPT³") == "_LPT³"
        # COM0/LPT0 are NOT reserved (docs list COM1-9 / LPT1-9 only)
        assert sanitize_filename("COM0") == "COM0"
        # a normal title that merely contains a reserved word is untouched
        assert sanitize_filename("CONcrete") == "CONcrete"


class TestSpotifyEmbedAPI:
    """Tests for SpotifyEmbedAPI class."""

    def test_init_creates_session(self):
        """Init should create a requests session if not provided."""
        api = SpotifyEmbedAPI()
        assert api._session is not None

    def test_init_uses_provided_session(self):
        """Init should use provided session."""
        import requests

        session = requests.Session()
        api = SpotifyEmbedAPI(session=session)
        assert api._session is session

    def test_headers_include_user_agent(self):
        """Headers should include a user agent."""
        api = SpotifyEmbedAPI()
        headers = api._headers()
        assert "user-agent" in headers
        assert "Chrome" in headers["user-agent"]

    def test_embed_url_selection_by_content_type(self):
        """Album content uses the album embed endpoint, playlist the playlist one."""
        api = SpotifyEmbedAPI()
        assert api._embed_url_for("abc", "album") == ("https://open.spotify.com/embed/album/abc")
        assert api._embed_url_for("abc", "playlist") == (
            "https://open.spotify.com/embed/playlist/abc"
        )

    def test_phase1_assigns_playlist_position_from_embed_slot(self):
        """Every track yielded from the embed page carries its 1-based
        position in trackList. Closes #51 - the prior code left position
        unset, so the downloader had to enumerate yield-order which is
        only correct as long as phase 2 (spclient) never runs."""
        api = SpotifyEmbedAPI()
        data = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "trackList": [
                                    {
                                        "uri": f"spotify:track:t{i}",
                                        "title": f"Title {i}",
                                        "subtitle": f"Artist {i}",
                                        "duration": 100000,
                                    }
                                    for i in range(1, 6)
                                ]
                            }
                        }
                    }
                }
            }
        }
        api._fetch_embed_data = lambda _url: data  # type: ignore[assignment]
        api._session.get = lambda *_a, **_kw: AssertionError("spclient skipped")  # type: ignore[assignment]

        tracks = list(api.iter_playlist_tracks("PL", content_type="playlist"))
        assert [t.id for t in tracks] == ["t1", "t2", "t3", "t4", "t5"]
        assert [t.position for t in tracks] == [1, 2, 3, 4, 5]

    def test_phase2_assigns_position_from_spclient_order_not_yield_order(self):
        """spclient yields in HTTP-completion order, NOT playlist order. The
        position field must still reflect the canonical playlist order
        (from spc_data.contents.items), so the downloader can write the
        correct number into the filename + TRCK regardless of which fetch
        finished first. This is the exact bug reported in #51 - on a
        181-track playlist the user saw tracks 101+ numbered randomly."""

        api = SpotifyEmbedAPI()
        # Phase 1: only a tiny embed (positions 1-2 in the playlist).
        embed = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "trackList": [
                                    {
                                        "uri": "spotify:track:p1",
                                        "title": "P1",
                                        "subtitle": "AP1",
                                        "duration": 1,
                                    },
                                    {
                                        "uri": "spotify:track:p2",
                                        "title": "P2",
                                        "subtitle": "AP2",
                                        "duration": 1,
                                    },
                                ]
                            }
                        }
                    }
                }
            }
        }
        api._fetch_embed_data = lambda _url: embed  # type: ignore[assignment]
        api._cached_token = "fake-token"

        # spclient returns the FULL playlist in canonical order
        # (p1 at slot 1, p2 at slot 2, then s3/s4/s5/s6 at 3-6).
        spc_response_body = {
            "length": 6,
            "contents": {
                "items": [
                    {"uri": "spotify:track:p1"},
                    {"uri": "spotify:track:p2"},
                    {"uri": "spotify:track:s3"},
                    {"uri": "spotify:track:s4"},
                    {"uri": "spotify:track:s5"},
                    {"uri": "spotify:track:s6"},
                ],
            },
        }

        class FakeResp:
            status_code = 200

            @staticmethod
            def json():
                return spc_response_body

        api._session.get = lambda *_a, **_kw: FakeResp()  # type: ignore[assignment]

        # Force the per-track metadata fetches to return in REVERSE playlist
        # order (s6 first, then s5, s4, s3) — the worst case for the prior
        # bug. _fetch_track_metadata is what the parallel pool calls.
        completion_order = ["s6", "s5", "s4", "s3"]

        def fake_fetch(tid):
            return TrackInfo(
                id=tid,
                title=f"Title {tid}",
                artists=f"Artist {tid}",
                album=None,
                release_date=None,
                cover_url=None,
                duration_ms=None,
                preview_url=None,
                raw={},
            )

        api._fetch_track_metadata = fake_fetch  # type: ignore[assignment]

        # Force as_completed-style ordering: monkey-patch the pool's
        # as_completed to return futures in the reverse order we want.
        import concurrent.futures as cf

        original_as_completed = cf.as_completed

        def reverse_as_completed(fs):
            # Re-sort futures by their bound track_id so s6 yields first.
            pairs = [(f, fs[f]) for f in fs]  # fs is future -> (tid, uri)
            pairs.sort(key=lambda p: completion_order.index(p[1][0]))
            return [p[0] for p in pairs]

        cf.as_completed = reverse_as_completed  # type: ignore[assignment]
        try:
            tracks = list(api.iter_playlist_tracks("PL", content_type="playlist"))
        finally:
            cf.as_completed = original_as_completed  # type: ignore[assignment]

        # Yield order is: p1, p2 (phase 1), then s6, s5, s4, s3 (phase 2 in
        # reverse completion). But POSITION must still match the playlist:
        by_id = {t.id: t.position for t in tracks}
        assert by_id == {"p1": 1, "p2": 2, "s3": 3, "s4": 4, "s5": 5, "s6": 6}

    def test_phase2_failed_fetch_still_gets_correct_position(self):
        """If a track's metadata fetch fails in phase 2, the fallback
        TrackInfo (`title=f"Track {id}"`, `artists="Unknown Artist"`)
        must still carry the correct playlist position so the user can
        still see WHERE in the playlist the track that failed was."""
        api = SpotifyEmbedAPI()
        # Empty embed forces every track through phase 2.
        api._fetch_embed_data = lambda _url: {  # type: ignore[assignment]
            "props": {"pageProps": {"state": {"data": {"entity": {"trackList": []}}}}}
        }
        api._cached_token = "tok"
        api._session.get = lambda *_a, **_kw: type(  # type: ignore[assignment]
            "R",
            (),
            {
                "status_code": 200,
                "json": staticmethod(
                    lambda: {
                        "length": 3,
                        "contents": {
                            "items": [
                                {"uri": "spotify:track:a"},
                                {"uri": "spotify:track:b"},
                                {"uri": "spotify:track:c"},
                            ]
                        },
                    }
                ),
            },
        )()
        # Every fetch raises - simulates a region-locked or 429 storm.
        api._fetch_track_metadata = lambda _tid: (_ for _ in ()).throw(  # type: ignore[assignment]
            RuntimeError("boom")
        )

        tracks = list(api.iter_playlist_tracks("PL", content_type="playlist"))
        # All three should still come back, fallback-shaped, with correct
        # positions matching the spclient ordering.
        by_id = {t.id: t for t in tracks}
        assert set(by_id) == {"a", "b", "c"}
        assert by_id["a"].position == 1
        assert by_id["b"].position == 2
        assert by_id["c"].position == 3
        assert by_id["a"].title == "Track a"
        assert by_id["a"].artists == "Unknown Artist"

    def test_album_iteration_tags_album_name_and_skips_spclient(self):
        """Album iteration uses the album embed URL, tags every track with the
        album name, and never invokes the playlist-only spclient fallback."""
        api = SpotifyEmbedAPI()
        fetched_urls: list[str] = []
        album_data = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "name": "My Album",
                                "trackList": [
                                    {
                                        "uri": "spotify:track:t1",
                                        "title": "One",
                                        "subtitle": "Artist A",
                                        "duration": 100000,
                                    },
                                    {
                                        "uri": "spotify:track:t2",
                                        "title": "Two",
                                        "subtitle": "Artist B",
                                        "duration": 200000,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }

        def fake_fetch(url: str) -> dict:
            fetched_urls.append(url)
            return album_data

        def explode(*_args, **_kwargs):
            raise AssertionError("spclient must not be called for albums")

        api._fetch_embed_data = fake_fetch  # type: ignore[assignment]
        api._session.get = explode  # type: ignore[assignment]

        tracks = list(api.iter_playlist_tracks("ALBUMID", content_type="album"))

        assert len(tracks) == 2
        assert all(t.album == "My Album" for t in tracks)
        assert fetched_urls == ["https://open.spotify.com/embed/album/ALBUMID"]


class TestParseOgDescriptionAlbum:
    """Parser-level tests for the og:description -> album extraction.

    The format `Artist · Album · Song · Year` is Spotify's social-share
    canonical and has been stable for years. These tests pin the parser
    to that contract and to the regex's attribute-order tolerance + HTML
    entity decoding.
    """

    def test_extracts_album_from_canonical_format(self):
        html = '<meta property="og:description" content="The Weeknd · After Hours · Song · 2020">'
        assert SpotifyEmbedAPI._parse_og_description_album(html) == "After Hours"

    def test_handles_attribute_order_reversed(self):
        """Attribute order in HTML isn't guaranteed by spec; the regex
        uses a lookahead so it matches either order. A Spotify deploy
        that reorders meta attributes must not silently kill albums."""
        html = (
            '<meta content="Queen · A Night At The Opera · Song · 1975" property="og:description">'
        )
        assert SpotifyEmbedAPI._parse_og_description_album(html) == "A Night At The Opera"

    def test_decodes_html_entities(self):
        """Albums with `&` or `\"` get HTML-encoded in the meta content;
        the parser must unescape before returning, otherwise the album
        tag ends up `Tom &amp; Jerry` in the ID3 frame."""
        html = (
            '<meta property="og:description" '
            'content="Tom &amp; Jerry · Greatest &quot;Hits&quot; · Song · 2010">'
        )
        assert SpotifyEmbedAPI._parse_og_description_album(html) == 'Greatest "Hits"'

    def test_returns_none_when_tag_missing(self):
        assert SpotifyEmbedAPI._parse_og_description_album("<html></html>") is None

    def test_returns_none_when_format_too_short(self):
        """One-part og:description (no album segment) returns None
        rather than misreporting the artist as the album."""
        html = '<meta property="og:description" content="Just one part">'
        assert SpotifyEmbedAPI._parse_og_description_album(html) is None

    def test_returns_none_when_album_empty_after_strip(self):
        html = '<meta property="og:description" content="Artist ·     · Song · 2020">'
        assert SpotifyEmbedAPI._parse_og_description_album(html) is None


class TestFetchTrackAlbumFromPage:
    """Tests for the per-track HTML scrape + caching + retry shell."""

    def _stub_session_returning(self, body: str, status: int = 200):
        """Build a fake session that returns one canned response."""
        from unittest.mock import MagicMock

        resp = MagicMock(status_code=status, text=body)
        sess = MagicMock()
        sess.get = MagicMock(return_value=resp)
        return sess

    def test_fetcher_returns_album_from_real_shape(self):
        body = (
            '<meta property="og:description" content="Linkin Park · Hybrid Theory · Song · 2000">'
        )
        api = SpotifyEmbedAPI(session=self._stub_session_returning(body))
        assert api._fetch_track_album_from_page("abc123") == "Hybrid Theory"

    def test_fetcher_returns_none_on_non_200(self):
        """Spotify dropping a 404/500 must not corrupt downstream metadata."""
        api = SpotifyEmbedAPI(session=self._stub_session_returning("error page", status=500))
        assert api._fetch_track_album_from_page("abc123") is None

    def test_fetcher_caches_result_to_avoid_re_fetch(self):
        """Second call for the same track_id must NOT hit the session;
        re-downloading the same playlist would otherwise re-pay the
        HTTP cost per track."""
        body = '<meta property="og:description" content="Daft Punk · Discovery · Song · 2001">'
        sess = self._stub_session_returning(body)
        api = SpotifyEmbedAPI(session=sess)
        assert api._fetch_track_album_from_page("xyz") == "Discovery"
        assert api._fetch_track_album_from_page("xyz") == "Discovery"
        assert sess.get.call_count == 1

    def test_fetcher_caches_none_too(self):
        """A track without an og:description tag should also be cached as
        None so a retry-loop in the caller doesn't repeatedly re-fetch."""
        api = SpotifyEmbedAPI(session=self._stub_session_returning("<html></html>", status=200))
        sess = api._session
        assert api._fetch_track_album_from_page("no-og") is None
        assert api._fetch_track_album_from_page("no-og") is None
        assert sess.get.call_count == 1

    def test_fetcher_uses_social_crawler_user_agent(self):
        """The /track/ HTML page serves a JS app shell (NO og:description)
        when fetched with a browser-shaped UA and serves the SEO page
        (WITH og:description) when fetched with a social-crawler UA.
        Verified empirically by hitting the endpoint with each."""
        body = '<meta property="og:description" content="Artist · Album · Song · 2020">'
        sess = self._stub_session_returning(body)
        api = SpotifyEmbedAPI(session=sess)
        api._fetch_track_album_from_page("ua-test")
        _, kwargs = sess.get.call_args
        assert kwargs["headers"]["user-agent"] == "facebookexternalhit/1.1"

    def test_fetcher_retries_then_returns_none_on_persistent_network_error(self):
        """Transient network errors back off (3 attempts) and degrade
        gracefully to no album rather than blowing up the whole
        per-track metadata fetch path."""
        from unittest.mock import MagicMock

        import requests as _requests

        sess = MagicMock()
        sess.get = MagicMock(side_effect=_requests.ConnectionError("boom"))
        api = SpotifyEmbedAPI(session=sess)
        assert api._fetch_track_album_from_page("flaky") is None
        # 3 retry attempts before giving up
        assert sess.get.call_count == 3

    def test_cache_eviction_when_at_capacity(self):
        """Cache is bounded at 256 entries; oldest gets evicted FIFO."""
        from unittest.mock import MagicMock

        # Build a session that returns the album corresponding to track_id
        sess = MagicMock()

        def _resp(url, **_kw):
            tid = url.rsplit("/", 1)[-1]
            r = MagicMock(status_code=200)
            r.text = f'<meta property="og:description" content="A · album-{tid} · Song · 2020">'
            return r

        sess.get = MagicMock(side_effect=_resp)
        api = SpotifyEmbedAPI(session=sess)
        # Fill cache to capacity + 1
        for i in range(257):
            api._fetch_track_album_from_page(f"t{i}")
        # t0 should be evicted, t1..t256 should still be cached
        assert "t0" not in api._album_cache
        assert "t256" in api._album_cache
        # Re-fetching t0 hits the network again
        before = sess.get.call_count
        api._fetch_track_album_from_page("t0")
        assert sess.get.call_count == before + 1


class TestPlaylistClient:
    """Tests for PlaylistClient class."""

    def test_init_creates_embed_api(self):
        """Init should create an embed API instance."""
        client = PlaylistClient()
        assert client._embed_api is not None
        assert isinstance(client._embed_api, SpotifyEmbedAPI)

    def test_get_track_download_link_returns_none(self):
        """Download link should return None (feature deprecated)."""
        client = PlaylistClient()
        assert client.get_track_download_link("abc123") is None

    def test_get_track_youtube_id_returns_none(self):
        """YouTube ID should return None (feature deprecated)."""
        client = PlaylistClient()
        assert client.get_track_youtube_id("abc123") is None


class TestTrackInfo:
    """Tests for TrackInfo dataclass."""

    def test_spotify_id_property(self):
        """spotify_id property should return the id field."""
        track = TrackInfo(
            id="abc123",
            title="Test",
            artists="Artist",
            album=None,
            release_date=None,
            cover_url=None,
            duration_ms=None,
            preview_url=None,
            raw={},
        )
        assert track.spotify_id == "abc123"


class TestPlaylistInfo:
    """Tests for PlaylistInfo dataclass."""

    def test_dataclass_fields(self):
        """Test dataclass field defaults."""
        info = PlaylistInfo(
            name="Test",
            owner=None,
            description=None,
            cover_url=None,
        )
        assert info.name == "Test"
        assert info.track_count is None


class TestDeepFind:
    """Tests for SpotifyEmbedAPI._deep_find static method."""

    def test_finds_key_at_top_level(self):
        data = {"trackList": [1, 2, 3], "other": "value"}
        result = SpotifyEmbedAPI._deep_find(data, "trackList")
        assert result is data

    def test_finds_key_nested(self):
        data = {"a": {"b": {"trackList": [1]}}}
        result = SpotifyEmbedAPI._deep_find(data, "trackList")
        assert result == {"trackList": [1]}

    def test_returns_none_when_missing(self):
        data = {"a": {"b": {"c": "d"}}}
        assert SpotifyEmbedAPI._deep_find(data, "trackList") is None

    def test_respects_max_depth(self):
        data = {"a": {"b": {"c": {"trackList": [1]}}}}
        assert SpotifyEmbedAPI._deep_find(data, "trackList", max_depth=2) is None
        assert SpotifyEmbedAPI._deep_find(data, "trackList", max_depth=4) is not None

    def test_non_dict_returns_none(self):
        assert SpotifyEmbedAPI._deep_find("string", "key") is None  # type: ignore
        assert SpotifyEmbedAPI._deep_find([], "key") is None  # type: ignore


class TestResolvePath:
    """Tests for SpotifyEmbedAPI._resolve_path static method."""

    def test_resolves_valid_path(self):
        data = {"a": {"b": {"c": "value"}}}
        assert SpotifyEmbedAPI._resolve_path(data, ("a", "b", "c")) == "value"

    def test_returns_none_on_missing_key(self):
        data = {"a": {"b": "value"}}
        assert SpotifyEmbedAPI._resolve_path(data, ("a", "x")) is None

    def test_returns_none_on_non_dict_intermediate(self):
        data = {"a": "string"}
        assert SpotifyEmbedAPI._resolve_path(data, ("a", "b")) is None

    def test_empty_path_returns_data(self):
        data = {"a": 1}
        assert SpotifyEmbedAPI._resolve_path(data, ()) is data


class TestResilientExtraction:
    """Tests for resilient entity and token extraction across JSON structures."""

    def test_extract_entity_standard_path(self):
        """Entity found via standard state.data.entity path."""
        api = SpotifyEmbedAPI()
        data = {"props": {"pageProps": {"state": {"data": {"entity": {"name": "Test"}}}}}}
        assert api._extract_entity(data) == {"name": "Test"}

    def test_extract_entity_no_state(self):
        """Entity found when 'state' wrapper is missing."""
        api = SpotifyEmbedAPI()
        data = {"props": {"pageProps": {"data": {"entity": {"name": "NoState"}}}}}
        assert api._extract_entity(data) == {"name": "NoState"}

    def test_extract_entity_flat(self):
        """Entity found directly under pageProps."""
        api = SpotifyEmbedAPI()
        data = {"props": {"pageProps": {"entity": {"name": "Flat"}}}}
        assert api._extract_entity(data) == {"name": "Flat"}

    def test_extract_entity_deep_find_fallback(self):
        """Entity found via _deep_find when no known path matches."""
        api = SpotifyEmbedAPI()
        data = {
            "props": {
                "pageProps": {
                    "weirdKey": {
                        "nested": {"trackList": [{"uri": "spotify:track:x"}], "name": "Deep"}
                    }
                }
            }
        }
        result = api._extract_entity(data)
        assert result["name"] == "Deep"
        assert "trackList" in result

    def test_extract_entity_missing_raises(self):
        """ExtractionError raised with pageProps keys when entity not found."""
        api = SpotifyEmbedAPI()
        data = {"props": {"pageProps": {"someKey": "value", "otherKey": 42}}}
        with pytest.raises(ExtractionError, match="pageProps keys:"):
            api._extract_entity(data)

    def test_token_extraction_standard(self):
        """Token extracted from standard path."""
        api = SpotifyEmbedAPI()
        data = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {"entity": {"name": "Test"}},
                        "settings": {
                            "session": {
                                "accessToken": "tok123",
                                "accessTokenExpirationTimestampMs": 9999999999999,
                            }
                        },
                    }
                }
            }
        }
        # Simulate what _fetch_embed_data does for token caching
        _TOKEN_PATHS = (
            ("props", "pageProps", "state", "settings", "session"),
            ("props", "pageProps", "settings", "session"),
            ("props", "pageProps", "session"),
        )
        for path in _TOKEN_PATHS:
            session_data = api._resolve_path(data, path)
            if isinstance(session_data, dict) and "accessToken" in session_data:
                api._cached_token = session_data.get("accessToken")
                break
        assert api._cached_token == "tok123"

    def test_token_extraction_no_state(self):
        """Token extracted when 'state' wrapper is missing."""
        api = SpotifyEmbedAPI()
        data = {
            "props": {
                "pageProps": {
                    "settings": {
                        "session": {
                            "accessToken": "tok_alt",
                            "accessTokenExpirationTimestampMs": 9999999999999,
                        }
                    }
                }
            }
        }
        _TOKEN_PATHS = (
            ("props", "pageProps", "state", "settings", "session"),
            ("props", "pageProps", "settings", "session"),
            ("props", "pageProps", "session"),
        )
        for path in _TOKEN_PATHS:
            session_data = api._resolve_path(data, path)
            if isinstance(session_data, dict) and "accessToken" in session_data:
                api._cached_token = session_data.get("accessToken")
                break
        assert api._cached_token == "tok_alt"

    def test_token_extraction_flat(self):
        """Token extracted from flat session path."""
        api = SpotifyEmbedAPI()
        data = {
            "props": {
                "pageProps": {
                    "session": {
                        "accessToken": "tok_flat",
                        "accessTokenExpirationTimestampMs": 9999999999999,
                    }
                }
            }
        }
        _TOKEN_PATHS = (
            ("props", "pageProps", "state", "settings", "session"),
            ("props", "pageProps", "settings", "session"),
            ("props", "pageProps", "session"),
        )
        for path in _TOKEN_PATHS:
            session_data = api._resolve_path(data, path)
            if isinstance(session_data, dict) and "accessToken" in session_data:
                api._cached_token = session_data.get("accessToken")
                break
        assert api._cached_token == "tok_flat"
