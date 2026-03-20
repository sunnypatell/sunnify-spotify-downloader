#
"""Sunnify (Spotify Downloader) - Educational project"""
__version__ = "2.0.2"

import json, logging, os, sys, threading, webbrowser
logging.getLogger("yt_dlp").setLevel(logging.ERROR)

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from PyQt5.QtCore import (QEasingCurve, QPropertyAnimation, QSize, Qt,
    QThread, QTimer, pyqtSignal, pyqtSlot)
from PyQt5.QtGui import QCursor, QImage, QPixmap
from PyQt5.QtWidgets import (QApplication, QFileDialog, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy, QVBoxLayout, QWidget)
from PyQt5 import QtSvg
from yt_dlp import YoutubeDL
from spotifydown_api import (ExtractionError, NetworkError, PlaylistClient, PlaylistInfo,
    RateLimitError, SpotifyDownAPIError, TrackInfo, detect_spotify_url_type,
    extract_playlist_id, sanitize_filename)
from Template import Ui_MainWindow

# ── Config ────────────────────────────────────────────────────────────────────
def _cfg_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME",
               os.path.join(os.path.expanduser("~"), ".config"))
    d = os.path.join(base, "Sunnify"); os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")

def load_config():
    try:
        with open(_cfg_path(), "r") as f: return json.load(f)
    except: return {}

def save_config(data):
    try:
        with open(_cfg_path(), "w") as f: json.dump(data, f, indent=2)
    except: pass


# ── _CoverLoader: mismo patrón que DownloadThumbnail — el que SÍ funciona ────
class _CoverLoader(QThread):
    _ready = pyqtSignal(bytes)

    def __init__(self, url: str, target_label, w: int, h: int):
        super().__init__()
        self.url = url
        self._label = target_label
        self._w = w; self._h = h
        self._ready.connect(self._apply)

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=10)
            if r.status_code == 200:
                self._ready.emit(r.content)
        except Exception:
            pass

    @pyqtSlot(bytes)
    def _apply(self, data: bytes):
        img = QImage()
        img.loadFromData(data)
        if not img.isNull():
            px = QPixmap.fromImage(img).scaled(
                self._w, self._h,
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._label.setPixmap(px)


# ── MarqueeLabel: texto carrusel LED si no cabe ───────────────────────────────
class MarqueeLabel(QLabel):
    """Label con scroll automático si el texto es más ancho que el widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(30)          # ~33 fps
        self._timer.timeout.connect(self._scroll)
        self._full_text = ""
        self._scrolling = False
        self._pause_counter = 0             # pausa al inicio y al final
        self.setStyleSheet("color:#ffffff; font:bold 10pt 'Segoe UI';")

    def set_text(self, text: str):
        self._full_text = text
        self._offset = 0
        self._pause_counter = 40            # 40 ticks ≈ 1.2s de pausa al inicio
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        if text_w > self.width():
            self._scrolling = True
            self._timer.start()
        else:
            self._scrolling = False
            self._timer.stop()
            self.setText(text)

    def _scroll(self):
        if self._pause_counter > 0:
            self._pause_counter -= 1
            return
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self._full_text)
        widget_w = self.width()
        if text_w <= widget_w:
            self._timer.stop(); self.setText(self._full_text); return
        self._offset += 1
        if self._offset > text_w + 20:
            self._offset = -widget_w
            self._pause_counter = 40        # pausa al reiniciar
        self.update()

    def paintEvent(self, event):
        if not self._scrolling:
            super().paintEvent(event); return
        from PyQt5.QtGui import QPainter
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        fm = painter.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.drawText(-self._offset, y, self._full_text)
        painter.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._full_text:
            self.set_text(self._full_text)


# ── TrackCard: sin foto, solo texto + carrusel ────────────────────────────────
class TrackCard(QWidget):
    S_PENDING = "QWidget#card{background:#1e1e1e;border:1px solid #1DB954;border-radius:8px;}"
    S_ACTIVE  = "QWidget#card{background:#0d2e1a;border:2px solid #1DB954;border-radius:8px;}"
    S_DONE    = "QWidget#card{background:#242424;border:1px solid #282828;border-radius:8px;}"

    def __init__(self, track, index, parent=None):
        super().__init__(parent)
        self.track = track; self.index = index
        self._build(); self.set_state("pending")

    def _build(self):
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.card = QWidget(self); self.card.setObjectName("card")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2); outer.setSpacing(0)
        inner = QHBoxLayout()
        inner.setContentsMargins(10, 6, 10, 6); inner.setSpacing(10)

        # Número
        self.numL = QLabel(f"{self.index + 1:02d}")
        self.numL.setFixedWidth(24)
        self.numL.setAlignment(Qt.AlignCenter)
        self.numL.setStyleSheet("color:#535353; font:9pt 'Segoe UI';")
        inner.addWidget(self.numL)

        # Columna de texto (carrusel para título)
        col = QVBoxLayout(); col.setContentsMargins(0,0,0,0); col.setSpacing(1)

        self.titleL = MarqueeLabel()
        self.titleL.setFixedHeight(20)
        col.addWidget(self.titleL)

        aa = self.track.artists
        if self.track.album: aa += f"  ·  {self.track.album}"
        self.artistL = QLabel(self._e(aa, 48))
        self.artistL.setStyleSheet("color:#808080; font:9pt 'Segoe UI';")
        self.artistL.setToolTip(aa)
        col.addWidget(self.artistL)

        inner.addLayout(col)
        inner.addStretch()

        # Duración
        self.durL = QLabel(self._d(self.track.duration_ms))
        self.durL.setFixedWidth(36)
        self.durL.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.durL.setStyleSheet("color:#535353; font:9pt 'Consolas';")
        inner.addWidget(self.durL)

        self.card.setLayout(inner)
        outer.addWidget(self.card)
        self.setLayout(outer)

    @staticmethod
    def _e(t, n): return t if len(t) <= n else t[:n-1] + "…"

    @staticmethod
    def _d(ms):
        if not ms: return "--:--"
        s = int(ms) // 1000; m, s = divmod(s, 60)
        return f"{m}:{s:02d}"

    def set_state(self, s):
        if   s == "active": self.card.setStyleSheet(self.S_ACTIVE);  c = "#1DB954"
        elif s == "done":   self.card.setStyleSheet(self.S_DONE);    c = "#ffffff"
        else:               self.card.setStyleSheet(self.S_PENDING); c = "#b3b3b3"
        self.titleL.setStyleSheet(f"color:{c}; font:bold 10pt 'Segoe UI';")
        nc = "#1DB954" if s == "active" else "#535353"
        self.numL.setStyleSheet(f"color:{nc}; font:{'bold ' if s=='active' else ''}9pt 'Segoe UI';")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.card.setGeometry(0, 2, self.width(), 52)
        # Re-evaluar carrusel al cambiar tamaño
        if self._build.__code__.co_varnames:  # siempre True, solo trigger
            self.titleL.set_text(self.track.title)

    def showEvent(self, e):
        super().showEvent(e)
        self.titleL.set_text(self.track.title)


# ── PlaylistLoaderThread ──────────────────────────────────────────────────────
class PlaylistLoaderThread(QThread):
    playlist_loaded = pyqtSignal(object, list)
    load_error      = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._session = requests.Session()

    def run(self):
        try:
            client = PlaylistClient(session=self._session)
            ut, eid = detect_spotify_url_type(self.url)
            if ut == "track":
                tr = client.get_track(eid)
                info = PlaylistInfo(name=tr.title, owner=tr.artists,
                                    description=None, cover_url=tr.cover_url, track_count=1)
                self.playlist_loaded.emit(info, [tr])
            else:
                info   = client.get_playlist_metadata(eid)
                tracks = list(client.iter_playlist_tracks(eid))
                self.playlist_loaded.emit(info, tracks)
        except Exception as e:
            self.load_error.emit(str(e))


# ── FFmpeg ────────────────────────────────────────────────────────────────────
def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        bp = sys._MEIPASS
        f = os.path.join(bp, "ffmpeg",
                         "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if os.path.exists(f): return os.path.join(bp, "ffmpeg")
    fn = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    for p in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        if os.path.exists(os.path.join(p, fn)): return p
    import shutil
    f = shutil.which("ffmpeg")
    return os.path.dirname(f) if f else None


# ── MusicScraper ──────────────────────────────────────────────────────────────
class MusicScraper(QThread):
    PlaylistCompleted    = pyqtSignal(str)
    PlaylistID           = pyqtSignal(str)
    song_Album           = pyqtSignal(str)
    song_meta            = pyqtSignal(dict)
    add_song_meta        = pyqtSignal(dict)
    count_updated        = pyqtSignal(int, int)
    dlprogress_signal    = pyqtSignal(int)
    Resetprogress_signal = pyqtSignal(int)
    error_signal         = pyqtSignal(str)
    track_started        = pyqtSignal(int)

    def __init__(self, cancel_event=None):
        super().__init__()
        self.counter = 0; self.session = requests.Session()
        self.spotifydown_api = None
        self._cancel_event = cancel_event or threading.Event()
        self._failed: list[str] = []
        self.preloaded_tracks   = None
        self.preloaded_metadata = None
        self.audio_quality      = "320"     # inyectado desde MainWindow

    def is_cancelled(self): return self._cancel_event.is_set()

    def _err(self, e, t=""):
        if isinstance(e, RateLimitError):   return "Rate limited…"
        if isinstance(e, NetworkError):     return "Network error…"
        if isinstance(e, ExtractionError):  return f"Can't access '{t}'"
        return f"Error: {str(e)[:50]}"

    def _api(self):
        if not self.spotifydown_api:
            self.spotifydown_api = PlaylistClient(session=self.session)
        return self.spotifydown_api

    def _san(self, t): return sanitize_filename(t, allow_spaces=True)
    def _fmt(self, m): return f"{m.name} - {m.owner or 'Spotify'}".strip(" -")

    def _folder(self, base, name):
        os.makedirs(base, exist_ok=True)
        safe = "".join(c for c in name if c.isalnum() or c in " _").strip() or "Sunnify"
        f = os.path.join(base, safe); os.makedirs(f, exist_ok=True); return f

    def _dl(self, query, dest):
        ff = get_ffmpeg_path()
        if not ff: raise RuntimeError("FFmpeg not found!")
        base, _ = os.path.splitext(dest)
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "noplaylist": True, "quiet": True, "no_warnings": True,
            "outtmpl": base + ".%(ext)s", "ffmpeg_location": ff,
            "socket_timeout": 15, "retries": 2, "fragment_retries": 2,
            "concurrent_fragment_downloads": 4, "http_chunk_size": 10485760,
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                 "preferredcodec": "mp3",
                                 "preferredquality": self.audio_quality}],
            "geo_bypass": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if info.get("entries"): info = info["entries"][0]
            ep = base + ".mp3"
            if os.path.exists(ep): return ep
            fb = ydl.prepare_filename(info)
            return fb if os.path.exists(fb) else ep

    def scrape_playlist(self, link, folder):
        pid = extract_playlist_id(link); self.PlaylistID.emit(pid)
        api = self._api()
        if self.preloaded_tracks is not None and self.preloaded_metadata is not None:
            meta, tracks = self.preloaded_metadata, self.preloaded_tracks
        else:
            meta = api.get_playlist_metadata(pid)
            tracks = list(api.iter_playlist_tracks(pid))
        self.song_Album.emit(self._fmt(meta))
        dest = self._folder(folder, self._fmt(meta))
        total = len(tracks)
        self.count_updated.emit(0, total)
        self.track_started.emit(0)

        for i, tr in enumerate(tracks):
            if self.is_cancelled(): self.PlaylistCompleted.emit("Cancelled"); return
            self.Resetprogress_signal.emit(0)
            fn = f"{self._san(tr.title)} - {self._san(tr.artists)}.mp3"
            fp = os.path.join(dest, fn)
            sm = {"title": tr.title, "artists": tr.artists,
                  "album": tr.album or "", "releaseDate": tr.release_date or "",
                  "cover": tr.cover_url or meta.cover_url or "", "file": fp}
            self.song_meta.emit(dict(sm))
            if os.path.exists(fp):
                self.add_song_meta.emit(sm); self._inc(total, i); continue
            try: fp2 = self._dl(f"ytsearch1:{tr.title} {tr.artists} audio", fp)
            except Exception as e:
                self.error_signal.emit(self._err(e, tr.title))
                self._failed.append(tr.title); self._inc(total, i); continue
            if not fp2 or not os.path.exists(fp2):
                self._failed.append(tr.title); self._inc(total, i); continue
            sm["file"] = fp2; self.add_song_meta.emit(sm)
            self._inc(total, i); self.dlprogress_signal.emit(100)

        msg = (f"¡Listo!  ({len(self._failed)} fallaron)"
               if self._failed else "¡Listo!")
        self.PlaylistCompleted.emit(msg)

    def scrape_track(self, link, folder):
        _, tid = detect_spotify_url_type(link)
        tr = self._api().get_track(tid)
        self.song_Album.emit("Single Track")
        os.makedirs(folder, exist_ok=True)
        self.Resetprogress_signal.emit(0)
        self.count_updated.emit(0, 1); self.track_started.emit(0)
        fn = f"{self._san(tr.title)} - {self._san(tr.artists)}.mp3"
        fp = os.path.join(folder, fn)
        sm = {"title": tr.title, "artists": tr.artists,
              "album": tr.album or "", "releaseDate": tr.release_date or "",
              "cover": tr.cover_url or "", "file": fp}
        self.song_meta.emit(dict(sm))
        if os.path.exists(fp):
            self.add_song_meta.emit(sm); self._inc(1, 0)
            self.PlaylistCompleted.emit("¡Listo!"); return
        try: fp2 = self._dl(f"ytsearch1:{tr.title} {tr.artists} audio", fp)
        except Exception as e:
            self.PlaylistCompleted.emit(self._err(e, tr.title)); return
        if not fp2 or not os.path.exists(fp2):
            self.PlaylistCompleted.emit("Failed"); return
        sm["file"] = fp2; self.add_song_meta.emit(sm)
        self._inc(1, 0); self.dlprogress_signal.emit(100)
        self.PlaylistCompleted.emit("¡Listo!")

    def _inc(self, total, current_idx):
        self.counter += 1; self.count_updated.emit(self.counter, total)
        nxt = current_idx + 1
        if nxt < total: self.track_started.emit(nxt)


class ScraperThread(QThread):
    progress_update = pyqtSignal(str)
    def __init__(self, link, folder=None, cancel_event=None,
                 preloaded_tracks=None, preloaded_metadata=None, audio_quality="320"):
        super().__init__()
        self.link = link
        self.folder = folder or os.path.join(os.getcwd(), "music")
        self._ce = cancel_event or threading.Event()
        self.scraper = MusicScraper(cancel_event=self._ce)
        self.scraper.preloaded_tracks   = preloaded_tracks
        self.scraper.preloaded_metadata = preloaded_metadata
        self.scraper.audio_quality      = audio_quality
    def request_cancel(self): self._ce.set()
    def run(self):
        self.progress_update.emit("Starting…")
        try:
            ut, _ = detect_spotify_url_type(self.link)
            if ut == "track": self.scraper.scrape_track(self.link, self.folder)
            else:             self.scraper.scrape_playlist(self.link, self.folder)
        except Exception as e: self.progress_update.emit(str(e))


class DownloadCover(QThread):
    albumCover = pyqtSignal(object)
    def __init__(self, url): super().__init__(); self.url = url
    def run(self):
        r = requests.get(self.url, stream=True)
        if r.status_code == 200: self.albumCover.emit(r.content)


class WritingMetaTagsThread(QThread):
    tags_success = pyqtSignal(str)
    def __init__(self, tags, filename, fields: set):
        super().__init__()
        self.tags = tags; self.filename = filename
        self.fields = fields          # qué campos escribir
        self._ct = None
    def run(self):
        try:
            audio = EasyID3(self.filename)
            if "title"       in self.fields: audio["title"]  = self.tags.get("title","")
            if "artist"      in self.fields: audio["artist"] = self.tags.get("artists","")
            if "album"       in self.fields: audio["album"]  = self.tags.get("album","")
            if "releaseDate" in self.fields: audio["date"]   = self.tags.get("releaseDate","")
            audio.save()
            if "cover" in self.fields:
                cu = self.tags.get("cover","")
                if cu:
                    self._ct = DownloadCover(cu)
                    self._ct.albumCover.connect(self.setPIC); self._ct.start()
        except Exception as e: print(f"[*] Meta: {e}")
    def setPIC(self, data):
        if not data: self.tags_success.emit("Cover Not Added"); return
        try:
            a = ID3(self.filename)
            a["APIC"] = APIC(encoding=3, mime="image/jpeg",
                              type=3, desc="Cover", data=data)
            a.save(); self.tags_success.emit("Tags added")
        except Exception as e: self.tags_success.emit(f"Cover err: {e}")


# ── MainWindow ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # Config
        cfg = load_config()
        sp = cfg.get("download_path","")
        if sp and os.path.isdir(os.path.dirname(sp)):
            self.download_path = sp; self._dp_set = True
        else:
            self.download_path = self._def_path(); self._dp_set = False
        self._config = cfg

        # Estado
        self._threads: list = []
        self._cards:   list[TrackCard] = []
        self._active_idx = -1
        self._downloading = False
        self._cancel  = threading.Event()
        self._pre_tracks  = None; self._pre_meta = None
        self._loader  = None
        self._view_mode = "list"
        self._user_scrolled = False; self._auto_scrolling = False
        self._individual_cover_loader = None

        # Timers
        self._dc = 0
        self._dtimer = QTimer(self); self._dtimer.setInterval(400)
        self._dtimer.timeout.connect(self._tick_dots); self._dmsg = ""
        self._secs = 0
        self._ctimer = QTimer(self); self._ctimer.setInterval(1000)
        self._ctimer.timeout.connect(self._tick_chrono)
        self._sdebounce = QTimer(self); self._sdebounce.setSingleShot(True)
        self._sdebounce.setInterval(2500); self._sdebounce.timeout.connect(self._rst_scroll)
        self._udebounce = QTimer(self); self._udebounce.setSingleShot(True)
        self._udebounce.setInterval(900);  self._udebounce.timeout.connect(self._load_info)

        self.SONGINFORMATION.setGraphicsEffect(
            QGraphicsDropShadowEffect(blurRadius=25, xOffset=2, yOffset=2))

        # Conexiones básicas
        self.PlaylistLink.returnPressed.connect(self.on_returnButton)
        self.DownloadBtn.clicked.connect(self.on_returnButton)
        self.showPreviewCheck.stateChanged.connect(self.show_preview)
        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)
        self.PlaylistLink.textChanged.connect(self._on_url_changed)
        self.trackScrollArea.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.viewSwitchBtn.toggled.connect(self._on_view_switch)

        # Acordeones
        self.metaDropBtn.toggled.connect(self._toggle_meta_panel)
        self.qualityDropBtn.toggled.connect(self._toggle_quality_panel)
        # "All" controla todos
        self.metaChecks["all"].stateChanged.connect(self._on_all_meta)
        for k, cb in self.metaChecks.items():
            if k != "all":
                cb.stateChanged.connect(self._on_single_meta)
        # Radio de calidad actualiza botón
        for q, rb in self.qualityRadios.items():
            rb.toggled.connect(lambda checked, qv=q: self._on_quality_changed(qv) if checked else None)

    # ── Acordeones ────────────────────────────────────────────────────────
    def _toggle_meta_panel(self, checked: bool):
        self.metaPanel.setVisible(checked)
        self.metaDropBtn.setText("▴ Meta Tags" if checked else "▾ Meta Tags")

    def _toggle_quality_panel(self, checked: bool):
        self.qualityPanel.setVisible(checked)
        q = self._selected_quality()
        self.qualityDropBtn.setText(
            f"▴ Quality: {q}kbps" if checked else f"▾ Quality: {q}kbps")

    def _on_all_meta(self, state: int):
        if state == Qt.Checked:
            for k, cb in self.metaChecks.items():
                if k != "all": cb.blockSignals(True); cb.setChecked(True); cb.blockSignals(False)

    def _on_single_meta(self):
        all_checked = all(
            cb.isChecked() for k, cb in self.metaChecks.items() if k != "all")
        self.metaChecks["all"].blockSignals(True)
        self.metaChecks["all"].setChecked(all_checked)
        self.metaChecks["all"].blockSignals(False)

    def _on_quality_changed(self, q: str):
        if self.qualityPanel.isVisible():
            self.qualityDropBtn.setText(f"▴ Quality: {q}kbps")
        else:
            self.qualityDropBtn.setText(f"▾ Quality: {q}kbps")

    def _selected_quality(self) -> str:
        for q, rb in self.qualityRadios.items():
            if rb.isChecked(): return q
        return "320"

    def _selected_meta_fields(self) -> set:
        """Devuelve set de campos a escribir."""
        fields = set()
        mapping = {
            "cover":       "cover",
            "title":       "title",
            "artist":      "artist",
            "album":       "album",
            "releaseDate": "releaseDate",
        }
        for k, cb in self.metaChecks.items():
            if k in mapping and cb.isChecked():
                fields.add(mapping[k])
        return fields

    # ── Switch vista ──────────────────────────────────────────────────────
    def _on_view_switch(self, checked: bool):
        if checked:
            self._view_mode = "individual"
            self.viewSwitchBtn.setText("♪ Individual")
            self.trackScrollArea.hide(); self.individualView.show()
        else:
            self._view_mode = "list"
            self.viewSwitchBtn.setText("☰ Lista")
            self.individualView.hide(); self.trackScrollArea.show()

    # ── Scroll inteligente ────────────────────────────────────────────────
    def _on_scroll(self, _):
        if not self._downloading or self._auto_scrolling: return
        self._user_scrolled = True; self._sdebounce.start()
        if 0 <= self._active_idx < len(self._cards):
            if self._card_visible(self._cards[self._active_idx]):
                self._user_scrolled = False; self._sdebounce.stop()

    def _rst_scroll(self): self._user_scrolled = False; self._scroll_to(self._active_idx)

    def _card_visible(self, card):
        vb = self.trackScrollArea.verticalScrollBar()
        top = vb.value(); bot = top + self.trackScrollArea.viewport().height()
        idx = self._cards.index(card); ct = idx * 60; cb = ct + 56
        return not (cb < top or ct > bot)

    def _scroll_to(self, idx):
        if self._user_scrolled or not (0 <= idx < len(self._cards)): return
        self._auto_scrolling = True
        self.trackScrollArea.ensureWidgetVisible(self._cards[idx], 0, 120)
        QTimer.singleShot(60, lambda: setattr(self, "_auto_scrolling", False))

    # ── URL auto-load ──────────────────────────────────────────────────────
    def _on_url_changed(self, text):
        if len(text.strip()) > 20: self._udebounce.start()
        else: self._udebounce.stop(); self._clear_ui()

    def _load_info(self):
        url = self.PlaylistLink.text().strip()
        try: detect_spotify_url_type(url)
        except: return
        if self._loader and self._loader.isRunning(): self._loader.quit()
        self.AlbumName.setText("Cargando…"); self.playlistStats.setText("")
        self._loader = PlaylistLoaderThread(url)
        self._loader.playlist_loaded.connect(self._on_loaded)
        self._loader.load_error.connect(lambda e: self.AlbumName.setText(f"Error: {e[:35]}"))
        self._loader.start()

    @pyqtSlot(object, list)
    def _on_loaded(self, info, tracks):
        self._pre_tracks = tracks; self._pre_meta = info
        ms = sum(t.duration_ms or 0 for t in tracks)
        tm = ms // 60000; h, m = divmod(tm, 60)
        ds = f"{h}h {m}min" if h else f"{m}min"
        self.AlbumName.setText(info.name)
        self.playlistStats.setText(f"{len(tracks)} canciones  ·  {ds}")
        self.panelPlaylistStats.setText(
            f"{len(tracks)} canciones  ·  {ds}  ·  {info.owner or 'Spotify'}")
        self.label_3.setText(info.name[:38])
        self._build_cards(tracks)
        if self.showPreviewCheck.isChecked(): self.OpenSongInformation()

    def _build_cards(self, tracks):
        for c in self._cards: c.setParent(None)
        self._cards.clear(); self._active_idx = -1
        n = self.trackListLayout.count()
        if n > 0:
            item = self.trackListLayout.itemAt(n-1)
            if item and item.spacerItem(): self.trackListLayout.removeItem(item)
        for i, tr in enumerate(tracks):
            c = TrackCard(tr, i); self._cards.append(c)
            self.trackListLayout.addWidget(c)
        self.trackListLayout.addStretch()

    def _clear_ui(self):
        self.AlbumName.setText(""); self.playlistStats.setText("")
        self.panelPlaylistStats.setText(""); self.label_3.setText("Playlist")
        self._pre_tracks = None; self._pre_meta = None
        for c in self._cards: c.setParent(None)
        self._cards.clear()

    # ── Dots / Chrono ──────────────────────────────────────────────────────
    def _start_dots(self, msg): self._dmsg=msg; self._dc=0; self._dtimer.start()
    def _stop_dots(self): self._dtimer.stop()
    def _tick_dots(self): self._dc=(self._dc%3)+1; self.statusMsg.setText(self._dmsg+"."*self._dc)

    def _start_chrono(self): self._secs=0; self.timeLabel.setText("00:00:00"); self._ctimer.start()
    def _stop_chrono(self): self._ctimer.stop()
    def _tick_chrono(self):
        self._secs+=1; h=self._secs//3600; m=(self._secs%3600)//60; s=self._secs%60
        self.timeLabel.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ── Paths ──────────────────────────────────────────────────────────────
    def _def_path(self):
        home = os.path.expanduser("~"); f = os.path.join(home,"Music","Sunnify")
        if sys.platform == "win32":
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                f = os.path.join(winreg.QueryValueEx(k,"My Music")[0],"Sunnify")
                winreg.CloseKey(k)
            except: pass
        return f

    def _ensure_path(self):
        try:
            os.makedirs(self.download_path, exist_ok=True)
            t = os.path.join(self.download_path,".t"); open(t,"w").close(); os.remove(t)
            return True
        except: return False

    def _prompt(self):
        f = QFileDialog.getExistingDirectory(self,"Select Download Folder",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly|QFileDialog.DontResolveSymlinks)
        if f:
            self.download_path=os.path.join(f,"Sunnify"); self._dp_set=True
            self._config["download_path"]=self.download_path; save_config(self._config)
            return True
        return False

    def open_settings(self):
        f = QFileDialog.getExistingDirectory(self,"Select Download Folder",
            self.download_path if os.path.exists(self.download_path)
            else os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly|QFileDialog.DontResolveSymlinks)
        if f:
            self.download_path=os.path.join(f,"Sunnify"); self._dp_set=True
            self._config["download_path"]=self.download_path; save_config(self._config)
            QMessageBox.information(self,"Settings",f"Download location:\n{self.download_path}")

    # ── Download ──────────────────────────────────────────────────────────
    @pyqtSlot()
    def on_returnButton(self):
        if self._downloading: self._stop(); return
        url = self.PlaylistLink.text().strip()
        if not url: self.statusMsg.setText("Please enter a Spotify URL"); return
        if not self._dp_set:
            if not self._prompt(): self.statusMsg.setText("Cancelled"); return
        if not self._ensure_path():
            QMessageBox.warning(self,"Invalid",f"Cannot write to:\n{self.download_path}")
            if not self._prompt(): return
        try:
            ut, _ = detect_spotify_url_type(url)
            self.statusMsg.setText(f"Detected: {ut}")
            self._cancel = threading.Event()
            self._downloading = True; self._user_scrolled = False
            self.DownloadBtn.setText("Stop"); self._start_chrono()
            if self._pre_tracks: self.OpenSongInformation()

            self.scraper_thread = ScraperThread(
                url, self.download_path, self._cancel,
                self._pre_tracks, self._pre_meta,
                audio_quality=self._selected_quality())    # ← calidad seleccionada
            st = self.scraper_thread
            st.progress_update.connect(self.statusMsg.setText)
            st.finished.connect(self._thread_done)
            st.scraper.song_Album.connect(lambda n: self.AlbumName.setText(n))
            st.scraper.song_meta.connect(self._song_meta)
            st.scraper.add_song_meta.connect(self._add_meta)
            st.scraper.dlprogress_signal.connect(self.SongDownloadprogress.setValue)
            st.scraper.Resetprogress_signal.connect(lambda _:self.SongDownloadprogress.setValue(0))
            st.scraper.PlaylistCompleted.connect(self._completed)
            st.scraper.error_signal.connect(self.statusMsg.setText)
            st.scraper.count_updated.connect(self._counter)
            st.scraper.track_started.connect(self._track_start)
            st.start()
        except ValueError as e:
            self.statusMsg.setText(str(e)); self._downloading=False; self.DownloadBtn.setText("Download")

    def _stop(self):
        self._stop_dots(); self._stop_chrono()
        self.statusMsg.setText("Stopping…"); self._cancel.set()
        if hasattr(self,"scraper_thread") and self.scraper_thread.isRunning():
            self.scraper_thread.request_cancel()
            if not self.scraper_thread.wait(3000):
                self.scraper_thread.terminate(); self.scraper_thread.wait(1000)
        self._downloading=False; self.DownloadBtn.setText("Download")
        self.statusMsg.setText("Stopped")

    def _thread_done(self):
        self._downloading=False; self.DownloadBtn.setText("Download")
        if hasattr(self,"scraper_thread"): self.scraper_thread.deleteLater()

    # ── Slots ──────────────────────────────────────────────────────────────
    @pyqtSlot(int,int)
    def _counter(self, n, t):
        self.CounterLabel.setText(f"{n}/{t}" if t else str(n))
        if not self._dtimer.isActive(): self._start_dots("Descargando")

    @pyqtSlot(int)
    def _track_start(self, idx):
        if 0<=self._active_idx<len(self._cards):
            self._cards[self._active_idx].set_state("done")
        self._active_idx = idx
        if idx < len(self._cards):
            self._cards[idx].set_state("active")
            if self._view_mode == "list": self._scroll_to(idx)

    @pyqtSlot(str)
    def _completed(self, msg):
        self._stop_dots(); self._stop_chrono(); self.statusMsg.setText(msg)
        if 0<=self._active_idx<len(self._cards):
            self._cards[self._active_idx].set_state("done")

    @pyqtSlot(dict)
    def _song_meta(self, m):
        title = m.get("title",""); artists = m.get("artists","")
        self.MainSongName.setText(f"{title} - {artists}")
        if self._view_mode == "individual":
            self.SongName.setText(title)
            self.ArtistNameText.setText(artists)
            self.AlbumText.setText(m.get("album",""))
            self.YearText.setText(m.get("releaseDate",""))
            cu = m.get("cover","")
            if cu:
                self._individual_cover_loader = _CoverLoader(cu, self.CoverImg, 150, 150)
                self._individual_cover_loader.start()

    @pyqtSlot(dict)
    def _add_meta(self, m):
        fields = self._selected_meta_fields()
        if not fields: return
        t = WritingMetaTagsThread(m, m["file"], fields)
        t.tags_success.connect(self.statusMsg.setText)
        self._threads.append(t)
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        t.start()

    # ── Panel anim ────────────────────────────────────────────────────────
    def CloseSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(250); self.animation.setEndValue(QSize(0,506))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad); self.animation.start()

    def OpenSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(600); self.animation.setEndValue(QSize(413,506))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad); self.animation.start()

    def show_preview(self, s):
        if s == 2: self.OpenSongInformation()
        else: self.CloseSongInformation()

    # ── Drag ──────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag=True; self.m_DragPosition=e.globalPos()-self.pos()
            e.accept(); self.setCursor(QCursor(Qt.ClosedHandCursor))
    def mouseMoveEvent(self, e):
        try:
            if Qt.LeftButton and self.m_drag:
                self.move(e.globalPos()-self.m_DragPosition); e.accept()
        except AttributeError: pass
    def mouseReleaseEvent(self, e):
        self.m_drag=False; self.setCursor(QCursor(Qt.ArrowCursor))

    def exitprogram(self): sys.exit()
    def Linkedin(self): webbrowser.open("https://www.linkedin.com/in/sunny-patel-30b460204/")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(550); Screen.setFixedWidth(825)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())