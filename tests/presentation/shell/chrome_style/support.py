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

"""Provide typed chrome-style lifecycle doubles."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor


class ThemeSignal:
    """Provide connection lifecycle behavior for theme callbacks."""

    def __init__(self) -> None:
        self.callbacks: list[Callable[[], None]] = []

    def connect(self, callback: Callable[[], None]) -> None:
        """Register one callback."""
        self.callbacks.append(callback)

    def disconnect(self, callback: Callable[[], None]) -> None:
        """Remove one registered callback."""
        if callback not in self.callbacks:
            raise TypeError("callback is not connected")
        self.callbacks.remove(callback)

    def emit(self) -> None:
        """Invoke a snapshot of registered callbacks."""
        for callback in list(self.callbacks):
            callback()


class ThemeConfig:
    """Expose the two QFluent theme refresh signals."""

    def __init__(self) -> None:
        self.themeChangedFinished = ThemeSignal()
        self.themeColorChanged = ThemeSignal()


class ThemeWidget:
    """Expose a Qt-like destroyed signal."""

    def __init__(self) -> None:
        self.destroyed = ThemeSignal()


class TitleBarButton:
    """Record qframelesswindow titlebar color assignments."""

    def __init__(self) -> None:
        self.normal_color: QColor | None = None
        self.hover_color: QColor | None = None
        self.pressed_color: QColor | None = None
        self.hover_background_color: QColor | None = None
        self.pressed_background_color: QColor | None = None

    def setNormalColor(self, color: QColor) -> None:
        """Record the normal icon color."""
        self.normal_color = QColor(color)

    def setHoverColor(self, color: QColor) -> None:
        """Record the hover icon color."""
        self.hover_color = QColor(color)

    def setPressedColor(self, color: QColor) -> None:
        """Record the pressed icon color."""
        self.pressed_color = QColor(color)

    def setHoverBackgroundColor(self, color: QColor) -> None:
        """Record the hover background color."""
        self.hover_background_color = QColor(color)

    def setPressedBackgroundColor(self, color: QColor) -> None:
        """Record the pressed background color."""
        self.pressed_background_color = QColor(color)


class TitleBar:
    """Expose the buttons consumed by shell titlebar theming."""

    def __init__(self) -> None:
        self.minBtn = TitleBarButton()
        self.maxBtn = TitleBarButton()
        self.closeBtn = TitleBarButton()
