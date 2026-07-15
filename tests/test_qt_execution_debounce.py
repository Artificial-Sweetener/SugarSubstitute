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

"""Tests for the Qt execution debouncer."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import cast

from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.qt.execution import QtDebouncer


def test_qt_debouncer_runs_only_latest_callback() -> None:
    """Repeated requests should coalesce to the latest callback."""

    app = _ensure_qapp()
    debouncer = QtDebouncer(interval_ms=0)
    delivered: list[str] = []

    debouncer.request(lambda: delivered.append("first"), reason="first")
    debouncer.request(lambda: delivered.append("second"), reason="second")

    assert debouncer.is_pending
    assert _process_until(app, lambda: delivered == ["second"])
    assert not debouncer.is_pending


def test_qt_debouncer_flush_and_cancel_manage_pending_work() -> None:
    """Flush should run pending work and cancel should drop it."""

    debouncer = QtDebouncer(interval_ms=1000)
    delivered: list[str] = []

    debouncer.request(lambda: delivered.append("flushed"), reason="flush_me")

    assert debouncer.flush(reason="test_flush")
    assert delivered == ["flushed"]
    assert not debouncer.flush(reason="empty_flush")

    debouncer.request(lambda: delivered.append("cancelled"), reason="cancel_me")

    assert debouncer.cancel(reason="test_cancel")
    assert delivered == ["flushed"]
    assert not debouncer.is_pending


def test_qt_debouncer_rejects_invalid_inputs() -> None:
    """Debounce configuration and reasons should be validated."""

    with pytest.raises(ValueError, match="interval_ms"):
        QtDebouncer(interval_ms=-1)
    debouncer = QtDebouncer(interval_ms=0)
    with pytest.raises(ValueError, match="reason"):
        debouncer.request(lambda: None, reason=" ")


def _ensure_qapp() -> QApplication:
    """Return a Qt application for timer tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_until(
    app: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 1.0,
) -> bool:
    """Process Qt events until a predicate is true or timeout expires."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        app.processEvents()
        time.sleep(0.005)
    return predicate()
