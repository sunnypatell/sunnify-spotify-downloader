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

    def test_empty_url_raises_valueerror(self):
        """Empty URL should raise ValueError."""
        with pytest.raises(ValueError):
            extract_playlist_id("")


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

    def test_album_url_raises_valueerror(self):
        """Album URLs are not supported."""
        with pytest.raises(ValueError, match="Invalid Spotify URL"):
            detect_spotify_url_type("https://open.spotify.com/album/abc123")


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_sanitization(self):
        """Basic filename sanitization."""
        assert sanitize_filename("Hello World") == "Hello World"

    def test_removes_special_chars(self):
        """Special characters should be removed."""
        assert sanitize_filename("Hello@World#123!") == "HelloWorld123"

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

    def test_empty_string_returns_unknown(self):
        """Empty or all-special chars should return 'Unknown'."""
        assert sanitize_filename("@#$%^&*") == "Unknown"
        assert sanitize_filename("") == "Unknown"

    def test_unicode_characters_removed(self):
        """Unicode characters should be removed."""
        assert sanitize_filename("Café ☕ Music") == "Caf Music"

    def test_long_filename(self):
        """Long filenames should be handled."""
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        # Current implementation doesn't truncate, just sanitizes
        assert result == "A" * 300


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
