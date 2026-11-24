"""Tests for Flask backend app."""

from __future__ import annotations

# Check if Flask is installed
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

# Add backend directory for imports
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "web-app" / "sunnify-backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Skip all tests in this module if Flask is not installed
pytestmark = pytest.mark.skipif(
    not FLASK_AVAILABLE,
    reason="Flask not installed (web backend tests require separate environment)",
)


@pytest.fixture
def app():
    """Create Flask test app."""
    # Import here to avoid issues with path setup
    from app import app as flask_app

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def _fresh_rate_limit():
    """Every test starts with an empty window; the limiter is process-wide."""
    if FLASK_AVAILABLE:
        from app import limiter

        limiter.reset()


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        """Health endpoint should return ok status."""
        response = client.get("/api/health")
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["mode"] == "metadata-only"


class TestRootEndpoint:
    """Tests for / endpoint."""

    def test_root_returns_api_info(self, client):
        """Root endpoint should return API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Sunnify API"
        assert "endpoints" in data


class TestScrapePlaylistEndpoint:
    """Tests for /api/scrape-playlist endpoint."""

    def test_missing_url_returns_400(self, client):
        """Missing URL should return 400."""
        response = client.post(
            "/api/scrape-playlist",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["event"] == "error"
        assert "No URL" in data["data"]["message"]

    def test_empty_url_returns_400(self, client):
        """Empty URL should return 400."""
        response = client.post(
            "/api/scrape-playlist",
            json={"playlistUrl": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_invalid_url_returns_400(self, client):
        """Invalid Spotify URL should return 400."""
        response = client.post(
            "/api/scrape-playlist",
            json={"playlistUrl": "https://example.com/invalid"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["event"] == "error"

    def test_malformed_json_returns_400(self, client):
        response = client.post(
            "/api/scrape-playlist",
            data="{not-json",
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.get_json()["event"] == "error"

    def test_non_object_json_returns_400(self, client):
        response = client.post(
            "/api/scrape-playlist",
            json=["https://open.spotify.com/playlist/abc123"],
        )
        assert response.status_code == 400
        assert response.get_json()["data"]["message"] == "Invalid request body"

    @pytest.mark.parametrize("value", [123, None, ["https://open.spotify.com/playlist/abc123"]])
    def test_non_string_url_returns_400(self, client, value):
        response = client.post("/api/scrape-playlist", json={"playlistUrl": value})
        assert response.status_code == 400
        assert "No URL" in response.get_json()["data"]["message"]

    @patch("app.get_playlist_client")
    def test_valid_playlist_url(self, mock_get_client, client):
        """Valid playlist URL should return track data."""
        # Create mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock playlist metadata
        mock_metadata = MagicMock()
        mock_metadata.name = "Test Playlist"
        mock_metadata.owner = "Test User"
        mock_metadata.cover_url = "https://example.com/cover.jpg"
        mock_client.get_playlist_metadata.return_value = mock_metadata

        # Mock track iteration
        mock_track = MagicMock()
        mock_track.spotify_id = "abc123"
        mock_track.title = "Test Song"
        mock_track.artists = "Test Artist"
        mock_track.album = "Test Album"
        mock_track.cover_url = None
        mock_track.release_date = "2024-01-01"
        mock_client.iter_playlist_tracks.return_value = [mock_track]

        response = client.post(
            "/api/scrape-playlist",
            json={"playlistUrl": "https://open.spotify.com/playlist/abc123"},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["event"] == "complete"
        assert data["data"]["playlistName"] == "Test Playlist - Test User"
        assert len(data["data"]["tracks"]) == 1
        assert data["data"]["tracks"][0]["title"] == "Test Song"

    @patch("app.SpotifyEmbedAPI")
    def test_valid_track_url(self, mock_api_class, client):
        """Valid track URL should return single track data."""
        # Create mock API instance
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        # Mock track data
        mock_track = MagicMock()
        mock_track.spotify_id = "xyz789"
        mock_track.title = "Single Track"
        mock_track.artists = "Solo Artist"
        mock_track.album = "Solo Album"
        mock_track.cover_url = "https://example.com/track-cover.jpg"
        mock_track.release_date = "2024-06-15"
        mock_api.get_track.return_value = mock_track

        response = client.post(
            "/api/scrape-playlist",
            json={"playlistUrl": "https://open.spotify.com/track/xyz789"},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["event"] == "complete"
        assert len(data["data"]["tracks"]) == 1
        assert data["data"]["tracks"][0]["title"] == "Single Track"


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, client):
        """CORS headers should be present on responses."""
        response = client.get("/api/health")
        # Flask-CORS adds these headers
        # The exact headers depend on the request origin
        assert response.status_code == 200

    def test_options_preflight(self, client):
        """OPTIONS preflight request should work."""
        response = client.options(
            "/api/scrape-playlist",
            headers={"Origin": "http://localhost:3000"},
        )
        # Should not error
        assert response.status_code in (200, 204)


class TestHardening:
    """The controls that keep a public, unauthenticated endpoint from being abused."""

    PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

    def test_cors_only_answers_the_web_client(self, client):
        ok = client.options(
            "/api/scrape-playlist",
            headers={
                "Origin": "https://sunnify-spotify-downloader.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert ok.headers.get("Access-Control-Allow-Origin") == (
            "https://sunnify-spotify-downloader.vercel.app"
        )
        evil = client.options(
            "/api/scrape-playlist",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert "Access-Control-Allow-Origin" not in evil.headers

    def test_security_headers_on_every_response(self, client):
        for response in (client.get("/api/health"), client.get("/nope")):
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert response.headers["Cache-Control"] == "no-store"

    def test_errors_use_the_json_envelope(self, client):
        response = client.get("/nope")
        assert response.status_code == 404
        assert response.get_json()["event"] == "error"
        assert client.get("/api/scrape-playlist").status_code == 405

    def test_oversized_body_is_refused_before_parsing(self, client):
        response = client.post(
            "/api/scrape-playlist",
            data=b'{"playlistUrl": "' + b"x" * 20_000 + b'"}',
            content_type="application/json",
        )
        assert response.status_code == 413
        assert response.get_json()["event"] == "error"

    def test_rate_limit_per_client(self, client, monkeypatch):
        import app as backend

        monkeypatch.setattr(backend.limiter, "per_minute", 2)
        for _ in range(2):
            assert client.post("/api/scrape-playlist", json={}).status_code == 400
        limited = client.post("/api/scrape-playlist", json={})
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) >= 1
        other = client.post(
            "/api/scrape-playlist", json={}, environ_base={"REMOTE_ADDR": "10.9.9.9"}
        )
        assert other.status_code == 400  # a different client still gets through

    def test_forwarded_for_from_the_proxy_identifies_the_client(self, client, monkeypatch):
        import app as backend

        monkeypatch.setattr(backend.limiter, "per_minute", 1)
        first = {"X-Forwarded-For": "203.0.113.7"}
        assert client.post("/api/scrape-playlist", json={}, headers=first).status_code == 400
        assert client.post("/api/scrape-playlist", json={}, headers=first).status_code == 429
        second = {"X-Forwarded-For": "203.0.113.8"}
        assert client.post("/api/scrape-playlist", json={}, headers=second).status_code == 400

    @patch("app.get_playlist_client")
    def test_huge_playlists_are_capped_and_flagged(self, mock_get_client, client, monkeypatch):
        import app as backend

        monkeypatch.setattr(backend, "MAX_TRACKS", 3)
        mock_client = MagicMock()
        mock_client.get_playlist_metadata.return_value = MagicMock(
            name="m", owner="o", cover_url=""
        )
        mock_client.iter_playlist_tracks.return_value = (
            MagicMock(
                spotify_id=str(i), title="t", artists="a", album="", cover_url="", release_date=""
            )
            for i in range(10)
        )
        mock_get_client.return_value = mock_client
        data = client.post("/api/scrape-playlist", json={"playlistUrl": self.PLAYLIST}).get_json()
        assert len(data["data"]["tracks"]) == 3
        assert data["data"]["truncated"] is True
