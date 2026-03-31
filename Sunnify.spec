# -*- mode: python ; coding: utf-8 -*-
"""
Cross-platform PyInstaller spec for Sunnify.

Build commands:
  macOS:   pyinstaller Sunnify.spec
  Windows: pyinstaller Sunnify.spec
  Linux:   pyinstaller Sunnify.spec

Output:
  macOS:   dist/Sunnify.app
  Windows: dist/Sunnify.exe
  Linux:   dist/Sunnify
"""

import sys
import platform

block_cipher = None

# Determine platform-specific settings
is_mac = sys.platform == 'darwin'
is_windows = sys.platform == 'win32'

# Windows version info (shows in Properties > Details)
win_version_info = None
if is_windows:
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct,
    )
    win_version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=(2, 0, 3, 0),
            prodvers=(2, 0, 3, 0),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,       # VOS_NT_WINDOWS32
            fileType=0x1,     # VFT_APP
            subtype=0x0,
        ),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', 'Sunny Jayendra Patel'),
                    StringStruct('FileDescription', 'Sunnify - Spotify Playlist Downloader'),
                    StringStruct('FileVersion', '2.0.3.0'),
                    StringStruct('InternalName', 'Sunnify'),
                    StringStruct('LegalCopyright', 'Copyright (C) 2026 Sunny Jayendra Patel'),
                    StringStruct('OriginalFilename', 'Sunnify.exe'),
                    StringStruct('ProductName', 'Sunnify'),
                    StringStruct('ProductVersion', '2.0.3.0'),
                ]),
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 0x04B0])]),
        ],
    )

# Icon files
if is_mac:
    icon_file = 'app.icns'
elif is_windows:
    icon_file = 'app.ico'
else:
    icon_file = None  # Linux doesn't use icons in the same way

# FFmpeg binaries (downloaded by CI before build)
import os
ffmpeg_dir = 'ffmpeg'
ffmpeg_datas = []
if os.path.exists(ffmpeg_dir):
    ffmpeg_datas = [(ffmpeg_dir, 'ffmpeg')]

a = Analysis(
    ['Spotify_Downloader.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('spotifydown_api.py', '.'),
        ('Template.py', '.'),
    ] + ffmpeg_datas,
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'mutagen',
        'mutagen.id3',
        'mutagen.easyid3',
        'yt_dlp',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_mac:
    # macOS: Create .app bundle
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Sunnify',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # No terminal window on macOS
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Sunnify',
    )
    app = BUNDLE(
        coll,
        name='Sunnify.app',
        icon=icon_file,
        bundle_identifier='com.sunnypatel.sunnify',
        info_plist={
            'CFBundleName': 'Sunnify',
            'CFBundleDisplayName': 'Sunnify',
            'CFBundleGetInfoString': 'Spotify Playlist Downloader',
            'CFBundleIdentifier': 'com.sunnypatel.sunnify',
            'CFBundleVersion': '2.0.3',
            'CFBundleShortVersionString': '2.0.3',
            'NSHumanReadableCopyright': '© 2026 Sunny Jayendra Patel',
            'NSHighResolutionCapable': True,
        },
    )
else:
    # Windows/Linux: Create single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='Sunnify',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # GUI mode, no terminal window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file if icon_file else None,
        version=win_version_info,
    )
