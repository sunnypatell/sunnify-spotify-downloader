"""Utility script to probe the external APIs used by the legacy PyQt desktop
Spotify downloader. The goal is to quickly detect which endpoints are failing
so that they can be replaced or patched in the GUI application."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class EndpointResult:
    name: str
    url: str
    method: str
    ok: bool
    status_code: Optional[int]
    notes: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "ok": self.ok,
            "status_code": self.status_code,
            "notes": self.notes,
        }


DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "origin": "https://spotifydown.com",
    "referer": "https://spotifydown.com/",
}


def safe_get(url: str, **kwargs: Any) -> EndpointResult:
    name = kwargs.pop("name")
    try:
        response = requests.get(url, timeout=15, **kwargs)
        ok = response.ok
        notes = response.text[:200] or "<empty response>"
        return EndpointResult(
            name=name,
            url=url,
            method="GET",
            ok=ok,
            status_code=response.status_code,
            notes=notes,
        )
    except requests.RequestException as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name=name,
            url=url,
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def safe_post(url: str, **kwargs: Any) -> EndpointResult:
    name = kwargs.pop("name")
    try:
        response = requests.post(url, timeout=15, **kwargs)
        ok = response.ok
        snippet = response.text[:200] or "<empty response>"
        return EndpointResult(
            name=name,
            url=url,
            method="POST",
            ok=ok,
            status_code=response.status_code,
            notes=snippet,
        )
    except requests.RequestException as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name=name,
            url=url,
            method="POST",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def main() -> int:
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Spotify's "Today's Top Hits"
    track_id = "4uLU6hMCjMI75M1A2tKUQC"  # Rick Astley - Never Gonna Give You Up
    youtube_id = "dQw4w9WgXcQ"

    results = [
        safe_get(
            f"https://api.spotifydown.com/trackList/playlist/{playlist_id}",
            headers=DEFAULT_HEADERS,
            name="spotifydown_track_list",
        ),
        safe_get(
            f"https://api.spotifydown.com/metadata/playlist/{playlist_id}",
            headers=DEFAULT_HEADERS,
            name="spotifydown_playlist_metadata",
        ),
        safe_get(
            f"https://api.spotifydown.com/getId/{track_id}",
            headers=DEFAULT_HEADERS,
            name="spotifydown_get_id",
        ),
        safe_get(
            f"https://api.spotifydown.com/download/{track_id}",
            headers=DEFAULT_HEADERS,
            name="spotifydown_download",
        ),
        safe_post(
            "https://corsproxy.io/?https://www.y2mate.com/mates/analyzeV2/ajax",
            data={
                "k_query": f"https://www.youtube.com/watch?v={youtube_id}",
                "k_page": "home",
                "hl": "en",
                "q_auto": 0,
            },
            headers={**DEFAULT_HEADERS, "content-type": "application/x-www-form-urlencoded"},
            name="corsproxy_y2mate_analyze",
        ),
        safe_post(
            "https://corsproxy.io/?https://www.y2mate.com/mates/convertV2/index",
            data={"vid": youtube_id, "k": "placeholder"},
            headers={**DEFAULT_HEADERS, "content-type": "application/x-www-form-urlencoded"},
            name="corsproxy_y2mate_convert",
        ),
    ]

    json.dump([result.as_dict() for result in results], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    raise SystemExit(main())
