"""Sunnify main window UI built programmatically from the design system.

Styling and the visual language live in `theme.py`; this file is only
layout. The purple card identity is preserved; the card background itself
is solid so text stays readable regardless of what's behind the window.
"""

from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from theme import Color, Font, build_stylesheet, sp


class Ui_MainWindow:
    """Drop-in replacement for the old pyuic5-generated UI.

    Public widget attributes preserved (these are touched by MainWindow or
    tests): title, author, version, frame, centralwidget, PlaylistLink,
    DownloadBtn, Closed, SettingsBtn, Select_Home, MainSongName, AlbumName,
    SongName, ArtistNameText, AlbumText, YearText, CoverImg, CounterLabel,
    statusMsg, SongDownloadprogressBar, SongDownloadprogress,
    showPreviewCheck, AddMetaDataCheck, SONGINFORMATION.
    """

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(860, 580)
        MainWindow.setMinimumSize(760, 540)
        MainWindow.setStyleSheet(build_stylesheet())
        MainWindow.setWindowTitle("Sunnify")

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # Outer margin so the card's drop shadow has room to breathe and the
        # frameless window does not clip the rounded corners.
        outer = QtWidgets.QVBoxLayout(self.centralwidget)
        outer.setContentsMargins(sp.xl, sp.xl, sp.xl, sp.xl)
        outer.setSpacing(0)

        # Main card
        self.frame = QtWidgets.QFrame(self.centralwidget)
        self.frame.setObjectName("frame")
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setGraphicsEffect(
            QtWidgets.QGraphicsDropShadowEffect(blurRadius=48, xOffset=0, yOffset=12)
        )

        card = QtWidgets.QVBoxLayout(self.frame)
        card.setContentsMargins(sp.xxl, sp.xl, sp.xxl, sp.lg)
        card.setSpacing(sp.md)

        # Title bar
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(sp.sm)

        brand_col = QtWidgets.QVBoxLayout()
        brand_col.setSpacing(2)
        self.title = QtWidgets.QLabel("Sunnify", self.frame)
        self.title.setObjectName("title")
        self.author = QtWidgets.QLabel(
            "Spotify playlists, tracks, and albums as tagged MP3s.", self.frame
        )
        self.author.setObjectName("author")
        brand_col.addWidget(self.title)
        brand_col.addWidget(self.author)

        title_row.addLayout(brand_col, 1)

        self.Select_Home = _chrome_button("in", "Open author's LinkedIn", self.frame)
        self.Select_Home.setObjectName("Select_Home")

        self.SettingsBtn = _chrome_button("⚙", "Open settings (Cmd+,)", self.frame)
        self.SettingsBtn.setObjectName("SettingsBtn")

        self.Closed = _chrome_button("✕", "Quit Sunnify", self.frame)
        self.Closed.setObjectName("Closed")

        title_row.addWidget(self.Select_Home, 0, QtCore.Qt.AlignTop)
        title_row.addWidget(self.SettingsBtn, 0, QtCore.Qt.AlignTop)
        title_row.addWidget(self.Closed, 0, QtCore.Qt.AlignTop)

        card.addLayout(title_row)
        card.addSpacing(sp.sm)

        # URL input + primary CTA
        url_header = QtWidgets.QLabel("SPOTIFY LINK", self.frame)
        url_header.setObjectName("sectionHeader")
        card.addWidget(url_header)

        url_row = QtWidgets.QHBoxLayout()
        url_row.setSpacing(sp.sm)

        self.PlaylistLink = QtWidgets.QLineEdit(self.frame)
        self.PlaylistLink.setObjectName("PlaylistLink")
        self.PlaylistLink.setPlaceholderText(
            "Paste a Spotify playlist, track, or album link, or drop one here"
        )
        self.PlaylistLink.setClearButtonEnabled(True)
        self.PlaylistLink.setMinimumHeight(42)
        self.PlaylistLink.setToolTip(
            "Accepts open.spotify.com URLs, /intl-xx/ locale links, and spotify: URIs"
        )

        self.DownloadBtn = QtWidgets.QPushButton("Download", self.frame)
        self.DownloadBtn.setObjectName("DownloadBtn")
        self.DownloadBtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.DownloadBtn.setMinimumWidth(130)
        self.DownloadBtn.setMinimumHeight(42)
        self.DownloadBtn.setToolTip("Start downloading. Click again while running to stop.")

        url_row.addWidget(self.PlaylistLink, 1)
        url_row.addWidget(self.DownloadBtn, 0)
        card.addLayout(url_row)

        # Now playing
        card.addSpacing(sp.sm)
        now_header = QtWidgets.QLabel("NOW PLAYING", self.frame)
        now_header.setObjectName("sectionHeader")
        card.addWidget(now_header)

        self.AlbumName = QtWidgets.QLabel("", self.frame)
        self.AlbumName.setObjectName("AlbumName")
        self.AlbumName.setWordWrap(True)
        card.addWidget(self.AlbumName)

        self.MainSongName = QtWidgets.QLabel("", self.frame)
        self.MainSongName.setObjectName("MainSongName")
        self.MainSongName.setWordWrap(True)
        self.MainSongName.setMinimumHeight(40)
        card.addWidget(self.MainSongName)

        # Progress bar
        self.SongDownloadprogressBar = QtWidgets.QProgressBar(self.frame)
        self.SongDownloadprogressBar.setRange(0, 100)
        self.SongDownloadprogressBar.setValue(0)
        self.SongDownloadprogressBar.setTextVisible(False)
        self.SongDownloadprogressBar.setFixedHeight(6)
        card.addWidget(self.SongDownloadprogressBar)

        self.SongDownloadprogress = self.SongDownloadprogressBar

        # Counter + status row
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(sp.md)

        self.CounterLabel = QtWidgets.QLabel("Ready", self.frame)
        self.CounterLabel.setObjectName("CounterLabel")

        status_row.addWidget(self.CounterLabel)
        status_row.addStretch(1)

        status_tag = QtWidgets.QLabel("STATUS", self.frame)
        status_tag.setObjectName("statusLabel")
        status_row.addWidget(status_tag)

        self.statusMsg = QtWidgets.QLabel("", self.frame)
        self.statusMsg.setObjectName("statusMsg")
        self.statusMsg.setMinimumWidth(320)
        self.statusMsg.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        status_row.addWidget(self.statusMsg)

        card.addLayout(status_row)

        # Options + footer
        options_row = QtWidgets.QHBoxLayout()
        options_row.setSpacing(sp.lg)
        options_row.setContentsMargins(0, sp.sm, 0, 0)

        self.showPreviewCheck = QtWidgets.QCheckBox("Show preview panel", self.frame)
        self.showPreviewCheck.setToolTip(
            "Reveal a side panel with cover art, album, and release year during downloads"
        )

        self.AddMetaDataCheck = QtWidgets.QCheckBox("Embed ID3 metadata", self.frame)
        self.AddMetaDataCheck.setChecked(True)
        self.AddMetaDataCheck.setToolTip(
            "Write title, artist, album, year, track number, and cover art into each file"
        )

        options_row.addWidget(self.showPreviewCheck)
        options_row.addWidget(self.AddMetaDataCheck)
        options_row.addStretch(1)

        self.version = QtWidgets.QLabel("V2.1.0", self.frame)
        self.version.setObjectName("version")
        options_row.addWidget(self.version)

        card.addLayout(options_row)
        card.addStretch(1)

        # Preview panel (sliding)
        # Anchored to the window root so it can expand over the card without
        # re-laying out the primary interface.
        self.SONGINFORMATION = QtWidgets.QFrame(self.centralwidget)
        self.SONGINFORMATION.setObjectName("SONGINFORMATION")
        self.SONGINFORMATION.setGeometry(QtCore.QRect(0, 0, 0, 0))

        side = QtWidgets.QVBoxLayout(self.SONGINFORMATION)
        side.setContentsMargins(sp.md, sp.md, sp.md, sp.md)
        side.setSpacing(sp.sm)

        side_header = QtWidgets.QLabel("TRACK DETAILS", self.SONGINFORMATION)
        side_header.setObjectName("sectionHeader")
        side.addWidget(side_header)

        self.CoverImg = QtWidgets.QLabel(self.SONGINFORMATION)
        self.CoverImg.setObjectName("CoverImg")
        self.CoverImg.setFixedSize(220, 220)
        self.CoverImg.setAlignment(QtCore.Qt.AlignCenter)
        self.CoverImg.setScaledContents(True)
        side.addWidget(self.CoverImg, 0, QtCore.Qt.AlignHCenter)

        side.addSpacing(sp.sm)

        self.SongName = _add_info_row(side, "Title", self.SONGINFORMATION)
        self.SongName.setObjectName("SongName")

        self.ArtistNameText = _add_info_row(side, "Artist", self.SONGINFORMATION)
        self.ArtistNameText.setObjectName("ArtistNameText")

        self.AlbumText = _add_info_row(side, "Album", self.SONGINFORMATION)
        self.AlbumText.setObjectName("AlbumText")

        self.YearText = _add_info_row(side, "Year", self.SONGINFORMATION)
        self.YearText.setObjectName("YearText")

        side.addStretch(1)
        self.SONGINFORMATION.raise_()

        outer.addWidget(self.frame)

        MainWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Sunnify"))


# ---
# Helpers
# ---
def _chrome_button(label: str, tooltip: str, parent) -> QtWidgets.QPushButton:
    """Borderless square button used for window controls and the settings gear."""
    btn = QtWidgets.QPushButton(label, parent)
    btn.setFixedSize(30, 30)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.setFocusPolicy(QtCore.Qt.NoFocus)
    return btn


def _add_info_row(layout: QtWidgets.QVBoxLayout, label_text: str, parent) -> QtWidgets.QLabel:
    """Build a `LABEL | value` row for the preview panel and return the value label."""
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(sp.sm)

    label = QtWidgets.QLabel(label_text.upper(), parent)
    label.setStyleSheet(
        f"color: {Color.fg_muted}; font-size: {Font.caption}px; "
        f"font-weight: 700; letter-spacing: 1px;"
    )
    label.setFixedWidth(56)

    value = QtWidgets.QLabel("", parent)
    value.setStyleSheet(f"color: {Color.fg_primary}; font-size: {Font.small}px;")
    value.setWordWrap(True)

    row.addWidget(label, 0, QtCore.Qt.AlignTop)
    row.addWidget(value, 1)
    layout.addLayout(row)
    return value
