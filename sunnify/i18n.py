"""User-facing strings in English and Bahasa Melayu.

The desktop app picks the language at launch (Settings > Language, "auto"
follows the system locale) and can switch while running. Anything that never
calls set_language() - the CLI, the tests, scripts - stays in English, so the
CLI's output and its JSON contract never change with the user's locale.

A key missing from a translation falls back to English; a key missing from
English comes back as the key itself, so a typo shows up on screen instead of
crashing a download.
"""

from __future__ import annotations

import locale
import os

LANGUAGES = ("en", "ms")

EN = {
    # engine
    "engine.cookies_stale": (
        "YouTube is still asking this network to prove it isn't a bot with your "
        "cookies loaded, which usually means they have expired. Export them again."
    ),
    "engine.network_blocked": (
        "YouTube is asking this network to prove it isn't a bot, so downloads are "
        "being refused. This is applied to your IP, not to Sunnify: try another "
        "network or connection, wait a few hours, or use YouTube cookies (see the docs)."
    ),
    "engine.spotify_rate_limited": "Rate limited by Spotify - waiting...",
    "engine.network_error": "Network error - retrying...",
    "engine.cannot_access": "Could not access '{title}' - may be unavailable",
    "engine.youtube_blocked_track": "YouTube blocked this network - '{title}' skipped",
    "engine.youtube_rate_limited": "YouTube rate limit - waiting...",
    "engine.not_on_youtube": "'{title}' not found on YouTube",
    "engine.error": "Error: {detail}",
    "engine.track_failed": "'{title}' - download failed",
    "engine.cancelled": "Download cancelled",
    "engine.resuming": "Resuming: skipping {count} already-downloaded track(s)",
    "engine.fetching": "Fetching track metadata ({done} of {total})...",
    "engine.worker_error": "Unexpected worker error: {error}",
    "engine.done_with_failures": "Done! {count} track(s) failed",
    "engine.complete": "Download Complete!",
    "engine.single_track": "Single Track Download",
    "engine.track_exists": "Track already exists!",
    "engine.no_audio": "Download failed - no audio file produced",
    "engine.started": "Scraping started...",
    "tags.skipped": "Tags skipped (unsupported container)",
    "tags.done": "Tags added successfully",
    "kind.playlist": "playlist",
    "kind.album": "album",
    "kind.track": "track",
    "kind.unknown": "unknown",
    # main window
    "main.author": "Spotify Downloader · by Sunny Patel",
    "main.placeholder": "Paste a Spotify link here",
    "main.paste": "Paste",
    "main.paste.tip": "Paste a link from the clipboard",
    "main.download": "Download",
    "main.stop": "Stop",
    "main.preview": "Show preview",
    "main.tags": "Add tags",
    "main.tags.tip": "Write title, artist, album, year, track number and cover art into each file",
    "main.open_folder": "Open folder",
    "main.open_folder.tip": "Open the folder of the last download",
    "main.history": "History",
    "main.linkedin": "Follow Sunny Patel on LinkedIn",
    "main.history.tip": "Download history (Ctrl+H)",
    "main.settings.tip": "Settings (Ctrl+,)",
    "main.minimize.tip": "Minimise",
    "main.close.tip": "Close",
    "main.idle": "Nothing downloading yet",
    "main.ready": (
        "Paste a link, then press Download or Enter. You can also drop a link onto the window."
    ),
    "main.playlist": "Playlist: {name}",
    "main.counter": "Songs downloaded {done}",
    "main.counter.of": " of {total}",
    "main.counter.failed": " ({failed} failed)",
    "panel.heading": "Song information",
    "panel.album": "Album",
    "panel.released": "Released",
    # status line
    "status.settings_saved": "Settings saved",
    "status.scale_next_open": "Window size applies when Sunnify next opens",
    "status.scale_restart_failed": (
        "Couldn't restart; the window size applies when Sunnify next opens"
    ),
    "status.enter_url": "Please enter a Spotify URL",
    "status.ffmpeg_missing": "FFmpeg not found",
    "status.cookies_unusable": "YouTube cookies can't be used",
    "status.select_location": "Select download location...",
    "status.no_folder": "Download cancelled - no folder selected",
    "status.not_writable": "Cannot write to download folder",
    "status.not_spotify": "Not a Spotify playlist, album or track link: {link}",
    "status.stopping_no_queue": "Stopping - add links again once it finishes",
    "status.queued": "Queued {new} link(s), {waiting} waiting",
    "status.already_queued": "That link is already downloading or queued",
    "status.detected": "Detected: {kind}",
    "status.stopping": "Stopping download...",
    "status.stopping_cleared": "Stopping download ({count} queued link(s) cleared)...",
    "status.no_link_found": "No Spotify link found there",
    "status.link_ready": "Link ready - press Download or Enter",
    "hint.queued": "{count} queued - paste another link and press Enter",
    "hint.queue_more": "Paste another link and press Enter to queue it",
    # message boxes
    "ffmpeg.title": "FFmpeg Required",
    "ffmpeg.body": (
        "FFmpeg is required for audio downloads and conversion but was not found "
        "on your system.\n\nInstall it with:\n  {hint}\n\nThen restart Sunnify."
    ),
    "cookies.title": "YouTube Cookies",
    "cookies.body": (
        "{problem}.\n\nFix it, or turn cookies off with:\n  sunnify config --set cookies_file="
    ),
    "not_writable.title": "Invalid Download Location",
    "not_writable.body": "Cannot write to:\n{path}\n\nPlease select a different folder.",
    "restart.title": "Window size",
    "restart.body": "Restart Sunnify now to apply the new window size?",
    "restart.now": "Restart now",
    "restart.later": "Later",
    "notify.title": "Download finished",
    "notify.body": "{name}: {landed} song(s) saved.",
    "notify.failed": "{failed} failed.",
    # settings
    "settings.title": "Sunnify Settings",
    "settings.not_set": "(not set)",
    "settings.choose_folder": "Choose folder",
    "settings.choose_folder.title": "Select Download Folder",
    "settings.sample_rate.auto": "auto (keep source)",
    "settings.style.song_artist": "Song - Artist",
    "settings.style.artist_song": "Artist - Song",
    "settings.style.song_only": "Song only",
    "settings.language.auto": "Follow the system",
    "settings.language.en": "English",
    "settings.language.ms": "Bahasa Melayu",
    "settings.theme.system": "Follow the system",
    "settings.theme.dark": "Dark",
    "settings.theme.light": "Light",
    "settings.section.downloads": "Downloads",
    "settings.section.names": "File names",
    "settings.section.matching": "Matching and extras",
    "settings.section.app": "App",
    "settings.folder": "Download folder",
    "settings.folder.hint": "Each playlist or album becomes its own folder inside this directory.",
    "settings.format": "Audio format",
    "settings.format.hint": (
        "mp3 plays everywhere. m4a is smaller at the same quality. flac and wav keep "
        "the source audio with nothing further lost (much larger files)."
    ),
    "settings.quality": "Audio quality",
    "settings.quality.hint": (
        "Applies to mp3, m4a and opus. The source is YouTube's ~128 kbps audio, so "
        "higher settings lose less of it but can't add to it."
    ),
    "settings.sample_rate": "Sample rate",
    "settings.sample_rate.hint": (
        "auto keeps the source rate (YouTube audio is 48 kHz). 44.1 kHz matches CDs "
        "and older players. Applies to mp3, flac and wav; opus and m4a keep their "
        "source rate."
    ),
    "settings.style": "Filename style",
    "settings.style.hint": (
        '"Song only" keeps the artist out of the filename; every tag (artist, album, '
        "art) is still written, and two different songs with the same title get a "
        "short id suffix instead of overwriting each other. Applies to new downloads; "
        "files already on disk keep their names."
    ),
    "settings.track_number": "Track number in filename",
    "settings.track_number.hint": (
        'Off → "Song - Artist.mp3".   On → "01. Song - Artist.mp3".   '
        "Files sort in playlist order in your file manager."
    ),
    "settings.preview": "Filename preview",
    "settings.preview.song": "Song",
    "settings.preview.artist": "Artist",
    "settings.loose_match": "Use closest result if no match",
    "settings.loose_match.hint": (
        "Off (default): skips a track rather than risk the wrong audio. On: falls "
        "back to the closest result by length, which recovers songs whose YouTube "
        "title is in another script (Greek, Cyrillic, Korean) but may let an "
        "occasional cover or remix slip through."
    ),
    "settings.lyrics": "Lyrics",
    "settings.lyrics.hint": (
        "Looks each song up on LRCLIB, a free lyrics database, and embeds the words "
        "in mp3, m4a and flac files. Time-synced lyrics also land as a .lrc file "
        "beside the song, for players that scroll along. Needs Add tags on the main "
        "window."
    ),
    "settings.language": "Language",
    "settings.language.hint": "Applies right away. The command-line tool stays in English.",
    "settings.theme": "Theme",
    "settings.ui_scale": "Window size",
    "settings.ui_scale.hint": (
        "Scales the whole window, text and buttons included, on top of your system's "
        "display scaling. Sizes that would not fit this screen are greyed out. Takes "
        "effect when Sunnify next opens."
    ),
    "settings.notify": "Notify when done",
    "settings.notify.hint": (
        "Flashes the taskbar and shows a system notification when a download "
        "finishes while Sunnify is in the background."
    ),
    "settings.save": "Save",
    "settings.open_logs": "Open logs folder",
    "common.cancel": "Cancel",
    "common.close": "Close",
    # toasts
    "update.eyebrow": "UPDATE AVAILABLE",
    "update.body": (
        "A newer version of Sunnify is available. Download it from the releases page "
        "to get the latest fixes and improvements."
    ),
    "update.later": "Remind me later",
    "update.download": "Download",
    "star.eyebrow": "FIRST SONG DOWNLOADED",
    "star.heading": "Enjoying Sunnify?",
    "star.body": (
        "A star on GitHub keeps this project alive - it's how new people find "
        "Sunnify, and it takes five seconds. This asks once and never again."
    ),
    "star.later": "Maybe later",
    "star.action": "Star on GitHub",
    # history
    "history.title": "Download history",
    "history.subtitle": (
        "Your recent downloads, newest first. Double-click one to open its folder."
    ),
    "history.empty": "Nothing here yet. Finished downloads show up here.",
    "history.open_folder": "Open folder",
    "history.again": "Download again",
    "history.clear": "Clear history",
    "history.status.done": "Done",
    "history.status.partial": "Some failed",
    "history.status.failed": "Failed",
    "history.status.stopped": "Stopped",
    "history.counts": "{landed} saved",
    "history.failed": "{failed} failed",
}

MS = {
    # enjin
    "engine.cookies_stale": (
        "YouTube masih meminta rangkaian ini membuktikan ia bukan bot walaupun kuki "
        "anda sudah dimuatkan. Biasanya ini bermakna kuki itu sudah tamat tempoh. "
        "Eksport semula."
    ),
    "engine.network_blocked": (
        "YouTube meminta rangkaian ini membuktikan ia bukan bot, jadi muat turun "
        "ditolak. Sekatan ini dikenakan pada IP anda, bukan pada Sunnify: cuba "
        "rangkaian atau sambungan lain, tunggu beberapa jam, atau guna kuki YouTube "
        "(lihat dokumentasi)."
    ),
    "engine.spotify_rate_limited": "Spotify mengehadkan permintaan - sedang menunggu...",
    "engine.network_error": "Ralat rangkaian - mencuba semula...",
    "engine.cannot_access": "Tidak dapat mengakses '{title}' - mungkin tidak tersedia",
    "engine.youtube_blocked_track": "YouTube menyekat rangkaian ini - '{title}' dilangkau",
    "engine.youtube_rate_limited": "YouTube mengehadkan permintaan - sedang menunggu...",
    "engine.not_on_youtube": "'{title}' tidak dijumpai di YouTube",
    "engine.error": "Ralat: {detail}",
    "engine.track_failed": "'{title}' - muat turun gagal",
    "engine.cancelled": "Muat turun dibatalkan",
    "engine.resuming": "Menyambung semula: melangkau {count} lagu yang sudah dimuat turun",
    "engine.fetching": "Mengambil metadata lagu ({done} daripada {total})...",
    "engine.worker_error": "Ralat pekerja yang tidak dijangka: {error}",
    "engine.done_with_failures": "Selesai! {count} lagu gagal",
    "engine.complete": "Muat turun selesai!",
    "engine.single_track": "Muat turun satu lagu",
    "engine.track_exists": "Lagu sudah wujud!",
    "engine.no_audio": "Muat turun gagal - tiada fail audio dihasilkan",
    "engine.started": "Memulakan muat turun...",
    "tags.skipped": "Tag dilangkau (format tidak disokong)",
    "tags.done": "Tag berjaya ditambah",
    "kind.playlist": "senarai main",
    "kind.album": "album",
    "kind.track": "lagu",
    "kind.unknown": "tidak diketahui",
    # tetingkap utama
    "main.author": "Pemuat Turun Spotify · oleh Sunny Patel",
    "main.placeholder": "Tampal pautan Spotify di sini",
    "main.paste": "Tampal",
    "main.paste.tip": "Tampal pautan dari papan keratan",
    "main.download": "Muat turun",
    "main.stop": "Henti",
    "main.preview": "Tunjuk pratonton",
    "main.tags": "Tambah tag",
    "main.tags.tip": (
        "Tulis tajuk, artis, album, tahun, nombor lagu dan kulit album ke dalam setiap fail"
    ),
    "main.open_folder": "Buka folder",
    "main.open_folder.tip": "Buka folder muat turun terakhir",
    "main.history": "Sejarah",
    "main.linkedin": "Ikuti Sunny Patel di LinkedIn",
    "main.history.tip": "Sejarah muat turun (Ctrl+H)",
    "main.settings.tip": "Tetapan (Ctrl+,)",
    "main.minimize.tip": "Kecilkan",
    "main.close.tip": "Tutup",
    "main.idle": "Belum ada muat turun",
    "main.ready": (
        "Tampal pautan, kemudian tekan Muat turun atau Enter. Anda juga boleh seret "
        "pautan ke tetingkap ini."
    ),
    "main.playlist": "Senarai main: {name}",
    "main.counter": "Lagu dimuat turun {done}",
    "main.counter.of": " daripada {total}",
    "main.counter.failed": " ({failed} gagal)",
    "panel.heading": "Maklumat lagu",
    "panel.album": "Album",
    "panel.released": "Tarikh keluar",
    # baris status
    "status.settings_saved": "Tetapan disimpan",
    "status.scale_next_open": "Saiz tetingkap berkuat kuasa apabila Sunnify dibuka semula",
    "status.scale_restart_failed": (
        "Tidak dapat mula semula; saiz tetingkap berkuat kuasa apabila Sunnify dibuka semula"
    ),
    "status.enter_url": "Sila masukkan pautan Spotify",
    "status.ffmpeg_missing": "FFmpeg tidak dijumpai",
    "status.cookies_unusable": "Kuki YouTube tidak boleh digunakan",
    "status.select_location": "Pilih lokasi muat turun...",
    "status.no_folder": "Muat turun dibatalkan - tiada folder dipilih",
    "status.not_writable": "Tidak dapat menulis ke folder muat turun",
    "status.not_spotify": "Bukan pautan senarai main, album atau lagu Spotify: {link}",
    "status.stopping_no_queue": "Sedang berhenti - tambah pautan semula selepas ia selesai",
    "status.queued": "{new} pautan dibariskan, {waiting} menunggu",
    "status.already_queued": "Pautan itu sedang dimuat turun atau sudah dalam barisan",
    "status.detected": "Dikesan: {kind}",
    "status.stopping": "Menghentikan muat turun...",
    "status.stopping_cleared": (
        "Menghentikan muat turun ({count} pautan dalam barisan dibuang)..."
    ),
    "status.no_link_found": "Tiada pautan Spotify dijumpai",
    "status.link_ready": "Pautan sedia - tekan Muat turun atau Enter",
    "hint.queued": "{count} dalam barisan - tampal pautan lain dan tekan Enter",
    "hint.queue_more": "Tampal pautan lain dan tekan Enter untuk membariskannya",
    # kotak mesej
    "ffmpeg.title": "FFmpeg Diperlukan",
    "ffmpeg.body": (
        "FFmpeg diperlukan untuk memuat turun dan menukar audio, tetapi tidak dijumpai "
        "dalam sistem anda.\n\nPasang dengan:\n  {hint}\n\nKemudian buka semula Sunnify."
    ),
    "cookies.title": "Kuki YouTube",
    "cookies.body": (
        "{problem}.\n\nBetulkan, atau matikan kuki dengan:\n  sunnify config --set cookies_file="
    ),
    "not_writable.title": "Lokasi Muat Turun Tidak Sah",
    "not_writable.body": "Tidak dapat menulis ke:\n{path}\n\nSila pilih folder lain.",
    "restart.title": "Saiz tetingkap",
    "restart.body": "Mula semula Sunnify sekarang untuk guna saiz tetingkap baharu?",
    "restart.now": "Mula semula sekarang",
    "restart.later": "Nanti",
    "notify.title": "Muat turun selesai",
    "notify.body": "{name}: {landed} lagu disimpan.",
    "notify.failed": "{failed} gagal.",
    # tetapan
    "settings.title": "Tetapan Sunnify",
    "settings.not_set": "(belum ditetapkan)",
    "settings.choose_folder": "Pilih folder",
    "settings.choose_folder.title": "Pilih Folder Muat Turun",
    "settings.sample_rate.auto": "auto (kekalkan sumber)",
    "settings.style.song_artist": "Lagu - Artis",
    "settings.style.artist_song": "Artis - Lagu",
    "settings.style.song_only": "Lagu sahaja",
    "settings.language.auto": "Ikut sistem",
    "settings.language.en": "English",
    "settings.language.ms": "Bahasa Melayu",
    "settings.theme.system": "Ikut sistem",
    "settings.theme.dark": "Gelap",
    "settings.theme.light": "Cerah",
    "settings.section.downloads": "Muat turun",
    "settings.section.names": "Nama fail",
    "settings.section.matching": "Padanan dan tambahan",
    "settings.section.app": "Aplikasi",
    "settings.folder": "Folder muat turun",
    "settings.folder.hint": (
        "Setiap senarai main atau album menjadi folder tersendiri di dalam direktori ini."
    ),
    "settings.format": "Format audio",
    "settings.format.hint": (
        "mp3 boleh dimainkan di mana-mana. m4a lebih kecil pada kualiti yang sama. "
        "flac dan wav mengekalkan audio sumber tanpa kehilangan lagi (fail jauh lebih "
        "besar)."
    ),
    "settings.quality": "Kualiti audio",
    "settings.quality.hint": (
        "Untuk mp3, m4a dan opus. Sumbernya ialah audio YouTube ~128 kbps, jadi "
        "tetapan lebih tinggi kurang menjejaskan kualiti tetapi tidak dapat menambahnya."
    ),
    "settings.sample_rate": "Kadar sampel",
    "settings.sample_rate.hint": (
        "auto mengekalkan kadar sumber (audio YouTube ialah 48 kHz). 44.1 kHz sepadan "
        "dengan CD dan pemain lama. Untuk mp3, flac dan wav; opus dan m4a kekal pada "
        "kadar sumber."
    ),
    "settings.style": "Gaya nama fail",
    "settings.style.hint": (
        '"Lagu sahaja" tidak memasukkan artis dalam nama fail; semua tag (artis, album, '
        "kulit album) tetap ditulis, dan dua lagu berlainan yang sama tajuk diberi "
        "akhiran id pendek supaya tidak saling menindih. Berkuat kuasa untuk muat "
        "turun baharu; fail sedia ada kekal dengan nama asal."
    ),
    "settings.track_number": "Nombor lagu dalam nama fail",
    "settings.track_number.hint": (
        'Tutup → "Lagu - Artis.mp3".   Buka → "01. Lagu - Artis.mp3".   '
        "Fail tersusun ikut urutan senarai main dalam pengurus fail anda."
    ),
    "settings.preview": "Pratonton nama fail",
    "settings.preview.song": "Lagu",
    "settings.preview.artist": "Artis",
    "settings.loose_match": "Guna hasil terdekat jika tiada padanan",
    "settings.loose_match.hint": (
        "Tutup (lalai): lagu dilangkau daripada berisiko mendapat audio yang salah. "
        "Buka: guna hasil yang paling hampir dari segi tempoh, yang dapat menyelamatkan "
        "lagu bertajuk YouTube dalam tulisan lain (Greek, Cyril, Korea) tetapi "
        "sesekali versi cover atau remix boleh terlepas masuk."
    ),
    "settings.lyrics": "Lirik",
    "settings.lyrics.hint": (
        "Mencari setiap lagu di LRCLIB, pangkalan data lirik percuma, dan menyisipkan "
        "liriknya ke dalam fail mp3, m4a dan flac. Lirik yang diselaraskan masa turut "
        "disimpan sebagai fail .lrc di sebelah lagu, untuk pemain yang menatal "
        "mengikut lagu. Perlukan Tambah tag dihidupkan di tetingkap utama."
    ),
    "settings.language": "Bahasa",
    "settings.language.hint": (
        "Berkuat kuasa serta-merta. Alat baris arahan kekal dalam bahasa Inggeris."
    ),
    "settings.theme": "Tema",
    "settings.ui_scale": "Saiz tetingkap",
    "settings.ui_scale.hint": (
        "Menskalakan seluruh tetingkap, termasuk teks dan butang, di atas penskalaan "
        "paparan sistem anda. Saiz yang tidak muat pada skrin ini dikelabukan. "
        "Berkuat kuasa apabila Sunnify dibuka semula."
    ),
    "settings.notify": "Maklumkan bila selesai",
    "settings.notify.hint": (
        "Mengelipkan bar tugas dan menunjukkan pemberitahuan sistem apabila muat turun "
        "selesai semasa Sunnify berada di latar belakang."
    ),
    "settings.save": "Simpan",
    "settings.open_logs": "Buka folder log",
    "common.cancel": "Batal",
    "common.close": "Tutup",
    # toast
    "update.eyebrow": "KEMAS KINI TERSEDIA",
    "update.body": (
        "Versi Sunnify yang lebih baharu sudah tersedia. Muat turun dari halaman "
        "keluaran untuk mendapatkan pembaikan dan penambahbaikan terkini."
    ),
    "update.later": "Ingatkan nanti",
    "update.download": "Muat turun",
    "star.eyebrow": "LAGU PERTAMA DIMUAT TURUN",
    "star.heading": "Suka Sunnify?",
    "star.body": (
        "Bintang di GitHub membantu projek ini terus hidup - begitulah orang baharu "
        "menemui Sunnify, dan ia cuma ambil lima saat. Permintaan ini muncul sekali "
        "sahaja."
    ),
    "star.later": "Mungkin nanti",
    "star.action": "Beri bintang di GitHub",
    # sejarah
    "history.title": "Sejarah muat turun",
    "history.subtitle": (
        "Muat turun terkini anda, yang terbaharu dahulu. Klik dua kali untuk membuka foldernya."
    ),
    "history.empty": "Belum ada apa-apa. Muat turun yang selesai akan dipaparkan di sini.",
    "history.open_folder": "Buka folder",
    "history.again": "Muat turun semula",
    "history.clear": "Kosongkan sejarah",
    "history.status.done": "Selesai",
    "history.status.partial": "Sebahagian gagal",
    "history.status.failed": "Gagal",
    "history.status.stopped": "Dihentikan",
    "history.counts": "{landed} disimpan",
    "history.failed": "{failed} gagal",
}

_TABLES = {"en": EN, "ms": MS}
_language = "en"


def language() -> str:
    return _language


def set_language(code: str) -> str:
    """Switch every later t() call; unknown codes fall back to English."""
    global _language
    _language = code if code in _TABLES else "en"
    return _language


def _system_locale_name() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        return locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        return ""


def resolve(setting: str | None, system_locale: str | None = None) -> str:
    """'en'/'ms' as chosen; 'auto' is Malay for a Malay locale (ms_MY, Malay_Malaysia)."""
    if setting in _TABLES:
        return setting
    name = (system_locale if system_locale is not None else _system_locale_name()).lower()
    return "ms" if name.startswith("ms") or "malay" in name else "en"


def t(key: str, **fields) -> str:
    """The string for key in the current language, with {fields} filled in."""
    text = _TABLES[_language].get(key) or EN.get(key) or key
    if not fields:
        return text
    try:
        return text.format(**fields)
    except (KeyError, IndexError, ValueError):
        return text
