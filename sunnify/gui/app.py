"""Desktop app start-up: logging, signals, scaling, language, then the window."""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import sys

from sunnify import config, i18n
from sunnify.gui import scale
from sunnify.logs import log, setup_logging


def run(argv: list[str] | None = None) -> int:
    # Logging must never stop the app from launching (e.g. a locked-down or
    # read-only log dir). Failure here just means no log file this session.
    with contextlib.suppress(Exception):
        setup_logging()

    # sigint/sigterm: log WHICH signal killed us, then re-raise under
    # SIG_DFL. A default-action signal skips atexit and every hook (why
    # signal deaths never left a log line); this keeps instant-kill
    # semantics with no event-loop dependence, plus one forensic line.
    def _fatal_signal(sig, _frame):
        with contextlib.suppress(Exception):
            log.info("terminated by signal %s (ctrl+c or external)", signal.Signals(sig).name)
            logging.shutdown()
        signal.signal(sig, signal.SIG_DFL)
        os.kill(os.getpid(), sig)

    with contextlib.suppress(Exception):
        signal.signal(signal.SIGINT, _fatal_signal)
        signal.signal(signal.SIGTERM, _fatal_signal)

    cfg = config.load_config()
    # the saved window size rides qt's scale factor, which must be set before QApplication
    with contextlib.suppress(Exception):
        scale.apply_ui_scale(cfg.get("ui_scale", "100"))

    from PyQt6.QtCore import QLocale, Qt, QTimer
    from PyQt6.QtWidgets import QApplication

    # fixed-pixel ui overflows on fractional dpi without this (#64); PassThrough avoids
    # rounding 150%->100%. must precede QApplication. ref: doc.qt.io/qt-6/highdpi.html
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception as exc:  # log so a scaling failure (rendering bugs) is diagnosable
        log.debug("high-dpi setup skipped: %s", exc)
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("Sunnify")
    app.setOrganizationName("Sunnify")
    lang = i18n.set_language(i18n.resolve(cfg.get("language"), QLocale.system().name()))
    log.info("language=%s theme=%s", lang, cfg.get("theme"))

    # wake python every 200ms during exec() so a pending signal's handler runs
    # promptly (qt's c++ loop otherwise defers python signals until a qt slot)
    signal_waker = QTimer()
    signal_waker.start(200)
    signal_waker.timeout.connect(lambda: None)

    from sunnify.gui.window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()
