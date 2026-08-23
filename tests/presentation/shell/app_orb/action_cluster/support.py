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

"""Provide app-orb action-cluster event probes."""

from __future__ import annotations


from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]


class _MenuProbe:
    """Record menu execution calls from the custom override button."""

    def __init__(self, *, open_on_exec: bool = True) -> None:
        """Initialize the empty execution call list."""

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


class _WidgetMenuProbe(QWidget):
    """Record menu calls while receiving real Qt mouse events."""

    def __init__(self) -> None:
        """Initialize widget-backed menu probe state."""

        super().__init__()
        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.hide_calls = 0

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record one menu execution and show the widget."""

        self.exec_calls.append((args, kwargs))
        self.show()

    def hide(self) -> None:
        """Record one hide and delegate to QWidget."""

        self.hide_calls += 1
        super().hide()


class _QFluentMenuProbe(_MenuProbe):
    """Record QFluent-style menu sizing and positioning calls."""

    def __init__(self, *, left_margin: int) -> None:
        """Initialize a visible QFluent-shaped menu probe."""

        super().__init__()
        self.left_margin = left_margin
        self.view = _QFluentMenuViewProbe()

    def layout(self) -> object:
        """Return a layout probe exposing content margins."""

        return _LayoutProbe(self.left_margin)

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


class _LayoutProbe:
    """Expose QFluent-style layout content margins."""

    def __init__(self, left_margin: int) -> None:
        """Store the left margin returned by the margin probe."""

        self._left_margin = left_margin

    def contentsMargins(self) -> object:
        """Return a margin probe."""

        return _MarginProbe(self._left_margin)


class _MarginProbe:
    """Expose the left content margin used by QFluent menu placement."""

    def __init__(self, left_margin: int) -> None:
        """Store the left margin."""

        self._left_margin = left_margin

    def left(self) -> int:
        """Return the stored left margin."""

        return self._left_margin


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
    _send_left_press(button, global_center)
    _send_left_release(button, global_center)


def _send_left_press(widget: QWidget, global_position: QPoint) -> None:
    """Send one left-button press to ``widget`` at ``global_position``."""

    local_position = widget.mapFromGlobal(global_position)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(local_position),
        QPointF(global_position),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, press)


def _send_left_release(
    widget: QWidget,
    global_position: QPoint | None = None,
) -> None:
    """Send a left-button release to ``widget``."""

    if global_position is None:
        global_position = widget.mapToGlobal(widget.rect().center())
    local_position = widget.mapFromGlobal(global_position)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(local_position),
        QPointF(global_position),
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

    import substitute.presentation.shell.menu_button_controller as controller_module

    monkeypatch.setattr(
        controller_module,
        "left_mouse_button_is_down",
        lambda: True,
    )
    menu.aboutToHide.emit()
