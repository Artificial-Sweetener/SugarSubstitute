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

"""Provide app-orb menu renderer and event probes."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]


class _RendererProbe:
    """Record app-orb render state requests."""

    def __init__(self) -> None:
        """Initialize the empty render call list."""

        self.calls: list[dict[str, object]] = []

    def app_icon(self) -> object:
        """Return a stable icon identity for tests that inspect the renderer."""

        return object()

    def clear_cache(self) -> None:
        """Accept cache clearing without side effects."""

    def render(self, size: object, **kwargs: object) -> QPixmap:
        """Record render state and return a transparent pixmap."""

        self.calls.append(kwargs)
        if not hasattr(size, "width") or not hasattr(size, "height"):
            pixmap = QPixmap(1, 1)
            pixmap.fill(Qt.GlobalColor.transparent)
            return pixmap
        typed_size = cast(Any, size)
        pixmap = QPixmap(
            max(1, int(typed_size.width())),
            max(1, int(typed_size.height())),
        )
        pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap


class _MenuProbe:
    """Record app-orb menu execution and hide calls."""

    def __init__(self, *, open_on_exec: bool = True) -> None:
        """Initialize fake menu state."""

        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.hide_calls = 0
        self.visible = False
        self.isHideBySystem = False
        self._open_on_exec = open_on_exec
        self.aboutToHide = _SignalProbe()
        self.closedSignal = _SignalProbe()

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record one menu execution call."""

        self.exec_calls.append((args, kwargs))
        self.visible = self._open_on_exec

    def hide(self) -> None:
        """Record one menu hide call."""

        self.hide_calls += 1
        self.visible = False

    def isVisible(self) -> bool:
        """Return whether the probe menu is considered visible."""

        return self.visible


class _QFluentMenuProbe(_MenuProbe):
    """Record QFluent-style app-orb menu sizing and positioning calls."""

    def __init__(self) -> None:
        """Initialize a QFluent-shaped menu probe."""

        super().__init__()
        self.view = _QFluentMenuViewProbe()

    def adjustSize(self) -> None:
        """Accept menu-level size adjustment."""


class _QFluentMenuViewProbe:
    """Record QFluent menu-view sizing calls."""

    def __init__(self) -> None:
        """Initialize empty sizing call storage."""

        self.minimum_widths: list[int] = []
        self.adjust_calls: list[tuple[object, ...]] = []

    def setMinimumWidth(self, width: int) -> None:
        """Record the requested minimum menu width."""

        self.minimum_widths.append(width)

    def adjustSize(self, *args: object) -> None:
        """Record QFluent view adjustment calls."""

        self.adjust_calls.append(args)

    def heightForAnimation(
        self,
        _position: QPoint,
        animation_type: MenuAnimationType,
    ) -> int:
        """Prefer drop-down animation for deterministic placement tests."""

        return 100 if animation_type is MenuAnimationType.DROP_DOWN else 20


class _SignalProbe:
    """Store and emit callbacks for fake Qt signals."""

    def __init__(self) -> None:
        """Initialize the callback list."""

        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self._callbacks.append(callback)

    def emit(self) -> None:
        """Invoke all connected callbacks."""

        for callback in self._callbacks:
            if callable(callback):
                callback()


def _send_left_click(button: QAbstractButton) -> None:
    """Send a real press/release sequence to ``button``."""

    center = button.rect().center()
    global_center = button.mapToGlobal(center)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(center),
        QPointF(global_center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(center),
        QPointF(global_center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(button, press)
    QApplication.sendEvent(button, release)


def _send_left_release(widget: QWidget) -> None:
    """Send a left-button release to ``widget``."""

    center = widget.rect().center()
    global_center = widget.mapToGlobal(center)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(center),
        QPointF(global_center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, release)


def _emit_about_to_hide_during_left_press(
    monkeypatch: pytest.MonkeyPatch,
    menu: _MenuProbe,
) -> None:
    """Emit menu closure while the application reports a left-button press."""

    import substitute.presentation.widgets.menu_button_controller as controller_module

    monkeypatch.setattr(
        controller_module,
        "left_mouse_button_is_down",
        lambda: True,
    )
    menu.aboutToHide.emit()
