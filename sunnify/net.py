"""Bounded HTTP reads for things the app shows or embeds (cover art, thumbnails).

The URLs come from Spotify's responses, so they are data, not code we wrote:
only http(s) is fetched, and a body larger than the cap is dropped rather than
read into memory, whatever the server's Content-Length claims.
"""

from __future__ import annotations

from typing import TypeGuard
from urllib.parse import urlsplit

import requests

from sunnify.logs import log

# Spotify's largest cover is 640x640 JPEG, well under 1 MB; 10 MB is generous
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_CHUNK = 64 * 1024


def is_web_url(url: str | None) -> TypeGuard[str]:
    """True for an absolute http(s) URL with a host; nothing else is fetched or opened."""
    if not url or not isinstance(url, str):
        return False
    parts = urlsplit(url)
    return parts.scheme in ("https", "http") and bool(parts.netloc)


def fetch_bytes(
    url: str | None, *, limit: int = MAX_IMAGE_BYTES, timeout: float = 15
) -> bytes | None:
    """The body of a 200 response, or None: bad URL, error, empty, or over `limit` bytes."""
    if not is_web_url(url):
        return None
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
    except (requests.RequestException, OSError) as exc:
        log.debug("fetch failed for %s: %s", url, exc)
        return None
    try:
        if resp.status_code != 200:
            return None
        declared = str(resp.headers.get("content-length") or "")
        if declared.isdigit() and int(declared) > limit:
            log.warning("refused %s: %s bytes is over the %s byte cap", url, declared, limit)
            return None
        body = bytearray()
        for chunk in resp.iter_content(_CHUNK):
            body += chunk
            if len(body) > limit:
                log.warning("refused %s: body passed the %s byte cap", url, limit)
                return None
        return bytes(body) or None
    except (requests.RequestException, OSError) as exc:
        log.debug("fetch failed for %s: %s", url, exc)
        return None
    finally:
        resp.close()
