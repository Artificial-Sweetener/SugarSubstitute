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

"""Render reusable anchor-aligned row picker flyouts."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets.components.material import (  # type: ignore[import-untyped]
    AcrylicFlyout,
    AcrylicFlyoutViewBase,
)

from substitute.presentation.widgets.anchored_row_flyout_placement import (
    anchored_row_flyout_placement,
    anchored_row_flyout_viewport,
)
from substitute.presentation.widgets.anchored_row_picker_scroll import (
    AnchoredRowPickerScrollSurface,
)
from substitute.presentation.widgets.anchored_row_picker_row import (
    ANCHORED_ROW_PICKER_HORIZONTAL_TEXT_PADDING,
    AnchoredRowPickerItem,
    AnchoredRowPickerRow,
    AnchoredRowPickerTextMode,
)

_ROW_SPACING = 2
_VIEW_MARGIN = 7


class AnchoredRowPickerView(AcrylicFlyoutViewBase):  # type: ignore[misc]
    """Render anchored picker rows and own row keyboard navigation."""

    itemSelected = Signal(str)

    def __init__(
        self,
        *,
        items: tuple[AnchoredRowPickerItem, ...],
        active_key: str,
        anchor_size: QSize,
        row_width: int | None = None,
        maximum_height: int | None = None,
        preferred_active_slot: int | None = None,
        active_text_mode: AnchoredRowPickerTextMode,
        inactive_text_mode: AnchoredRowPickerTextMode,
        horizontal_text_padding: int = ANCHORED_ROW_PICKER_HORIZONTAL_TEXT_PADDING,
        parent: QWidget | None = None,
    ) -> None:
        """Create picker rows for the supplied items and text modes."""

        super().__init__(parent)
        self._items = items
        self._active_key = self._normalize_active_key(active_key)
        self._preferred_active_slot = preferred_active_slot
        self._row_slot_size = QSize(
            row_width if row_width is not None else anchor_size.width(),
            anchor_size.height(),
        )
        self._rows: dict[str, AnchoredRowPickerRow] = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            _VIEW_MARGIN, _VIEW_MARGIN, _VIEW_MARGIN, _VIEW_MARGIN
        )
        layout.setSpacing(_ROW_SPACING)
        maximum_scroll_height = (
            None
            if maximum_height is None
            else max(1, maximum_height - (2 * _VIEW_MARGIN))
        )
        self._scroll = AnchoredRowPickerScrollSurface(
            row_width=self._row_slot_size.width(),
            row_height=self._row_slot_size.height(),
            row_count=len(self._items),
            row_spacing=_ROW_SPACING,
            maximum_height=maximum_scroll_height,
            parent=self,
        )
        layout.addWidget(self._scroll)
        self.setFixedSize(
            self._scroll.width() + (2 * _VIEW_MARGIN),
            self._scroll.height() + (2 * _VIEW_MARGIN),
        )

        for item in self._items:
            row = AnchoredRowPickerRow(
                item,
                active=item.key == self._active_key,
                row_size=self._row_slot_size,
                anchor_slot_width=anchor_size.width(),
                active_text_mode=active_text_mode,
                inactive_text_mode=inactive_text_mode,
                horizontal_text_padding=horizontal_text_padding,
                parent=self._scroll.content,
            )
            row.selected.connect(lambda key, self=self: self.itemSelected.emit(key))
            self._rows[item.key] = row
            self._scroll.add_row(row)

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        """Support the qfluent flyout view extension contract."""

        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.addWidget(widget, stretch, align)

    def item_keys(self) -> tuple[str, ...]:
        """Return visible item keys in display order for tests."""

        return tuple(item.key for item in self._items)

    def row_for_key(self, key: str) -> AnchoredRowPickerRow | None:
        """Return the row widget for an item key if it exists."""

        return self._rows.get(key)

    def row_slot_width(self) -> int:
        """Return the row slot width used for placement calculations."""

        return self._row_slot_size.width()

    def active_key(self) -> str:
        """Return the currently highlighted key for tests and adapters."""

        return self._active_key

    def visible_row_count(self) -> int:
        """Return the number of complete rows exposed without scrolling."""

        return self._scroll.visible_row_count()

    def requires_scroll(self) -> bool:
        """Return whether the picker row document exceeds its viewport."""

        return self._scroll.requires_scroll()

    def reveal_active_row(self) -> None:
        """Reveal the highlighted row at its preferred anchor-relative slot."""

        row = self._rows.get(self._active_key)
        if row is None:
            return
        active_index = active_row_index_from_top(
            items=self._items,
            active_key=self._active_key,
        )
        visible_slot = self._initial_active_slot(active_index)
        self._scroll.reveal_at_slot(active_index, visible_slot)
        self._scroll.reveal(row)

    def active_row_index_in_view(self) -> int:
        """Return the highlighted row slot after initial overflow scrolling."""

        active_index = active_row_index_from_top(
            items=self._items,
            active_key=self._active_key,
        )
        if not self._scroll.requires_scroll():
            return active_index
        visible_slot = self._initial_active_slot(active_index)
        maximum_start = max(0, len(self._items) - self._scroll.visible_row_count())
        start_index = min(maximum_start, max(0, active_index - visible_slot))
        return active_index - start_index

    def _initial_active_slot(self, active_index: int) -> int:
        """Return the preferred visible slot for initial active-row alignment."""

        maximum_slot = max(0, self._scroll.visible_row_count() - 1)
        if self._preferred_active_slot is None:
            preferred_slot = self._scroll.visible_row_count() // 2
        else:
            preferred_slot = self._preferred_active_slot
        return min(active_index, maximum_slot, max(0, preferred_slot))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle simple keyboard navigation for the active picker."""

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.window().close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.itemSelected.emit(self._active_key)
            return
        if key == Qt.Key.Key_Up:
            self._move_active(1)
            return
        if key == Qt.Key.Key_Down:
            self._move_active(-1)
            return
        super().keyPressEvent(event)

    def _move_active(self, delta: int) -> None:
        """Move active row highlight by delta without committing selection."""

        enabled_keys = tuple(item.key for item in self._items if item.enabled)
        if not enabled_keys:
            return
        try:
            active_position = enabled_keys.index(self._active_key)
        except ValueError:
            active_position = 0
        next_position = max(
            0,
            min(len(enabled_keys) - 1, active_position - delta),
        )
        next_key = enabled_keys[next_position]
        if next_key == self._active_key:
            return
        self._active_key = next_key
        for key, row in self._rows.items():
            row.set_active(key == next_key)
        self._scroll.reveal(self._rows[next_key])

    def _normalize_active_key(self, active_key: str) -> str:
        """Return an active key that exists and is enabled in the row set."""

        enabled_keys = tuple(item.key for item in self._items if item.enabled)
        if active_key in enabled_keys:
            return active_key
        if enabled_keys:
            return enabled_keys[0]
        return active_key


class AnchoredRowPicker:
    """Own acrylic flyout creation, placement, and item selection wiring."""

    def __init__(self, parent: QWidget) -> None:
        """Create a picker controller for an anchored row selector."""

        self._parent = parent
        self._flyout: QWidget | None = None

    def show_for(
        self,
        anchor: QWidget,
        *,
        items: tuple[AnchoredRowPickerItem, ...],
        active_key: str,
        row_width: int | None = None,
        active_text_mode: AnchoredRowPickerTextMode,
        inactive_text_mode: AnchoredRowPickerTextMode,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Show a qfluent popup aligned to the selector button."""

        if self.is_visible():
            self.close()
            return
        self._flyout = None

        anchor_global_rect = QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
        screen = QGuiApplication.screenAt(anchor_global_rect.center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            screen_geometry = QRect(anchor_global_rect.topLeft(), anchor.size())
        else:
            screen_geometry = screen.availableGeometry()

        viewport = anchored_row_flyout_viewport(
            anchor_global_rect=anchor_global_rect,
            screen_available_geometry=screen_geometry,
            row_height=anchor.height(),
            row_spacing=_ROW_SPACING,
            view_margin=_VIEW_MARGIN,
        )

        view = AnchoredRowPickerView(
            items=items,
            active_key=active_key,
            anchor_size=anchor.size(),
            row_width=row_width,
            maximum_height=viewport.maximum_view_height,
            preferred_active_slot=viewport.active_row_slot_from_top,
            active_text_mode=active_text_mode,
            inactive_text_mode=inactive_text_mode,
        )
        view.itemSelected.connect(selected_callback)
        view.itemSelected.connect(lambda _key: self.close())

        flyout = AcrylicFlyout(view, self._parent, isDeleteOnClose=True)
        flyout.show()
        flyout.ensurePolished()
        flyout.adjustSize()
        flyout_layout = flyout.layout()
        if flyout_layout is not None:
            flyout_layout.activate()
        popup_size = flyout.size()
        row_origin = view.mapTo(flyout, QPoint(_VIEW_MARGIN, _VIEW_MARGIN))
        outer_top_margin = max(0, row_origin.y() - _VIEW_MARGIN)
        outer_bottom_margin = max(
            0,
            flyout.height() - view.y() - view.height(),
        )

        active_row_index = view.active_row_index_in_view()
        placement = anchored_row_flyout_placement(
            anchor_global_rect=anchor_global_rect,
            popup_size=popup_size,
            row_width=view.row_slot_width(),
            row_height=anchor.height(),
            row_count=min(len(items), view.visible_row_count()),
            active_row_index_from_top=active_row_index,
            row_left_offset=row_origin.x(),
            row_top_offset=row_origin.y(),
            row_spacing=_ROW_SPACING,
            screen_available_geometry=screen_geometry.adjusted(
                0,
                -outer_top_margin,
                0,
                outer_bottom_margin,
            ),
        )
        self._flyout = cast(QWidget, flyout)
        flyout.move(placement.position)
        flyout.activateWindow()
        view.reveal_active_row()
        closed_signal = getattr(self._flyout, "closed", None)
        connect = getattr(closed_signal, "connect", None)
        if callable(connect):
            connect(self._handle_flyout_closed)
        view.setFocus()

    def close(self) -> None:
        """Close the visible picker popup."""

        if self._flyout is None:
            return
        try:
            self._flyout.close()
        except RuntimeError:
            pass
        self._flyout = None

    def is_visible(self) -> bool:
        """Return whether the picker popup is currently visible."""

        if self._flyout is None:
            return False
        try:
            visible = self._flyout.isVisible()
        except RuntimeError:
            self._flyout = None
            return False
        if not visible:
            self._flyout = None
        return visible

    def _handle_flyout_closed(self) -> None:
        """Forget closed popups so subsequent selector clicks reopen cleanly."""

        self._flyout = None


def active_row_index_from_top(
    *,
    items: tuple[AnchoredRowPickerItem, ...],
    active_key: str,
) -> int:
    """Return zero-based visual row index for the active item."""

    row_keys = tuple(item.key for item in items)
    try:
        return row_keys.index(active_key)
    except ValueError:
        return 0


__all__ = [
    "AnchoredRowPicker",
    "AnchoredRowPickerView",
    "active_row_index_from_top",
]
