"""Sunnify (Spotify Downloader)
Copyright (C) 2024-2026 Sunny Patel <sunnypatel124555@gmail.com>

EDUCATIONAL PROJECT DISCLAIMER:
This software is a student portfolio project developed for educational purposes only.
It is intended to demonstrate software engineering skills and is provided free of charge.
Users are solely responsible for ensuring compliance with applicable laws in their jurisdiction.
This software should only be used with content you own or have permission to download.
See DISCLAIMER.md for full terms.

Package layout (import cost rises down the list; the CLI never goes past engine):
  config    settings registry, config.json            stdlib only
  logs      rotating session log, crash forensics     stdlib only
  tools     ffmpeg, javascript runtime, cookies       stdlib only
  locking   one writer per playlist folder            stdlib only
  history   past downloads, newest first              stdlib only
  i18n      English / Bahasa Melayu strings           stdlib only
  lyrics    LRCLIB lookup                             requests
  tagging   tag + cover + lyrics writers              mutagen, QtCore
  updates   newer-release check                       requests, QtCore
  engine    MusicScraper: spotify -> youtube -> file  yt-dlp, QtCore
  gui/      the desktop window and its dialogs        QtWidgets
"""

__version__ = "3.0.0"
