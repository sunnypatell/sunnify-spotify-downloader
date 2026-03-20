# -*- coding: utf-8 -*-
# Sunnify - UI v4
# Carrusel en títulos, dropdowns acordeón, iconos SVG, sin foto en lista

from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(825, 550)

        MainWindow.setStyleSheet(
            """
            QFrame#frame {
                background-color: #181818;
                border-radius: 12px;
                border: 1px solid #282828;
            }
            QFrame#SONGINFORMATION {
                background-color: #1a1a1a;
                border-radius: 12px;
                border: 1px solid #282828;
            }
            QPushButton#Closed {
                background-color: #282828;
                color: #b3b3b3;
                border-radius: 10px;
                font-weight: bold;
                border: none;
            }
            QPushButton#Closed:hover  { background-color: #E53935; color: #ffffff; }
            QPushButton#Closed:pressed{ background-color: #c62828; }

            QPushButton#SettingsBtn {
                background-color: #282828;
                color: #b3b3b3;
                border-radius: 10px;
                border: none;
            }
            QPushButton#SettingsBtn:hover  { background-color: #1DB954; color: #000000; }
            QPushButton#SettingsBtn:pressed{ background-color: #17a349; }

            QLineEdit#PlaylistLink {
                background-color: #282828;
                border: 2px solid #383838;
                border-radius: 8px;
                color: #ffffff;
                padding: 4px 10px;
                selection-background-color: #1DB954;
            }
            QLineEdit#PlaylistLink:focus {
                border-color: #1DB954;
                background-color: #2a2a2a;
            }
            QPushButton#DownloadBtn {
                background-color: #1DB954;
                color: #000000;
                border-radius: 8px;
                font-weight: 700;
            }
            QPushButton#DownloadBtn:hover  { background-color: #1ed760; }
            QPushButton#DownloadBtn:pressed{ background-color: #17a349; padding-top:1px; }

            QPushButton#Select_Home {
                background-color: transparent;
                color: #535353;
                border: 1px solid #282828;
                border-radius: 6px;
            }
            QPushButton#Select_Home:hover { color: #1DB954; border-color: #1DB954; }

            /* Botones acordeón */
            QPushButton#metaDropBtn, QPushButton#qualityDropBtn {
                background-color: #242424;
                color: #b3b3b3;
                border: 1px solid #383838;
                border-radius: 6px;
                text-align: left;
                padding-left: 8px;
            }
            QPushButton#metaDropBtn:hover, QPushButton#qualityDropBtn:hover {
                border-color: #1DB954;
                color: #ffffff;
            }
            QPushButton#metaDropBtn:checked, QPushButton#qualityDropBtn:checked {
                border-color: #1DB954;
                color: #1DB954;
            }

            /* Panel acordeón */
            QFrame#metaPanel, QFrame#qualityPanel {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
            }

            QLabel { color: #b3b3b3; background-color: transparent; }

            QCheckBox { color: #b3b3b3; spacing: 6px; }
            QCheckBox::indicator {
                width: 15px; height: 15px;
                border-radius: 3px;
                border: 2px solid #535353;
                background-color: #282828;
            }
            QCheckBox::indicator:checked { background-color: #1DB954; border-color: #1DB954; }
            QCheckBox::indicator:hover   { border-color: #1DB954; }

            /* Radio buttons para calidad */
            QRadioButton { color: #b3b3b3; spacing: 6px; }
            QRadioButton::indicator {
                width: 14px; height: 14px;
                border-radius: 7px;
                border: 2px solid #535353;
                background-color: #282828;
            }
            QRadioButton::indicator:checked {
                background-color: #1DB954;
                border-color: #1DB954;
            }
            QRadioButton::indicator:hover { border-color: #1DB954; }

            QProgressBar { background-color: #282828; border-radius: 2px; border: none; }
            QProgressBar::chunk { background-color: #1DB954; border-radius: 2px; }

            QScrollArea#trackScrollArea { background-color: transparent; border: none; }
            QScrollArea#trackScrollArea > QWidget > QWidget { background-color: transparent; }
            QScrollBar:vertical {
                background: #1a1a1a; width: 6px; border-radius: 3px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1DB954; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #1ed760; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: #282828; border-radius: 3px;
            }

            QPushButton#viewSwitchBtn {
                background-color: #282828;
                color: #b3b3b3;
                border: 1px solid #383838;
                border-radius: 12px;
                padding: 0 8px;
            }
            QPushButton#viewSwitchBtn:checked {
                background-color: #1DB954; color: #000000; border: 1px solid #1DB954;
            }
            QPushButton#viewSwitchBtn:hover { border-color: #1DB954; }
        """
        )

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # ══════════════════════════════════════════════════════════════════
        # PANEL IZQUIERDO  352 x 506
        # ══════════════════════════════════════════════════════════════════
        self.frame = QtWidgets.QFrame(self.centralwidget)
        self.frame.setGeometry(QtCore.QRect(33, 22, 352, 506))
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")

        # ── Versión ──
        self.version = QtWidgets.QLabel(self.frame)
        self.version.setGeometry(QtCore.QRect(11, 11, 55, 22))
        self.version.setFont(QtGui.QFont("Consolas", 9))
        self.version.setStyleSheet("color:#535353;")
        self.version.setObjectName("version")

        # ── Título ──
        self.title = QtWidgets.QLabel(self.frame)
        self.title.setGeometry(QtCore.QRect(66, 11, 220, 38))
        ft = QtGui.QFont("Segoe UI", 18)
        ft.setBold(True)
        self.title.setFont(ft)
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setStyleSheet("color:#1DB954; letter-spacing:2px;")
        self.title.setScaledContents(True)
        self.title.setObjectName("title")

        # ── Botón Settings (SVG) ──
        self.SettingsBtn = QtWidgets.QPushButton(self.frame)
        self.SettingsBtn.setGeometry(QtCore.QRect(292, 11, 22, 22))
        self.SettingsBtn.setMaximumSize(QtCore.QSize(22, 22))
        self.SettingsBtn.setObjectName("SettingsBtn")
        # SVG inline de engranaje
        _gear_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#b3b3b3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>"""
        _px_gear = QtGui.QPixmap(22, 22)
        _px_gear.fill(QtCore.Qt.transparent)
        _svg_r = QtSvg.QSvgRenderer(_gear_svg)
        _p = QtGui.QPainter(_px_gear)
        _svg_r.render(_p)
        _p.end()
        self.SettingsBtn.setIcon(QtGui.QIcon(_px_gear))
        self.SettingsBtn.setIconSize(QtCore.QSize(16, 16))

        # ── Botón Cerrar (SVG X) ──
        self.Closed = QtWidgets.QPushButton(self.frame)
        self.Closed.setGeometry(QtCore.QRect(319, 11, 22, 22))
        self.Closed.setMaximumSize(QtCore.QSize(22, 22))
        self.Closed.setObjectName("Closed")
        _x_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#b3b3b3" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>"""
        _px_x = QtGui.QPixmap(22, 22)
        _px_x.fill(QtCore.Qt.transparent)
        _svg_rx = QtSvg.QSvgRenderer(_x_svg)
        _px2 = QtGui.QPainter(_px_x)
        _svg_rx.render(_px2)
        _px2.end()
        self.Closed.setIcon(QtGui.QIcon(_px_x))
        self.Closed.setIconSize(QtCore.QSize(14, 14))

        # ── Autor ──
        self.author = QtWidgets.QLabel(self.frame)
        self.author.setGeometry(QtCore.QRect(33, 42, 286, 22))
        self.author.setFont(QtGui.QFont("Segoe UI", 8))
        self.author.setAlignment(QtCore.Qt.AlignCenter)
        self.author.setStyleSheet("color:#535353;")
        self.author.setObjectName("author")

        sep1 = QtWidgets.QFrame(self.frame)
        sep1.setGeometry(QtCore.QRect(22, 68, 308, 1))
        sep1.setStyleSheet("background-color:#282828;")
        sep1.setFrameShape(QtWidgets.QFrame.HLine)

        # ── Input URL ──
        self.PlaylistLink = QtWidgets.QLineEdit(self.frame)
        self.PlaylistLink.setGeometry(QtCore.QRect(22, 77, 220, 44))
        self.PlaylistLink.setFont(QtGui.QFont("Segoe UI", 11))
        self.PlaylistLink.setClearButtonEnabled(True)
        self.PlaylistLink.setObjectName("PlaylistLink")

        # ── Botón Download ──
        self.DownloadBtn = QtWidgets.QPushButton(self.frame)
        self.DownloadBtn.setGeometry(QtCore.QRect(248, 77, 83, 44))
        fdl = QtGui.QFont("Segoe UI", 10)
        fdl.setBold(True)
        self.DownloadBtn.setFont(fdl)
        self.DownloadBtn.setObjectName("DownloadBtn")

        sep2 = QtWidgets.QFrame(self.frame)
        sep2.setGeometry(QtCore.QRect(22, 127, 308, 1))
        sep2.setStyleSheet("background-color:#282828;")
        sep2.setFrameShape(QtWidgets.QFrame.HLine)

        # ── Playlist Name ──
        self.AlbumName = QtWidgets.QLabel(self.frame)
        self.AlbumName.setGeometry(QtCore.QRect(22, 132, 308, 22))
        self.AlbumName.setFont(QtGui.QFont("Segoe UI", 10))
        self.AlbumName.setStyleSheet("color:#ffffff;")
        self.AlbumName.setWordWrap(True)
        self.AlbumName.setObjectName("AlbumName")

        self.playlistStats = QtWidgets.QLabel(self.frame)
        self.playlistStats.setGeometry(QtCore.QRect(22, 155, 308, 18))
        self.playlistStats.setFont(QtGui.QFont("Segoe UI", 9))
        self.playlistStats.setStyleSheet("color:#535353;")
        self.playlistStats.setText("")
        self.playlistStats.setObjectName("playlistStats")

        sep3 = QtWidgets.QFrame(self.frame)
        sep3.setGeometry(QtCore.QRect(22, 178, 308, 1))
        sep3.setStyleSheet("background-color:#282828;")
        sep3.setFrameShape(QtWidgets.QFrame.HLine)

        # ── Spotify Song Name label ──
        self.PlaylistMsg_2 = QtWidgets.QLabel(self.frame)
        self.PlaylistMsg_2.setGeometry(QtCore.QRect(22, 183, 308, 18))
        self.PlaylistMsg_2.setFont(QtGui.QFont("Segoe UI", 9))
        self.PlaylistMsg_2.setStyleSheet("color:#535353;")
        self.PlaylistMsg_2.setWordWrap(True)
        self.PlaylistMsg_2.setObjectName("PlaylistMsg_2")

        # ── Nombre canción actual ──
        self.MainSongName = QtWidgets.QLabel(self.frame)
        self.MainSongName.setGeometry(QtCore.QRect(22, 201, 308, 36))
        fsn = QtGui.QFont("Segoe UI", 11)
        fsn.setBold(True)
        self.MainSongName.setFont(fsn)
        self.MainSongName.setText("")
        self.MainSongName.setAlignment(QtCore.Qt.AlignCenter)
        self.MainSongName.setWordWrap(True)
        self.MainSongName.setStyleSheet("color:#ffffff;")
        self.MainSongName.setObjectName("MainSongName")

        # ── Show Preview checkbox (solo este queda) ──
        self.showPreviewCheck = QtWidgets.QCheckBox(self.frame)
        self.showPreviewCheck.setGeometry(QtCore.QRect(22, 242, 140, 22))
        self.showPreviewCheck.setFont(QtGui.QFont("Segoe UI", 10))
        self.showPreviewCheck.setObjectName("showPreviewCheck")

        # ── Dropdown Calidad (acordeón) ──
        self.qualityDropBtn = QtWidgets.QPushButton(self.frame)
        self.qualityDropBtn.setGeometry(QtCore.QRect(170, 239, 160, 26))
        self.qualityDropBtn.setFont(QtGui.QFont("Segoe UI", 9))
        self.qualityDropBtn.setObjectName("qualityDropBtn")
        self.qualityDropBtn.setCheckable(True)
        self.qualityDropBtn.setChecked(False)

        # Panel calidad (oculto por defecto)
        self.qualityPanel = QtWidgets.QFrame(self.frame)
        self.qualityPanel.setGeometry(QtCore.QRect(170, 268, 160, 90))
        self.qualityPanel.setObjectName("qualityPanel")
        self.qualityPanel.hide()
        _ql = QtWidgets.QVBoxLayout(self.qualityPanel)
        _ql.setContentsMargins(10, 6, 10, 6)
        _ql.setSpacing(4)
        self.qualityRadios = {}
        for _q in ["128 kbps", "192 kbps", "256 kbps", "320 kbps"]:
            _rb = QtWidgets.QRadioButton(_q, self.qualityPanel)
            _rb.setFont(QtGui.QFont("Segoe UI", 9))
            _ql.addWidget(_rb)
            self.qualityRadios[_q.replace(" kbps", "")] = _rb
        self.qualityRadios["320"].setChecked(True)  # default 320

        # ── Dropdown Metadatos (acordeón) ──
        self.metaDropBtn = QtWidgets.QPushButton(self.frame)
        self.metaDropBtn.setGeometry(QtCore.QRect(22, 269, 140, 26))
        self.metaDropBtn.setFont(QtGui.QFont("Segoe UI", 9))
        self.metaDropBtn.setObjectName("metaDropBtn")
        self.metaDropBtn.setCheckable(True)
        self.metaDropBtn.setChecked(False)

        # Panel metadatos (oculto por defecto) — se superpone sobre los stats
        self.metaPanel = QtWidgets.QFrame(self.frame)
        self.metaPanel.setGeometry(QtCore.QRect(22, 298, 160, 148))
        self.metaPanel.setObjectName("metaPanel")
        self.metaPanel.hide()
        # Elevar para que tape los widgets de abajo
        self.metaPanel.raise_()
        _ml = QtWidgets.QVBoxLayout(self.metaPanel)
        _ml.setContentsMargins(10, 6, 10, 6)
        _ml.setSpacing(3)
        _meta_items = [
            ("all", "All Meta Tags"),
            ("cover", "Cover / Foto"),
            ("title", "Title"),
            ("artist", "Artist"),
            ("album", "Album"),
            ("releaseDate", "Release Date"),
            ("trackNum", "Track Number"),
        ]
        self.metaChecks = {}
        for _key, _label in _meta_items:
            _cb = QtWidgets.QCheckBox(_label, self.metaPanel)
            _cb.setFont(QtGui.QFont("Segoe UI", 9))
            _cb.setChecked(True)
            _ml.addWidget(_cb)
            self.metaChecks[_key] = _cb
        # También mantener AddMetaDataCheck como alias (compatibilidad)
        self.AddMetaDataCheck = self.metaChecks["all"]

        # ── Fila: Counter ──
        self.horizontalLayoutWidget_4 = QtWidgets.QWidget(self.frame)
        self.horizontalLayoutWidget_4.setGeometry(QtCore.QRect(22, 303, 308, 26))
        self.horizontalLayoutWidget_4.setObjectName("horizontalLayoutWidget_4")
        self.counterBox = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_4)
        self.counterBox.setContentsMargins(0, 0, 0, 0)
        self.counterBox.setSpacing(5)

        self.label_10 = QtWidgets.QLabel(self.horizontalLayoutWidget_4)
        self.label_10.setMinimumSize(QtCore.QSize(66, 0))
        self.label_10.setMaximumSize(QtCore.QSize(77, 16777215))
        self.label_10.setFont(QtGui.QFont("Segoe UI", 11))
        self.label_10.setStyleSheet("color:#1DB954;")
        self.label_10.setObjectName("label_10")
        self.counterBox.addWidget(self.label_10)

        self.CounterLabel = QtWidgets.QLabel(self.horizontalLayoutWidget_4)
        self.CounterLabel.setFont(QtGui.QFont("Segoe UI", 10))
        self.CounterLabel.setStyleSheet("color:#ffffff;")
        self.CounterLabel.setObjectName("CounterLabel")
        self.counterBox.addWidget(self.CounterLabel)

        # ── Fila: Status ──
        self.horizontalLayoutWidget_3 = QtWidgets.QWidget(self.frame)
        self.horizontalLayoutWidget_3.setGeometry(QtCore.QRect(22, 334, 308, 26))
        self.horizontalLayoutWidget_3.setObjectName("horizontalLayoutWidget_3")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_3)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_3.setSpacing(5)

        self.label_7 = QtWidgets.QLabel(self.horizontalLayoutWidget_3)
        self.label_7.setMinimumSize(QtCore.QSize(55, 0))
        self.label_7.setMaximumSize(QtCore.QSize(66, 16777215))
        self.label_7.setFont(QtGui.QFont("Segoe UI", 11))
        self.label_7.setStyleSheet("color:#1DB954;")
        self.label_7.setObjectName("label_7")
        self.horizontalLayout_3.addWidget(self.label_7)

        self.statusMsg = QtWidgets.QLabel(self.horizontalLayoutWidget_3)
        self.statusMsg.setFont(QtGui.QFont("Segoe UI", 10))
        self.statusMsg.setText("")
        self.statusMsg.setStyleSheet("color:#b3b3b3;")
        self.statusMsg.setObjectName("statusMsg")
        self.horizontalLayout_3.addWidget(self.statusMsg)

        # ── Fila: Time ──
        self.horizontalLayoutWidget_time = QtWidgets.QWidget(self.frame)
        self.horizontalLayoutWidget_time.setGeometry(QtCore.QRect(22, 365, 308, 26))
        self.horizontalLayoutWidget_time.setObjectName("horizontalLayoutWidget_time")
        self.timeBox = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_time)
        self.timeBox.setContentsMargins(0, 0, 0, 0)
        self.timeBox.setSpacing(5)

        self.labelTime = QtWidgets.QLabel(self.horizontalLayoutWidget_time)
        self.labelTime.setMinimumSize(QtCore.QSize(55, 0))
        self.labelTime.setMaximumSize(QtCore.QSize(66, 16777215))
        self.labelTime.setFont(QtGui.QFont("Segoe UI", 11))
        self.labelTime.setStyleSheet("color:#1DB954;")
        self.labelTime.setObjectName("labelTime")
        self.timeBox.addWidget(self.labelTime)

        self.timeLabel = QtWidgets.QLabel(self.horizontalLayoutWidget_time)
        self.timeLabel.setFont(QtGui.QFont("Consolas", 10))
        self.timeLabel.setText("00:00:00")
        self.timeLabel.setStyleSheet("color:#ffffff;")
        self.timeLabel.setObjectName("timeLabel")
        self.timeBox.addWidget(self.timeLabel)

        # ── Progress bar principal ──
        self.SongDownloadprogress = QtWidgets.QProgressBar(self.frame)
        self.SongDownloadprogress.setGeometry(QtCore.QRect(22, 451, 308, 5))
        self.SongDownloadprogress.setProperty("value", 0)
        self.SongDownloadprogress.setTextVisible(False)
        self.SongDownloadprogress.setObjectName("SongDownloadprogress")

        # ── Botón LinkedIn ──
        self.Select_Home = QtWidgets.QPushButton(self.frame)
        self.Select_Home.setGeometry(QtCore.QRect(22, 462, 308, 28))
        self.Select_Home.setSizePolicy(
            QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
            )
        )
        self.Select_Home.setFont(QtGui.QFont("Segoe UI", 11))
        self.Select_Home.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.Select_Home.setObjectName("Select_Home")

        # ══════════════════════════════════════════════════════════════════
        # PANEL DERECHO  x=380, y=22 | abierto: 413 x 506
        # ══════════════════════════════════════════════════════════════════
        self.SONGINFORMATION = QtWidgets.QFrame(self.centralwidget)
        self.SONGINFORMATION.setGeometry(QtCore.QRect(380, 22, 0, 506))
        self.SONGINFORMATION.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.SONGINFORMATION.setFrameShadow(QtWidgets.QFrame.Raised)
        self.SONGINFORMATION.setObjectName("SONGINFORMATION")

        # Header
        self.label_3 = QtWidgets.QLabel(self.SONGINFORMATION)
        self.label_3.setGeometry(QtCore.QRect(10, 10, 260, 26))
        fsi = QtGui.QFont("Segoe UI", 13)
        fsi.setBold(True)
        self.label_3.setFont(fsi)
        self.label_3.setStyleSheet("color:#ffffff;")
        self.label_3.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.label_3.setObjectName("label_3")

        self.viewSwitchBtn = QtWidgets.QPushButton(self.SONGINFORMATION)
        self.viewSwitchBtn.setGeometry(QtCore.QRect(278, 8, 115, 26))
        self.viewSwitchBtn.setFont(QtGui.QFont("Segoe UI", 9))
        self.viewSwitchBtn.setObjectName("viewSwitchBtn")
        self.viewSwitchBtn.setCheckable(True)
        self.viewSwitchBtn.setChecked(False)

        self.panelPlaylistStats = QtWidgets.QLabel(self.SONGINFORMATION)
        self.panelPlaylistStats.setGeometry(QtCore.QRect(10, 38, 393, 18))
        self.panelPlaylistStats.setFont(QtGui.QFont("Segoe UI", 9))
        self.panelPlaylistStats.setStyleSheet("color:#535353;")
        self.panelPlaylistStats.setText("")
        self.panelPlaylistStats.setObjectName("panelPlaylistStats")

        sep_panel = QtWidgets.QFrame(self.SONGINFORMATION)
        sep_panel.setGeometry(QtCore.QRect(10, 60, 393, 1))
        sep_panel.setStyleSheet("background-color:#282828;")
        sep_panel.setFrameShape(QtWidgets.QFrame.HLine)

        # VISTA LISTA
        self.trackScrollArea = QtWidgets.QScrollArea(self.SONGINFORMATION)
        self.trackScrollArea.setGeometry(QtCore.QRect(10, 66, 393, 430))
        self.trackScrollArea.setObjectName("trackScrollArea")
        self.trackScrollArea.setWidgetResizable(True)
        self.trackScrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.trackScrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.trackListWidget = QtWidgets.QWidget()
        self.trackListWidget.setObjectName("trackListWidget")
        self.trackListWidget.setStyleSheet("background-color:transparent;")
        self.trackListLayout = QtWidgets.QVBoxLayout(self.trackListWidget)
        self.trackListLayout.setContentsMargins(0, 0, 6, 0)
        self.trackListLayout.setSpacing(4)
        self.trackListLayout.addStretch()
        self.trackScrollArea.setWidget(self.trackListWidget)

        # VISTA INDIVIDUAL
        self.individualView = QtWidgets.QWidget(self.SONGINFORMATION)
        self.individualView.setGeometry(QtCore.QRect(10, 66, 393, 430))
        self.individualView.setStyleSheet("background-color:transparent;")
        self.individualView.setObjectName("individualView")
        self.individualView.hide()

        self.CoverImg = QtWidgets.QLabel(self.individualView)
        self.CoverImg.setGeometry(QtCore.QRect(121, 20, 150, 150))
        self.CoverImg.setStyleSheet(
            "background-color:#282828; border-radius:10px; border:2px solid #383838;"
        )
        self.CoverImg.setText("")
        self.CoverImg.setScaledContents(True)
        self.CoverImg.setObjectName("CoverImg")

        _fl = QtGui.QFont("Segoe UI", 9)
        _fl.setBold(True)
        _fv = QtGui.QFont("Segoe UI", 11)

        def _lbl(y, txt):
            l = QtWidgets.QLabel(self.individualView)
            l.setGeometry(QtCore.QRect(10, y, 100, 26))
            l.setFont(_fl)
            l.setStyleSheet("color:#1DB954; letter-spacing:1px;")
            l.setText(txt)

        def _val(y, name):
            l = QtWidgets.QLabel(self.individualView)
            l.setGeometry(QtCore.QRect(115, y, 268, 26))
            l.setFont(_fv)
            l.setStyleSheet("color:#ffffff;")
            l.setWordWrap(True)
            l.setObjectName(name)
            setattr(self, name, l)

        _lbl(182, "SONG")
        _val(182, "SongName")
        _lbl(214, "ARTIST")
        _val(214, "ArtistNameText")
        _lbl(246, "ALBUM")
        _val(246, "AlbumText")
        _lbl(278, "RELEASED")
        _val(278, "YearText")

        self.SongDownloadprogressBar = QtWidgets.QProgressBar(self.individualView)
        self.SongDownloadprogressBar.setGeometry(QtCore.QRect(10, 320, 373, 5))
        self.SongDownloadprogressBar.setProperty("value", 0)
        self.SongDownloadprogressBar.setTextVisible(False)
        self.SongDownloadprogressBar.setObjectName("SongDownloadprogressBar")

        # Z-order
        self.SONGINFORMATION.raise_()
        self.frame.raise_()
        self.metaPanel.raise_()

        MainWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _t = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_t("MainWindow", "Sunnify"))
        self.title.setText(_t("MainWindow", "Sunnify"))
        self.DownloadBtn.setText(_t("MainWindow", "Download"))
        self.PlaylistLink.setPlaceholderText(_t("MainWindow", "Paste Spotify URL"))
        self.AlbumName.setText(_t("MainWindow", ""))
        self.author.setText(
            _t("MainWindow", "(Spotify Downloader) Created By Sunny Patel")
        )
        self.label_7.setText(_t("MainWindow", "Status :"))
        self.PlaylistMsg_2.setText(_t("MainWindow", "Spotify Song Name :"))
        self.Select_Home.setText(_t("MainWindow", "Follow me on Linkedin"))
        self.version.setText(_t("MainWindow", "V2.0.2"))
        self.label_10.setText(_t("MainWindow", "Counter :"))
        self.CounterLabel.setText(_t("MainWindow", "0"))
        self.showPreviewCheck.setText(_t("MainWindow", "Show Preview"))
        self.labelTime.setText(_t("MainWindow", "Time :"))
        self.label_3.setText(_t("MainWindow", "Playlist"))
        self.viewSwitchBtn.setText(_t("MainWindow", "☰ Lista"))
        self.metaDropBtn.setText(_t("MainWindow", "▾ Meta Tags"))
        self.qualityDropBtn.setText(_t("MainWindow", "▾ Quality: 320kbps"))
