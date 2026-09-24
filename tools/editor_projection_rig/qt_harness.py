#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Create hidden Qt harness surfaces for editor projection replay."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QWidget

_SETTLE_TURN_TIMEOUT_MS = 20


def ensure_qapplication() -> QApplication:
    """Return a QApplication configured for hidden/offscreen execution."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def create_hidden_host(*, show_window: bool = False) -> QWidget:
    """Create a realistically sized top-level host for replay checks."""

    ensure_qapplication()
    host = QWidget()
    host.resize(1440, 1000)
    if show_window:
        host.show()
    return host


def drain_until(predicate: Callable[[], bool], *, max_turns: int) -> None:
    """Run a bounded Qt event loop until the supplied condition is observable."""

    app = QApplication.instance()
    if app is None or predicate():
        return
    loop = QEventLoop()
    completion_poll = QTimer()
    completion_poll.setInterval(1)
    completion_poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    completion_poll.start()
    timeout.start(max(1, max_turns) * _SETTLE_TURN_TIMEOUT_MS)
    loop.exec()
    completion_poll.stop()
    timeout.stop()
    if not predicate():
        raise TimeoutError("Production editor projection did not complete in the rig.")


def drain_qt_events(turns: int) -> None:
    """Process a fixed number of Qt events, including deferred deletion."""

    app = QApplication.instance()
    if app is None:
        return
    for _turn in range(turns):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def widget_count() -> int:
    """Return the current QApplication widget count."""

    app = QApplication.instance()
    if app is None:
        return 0
    return len(cast(QApplication, app).allWidgets())
