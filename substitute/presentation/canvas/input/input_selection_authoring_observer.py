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

"""Observe the pointer lifetime of Input pixel-selection authoring."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas

_SELECTION_OPERATIONS = frozenset(
    {
        CuteCanvas.CONTROL_MODE_SELECT_RECTANGLE,
        CuteCanvas.CONTROL_MODE_SELECT_ELLIPSE,
        CuteCanvas.CONTROL_MODE_SELECT_LASSO,
    }
)


class InputSelectionAuthoringObserver(QObject):
    """Publish whether a selection tool currently owns a pointer gesture."""

    activeChanged = Signal(bool)

    def __init__(
        self,
        *,
        canvas: QWidget,
        operation_provider: Callable[[], str],
        parent: QObject,
    ) -> None:
        """Observe one canvas without participating in selection state."""
        super().__init__(parent)
        self._canvas = canvas
        self._operation_provider = operation_provider
        self._active = False
        canvas.installEventFilter(self)

    @property
    def active(self) -> bool:
        """Return whether selection authoring currently owns the pointer."""
        return self._active

    def close(self) -> None:
        """Release canvas observation and clear transient state."""
        self._canvas.removeEventFilter(self)
        self._set_active(False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Observe selection pointer boundaries without consuming input."""
        if watched is not self._canvas:
            return False
        if event.type() is QEvent.Type.MouseButtonPress:
            if (
                isinstance(event, QMouseEvent)
                and event.button() is Qt.MouseButton.LeftButton
                and self._operation_provider() in _SELECTION_OPERATIONS
            ):
                self._set_active(True)
        elif event.type() is QEvent.Type.MouseButtonRelease and self._active:
            QTimer.singleShot(0, self._finish_gesture)
        elif event.type() in {QEvent.Type.Hide, QEvent.Type.FocusOut}:
            self._set_active(False)
        return False

    def _finish_gesture(self) -> None:
        """Publish settlement after the canvas processes the release event."""
        self._set_active(False)

    def _set_active(self, active: bool) -> None:
        """Replace transient gesture state exactly once."""
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        self.activeChanged.emit(active)


__all__ = ["InputSelectionAuthoringObserver"]
