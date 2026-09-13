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

"""Verify exact-surface presentation callbacks cannot outlive their window."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete

from substitute.app.bootstrap.surface_presentation import run_after_surface_paint


def test_destroyed_surface_abandons_callback_queued_by_paint() -> None:
    """Destroying a painted window must not publish readiness for dead UI."""

    window = QWidget()
    callbacks: list[str] = []
    run_after_surface_paint(window, lambda: callbacks.append("presented"))

    QApplication.sendEvent(window, QEvent(QEvent.Type.Paint))
    delete(window)
    QApplication.processEvents()

    assert callbacks == []


def test_live_surface_runs_callback_exactly_once_after_paint() -> None:
    """Repeated paint events should publish one presentation receipt."""

    window = QWidget()
    callbacks: list[str] = []
    run_after_surface_paint(window, lambda: callbacks.append("presented"))

    QApplication.sendEvent(window, QEvent(QEvent.Type.Paint))
    QApplication.sendEvent(window, QEvent(QEvent.Type.Paint))
    QApplication.processEvents()

    assert callbacks == ["presented"]
    delete(window)
