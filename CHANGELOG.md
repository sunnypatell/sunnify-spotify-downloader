# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.1] - 2026-07-13

### Added
- **filename order is now a setting: "Artist - Song" instead of "Song - Artist" (closes #77).** a checkbox in Settings swaps the two components in every naming path (playlist, single track, and the duplicate-name collision guard), composing with the track-number prefix (`01. Artist - Song.mp3`). both parts still go through the same cross-platform sanitizer documented against the [windows naming rules](https://learn.microsoft.com/windows/win32/fileio/naming-a-file) and [posix pathname rules](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html), so the swap cannot change path safety - verified with an adversarial battery (reserved device names, trailing dots, control chars, emoji, 300-char titles) in both orders.
- **sample rate is now a setting: auto (source), 44.1 kHz, or 48 kHz (closes #80).** youtube audio is 48 kHz, so flac/wav rips came out 48 kHz with no way to get cd-standard 44.1; the new selector rides yt-dlp's [`postprocessor_args`](https://github.com/yt-dlp/yt-dlp#post-processing-options) into ffmpeg's `-ar`. deliberately scoped to the formats that always transcode (mp3/flac/wav): opus is [48 kHz-only by codec design](https://datatracker.ietf.org/doc/html/rfc6716#section-2), and m4a may stream-copy an aac source (where ffmpeg silently ignores `-ar`), so both grey the selector out instead of sometimes-working.
- **the macOS Intel binary is back: `Sunnify-macOS-Intel.zip` (closes #79).** intel builds were dropped in 01c241e5 on the mistaken premise that rosetta covers intel macs - rosetta 2 only translates x86_64 to apple silicon, never the reverse, so intel users on macOS 15 (the [last macOS for intel hardware](https://support.apple.com/en-us/120282)) got "not supported on this type of Mac" while the readme still claimed intel support. builds now run natively on github's [`macos-15-intel` runner](https://github.com/actions/runner-images/issues/13045) against [qt 6.11's supported x86_64 target](https://doc.qt.io/qt-6/supported-platforms.html), with the same hash-locked deps, sha-pinned ffmpeg, and slsa l3 attestation as every other binary. the homebrew cask now picks the right architecture automatically. intel builds ride github's final x86_64 image (supported into august 2027), carrying intel macs through the rest of their supported life alongside apple's own timeline.
- **every macOS build must now boot before it ships.** the release pipeline launches the freshly built app headless on the build runner and fails the release if it dies within 10 seconds - the exact gate that would have caught arm64-only binaries being served to intel users.
- **a signal death now leaves a forensic line in the log.** historical "the app died right after launch, no session-end, nothing in the log" reports were untraceable: a default-action SIGINT/SIGTERM skips atexit and every hook. the app now logs `terminated by signal <NAME>`, flushes, and re-raises under `SIG_DFL` - identical instant-kill behavior (verified: no hang at any timing from 0.15s to 2.5s after launch), but the next mystery kill names its killer.

### Fixed
- **non-latin tracks download again: cyrillic, greek, cjk, indic (closes the #77 report "files with cyrillic in the name don't download").** the youtube match normalizer collapsed every non-latin title to an empty string, so even a character-identical youtube upload was rejected and the track skipped. normalization now keeps letters, digits, and combining marks from any script (category-based per [unicode's general categories](https://www.unicode.org/reports/tr44/#General_Category_Values) - marks must survive or distinct indic words collapse into the same consonant skeleton), and a fully non-latin artist no longer arms the artist gate against romanized uploads. latin matching is byte-identical to before - proven by a 100,000-case fuzz against the old implementation and pinned in tests - so the #52 wrong-audio safeguard is untouched.

### Notes
- verified before shipping: 228 tests green; the exact reported scenario reproduced first (identical cyrillic title rejected by the matcher, live) and re-verified fixed end-to-end with real downloads landing `Группа крови - Кино.mp3` and a 44.1 kHz flac confirmed by ffprobe; an x86_64 build was produced and boot-verified locally under rosetta before the ci intel job was written; the full pipeline (all four binaries) dry-ran green on a throwaway rc tag before this release was cut. binaries built with yt-dlp 2026.6.9 on python 3.13.

## [2.1.0] - 2026-07-02

### Changed
- **the ui framework moved from qt 5 to qt 6 (PyQt6 6.11).** qt 5 has been end-of-life for open-source users, so the app now runs on a maintained framework with current security fixes. the port follows [riverbank's documented pyqt5→pyqt6 differences](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html) (scoped enums, `exec()`, `globalPosition()`) and [qt's own porting guidance](https://doc.qt.io/qt-6/portingguide.html); qt 6's always-on [high-dpi scaling](https://doc.qt.io/qt-6/highdpi.html) replaces the manual attributes while the `PassThrough` rounding policy from the #64 fix stays explicit. no visual or behavioral changes intended - the ui is the same gradient card, verified pixel-by-pixel (see notes).
- **the pyqt5-qt5 windows wheel pin is gone for good.** pyqt5-qt5 published no windows wheels after 5.15.2, which forced a hand-maintained per-platform pin and a dependabot ignore (and caused real breakage in #70); pyqt6-qt6 ships current wheels on all three platforms, so the pin, the ignore, and the guardrail note are all deleted.
- `Template.py` was ported by hand (imports, scoped enums, and integer font weights to [qt 6's opentype weight scale](https://doc.qt.io/qt-6/qfont.html#Weight-enum)); it is deliberately not regenerated from the stale `Template.ui`.

### Fixed
- **closing the app no longer records itself as a crash.** the window's close button called `sys.exit()` inside a qt slot, which raised `SystemExit` into qt's exception hook and wrote a `CRITICAL uncaught exception` to the log on every normal close, with no clean session-end - so the logs read as if the app kept crashing. it now leaves the event loop the [documented way](https://doc.qt.io/qt-6/qcoreapplication.html#quit) (`QApplication.quit()`), and an intentional `SystemExit` is treated as a clean exit, not a crash.
- **the "Show Preview" panel no longer crashes on qt 6.** its slide animation referenced `QEasingCurve.InOutQuad`, which is `QEasingCurve.Type.InOutQuad` under qt 6's scoped enums - it would have aborted on the first click. new interaction tests now drive the animation, the frameless-window drag, and the close path so this class of enum regression can't hide behind a green suite again.

### Notes
- verified before shipping: 213 tests green under pyqt6 across python 3.10-3.13 on all three OSes; every dialog and the main window rendered at 1x/1.5x/2x on macos, windows, and linux and compared against the pyqt5 baselines (identity preserved, including the linux font-substitution case); every button, dialog, animation, and the drag handlers exercised headless with zero enum failures; close and ctrl+c both verified to exit cleanly with a proper session-end log; and a full release-pipeline dry-run built and attested all three platforms before this release was cut. binaries built with yt-dlp 2026.6.9 on python 3.13.

## [2.0.15] - 2026-07-02

### Changed
- **python floor raised to 3.10; binaries now bundle python 3.13.** 3.9 hit end-of-life in october 2025 and only ever applied to source installs - every shipped binary has always bundled its own interpreter, so binary users are unaffected. 3.10 keeps ubuntu 22.04 LTS source installs working. release, lint, and lock-check CI moved from 3.11 to 3.13; the test matrix is now 3.10-3.13 across all three OSes.
- **mutagen 1.47 -> 1.48.1 in shipped binaries** (the eol-3.9 back-pin retired). tag writing verified unchanged: the byte-level id3v2.3 suite passes against 1.48.1.
- **pytest 8 -> 9 in ci** (same retired pin); clears the last python-side security advisory (GHSA-6w46-j5rx-g56g).
- **(web) backend runtime bumped from an unpatched python 3.11.0 (oct 2022) to 3.13.14** on render.
- **(web) dead `framer-motion` dependency removed** (declared, never imported); node engines raised to 22 (20 hit eol april 2026); the webclient readme's stale "next.js 14 / node 18" claims corrected.

### Notes
- currency release; no changes to the spotify metadata path, audio formats, tags, or the default matching policy. verified end-to-end: 208 tests green on pytest 9.1.1 + mutagen 1.48.1, live upstream contract check green (spotify embed + anonymous token + youtube search + the real match selector via `scripts/check_api_status.py`), webclient typecheck/lint/build green. binaries built with yt-dlp 2026.6.9.

## [2.0.14] - 2026-07-02

### Added
- **one-time "star the repo" ask when the first song lands.** a small card (same pattern as the update notifier) appears exactly once per install, the moment the first song of the user's first run finishes writing to disk - so value is proven by a real file and huge playlists don't have to reach "complete" for it to ever show. the shown-flag persists before the dialog opens so a crash can never re-prompt, a run the user stopped never prompts, it never stacks on the update notifier (defers and retries on the next landed song), and both buttons dismiss it forever. no telemetry, no recurring nag.

### Fixed
- **the toast cards can no longer be quietly compressed on fractional display scaling.** at 125%/150% the wrapped body text under-measured and squeezed the card, clipping the headline's descenders (same bug class as #64); the update and star toasts now always size exactly to their content, verified by rendering at 1x/1.5x/2x on light and dark backdrops. the ghost dismiss button's click area was also widened to match the update notifier's (110x40) without moving a visible pixel.

### Notes
- growth + ui-polish release; no changes to the spotify metadata path, audio formats, tags, or the default matching policy. binaries built with yt-dlp 2026.6.9.

## [2.0.13] - 2026-06-28

### Added
- **in-app update notifier.** on launch sunnify checks the GitHub releases API in the background and, if a newer version exists, shows a small toast (current → new version) linking to the releases page. it's fail-silent offline, sends no telemetry, and has zero per-release maintenance (no hand-edited "what's new" copy to keep in sync).

### Fixed
- **settings descriptions were invisible on the Windows/Linux light theme.** the hint text under each setting was hardcoded white, so on a light-background dialog it disappeared entirely; it now derives from the palette and stays legible on both light and dark. only the gray descriptions were affected (the setting labels were always visible).
- **the window overflowed its own widgets on high-DPI / fractional scaling (closes #64).** the fixed-pixel UI now enables Qt high-DPI scaling with `PassThrough` rounding, so 125%/150% displays and Remote Desktop sessions scale the whole window together instead of spilling text out of its boxes (the reported "Download" → "ownloa", clipped byline, etc.). (ref: [Qt High DPI](https://doc.qt.io/qt-5/highdpi.html))
- **long settings labels and the "Add Meta Tags" option no longer clip.** the settings label column is measured from the longest label instead of a fixed width, the dialog sizes to its word-wrapped hints after they exist, and the options row sizes to its content.
- **flac cover embedding is now idempotent.** mutagen's `add_picture()` appends, so re-tagging a flac that already had a cover would stack duplicate Picture blocks; the writer now calls `clear_pictures()` first. mp3 (APIC frame replaced by HashKey) and m4a (`covr` atom assignment) already replaced in place, so only flac was affected. (ref: [mutagen FLAC API](https://mutagen.readthedocs.io/en/latest/api/flac.html))
- **filenames are capped to the cross-platform 255-byte component limit.** an extremely long song/artist title (or a troll-length one) used to fail to write with ENAMETOOLONG and silently drop the track; the name is now truncated on a codepoint boundary with the extension preserved. real-length titles are unaffected. (limit per [POSIX NAME_MAX](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/limits.h.html) and [Linux inode(7)](https://man7.org/linux/man-pages/man7/inode.7.html))
- **playlist folder names now use the same cross-platform sanitizer as track files.** the folder path previously used an ascii-only allowlist that could produce an uncreatable folder on windows when a playlist was named like a reserved device name (CON, NUL, COM1, including the superscript COM/LPT variants) and silently dropped punctuation; it now goes through `sanitize_filename` and reuses any existing older-named folder so a re-run's resume manifest isn't orphaned. rules follow the documented [Windows naming](https://learn.microsoft.com/windows/win32/fileio/naming-a-file), [POSIX pathname](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html), and [Unicode NFC](https://unicode.org/reports/tr15/) specs.
- **(web) the backend no longer leaks exception detail to clients.** scrape errors are logged server-side and return a generic message; an invalid or unsupported Spotify URL now returns 400 (client error) instead of 500.
- **(web) the webclient validates the Spotify URL by hostname** instead of a substring match, so `evil.com/open.spotify.com` no longer passes the check.

### Changed
- **the release-build workflow declares least-privilege token permissions** (top-level `contents: read`, widened only where the build genuinely needs `id-token`/`attestations`).

### Notes
- UI-robustness + observability release; no changes to the Spotify metadata path, audio formats, tags, or the default matching policy. the high-DPI fix is verified by simulation on macOS at 1x/1.5x and ships pending confirmation on the original reporter's Windows RDP session. metadata work this cycle was checked against [ID3v2.3](https://id3.org/id3v2.3.0) / [ID3v2.4](https://id3.org/id3v2.4.0-frames), [mutagen ID3](https://mutagen.readthedocs.io/en/latest/api/id3.html) / [MP4](https://mutagen.readthedocs.io/en/latest/api/mp4.html) / [FLAC](https://mutagen.readthedocs.io/en/latest/api/flac.html), and [Xiph FLAC](https://xiph.org/flac/format.html).

## [2.0.12] - 2026-06-20

### Added
- **"use closest result if no match" (opt-in, off by default).** when sunnify can't confidently match a track, it can now fall back to the closest youtube result by length instead of skipping it. this recovers songs whose youtube title is in a different alphabet than spotify (greek, cyrillic, korean, etc.), which the ascii title match could never make. the strict wrong-audio safeguard stays the default; the settings note spells out the tradeoff. thanks to Kyriazis for the suggestion over email.
- **`SUNNIFY_DEBUG` env toggle** for the full per-track + yt-dlp verbose trail on demand, while the default log stays lean.

### Fixed
- **youtube downloads that silently produced no file now log the real reason.** the actual yt-dlp error (bot-check, video unavailable, format, etc.) was being swallowed under `ignoreerrors`; it's now captured per attempt, so a single pasted log pinpoints the cause instead of a generic "not found".

### Changed
- **the log scales with failures, not playlist size.** per-track search/selection detail dropped to debug level, so a clean run stays quiet and only failures (with their reason) surface at the default level. spotify rate-limit (429) and retry backoff are now logged too (were previously silent).

### Notes
- observability + internationalization release; no changes to the spotify metadata path, audio formats, tags, or the default matching policy. binaries built with yt-dlp 2026.6.9 (current latest).

## [2.0.11] - 2026-06-19

### Added
- **rigorous diagnostic logging** (refs #62, #63). the app writes a rotating log to the platform's conventional location (`%LOCALAPPDATA%\Sunnify\logs` on windows, `~/Library/Logs/Sunnify` on macOS, `~/.local/state/sunnify/logs` on linux), capped at ~6MB total (1MB x 5 backups) so it's diagnostic, never bloat. every launch records a session header (app version, os/arch, python, yt-dlp version, ffmpeg path).
- **the log explains a whole session, not just the happy path.** the youtube path records its exact decision trail (search query, result count, and precisely why a track resolved or was rejected: no results vs title-filter vs artist-filter vs duration-off). each scrape logs a start line (type, name, id, track count, resume-skips, sequential/parallel + worker count, format/quality) and a completion summary (ok/failed counts plus the titles of any tracks that failed), so a single pasted log is enough to diagnose a run.
- **crashes are never silent.** uncaught exceptions on the main thread and worker threads, plus native crashes in qt/ffmpeg (via faulthandler, written to a sibling `crash.log`), are captured before the app exits, with a clean session-end marker on normal close.
- **every failure path is logged instead of swallowed**: per-track download errors (with traceback), tracks that produced no audio (no confident match or a youtube block), dead workers, failed scrapes, tag/cover-art write failures, and an unwritable download folder.
- **"Open logs folder" button** in Settings, and the bug-report template asks for the log file (per-os path + native upload), so a report arrives with the exact failure context.

### Changed
- **youtube download now falls back across player clients** (refs #62). when the default client fails to produce audio, the download retries forcing the `android`/`ios`/`tv`/`web_safari` clients, which use different endpoints and often still serve audio when youtube bot-challenges the default client per-ip (an increasingly common cause of "not found on YouTube" that is independent of the user's connection). the happy path is unchanged - the fallback only runs after the first attempt produces no file.
- **a terminal ctrl+c now exits cleanly** instead of surfacing a stray traceback.

### Notes
- no changes to the spotify metadata path, audio formats, tags, or matching policy; this release is observability + youtube resilience only. binaries built with yt-dlp 2026.6.9 (the current latest).

## [2.0.10] - 2026-06-09

### Changed
- **release pipeline rebuilt around a dedicated trusted builder** (#54). binaries are now built and attested inside the `release-build.yml` reusable workflow, which upgrades build provenance from slsa build L2 to L3 ([github's guidance](https://docs.github.com/actions/security-guides/using-artifact-attestations-and-reusable-workflows-to-achieve-slsa-v1-build-level-3)); build inputs are hash-locked (`pip install --require-hashes`, every wheel sha256-pinned across all three platforms, pyinstaller included), builds check out the release tag itself, and `PYTHONHASHSEED` + `SOURCE_DATE_EPOCH` are set per pyinstaller's reproducibility docs. no app-code changes; binaries are rebuilt from the same source as 2.0.9 with newer locked deps (notably yt-dlp 2026.6.9).
- **macos packaging**: explicit ad-hoc re-sign plus a `codesign --verify --strict` gate, and `ditto -c -k --keepParent` instead of `zip -r` (zip dereferences qt framework symlinks, which can silently break the signature seal). an intact seal turns a blocked first launch into the recoverable "open anyway" path instead of the dead-end "damaged" dialog.
- **homebrew cask**: postflight now strips quarantine after brew has verified the archive's sha256 against the cask, so `brew install --cask sunnify` opens with zero prompts; the old `sudo xattr -cr` instruction is gone (sudo was never needed, `-c` was over-broad).

### Added
- `<binary>.sigstore.json` offline verification bundles attached to every release asset set (verify with `gh attestation verify <bin> --bundle <bin>.sigstore.json`).
- openssf scorecard (weekly score + readme badge + sarif), actionlint + zizmor gating workflow changes, tuned dependabot (grouped, monthly, 7-day cooldown where supported), RELEASING.md runbook, SUPPORT.md, GOVERNANCE.md, CITATION.cff; SECURITY.md now leads with github private vulnerability reporting.

### Fixed
- the `actions/checkout` sha pin inherited across all workflows was orphaned by an upstream retag (unreachable in actions/checkout history); repinned to the commit v6.0.3 actually dereferences to. caught by the new workflow-lint gate on its first run.
- `.secrets.baseline` was gitignored, so the detect-secrets pre-commit hook failed for anyone who ran it; the baseline is now tracked.

## [2.0.9] - 2026-06-09

### Fixed
- **wrong audio with right metadata on some tracks** (closes #52, reported by @aspertiwilliam-cell). reporter showed an mp3 named "Mi Gente - DJ Goja.mp3" that played Mi Chico audio. the youtube search for that query returns "Dj Goja - Mi Chico (Official Video)" at 117s as the top hit; spotify's real Mi Gente is 114.8s. only 2.2s off, well within the v2.0.7 ±7s tolerance, so the duration-only matcher trusted Mi Chico and the metadata writer stamped Mi Gente title + cover onto it. selection now requires the spotify song title to appear in the youtube title, at least one spotify artist to also appear, and the duration to be within ±30s; failing any of those returns `not found on YouTube` instead of grabbing the closest wrong thing. handles common edge cases (spotify's "title - remastered yyyy" variant suffix stripped before matching, multi-artist collaborations match if any artist appears, accented and apostrophe titles normalize, youtube's "artist - song" format isn't split). 11 new tests + verified live on the bug case plus 5 well-known tracks.

### Added
- **album metadata on single-track downloads** (closes #53). single tracks now carry an `album` tag in the ID3/M4A/FLAC frame, matching what album downloads have always done. the embed page JSON genuinely does not expose album for single tracks, so the album name is scraped from the `og:description` meta tag on `open.spotify.com/track/{id}` (canonical `Artist · Album · Song · Year` format, stable for years because it drives social-share previews). primary contribution by @WhatDidYouExpect in #53; cleanups on top: retry/backoff via the same `@retry_on_network_error` discipline `_fetch_embed_data` uses, html.unescape so `Tom &amp; Jerry's Greatest Hits` doesn't end up encoded in the tag, attribute-order-agnostic regex for resilience against future Spotify HTML deploys, per-instance dict cache (256 entries, FIFO) so re-downloads don't re-hit Spotify, dead `entity.album` branch dropped, 13 unit tests covering the parser + fetcher.
- **inline help under every setting** in the Settings dialog. each control now carries a one-line gray caption directly underneath explaining what it does, with the new `Track number in filename:` toggle showing concrete `Off → "Song - Artist.mp3"` / `On → "01. Song - Artist.mp3"` examples. the previous dialog gave four labels and four widgets with no indication of what the toggles did. implementation uses per-setting `QVBoxLayout` blocks (each owns its own height) instead of `QFormLayout` (sizes row to label height; word-wrapped hints got clipped); hint color is `rgba(255,255,255,0.65)` so it stays readable on both the current dark gradient and any future light theme. cocoa-rendered + verified visually before merge.

### Notes
- only the desktop app and the Python core are affected; the web client / backend continue to work the same way.

## [2.0.8] - 2026-06-08

### Added
- **optional track-number prefix in filenames** (closes #44). settings now exposes a "Track number in filename:" checkbox. when on, downloaded files are prefixed with their zero-padded playlist position (`01. song - artist.mp3`, `02. ...`, ... `12. ...`) so the folder sorts in playlist order in any file manager. default off, so existing downloads are byte-for-byte unchanged; the position number is the same `TRCK` value that's already written to the ID3 tag, so this just surfaces existing data in the filename. primary contribution by @r-a-cristian-93 in #44; cleanups (3.9 compat via `from __future__ import annotations`, padded collision-guard, redundant bool validation dropped, default-off, tests) layered on top before merge.

### Fixed
- **mp3 cover art (and text tags) not showing in older players, car head-units, and stock android** (closes #46). mutagen defaults to ID3v2.4 with UTF-8 text encoding, but the v2.3 spec only defines two text encodings: `$00` ISO-8859-1 and `$01` Unicode (UTF-16 with BOM); the v2.4-only `$03` UTF-8 byte makes strict parsers (older iTunes/Apple Music, Windows Media Player, most car head-units, stock android) reject the frame, which manifests as "cover shows in preview but missing once downloaded" and (sometimes) missing title/artist/album. tags + the APIC cover frame are now written as v2.3 via `EasyID3.save(v2_version=3)` plus `id3.add(APIC(encoding=1, ...))` + `id3.update_to_v23()` + `id3.save(v2_version=3)`, which is the lowest-common-denominator format that's understood everywhere modern v2.4 is. APIC uses `encoding=1` (UTF-16+BOM), `type=3` ("Cover (front)"), and `desc='Cover'`. canonical `id3.add(APIC(...))` replaces the dict-style `id3["APIC"] = ...` assignment. refs: [ID3v2.3 spec section 3.3](https://id3.org/id3v2.3.0) (defines encodings $00 / $01); [ID3v2.4 spec](https://id3.org/id3v2.4.0-frames) (adds $02 UTF-16BE, $03 UTF-8); [mutagen `update_to_v23()`](https://mutagen.readthedocs.io/en/latest/api/id3.html) (UTF-8 -> UTF-16 downgrade).
- cover-art mime is now sniffed from the image's magic bytes for all three containers (mp3 APIC, m4a `covr`, FLAC `Picture`) instead of being hardcoded to `image/jpeg`. Spotify has served JPEG since at least 2015 (so today's behaviour doesn't change), but the previous code would silently produce a broken frame mis-tagged as JPEG if Spotify ever switches to PNG/WebP. refs: [JPEG SOI marker](https://www.w3.org/Graphics/JPEG/itu-t81.pdf) (`FF D8 FF`); [PNG signature](https://www.w3.org/TR/png/#5PNG-file-signature) (`89 50 4E 47 0D 0A 1A 0A`).

### Notes
- existing 2.0.7 downloads that have v2.4 + UTF-8 tags are not rewritten by 2.0.8; the change applies to new downloads. if you need to fix old files, re-downloading the affected track is the simplest path.
- m4a (`covr`) and FLAC (`Picture`) cover art is unaffected by the v2.3 work; those containers don't have the v2.3/v2.4 encoding distinction and were already correctly written.

## [2.0.7] - 2026-05-26

### Added
- **album downloads** (closes #38). album URLs and `spotify:album:` URIs now work alongside playlists and tracks. albums reuse the embed-parsing path through `/embed/album/{id}`, and because the album embed exposes the album name, every downloaded album track gets its `album` tag written (something playlist downloads can't provide, since playlist embeds don't carry it). verified end-to-end: a real album download writes `album=...` into the output file's tags.
- **resume support for large playlists** (closes #40). a per-playlist manifest (`.sunnify-manifest.jsonl`) inside each download folder records which tracks already landed. on a re-run, those tracks are skipped *before* their rate-limited `/embed/track/` metadata is fetched, so a playlist throttled by spotify's rate limit can be finished across several sessions instead of one long sit. entries whose files were deleted are pruned on load, so a removed track re-downloads. append-only json-lines keeps recording O(1) regardless of playlist size.

### Fixed
- wrong audio for some tracks: the file name was correct but it played a different recording (reported by email). the youtube search took the top hit, which is frequently the **music video** (extra intro/skit/outro) or an extended/remix cut, so the audio didn't match the spotify track. confirmed it was present in every prior version (old `ytsearch1` picked the same wrong result) and not caused by any mirror. download now flat-searches the top results and picks the candidate whose **duration matches the spotify track** (within ~7s), steering to the real audio instead of the music video; falls back to the top result only when no duration is known.
- tracks that scraped but never finished downloading (closes #42). the youtube search used `ytsearch1` (a single result), so a track whose top match was region-locked or removed failed outright; worse, `download_track_audio` returned the expected path even when no file was produced, so the app reported success for a download that never happened. the search now tries up to 5 results (skipping unavailable ones) with a simplified fallback query for hyper-specific titles (e.g. classical works with `(Op. 49, No. 4)`), and raises a clear "not found on YouTube" error when no audio lands. failures are now reported instead of silently hanging.
- accented and non-Latin characters were being stripped from filenames (reported on r/selfhosted). `sanitize_filename` used an ASCII-only allowlist, so titles like "MONTAGEM BAILÃO" lost the "Ã" and fully non-Latin titles (CJK, Cyrillic) collapsed to "Unknown". confirmed end-to-end that the loss was ours (Spotify returns the characters intact and yt-dlp/FFmpeg write them to disk fine). it now keeps every character except the ones the filesystem actually rejects: drops the Windows-reserved set `<>:"/\|?*` plus control characters, trims trailing dots/spaces, and escapes the Windows reserved device names (`CON`, `NUL`, `COM1`...). refs: Windows [Naming Files, Paths, and Namespaces](https://learn.microsoft.com/windows/win32/fileio/naming-a-file); macOS/Linux forbid only `/` and NUL ([POSIX portable filename set](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html#tag_03_282)).
- windows exe version metadata: the `FixedFileInfo` `filevers` / `prodvers` tuples in `Sunnify.spec` were stuck at `2.0.3` (missed in the 2.0.4-2.0.6 bumps) while the string fields read the current version. both are now bumped together so the embedded Windows version is internally consistent.

## [2.0.6] - 2026-04-16

### Added
- **audio format + bitrate selection** in settings. choose between mp3, m4a, opus, flac, and wav, with 128/192/256/320 kbps for the lossy formats. the selection is persisted to disk (`~/Library/Application Support/Sunnify/config.json` on macos, `%APPDATA%\Sunnify` on windows, `$XDG_CONFIG_HOME/Sunnify` on linux) so it survives app restarts. end-to-end verified across all 10 format/quality combos via ffprobe (mp3 @ 128/192/256/320 kbps exact, m4a aac @ 129/327 kbps, opus, flac lossless, wav pcm_s16le @ 1536 kbps).
- **multi-format metadata writers**: id3 for mp3, itunes atoms for m4a, vorbis comments for flac. each container gets its cover art + tags written correctly by the format-appropriate writer; unsupported containers (opus/wav) skip tagging gracefully instead of silently breaking.
- counter now shows `X of Y` during downloads so users can see progress against the full playlist size instead of a bare increment.
- metadata fetch now emits `Fetching track metadata (X of Y)...` every 10 tracks during the pre-download materialization phase so large playlists (700+ tracks) no longer look frozen for the 30-60 seconds of parallel embed fetches.
- artist preview in the song info panel truncates long collaborator lists to `Artist A, Artist B +N` with a tooltip showing the full string, so classical tracks with 4+ performers no longer clip through the fixed-height label.

### Fixed
- stop button now takes effect immediately on large playlists instead of hanging for 10+ seconds. `iter_playlist_tracks` issues serial spclient + per-track metadata requests for playlists over 100 tracks, and the previous `list()` call held the thread for the whole duration before the cancel check could run. materialization now checks `is_cancelled()` between yields so stop preempts mid-fetch.
- cancel-during-parallel-metadata hang: the parallel `/embed/track/{id}` `ThreadPoolExecutor` in `iter_playlist_tracks` previously blocked on `__exit__` waiting for all submitted futures to complete, holding the generator open for 20-30 seconds after the user pressed stop and causing the "download button won't go" symptom on restart. pool lifecycle is now managed via `try/finally` with `shutdown(wait=False, cancel_futures=True)` so pending HTTP fetches get cancelled immediately.
- `RateLimitError` (HTTP 429 from spotify's embed endpoint) is now in the retry decorator's exception list with 4-attempt exponential backoff (1.5× factor), so transient rate limits under concurrent load recover automatically instead of surfacing as a terminal error.
- metadata fetch concurrency dropped from 8 → 4 workers in `iter_playlist_tracks` to stay under spotify's embed-endpoint rate threshold on 700+ track playlists.
- card is now fully opaque (closes #33). the translucent alpha values on the gradient stops (`155` / `191`) made text hard to read when the app sat in front of a bright wallpaper; both stops are now `255`. frameless window stays; only the card content is opacified.
- album row in the song info panel is hidden entirely. spotify's unauthenticated embed endpoints do not expose album name, so the field was always blank; removing it is honest about the limitation instead of showing an empty "Album :" row.

### Changed
- url parsing now accepts `spotify:` URIs (copy-URI from the spotify desktop app), `/intl-xx/` locale-prefixed URLs, and trailing `?si=...` query params. drop-in compatible with the prior HTTPS-only detector; previously-working inputs still work.

### Known limitations
- changing audio format or quality mid-download does not apply to the in-flight download. `ScraperThread` captures the format/quality at construction and the running pool keeps them; new settings take effect on the next download. stop + re-start after changing settings to switch format mid-playlist (no resume, restarts from track 1).

## [2.0.5] - 2026-04-14

### Fixed
- every track in a playlist sharing the same cover art (closes #31). spotify's playlist embed trackList does not include per-track cover urls at all, so every track was falling back to the playlist cover. the download worker now enriches missing cover urls by fetching `/embed/track/{id}` (which has the real `visualIdentity.image`) in parallel with the youtube search, so per-track covers land in the id3 tags at no wall-clock cost.
- release date is now also pulled from the per-track enrichment call when missing, so the `year` id3 tag populates correctly for playlist downloads.

### Added
- track number (id3 `TRCK` / `tracknumber`) is now written to downloaded files using the 1-based playlist position. addresses the broader "no meta tags apart from song name and artist" feedback from #31.

### Notes
- album name and genre remain unavailable in this release because spotify's unauthenticated embed endpoints do not expose them at all. the `/embed/track/{id}` entity's `relatedEntityUri` points at the artist, not the album, and the non-embed track page is a client-rendered spa with no ssr payload. adding those fields would require oauth, which conflicts with the "no account required" model the app is built around.

## [2.0.4] - 2026-04-13

### Added
- parallel track downloads via `ThreadPoolExecutor` with 4 concurrent workers by default (closes #34)
- `MusicScraper.MAX_WORKERS` constant documenting the measured sweet spot
- thread-safe counter and `_failed_tracks` mutation via `threading.Lock`
- `MusicScraper._download_one_track()` extracted as the per-track worker function
- filename collision guard: TOCTOU-safe in-flight file set, de-duped with track id suffix so two tracks that sanitize to the same name don't race
- 13 new tests covering worker count bounds, counter/append atomicity, exception isolation, generator materialization thread-safety, filename collision handling, parallel-mode UI suppression, aggregate progress monotonicity, cancel-before-pool-start behavior, and proof the pool spawns `MAX_WORKERS` concurrent threads under load

### Changed
- `scrape_playlist` materializes the track generator upfront before threading (`iter_playlist_tracks` is a generator and generators are not thread-safe)
- small playlists (under 3 tracks) stay on the single-worker path to preserve single-track UI feel
- cooperative cancel checks at multiple points: before generator materialization, at the top of each worker, and between future completions; queued workers cancel immediately, in-flight downloads finish their current track
- in parallel mode, `song_meta` (UI preview) emits and per-byte `dlprogress_signal` emits are suppressed to prevent label flicker and thumbnail thread spam; progress bar is driven by aggregate completion count
- sequential-mode progress bar still resets per track so single-worker UX is unchanged
- `_parallel_mode` flag is reset after the executor context manager fully exits, avoiding a race where workers still running after a cancel-break could emit single-track UI signals

### Performance
- measured ~4x wall-clock time reduction on 12-track playlists (Apple Silicon M4 Max, macOS). cross-platform builds for Windows, Linux, and macOS ship the same parallel downloader since the concurrency model is pure python + yt-dlp and has no platform-specific code.
- no YouTube or Spotify rate limiting observed at 4-8 concurrent workers during stress testing

## [2.0.3] - 2026-03-31

### Fixed
- cover art now embeds reliably by fetching synchronously in the meta tag writer thread (nested QThread signal delivery was silently failing)
- stop button no longer calls `terminate()`, uses fully cooperative cancellation via cancel event and disables the button during wind-down to prevent double-clicks

### Added
- yt-dlp download resilience: 5 retries, 15s socket timeout, 4 concurrent fragment downloads
- tests for yt-dlp perf options, synchronous cover art fetch, cover art failure handling, and cooperative cancellation

### Changed
- `WritingMetaTagsThread` fetches cover art synchronously with `requests.get()` instead of spawning a nested `DownloadCover` QThread (fixes signal delivery race condition)
- stop button disables during wind-down and re-enables via `thread_finished` signal

## [2.0.2] - 2026-02-01

### Fixed
- resilient embed page extraction handles Spotify A/B testing structure changes (closes #27)
- token extraction tries multiple JSON paths before giving up

### Added
- `_deep_find()` and `_resolve_path()` helpers for flexible JSON traversal
- comprehensive tests for alternative embed page structures
- unit test suite with pytest (43+ tests covering API, downloader, backend)
- comprehensive legal disclaimers across all documentation

### Changed
- split CI workflow into separate tests.yml, lint.yml, webclient.yml for better visibility
- improved thread safety with cooperative cancellation (replaced unsafe terminate())
- added custom exception classes (NetworkError, ExtractionError, RateLimitError)
- added retry decorator with exponential backoff for network requests
- user-friendly error messages in UI for common failure cases

## [2.0.1] - 2026-01-16

### Fixed
- Stop button now properly halts downloads mid-playlist
- Resolved QThread crashes on rapid start/stop
- Improved FFmpeg detection for Homebrew and system installs
- Fixed meta tag writing timing issues
- Fixed download prompt behavior

### Added
- Sponsor buttons to web app
- Homebrew cask now declares FFmpeg dependency

---

## [2.0.0] - 2026-01-15

### Added
- Single track download support (not just playlists)
- Stop button for cancelling downloads mid-progress
- Preview mode banner in webclient explaining desktop app requirement
- Sponsor buttons in desktop app
- Health check endpoint in backend API
- Homebrew cask for macOS installation (see README for install commands)
- Cross-platform release builds (Windows, macOS, Linux) via GitHub Actions
- FFmpeg bundled with pre-built apps (zero-dependency install)
- Redesigned webclient UI matching desktop app aesthetic
- Cold start banner for free-tier backend delays

### Changed
- Switched from spotifydown mirrors to Spotify embed page API (more reliable)
- Migrated backend from AWS Lambda to Render free tier
- Improved FFmpeg detection (homebrew paths, system paths, bundled)
- Modernized Python type annotations throughout codebase
- Enhanced CI/CD with CodeQL scanning, Dependabot, stale automation

### Fixed
- Read-only filesystem error on macOS app bundles
- Threading crashes when stopping downloads
- Meta tags timing issues
- Cover URL extraction with playlist cover fallback
- Cross-platform font compatibility

### Technical
- Python 3.9+ with modern type hints
- Node 20+ for webclient
- PyQt5 desktop app with PyInstaller packaging
- Flask backend with SSE streaming
- Next.js 14 + Tailwind + shadcn/ui webclient

## [1.0.0] - 2024-02-01

### Added
- Initial release
- PyQt5 desktop application for Windows
- Flask backend API with SSE streaming
- Next.js 14 web client
- Multi-provider strategy (Spotify Web API → spotifydown mirrors → yt-dlp)
- ID3 metadata tagging with cover art embedding
- Diagnostic script (`scripts/check_api_status.py`)

### Technical
- Python 3.9+ support
- Node 20+ for webclient
- FFmpeg + yt-dlp for audio processing

[Unreleased]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.1.1...HEAD
[2.1.1]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.15...v2.1.0
[2.0.15]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.14...v2.0.15
[2.0.14]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.13...v2.0.14
[2.0.13]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.12...v2.0.13
[2.0.12]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.11...v2.0.12
[2.0.11]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.10...v2.0.11
[2.0.10]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.9...v2.0.10
[2.0.9]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.8...v2.0.9
[2.0.8]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.7...v2.0.8
[2.0.7]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.6...v2.0.7
[2.0.6]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.5...v2.0.6
[2.0.5]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v1.0.0
