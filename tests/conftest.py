"""Shared fixtures for Sunnify tests."""

from __future__ import annotations

import pytest  # noqa: F401

# Sample Spotify embed page HTML with __NEXT_DATA__
SAMPLE_EMBED_HTML = """
<!DOCTYPE html>
<html>
<head><title>Spotify Embed</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "state": {
        "data": {
          "entity": {
            "name": "Test Playlist",
            "title": "Test Playlist",
            "subtitle": "Test User",
            "description": "A test playlist",
            "coverArt": {
              "sources": [
                {"url": "https://example.com/cover-small.jpg", "width": 64},
                {"url": "https://example.com/cover-large.jpg", "width": 300}
              ]
            },
            "trackList": [
              {
                "uri": "spotify:track:abc123",
                "title": "Test Song 1",
                "subtitle": "Artist 1",
                "duration": 180000,
                "audioPreview": {"url": "https://preview.example.com/1.mp3"},
                "album": {"name": "Test Album"}
              },
              {
                "uri": "spotify:track:def456",
                "title": "Test Song 2",
                "subtitle": "Artist 2",
                "duration": 200000,
                "audioPreview": {"url": "https://preview.example.com/2.mp3"},
                "album": {"name": "Test Album 2"}
              }
            ]
          }
        },
        "settings": {
          "session": {
            "accessToken": "test_token_12345",
            "accessTokenExpirationTimestampMs": 9999999999999
          }
        }
      }
    }
  }
}
</script>
</body>
</html>
"""

# Sample track embed HTML
SAMPLE_TRACK_EMBED_HTML = """
<!DOCTYPE html>
<html>
<head><title>Spotify Track</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "state": {
        "data": {
          "entity": {
            "name": "Individual Track",
            "title": "Individual Track",
            "subtitle": "Solo Artist",
            "duration": 210000,
            "artists": [{"name": "Solo Artist"}],
            "visualIdentity": {
              "image": [
                {"url": "https://example.com/track-cover.jpg", "maxWidth": 300}
              ]
            },
            "releaseDate": {"isoString": "2024-01-15T00:00:00Z"},
            "audioPreview": {"url": "https://preview.example.com/track.mp3"}
          }
        },
        "settings": {
          "session": {
            "accessToken": "test_token_track",
            "accessTokenExpirationTimestampMs": 9999999999999
          }
        }
      }
    }
  }
}
</script>
</body>
</html>
"""

# Sample spclient response for large playlists
SAMPLE_SPCLIENT_RESPONSE = {
    "length": 150,
    "contents": {
        "items": [
            {"uri": "spotify:track:abc123"},
            {"uri": "spotify:track:def456"},
            {"uri": "spotify:track:ghi789"},
            {"uri": "spotify:track:jkl012"},
        ]
    },
}

# Sample track metadata dict
SAMPLE_TRACK_META = {
    "title": "Test Song",
    "artists": "Test Artist",
    "album": "Test Album",
    "releaseDate": "2024-01-01",
    "cover": "https://example.com/cover.jpg",
    "file": "/tmp/test.mp3",
}


@pytest.fixture
def sample_embed_html():
    """Return sample Spotify embed HTML."""
    return SAMPLE_EMBED_HTML


@pytest.fixture
def sample_track_embed_html():
    """Return sample Spotify track embed HTML."""
    return SAMPLE_TRACK_EMBED_HTML


@pytest.fixture
def sample_spclient_response():
    """Return sample spclient API response."""
    return SAMPLE_SPCLIENT_RESPONSE


@pytest.fixture
def sample_track_meta():
    """Return sample track metadata dict."""
    return dict(SAMPLE_TRACK_META)


@pytest.fixture
def mock_session(mocker):
    """Create a mock requests session."""
    return mocker.MagicMock()
