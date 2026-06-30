"""Metadata writer utilities for embedding ID3 tags and cover art in audio files."""

import asyncio
import os
from pathlib import Path
from typing import TypedDict

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._frames import  APIC, TXXX

from models.new import TrackDerived
from core.singleton.logger import logger


class TrackMetadata(TypedDict):
    """Metadata to embed in audio file."""
    title: str
    artists: str
    album: str | None
    release_date: str | None
    recording_label: str | None
    track_number: int | None
    youtube_url: str | None


async def fetch_cover_bytes(cover_url: str | None) -> bytes | None:
    """Download cover image bytes asynchronously.

    Args:
        cover_url: URL to cover image

    Returns:
        Image bytes or None on failure
    """
    if not cover_url:
        return None

    try:
        def _fetch():
            resp = requests.get(cover_url, timeout=15)
            if resp.status_code == 200 and resp.content:
                return resp.content
            return None

        return await asyncio.to_thread(_fetch)
    except (requests.RequestException, OSError) as exc:
        logger.warning(f"Error fetching cover from {cover_url}: {exc}")
        return None


def write_metadata_mp3(
    file_path: str,
    metadata: TrackMetadata,
    cover_bytes: bytes | None = None
) -> bool:
    """Write ID3 tags and cover art to MP3 file.

    Args:
        file_path: Path to MP3 file
        metadata: Dict with keys: title, artists, album, release_date,
                 recording_label, track_number, youtube_url
        cover_bytes: JPEG image bytes for cover art

    Returns:
        True on success, False on failure
    """
    try:
        # Read existing ID3 tags if they exist
        try:
            audio = EasyID3(file_path)
        except Exception:
            audio = EasyID3()

        # Update with new values
        if metadata.get("title"):
            audio["title"] = metadata["title"]
        if metadata.get("artists"):
            audio["artist"] = metadata["artists"]
        if metadata.get("album"):
            audio["album"] = metadata["album"]
        if metadata.get("release_date"):
            audio["date"] = metadata["release_date"]
        if metadata.get("recording_label"):
            audio["publisher"] = metadata["recording_label"]
        if metadata.get("track_number"):
            audio["tracknumber"] = str(metadata["track_number"])

        audio.save()

        # Write additional frames using ID3 directly
        try:
            id3 = ID3(file_path)
        except Exception:
            id3 = ID3()

        # Add cover art if provided
        if cover_bytes:
            id3["APIC"] = APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Front cover
                desc="Cover",
                data=cover_bytes
            )

        # Save YouTube URL as custom frame
        youtube_url = metadata.get("youtube_url")
        if youtube_url:
            id3["TXXX:YouTubeURL"] = TXXX(
                encoding=3,
                desc="YouTubeURL",
                text=[youtube_url]
            )

        id3.save(file_path, v2_version=4)
        return True

    except Exception as exc:
        logger.error(f"Error writing metadata to MP3 {file_path}: {exc}")
        return False


def write_metadata_m4a(
    file_path: str,
    metadata: TrackMetadata,
    cover_bytes: bytes | None = None
) -> bool:
    """Write iTunes atom tags and cover art to M4A file.

    Args:
        file_path: Path to M4A file
        metadata: Dict with metadata fields
        cover_bytes: JPEG image bytes for cover art

    Returns:
        True on success, False on failure
    """
    try:
        from mutagen.mp4 import MP4, MP4Cover

        audio = MP4(file_path)

        if metadata["title"]:
            audio["\xa9nam"] = metadata["title"]
        if metadata["artists"]:
            audio["\xa9ART"] = metadata["artists"]
        if metadata["album"]:
            audio["\xa9alb"] = metadata["album"]
        if metadata["release_date"]:
            audio["\xa9day"] = metadata["release_date"]
        if metadata["track_number"]:
            audio["trkn"] = metadata["track_number"] or 0
        if metadata["youtube_url"]:
            audio["----:com.apple.itunes:YouTubeURL"] = [(metadata["youtube_url"] or "").encode("utf-8")]
        if cover_bytes:
            audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        return True

    except Exception as exc:
        logger.error(f"Error writing metadata to M4A {file_path}: {exc}")
        return False


def write_metadata_flac(
    file_path: str,
    metadata: TrackMetadata,
    cover_bytes: bytes | None = None
) -> bool:
    """Write Vorbis comments and cover art to FLAC file.

    Args:
        file_path: Path to FLAC file
        metadata: Dict with metadata fields
        cover_bytes: JPEG image bytes for cover art

    Returns:
        True on success, False on failure
    """
    try:
        from mutagen.flac import FLAC, Picture

        audio = FLAC(file_path)

        if metadata.get("title"):
            audio["title"] = metadata["title"]
        if metadata.get("artists"):
            audio["artist"] = metadata["artists"]
        if metadata.get("album"):
            audio["album"] = metadata["album"]
        if metadata.get("release_date"):
            audio["date"] = metadata["release_date"]
        if metadata.get("recording_label"):
            audio["publisher"] = metadata["recording_label"]
        if metadata.get("track_number"):
            audio["tracknumber"] = str(metadata["track_number"])
        if metadata.get("youtube_url"):
            audio["YouTubeURL"] = metadata["youtube_url"]

        if cover_bytes:
            pic = Picture()
            pic.type = 3  # Front cover
            pic.mime = "image/jpeg"
            pic.desc = "Cover"
            pic.data = cover_bytes
            audio.add_picture(pic)

        audio.save()
        return True

    except Exception as exc:
        logger.error(f"Error writing metadata to FLAC {file_path}: {exc}")
        return False


_METADATA_WRITERS = {
    ".mp3": write_metadata_mp3,
    ".m4a": write_metadata_m4a,
    ".flac": write_metadata_flac,
}


async def write_metadata_to_file(
    file_path: str,
    track_data: TrackDerived,
):
    """Write metadata and cover art to audio file asynchronously.

    Determines file format and calls appropriate metadata writer via asyncio.to_thread.
    Cover image is fetched asynchronously if URL is available.

    Args:
        file_path: Path to audio file
        track_data: TrackDerived with metadata
        add_meta_tags: Whether to embed metadata (from UserConfig)

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Verify file exists
    if not Path(file_path).exists():
        logger.error(f"write_metadata_to_file - File not found: {file_path}")
        return (False, "FILE_NOT_FOUND", f"Path: {file_path}")
    logger.info(f"write_metadata_to_file - File found: {file_path}")
    
    # Get file extension
    ext = os.path.splitext(file_path)[1].lower()
    writer = _METADATA_WRITERS.get(ext)

    if not writer:
        logger.error(f"write_metadata_to_file - Unsupported format: {ext}")
        return (False, "UNSUPPORTED_FORMAT", f"Format: {ext}")
    logger.info(f"write_metadata_to_file - Format supported: {ext}")

    # Fetch cover bytes if URL available
    cover_bytes: bytes | None = None
    if track_data.cover_url:
        cover_bytes = await fetch_cover_bytes(track_data.cover_url)
        if not cover_bytes:
            logger.warning(f"Could not fetch cover for {track_data.title}")
    logger.info(f"write_metadata_to_file - Fetched Cover URL: {track_data.cover_url}")

    # Prepare metadata dict
    metadata: TrackMetadata = {
        "title": track_data.title,
        "artists": track_data.artists,
        "album": track_data.album,
        "release_date": None,  # TODO: get from TrackRaw when available in TrackDerived
        "recording_label": track_data.recording_label,
        "track_number": None,  # TODO: get track position if needed
        "youtube_url": track_data.youtube_url,
    }

    # Write metadata via executor thread (mutagen is sync-only)
    try:
        logger.info(f"write_metadata_to_file - Writing metadata to file with asyncio.to_thread")
        success = await asyncio.to_thread(
            writer,
            file_path,
            metadata,
            cover_bytes
        )

        if success:
            logger.info(f"write_metadata_to_file - Writing metadata to file with asyncio.to_thread - Success")
            return (True, "SUCCESS", "Metadata written successfully")
        else:
            logger.error(f"write_metadata_to_file - Writing metadata to file with asyncio.to_thread - Failed")
            return (False, "FAILED_TO_WRITE_METADATA", "Failed to write metadata")

    except Exception as exc:
        logger.error(f"write_metadata_to_file - Writing metadata to file with asyncio.to_thread - Exception: {exc}")
        return (False, "FAILED_TO_WRITE_METADATA_EXCEPTION", str(exc))
