"""Regenerate app.icns, app.ico, and app.png from the SVG source.

Pipeline:
  1. Render `assets/app_icon.svg` at 1024x1024 via Qt's QSvgRenderer.
  2. Downsample to the PNG sizes Apple + Microsoft icon containers expect.
  3. Pack them: iconutil for .icns on macOS, Pillow for .ico.

Run when the SVG changes:

    python scripts/build_icon.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PIL import Image
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_PATH = os.path.join(REPO, "assets", "app_icon.svg")
PNG_OUT = os.path.join(REPO, "app.png")
ICNS_OUT = os.path.join(REPO, "app.icns")
ICO_OUT = os.path.join(REPO, "app.ico")


def render_svg(size: int) -> Image.Image:
    """Render the SVG at the requested size and return a PIL RGBA image."""
    renderer = QSvgRenderer(SVG_PATH)
    if not renderer.isValid():
        raise RuntimeError(f"SVG at {SVG_PATH} failed to load")

    qimg = QImage(QSize(size, size), QImage.Format_ARGB32_Premultiplied)
    qimg.fill(0)
    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
    buf = qimg.bits()
    buf.setsize(qimg.byteCount())
    return Image.frombuffer(
        "RGBA", (qimg.width(), qimg.height()), bytes(buf), "raw", "RGBA", 0, 1
    ).copy()


def build_icns(master: Image.Image) -> None:
    if sys.platform != "darwin":
        print("skipping .icns (iconutil is macOS-only)")
        return
    tmp = os.path.join(REPO, "app.iconset")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    pairs = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for px, fname in pairs:
        master.resize((px, px), Image.LANCZOS).save(os.path.join(tmp, fname))
    subprocess.run(["iconutil", "-c", "icns", tmp, "-o", ICNS_OUT], check=True)
    shutil.rmtree(tmp)


def build_ico(master: Image.Image) -> None:
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(ICO_OUT, format="ICO", sizes=sizes)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

    print(f"rendering {SVG_PATH} -> 1024x1024 master")
    master = render_svg(1024)
    master.save(PNG_OUT)
    print(f"  wrote {PNG_OUT}")

    print("building app.icns...")
    build_icns(master)
    print(f"  wrote {ICNS_OUT}")

    print("building app.ico...")
    build_ico(master)
    print(f"  wrote {ICO_OUT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
