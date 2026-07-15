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

"""Tests for shell dock widget behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDockWidget, QWidget

from substitute.presentation.shell.dock_widgets import (
    ClosableDockWidget,
    handle_dock_closed,
)


def test_closable_dock_widget_hides_and_emits_closed_signal() -> None:
    """Hide the dock and notify listeners while ignoring destruction close events."""

    _application()
    dock_widget = ClosableDockWidget()
    closed_calls: list[bool] = []
    dock_widget.closed.connect(lambda: closed_calls.append(True))
    dock_widget.show()
    close_event = QCloseEvent()

    dock_widget.closeEvent(close_event)

    assert closed_calls == [True]
    assert close_event.isAccepted() is False
    assert dock_widget.isVisible() is False


def test_handle_dock_closed_redocks_floating_dock() -> None:
    """Floating dock closes should re-dock and show instead of disappearing."""

    shell = _Shell()
    dock_widget = _DockWidget(floating=True)
    content_widget = cast(QWidget, object())

    handle_dock_closed(shell, cast(QDockWidget, dock_widget), content_widget)

    assert dock_widget.floating is False
    assert dock_widget.show_calls == 1
    assert shell.added_docks == [(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)]


def test_handle_dock_closed_shows_docked_widget_without_readding() -> None:
    """Docked widgets should be shown without another addDockWidget call."""

    shell = _Shell()
    dock_widget = _DockWidget(floating=False)
    content_widget = cast(QWidget, object())

    handle_dock_closed(shell, cast(QDockWidget, dock_widget), content_widget)

    assert dock_widget.floating is False
    assert dock_widget.show_calls == 1
    assert shell.added_docks == []


class _Shell:
    """Record dock insertion calls."""

    def __init__(self) -> None:
        """Initialize empty dock insertion state."""

        self.added_docks: list[tuple[Qt.DockWidgetArea, object]] = []

    def addDockWidget(self, area: Qt.DockWidgetArea, dock_widget: object) -> None:
        """Record one dock insertion."""

        self.added_docks.append((area, dock_widget))


class _DockWidget:
    """Record dock floating and visibility operations."""

    def __init__(self, *, floating: bool) -> None:
        """Initialize dock state."""

        self.floating = floating
        self.show_calls = 0

    def isFloating(self) -> bool:
        """Return whether this fake dock is floating."""

        return self.floating

    def setFloating(self, floating: bool) -> None:
        """Record floating state."""

        self.floating = floating

    def show(self) -> None:
        """Record one show request."""

        self.show_calls += 1


def _application() -> QApplication:
    """Return the active QApplication instance required for widget construction."""

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return cast(QApplication, application)
