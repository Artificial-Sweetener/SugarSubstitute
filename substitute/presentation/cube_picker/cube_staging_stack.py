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

"""Temporary cube stack draft visualization for the staging drawer."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QEnterEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets.common.icon import FluentIcon  # type: ignore[import-untyped]

from substitute.application.cubes import (
    CubeStackAliasPlan,
    CubeStackDraftEntry,
    plan_cube_stack_aliases,
)
from substitute.presentation.cubes.cube_card_visual import (
    CubeCardVisual,
    CubeCardVisualState,
)
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_BUTTON_SIZE,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
    CUBE_STACK_EDGE_INSET,
    CUBE_STACK_EXPANDED_WIDTH,
    CUBE_STACK_ITEM_SPACING,
)
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableTabToolButton,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh


_ANIMATION_MS = 115


class CubeDraftStackCard(QFrame):
    """Render one draft cube with stack-like proportions."""

    drag_started = Signal(str, object)
    drag_moved = Signal(object)
    drag_finished = Signal(object)
    remove_requested = Signal(str)

    def __init__(
        self,
        *,
        entry: CubeStackDraftEntry,
        planned_alias: str,
        icon: QIcon,
        parent: QWidget | None = None,
    ) -> None:
        """Create a staged cube card."""

        super().__init__(parent)
        self.entry = entry
        self._planned_alias = planned_alias
        self._icon = icon
        self._press_pos: QPoint | None = None
        self._dragging = False
        self._hovered = False
        self._pressed = False
        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.setObjectName("cubeStagingCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(planned_alias)
        self.setAccessibleDescription(entry.secondary_text)
        self.setFixedSize(CUBE_ITEM_EXPANDED_WIDTH, CUBE_ITEM_HEIGHT)
        self.closeButton = ReorderableTabToolButton(FluentIcon.CLOSE, self)
        self.closeButton.setFixedSize(
            CUBE_ITEM_CLOSE_BUTTON_SIZE,
            CUBE_ITEM_CLOSE_BUTTON_SIZE,
        )
        self.closeButton.setIconSize(QSize(10, 10))
        self.closeButton.setCursor(Qt.CursorShape.ArrowCursor)
        self.closeButton.setToolTip("Remove")
        self.closeButton.setAccessibleName(f"Remove {planned_alias}")
        self.closeButton.clicked.connect(
            lambda: self.remove_requested.emit(self.entry.draft_id)
        )
        self._position_close_button()
        self.closeButton.raise_()
        connect_theme_refresh(self, self._apply_theme_styles)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Record a possible staged-card drag."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._press_pos = event.position().toPoint()
            self._dragging = False
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit drag lifecycle signals after the drag threshold."""

        if self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        current_pos = event.position().toPoint()
        if not self._dragging:
            distance = (current_pos - self._press_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                return
            self._dragging = True
            self.drag_started.emit(self.entry.draft_id, _event_global_pos(event))
        self.drag_moved.emit(_event_global_pos(event))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish an active staged drag."""

        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            if self._dragging:
                self.drag_finished.emit(_event_global_pos(event))
            self._pressed = False
            self._press_pos = None
            self._dragging = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state for the shared card visual."""

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
        """Remove focused staged cards with Delete or Backspace."""

        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.remove_requested.emit(self.entry.draft_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the close button aligned with the real cube stack."""

        super().resizeEvent(event)
        self._position_close_button()
        self.closeButton.raise_()

    def paintEvent(self, event: object) -> None:
        """Paint the staged card with the shared selected cube-card visual."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        CubeCardVisual.draw(
            painter,
            rect=self.rect(),
            font=self.font(),
            state=self._visual_state(),
        )

    def _position_close_button(self) -> None:
        """Position the close button inside the reserved action column."""

        self.closeButton.move(
            self._close_button_x(self.width(), self.closeButton.width()),
            int(self.height() / 2 - self.closeButton.height() / 2),
        )

    @staticmethod
    def _close_button_x(item_width: int, button_width: int) -> int:
        """Return close-button X centered between text cutoff and card edge."""

        return CubeCardVisual.close_button_x(item_width, button_width)

    def _visual_state(self) -> CubeCardVisualState:
        """Return the shared visual state for this staged draft card."""

        return CubeCardVisualState(
            primary_text=self._planned_alias,
            secondary_text=self.entry.secondary_text,
            icon=self._icon,
            selected=True,
            hovered=self._hovered or self.hasFocus(),
            pressed=self._pressed,
            enabled=self.isEnabled(),
            close_visible=self.closeButton.isVisible(),
            compact_progress=0.0,
            selected_fill_color=self._selected_fill_color,
        )

    def _apply_theme_styles(self) -> None:
        """Refresh selected fill so staged cards match live cube-stack cards."""

        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.update()


class CubeDraftStack(QWidget):
    """Render and manage the temporary draft stack."""

    staged_drag_started = Signal(str, object)
    staged_drag_moved = Signal(object)
    staged_drag_finished = Signal(object)
    remove_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Create the staged stack surface."""

        super().__init__(parent)
        self._entries: list[CubeStackDraftEntry] = []
        self._icons: dict[str, QIcon] = {}
        self._alias_plan = plan_cube_stack_aliases(())
        self._placeholder_index: int | None = None
        self._placeholder = CubePlaceholderCard(
            self,
            plus_visible=False,
            interactive=False,
        )
        self._placeholder.setObjectName("cubeStagingPlaceholder")
        self._placeholder.setMaximumHeight(0)
        self._placeholder.setMinimumHeight(0)
        self._empty_placeholder = CubePlaceholderCard(
            self,
            plus_visible=False,
            interactive=False,
        )
        self._empty_placeholder.setObjectName("cubeStagingEmptyPlaceholder")
        self._placeholder_animation = QPropertyAnimation(
            self._placeholder,
            b"maximumHeight",
            self,
        )
        self._placeholder_animation.setDuration(_ANIMATION_MS)
        self._placeholder_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setObjectName("cubeStagingStack")
        self.setMinimumWidth(CUBE_STACK_EXPANDED_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            CUBE_STACK_EDGE_INSET,
            0,
            CUBE_STACK_EDGE_INSET,
            0,
        )
        self._layout.setSpacing(CUBE_STACK_ITEM_SPACING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._apply_style()
        self._rebuild()

    def content_height(self) -> int:
        """Return deterministic stack content height for current entries."""

        if not self._entries and self._placeholder_index is None:
            return CUBE_ITEM_HEIGHT
        visible_rows = len(self._entries) + (
            1 if self._placeholder_index is not None else 0
        )
        if visible_rows == 0:
            return CUBE_ITEM_HEIGHT
        return (
            (len(self._entries) * CUBE_ITEM_HEIGHT)
            + (1 if self._placeholder_index is not None else 0)
            * self._placeholder.maximumHeight()
            + max(0, visible_rows - 1) * CUBE_STACK_ITEM_SPACING
        )

    def preferred_height(self) -> int:
        """Return content height including layout margins."""

        margins = self._layout.contentsMargins()
        return margins.top() + self.content_height() + margins.bottom()

    def entries(self) -> tuple[CubeStackDraftEntry, ...]:
        """Return draft entries in current order."""

        return tuple(self._entries)

    def alias_plan(self) -> CubeStackAliasPlan:
        """Return planned aliases for the current draft order."""

        return self._alias_plan

    def planned_alias_for(self, draft_id: str) -> str:
        """Return the visible alias planned for one draft entry."""

        return self._alias_plan.planned_alias_for(draft_id)

    def set_entries(
        self,
        entries: list[CubeStackDraftEntry],
        *,
        icons: dict[str, QIcon],
    ) -> None:
        """Replace staged entries and resolved icons."""

        self._entries = list(entries)
        self._icons = dict(icons)
        self._rebuild()

    def set_placeholder_index(self, index: int | None) -> None:
        """Show the insertion placeholder at one staged index."""

        if index is not None:
            index = max(0, min(index, len(self._entries)))
        if index == self._placeholder_index:
            return
        self._placeholder_index = index
        self._rebuild()
        self._animate_placeholder(visible=index is not None)

    def insertion_index_at_global_pos(self, global_pos: QPoint) -> int | None:
        """Return insertion index for a global pointer position."""

        local_pos = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local_pos):
            return None
        if not self._entries:
            return 0
        for index in range(len(self._entries)):
            widget = self._card_widget_at(index)
            if widget is None:
                continue
            if local_pos.y() < widget.y() + (widget.height() // 2):
                return index
        return len(self._entries)

    def staged_entry(self, staged_id: str) -> CubeStackDraftEntry | None:
        """Return a draft entry by temporary identity."""

        for entry in self._entries:
            if entry.draft_id == staged_id:
                return entry
        return None

    def remove_staged_id(self, staged_id: str) -> CubeStackDraftEntry | None:
        """Remove and return a draft entry."""

        for index, entry in enumerate(self._entries):
            if entry.draft_id == staged_id:
                removed = self._entries.pop(index)
                self._rebuild()
                return removed
        return None

    def insert_entry(
        self,
        index: int,
        entry: CubeStackDraftEntry,
        icon: QIcon,
    ) -> None:
        """Insert one draft entry."""

        bounded_index = max(0, min(index, len(self._entries)))
        self._entries.insert(bounded_index, entry)
        self._icons[entry.draft_id] = icon
        self._rebuild()

    def clear_entries(self) -> None:
        """Remove all staged entries."""

        self._entries.clear()
        self._icons.clear()
        self._placeholder_index = None
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild visible cards when staged order changes."""

        self._alias_plan = plan_cube_stack_aliases(self._entries)
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if (
                widget is not None
                and widget is not self._placeholder
                and widget is not self._empty_placeholder
            ):
                widget.deleteLater()
        self._empty_placeholder.hide()
        self._placeholder.hide()

        if not self._entries and self._placeholder_index is None:
            self._layout.addWidget(self._empty_placeholder)
            self._empty_placeholder.show()
            self.setMinimumHeight(self.preferred_height())
            return

        for index, entry in enumerate(self._entries):
            if self._placeholder_index == index:
                self._layout.addWidget(self._placeholder)
                self._placeholder.show()
            card = CubeDraftStackCard(
                entry=entry,
                planned_alias=self._alias_plan.planned_alias_for(entry.draft_id),
                icon=self._icons.get(entry.draft_id, QIcon()),
                parent=self,
            )
            card.drag_started.connect(self.staged_drag_started)
            card.drag_moved.connect(self.staged_drag_moved)
            card.drag_finished.connect(self.staged_drag_finished)
            card.remove_requested.connect(self.remove_requested)
            self._layout.addWidget(card)
        if self._placeholder_index == len(self._entries):
            self._layout.addWidget(self._placeholder)
            self._placeholder.show()
        self.setMinimumHeight(self.preferred_height())

    def _card_widget_at(self, logical_index: int) -> QWidget | None:
        """Return the card widget for one staged entry index."""

        seen = 0
        for layout_index in range(self._layout.count()):
            item = self._layout.itemAt(layout_index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, CubeDraftStackCard):
                if seen == logical_index:
                    return widget
                seen += 1
        return None

    def _animate_placeholder(self, *, visible: bool) -> None:
        """Animate placeholder height for insertion feedback."""

        self._placeholder_animation.stop()
        self._placeholder_animation.setStartValue(self._placeholder.maximumHeight())
        self._placeholder_animation.setEndValue(CUBE_ITEM_HEIGHT if visible else 0)
        self._placeholder_animation.start()

    def _apply_style(self) -> None:
        """Apply stack surface style."""

        self.setStyleSheet(
            """
            QWidget#cubeStagingStack {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            """
        )


def _event_global_pos(event: QMouseEvent) -> QPoint:
    """Return mouse global position across PySide event variants."""

    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        return cast(QPoint, global_position().toPoint())
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return cast(QPoint, global_pos())
    return QPoint()


__all__ = [
    "CubeDraftStack",
    "CubeDraftStackCard",
]
