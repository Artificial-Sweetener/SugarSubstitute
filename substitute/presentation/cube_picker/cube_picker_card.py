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

"""Render selectable cube cards for the cube picker drawer."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QEnterEvent, QIcon, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QSizePolicy,
    QWidget,
)

from substitute.application.cubes import CubePickerEntry
from substitute.presentation.cubes.cube_card_visual import (
    CubeCardVisual,
    CubeCardVisualState,
)
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh

CUBE_PICKER_CARD_WIDTH = CUBE_ITEM_EXPANDED_WIDTH
CUBE_PICKER_CARD_HEIGHT = CUBE_ITEM_HEIGHT


class CubePickerCard(QFrame):
    """Display one selectable cube picker result."""

    activated = Signal(str)
    drag_started = Signal(str, object)
    drag_moved = Signal(object)
    drag_finished = Signal(object)

    def __init__(
        self,
        entry: CubePickerEntry,
        *,
        icon: QIcon,
        parent: QWidget | None = None,
    ) -> None:
        """Create a picker card for one cube entry."""

        super().__init__(parent)
        self._entry = entry
        self._icon = icon
        self._selected = False
        self._hovered = False
        self._pressed = False
        self._press_pos: QPoint | None = None
        self._dragging = False
        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.setObjectName("cubePickerCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(entry.display_name)
        self.setAccessibleDescription(entry.secondary_text)
        self.setFixedSize(CUBE_PICKER_CARD_WIDTH, CUBE_PICKER_CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        connect_theme_refresh(self, self._apply_theme_styles)

    @property
    def cube_id(self) -> str:
        """Return the canonical cube id represented by this card."""

        return self._entry.cube_id

    def set_selected(self, selected: bool) -> None:
        """Set selected visual state."""

        if self._selected == selected:
            return
        self._selected = selected
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Record a possible click or drag start."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._press_pos = event.position().toPoint()
            self._dragging = False
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit drag movement after the pointer crosses the drag threshold."""

        if self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        current_pos = event.position().toPoint()
        if not self._dragging:
            distance = (current_pos - self._press_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                return
            self._dragging = True
            self.drag_started.emit(self._entry.cube_id, _event_global_pos(event))
        self.drag_moved.emit(_event_global_pos(event))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Activate clicks and finish active drags."""

        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            if self._dragging:
                self.drag_finished.emit(_event_global_pos(event))
            else:
                self.activated.emit(self._entry.cube_id)
            self._pressed = False
            self._press_pos = None
            self._dragging = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state for the shared cube-card visual."""

        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover and pressed state after the pointer leaves."""

        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Activate the card when Enter or Return is pressed."""

        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.activated.emit(self._entry.cube_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Apply focus-selected visual state."""

        self.set_selected(True)
        super().focusInEvent(event)

    def paintEvent(self, event: object) -> None:
        """Paint the picker card with the shared cube-card visual."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        CubeCardVisual.draw(
            painter,
            rect=self.rect(),
            font=self.font(),
            state=self._visual_state(),
        )

    def _visual_state(self) -> CubeCardVisualState:
        """Return the stable framed visual state for this library card."""

        return CubeCardVisualState(
            primary_text=self._entry.display_name,
            secondary_text=self._entry.secondary_text,
            icon=self._icon,
            selected=True,
            hovered=self._hovered,
            pressed=self._pressed,
            enabled=self.isEnabled(),
            close_visible=False,
            compact_progress=0.0,
            selected_fill_color=self._selected_fill_color,
        )

    def _apply_theme_styles(self) -> None:
        """Refresh selected fill so picker cards match live cube-stack cards."""

        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.update()


def _event_global_pos(event: QMouseEvent) -> QPoint:
    """Return mouse global position across PySide event variants."""

    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        return cast(QPoint, global_position().toPoint())
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return cast(QPoint, global_pos())
    return QPoint()


__all__ = ["CUBE_PICKER_CARD_HEIGHT", "CUBE_PICKER_CARD_WIDTH", "CubePickerCard"]
