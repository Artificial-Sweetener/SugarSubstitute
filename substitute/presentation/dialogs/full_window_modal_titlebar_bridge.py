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

"""Permit native titlebar movement through a blocking modal wash."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from qframelesswindow.titlebar import startSystemMove  # type: ignore[import-untyped]


class FullWindowModalTitleBarBridge(QObject):
    """Block titlebar controls while forwarding valid native drag gestures."""

    def __init__(
        self,
        *,
        owner: QWidget,
        wash: QWidget,
        parent: QObject,
    ) -> None:
        """Store the covered window and pointer-owning wash surface."""

        super().__init__(parent)
        self._owner = owner
        self._wash = wash
        self._press_origin: QPoint | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Consume titlebar input and start only qualified window drags."""

        if watched is not self._wash or not isinstance(event, QMouseEvent):
            return bool(super().eventFilter(watched, event))

        event_type = event.type()
        position = event.position().toPoint()
        over_titlebar = self._is_titlebar_position(position)

        if event_type == QEvent.Type.MouseButtonPress:
            if not over_titlebar:
                return False
            self._press_origin = (
                position
                if event.button() == Qt.MouseButton.LeftButton
                and self._is_draggable_titlebar_position(position)
                else None
            )
            return True

        if event_type == QEvent.Type.MouseMove:
            press_origin = self._press_origin
            if press_origin is None:
                return over_titlebar
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self._press_origin = None
                return True
            if (
                position - press_origin
            ).manhattanLength() >= QApplication.startDragDistance():
                self._press_origin = None
                startSystemMove(self._owner, event.globalPosition().toPoint())
            return True

        if event_type == QEvent.Type.MouseButtonRelease:
            had_titlebar_press = self._press_origin is not None
            self._press_origin = None
            return over_titlebar or had_titlebar_press

        if event_type == QEvent.Type.MouseButtonDblClick:
            self._press_origin = None
            return over_titlebar

        return False

    def _is_titlebar_position(self, wash_position: QPoint) -> bool:
        """Return whether a wash point covers the owner's titlebar geometry."""

        mapped = self._map_to_titlebar(wash_position)
        return mapped is not None

    def _is_draggable_titlebar_position(self, wash_position: QPoint) -> bool:
        """Return whether qframeless accepts the covered point as draggable."""

        mapped = self._map_to_titlebar(wash_position)
        if mapped is None:
            return False
        titlebar, position = mapped
        can_drag = getattr(titlebar, "canDrag", None)
        return bool(can_drag(position)) if callable(can_drag) else True

    def _map_to_titlebar(self, wash_position: QPoint) -> tuple[QWidget, QPoint] | None:
        """Map one wash-local point into the owner's titlebar when available."""

        titlebar = getattr(self._owner, "titleBar", None)
        if not isinstance(titlebar, QWidget):
            return None
        global_position = self._wash.mapToGlobal(wash_position)
        titlebar_position = titlebar.mapFromGlobal(global_position)
        if not titlebar.rect().contains(titlebar_position):
            return None
        return titlebar, titlebar_position


__all__ = ["FullWindowModalTitleBarBridge"]
