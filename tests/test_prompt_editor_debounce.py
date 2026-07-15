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

"""Contract tests for prompt-editor Qt debounce primitives."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.async_work import (
    QtPromptEditorDebouncer,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "Qt debouncer timer tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_qt_debouncer_defers_callback_until_timer_delivery() -> None:
    """Debounced callbacks should run after the Qt timer fires."""

    app = _ensure_qapp()
    debouncer = QtPromptEditorDebouncer(interval_ms=0)
    calls: list[str] = []

    debouncer.request(lambda: calls.append("called"), reason="text_changed")

    assert calls == []
    assert debouncer.is_pending is True

    _process_events(app)

    assert calls == ["called"]
    assert debouncer.is_pending is False
    debouncer.deleteLater()
    _process_events(app)


def test_qt_debouncer_coalesces_to_latest_callback() -> None:
    """Repeated requests should keep only the latest callback."""

    app = _ensure_qapp()
    debouncer = QtPromptEditorDebouncer(interval_ms=0)
    calls: list[str] = []

    debouncer.request(lambda: calls.append("first"), reason="first")
    debouncer.request(lambda: calls.append("second"), reason="second")

    _process_events(app)

    assert calls == ["second"]
    debouncer.deleteLater()
    _process_events(app)


def test_qt_debouncer_flush_runs_pending_callback_immediately() -> None:
    """flush should deliver and clear the pending callback."""

    debouncer = QtPromptEditorDebouncer(interval_ms=1000)
    calls: list[str] = []

    debouncer.request(lambda: calls.append("flushed"), reason="queued")

    assert debouncer.flush(reason="manual_flush") is True
    assert calls == ["flushed"]
    assert debouncer.is_pending is False
    assert debouncer.flush(reason="manual_flush") is False
    debouncer.deleteLater()
    _process_events(_ensure_qapp())


def test_qt_debouncer_cancel_drops_pending_callback() -> None:
    """cancel should suppress pending work."""

    app = _ensure_qapp()
    debouncer = QtPromptEditorDebouncer(interval_ms=0)
    calls: list[str] = []

    debouncer.request(lambda: calls.append("cancelled"), reason="queued")

    assert debouncer.cancel(reason="source_replaced") is True
    assert debouncer.cancel(reason="source_replaced") is False

    _process_events(app)

    assert calls == []
    debouncer.deleteLater()
    _process_events(app)


def test_qt_debouncer_rejects_invalid_inputs() -> None:
    """Debounce intervals and reasons should be explicit."""

    with pytest.raises(ValueError, match="interval_ms"):
        QtPromptEditorDebouncer(interval_ms=-1)

    debouncer = QtPromptEditorDebouncer(interval_ms=0)
    with pytest.raises(ValueError, match="reason"):
        debouncer.request(lambda: None, reason=" ")
    with pytest.raises(ValueError, match="reason"):
        debouncer.flush(reason=" ")
    with pytest.raises(ValueError, match="reason"):
        debouncer.cancel(reason=" ")
    debouncer.deleteLater()
    _process_events(_ensure_qapp())


def test_qt_debouncer_ignores_requests_after_qt_destruction() -> None:
    """Deleted debouncers should drop late request callbacks."""

    app = _ensure_qapp()
    debouncer = QtPromptEditorDebouncer(interval_ms=0)
    calls: list[str] = []

    debouncer.deleteLater()
    _process_events(app)
    debouncer.request(lambda: calls.append("late"), reason="late_request")
    _process_events(app)

    assert calls == []


def _ensure_qapp() -> QApplication:
    """Return a QApplication for Qt timer tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, *, cycles: int = 5) -> None:
    """Flush queued timer and deferred-delete events."""

    for _ in range(cycles):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
