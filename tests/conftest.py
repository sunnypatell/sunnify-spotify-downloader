"""Shared fixtures for Sunnify tests."""

from __future__ import annotations

# Force the offscreen Qt platform BEFORE any test imports PyQt6. Tests that
# construct QApplication / QDialog without this hit the cocoa qFatal path on
# headless CI and the macOS pytest run alike; conftest.py is collected before
# the test modules so this env var is set in time.
# Hard-assign (not setdefault) because the developer's environment may have
# QT_QPA_PLATFORM exported for a different reason; tests need offscreen
# regardless.
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
# offscreen on Windows has no font database of its own; without the system
# fonts every glyph is a box and text-fit checks measure nonsense
_win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
if os.name == "nt" and os.path.isdir(_win_fonts):
    os.environ.setdefault("QT_QPA_FONTDIR", _win_fonts)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path_factory, monkeypatch):
    """Every test gets its own config dir: config.json and history.json writes
    (a settings save, a finished download) must never touch the developer's
    real settings or history. Tests that patch _config_path still win."""
    from sunnify import config

    folder = str(tmp_path_factory.mktemp("sunnify-config"))
    monkeypatch.setattr(config, "_config_dir", lambda: folder)
    return folder


@pytest.fixture(autouse=True)
def _english_ui():
    """Assertions read English; a test that switches language can't leak it."""
    from sunnify import i18n

    i18n.set_language("en")
    yield
    i18n.set_language("en")


# Module-scoped QApplication so every Qt test in the session reuses one
# instance. PyQt6 + macOS gets unhappy if QApplication is constructed
# multiple times in the same process, and the cocoa platform's
# QWidgetPrivate constructor will qFatal on what looks like a half-shutdown
# Qt state. Providing a single managed instance side-steps that whole
# class of pytest-Qt interaction bugs.
@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance
    # Don't quit() on teardown - Python is about to exit anyway and quitting
    # mid-test cleanup can race with widget destruction.


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

# Alternative structure: no "state" wrapper (Spotify A/B test variant)
SAMPLE_EMBED_HTML_NO_STATE = """
<!DOCTYPE html>
<html>
<head><title>Spotify Embed</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "data": {
        "entity": {
          "name": "Test Playlist",
          "subtitle": "Test User",
          "trackList": [
            {
              "uri": "spotify:track:abc123",
              "title": "Test Song 1",
              "subtitle": "Artist 1",
              "duration": 180000
            }
          ]
        }
      },
      "settings": {
        "session": {
          "accessToken": "token_no_state",
          "accessTokenExpirationTimestampMs": 9999999999999
        }
      }
    }
  }
}
</script>
</body>
</html>
"""

# Alternative structure: entity directly under pageProps (flat)
SAMPLE_EMBED_HTML_FLAT = """
<!DOCTYPE html>
<html>
<head><title>Spotify Embed</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "entity": {
        "name": "Flat Playlist",
        "subtitle": "Flat User",
        "trackList": [
          {
            "uri": "spotify:track:flat001",
            "title": "Flat Song",
            "subtitle": "Flat Artist",
            "duration": 200000
          }
        ]
      },
      "session": {
        "accessToken": "token_flat",
        "accessTokenExpirationTimestampMs": 9999999999999
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
def sample_embed_html_no_state():
    """Return sample embed HTML without 'state' wrapper."""
    return SAMPLE_EMBED_HTML_NO_STATE


@pytest.fixture
def sample_embed_html_flat():
    """Return sample embed HTML with flat entity structure."""
    return SAMPLE_EMBED_HTML_FLAT


@pytest.fixture
def mock_session(mocker):
    """Create a mock requests session."""
    return mocker.MagicMock()
