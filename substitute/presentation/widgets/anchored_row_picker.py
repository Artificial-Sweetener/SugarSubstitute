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
from dataclasses import dataclass
from typing import Literal, cast

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
)
from qfluentwidgets.components.material import (  # type: ignore[import-untyped]
    AcrylicFlyout,
    AcrylicFlyoutViewBase,
)

from substitute.presentation.widgets.anchored_row_flyout_placement import (
    anchored_row_flyout_placement,
)

AnchoredRowPickerTextMode = Literal[
    "anchor_center",
    "anchor_left",
    "row_center",
    "row_left",
]

_ROW_SPACING = 2
_FLYOUT_LEFT_MARGIN = 15
_FLYOUT_TOP_MARGIN = 8
_VIEW_MARGIN = 7
_DEFAULT_HORIZONTAL_TEXT_PADDING = 12


@dataclass(frozen=True, slots=True)
class AnchoredRowPickerItem:
    """Describe one visible row in an anchored row picker."""

    key: str
    label: str
    enabled: bool = True


class AnchoredRowPickerRow(QPushButton):
    """Render one selectable anchored picker row with explicit text geometry."""

    selected = Signal(str)

    def __init__(
        self,
        item: AnchoredRowPickerItem,
        *,
        active: bool,
        row_size: QSize,
        anchor_slot_width: int,
        active_text_mode: AnchoredRowPickerTextMode,
        inactive_text_mode: AnchoredRowPickerTextMode,
        horizontal_text_padding: int = _DEFAULT_HORIZONTAL_TEXT_PADDING,
        parent: QWidget | None = None,
    ) -> None:
        """Create a fixed-size picker row with explicit text painting."""

        super().__init__(item.label, parent)
        self.item = item
        self._active = active
        self._anchor_slot_width = anchor_slot_width
        self._active_text_mode = active_text_mode
        self._inactive_text_mode = inactive_text_mode
        self._horizontal_text_padding = horizontal_text_padding
        self.setProperty("active", active)
        self.setFixedSize(row_size)
        self.setEnabled(item.enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        setFont(self, 14)
        self.clicked.connect(lambda: self._emit_if_enabled())
        self._apply_theme_styles()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit selection directly so popup row clicks do not depend on focus."""

        if (
            self.item.enabled
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.selected.emit(self.item.key)
            return
        super().mouseReleaseEvent(event)

    def set_active(self, active: bool) -> None:
        """Update active state and repaint."""

        self._active = active
        self.setProperty("active", active)
        self._apply_theme_styles()
        self.update()

    def text_rect_for_paint(self) -> QRect:
        """Return the text rect used by explicit row painting."""

        mode = self._current_text_mode()
        if mode in ("anchor_center", "anchor_left"):
            width = min(self._anchor_slot_width, self.width())
            base_rect = QRect(0, 0, width, self.height())
        else:
            base_rect = self.rect()
        if mode in ("anchor_left", "row_left"):
            return base_rect.adjusted(
                self._horizontal_text_padding,
                0,
                -self._horizontal_text_padding,
                0,
            )
        return base_rect

    def text_alignment_for_paint(self) -> Qt.AlignmentFlag:
        """Return the text alignment used by explicit row painting."""

        mode = self._current_text_mode()
        if mode in ("anchor_center", "row_center"):
            return Qt.AlignmentFlag.AlignCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def paintEvent(self, event: object) -> None:
        """Paint row fill and text from explicit alignment modes."""

        del event
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing,
        )
        fill = self._fill_color()
        if fill is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(self.rect(), 5, 5)
        painter.setFont(self.font())
        painter.setPen(self._text_color())
        painter.drawText(
            self.text_rect_for_paint(),
            self.text_alignment_for_paint(),
            self.item.label,
        )

    def _emit_if_enabled(self) -> None:
        """Emit the row key when the item is enabled."""

        if self.item.enabled:
            self.selected.emit(self.item.key)

    def _current_text_mode(self) -> AnchoredRowPickerTextMode:
        """Return the active or inactive text mode for this row."""

        return self._active_text_mode if self._active else self._inactive_text_mode

    def _apply_theme_styles(self) -> None:
        """Apply qfluent-compatible base row states."""

        self.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                padding: 0px;
            }
            """
        )

    def _fill_color(self) -> QColor | None:
        """Return the current hover or active fill color."""

        if self._active:
            return QColor(255, 255, 255, 31) if isDarkTheme() else QColor(0, 0, 0, 20)
        if self.underMouse():
            return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 15)
        return None

    def _text_color(self) -> QColor:
        """Return the current row text color."""

        if not self.isEnabled():
            return QColor(255, 255, 255, 92) if isDarkTheme() else QColor(0, 0, 0, 92)
        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)


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
        active_text_mode: AnchoredRowPickerTextMode,
        inactive_text_mode: AnchoredRowPickerTextMode,
        horizontal_text_padding: int = _DEFAULT_HORIZONTAL_TEXT_PADDING,
        parent: QWidget | None = None,
    ) -> None:
        """Create picker rows for the supplied items and text modes."""

        super().__init__(parent)
        self._items = items
        self._active_key = self._normalize_active_key(active_key)
        self._row_slot_size = QSize(
            row_width if row_width is not None else anchor_size.width(),
            anchor_size.height(),
        )
        self._rows: dict[str, AnchoredRowPickerRow] = {}
        self.setFixedWidth(self._row_slot_size.width() + 2 * _VIEW_MARGIN)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            _VIEW_MARGIN, _VIEW_MARGIN, _VIEW_MARGIN, _VIEW_MARGIN
        )
        layout.setSpacing(_ROW_SPACING)

        for item in self._items:
            row = AnchoredRowPickerRow(
                item,
                active=item.key == self._active_key,
                row_size=self._row_slot_size,
                anchor_slot_width=anchor_size.width(),
                active_text_mode=active_text_mode,
                inactive_text_mode=inactive_text_mode,
                horizontal_text_padding=horizontal_text_padding,
                parent=self,
            )
            row.selected.connect(lambda key, self=self: self.itemSelected.emit(key))
            self._rows[item.key] = row
            layout.addWidget(row)

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

        view = AnchoredRowPickerView(
            items=items,
            active_key=active_key,
            anchor_size=anchor.size(),
            row_width=row_width,
            active_text_mode=active_text_mode,
            inactive_text_mode=inactive_text_mode,
        )
        view.itemSelected.connect(selected_callback)
        view.itemSelected.connect(lambda _key: self.close())

        popup_size = QSize(view.sizeHint().width() + 30, view.sizeHint().height() + 28)
        anchor_global_rect = QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
        screen = QGuiApplication.screenAt(anchor_global_rect.center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            screen_geometry = QRect(anchor_global_rect.topLeft(), popup_size)
        else:
            screen_geometry = screen.availableGeometry()

        active_row_index = active_row_index_from_top(
            items=items,
            active_key=view.active_key(),
        )
        placement = anchored_row_flyout_placement(
            anchor_global_rect=anchor_global_rect,
            popup_size=popup_size,
            row_width=view.row_slot_width(),
            row_height=anchor.height(),
            row_count=len(items),
            active_row_index_from_top=active_row_index,
            row_left_offset=_FLYOUT_LEFT_MARGIN + _VIEW_MARGIN,
            row_top_offset=_FLYOUT_TOP_MARGIN + _VIEW_MARGIN,
            row_spacing=_ROW_SPACING,
            screen_available_geometry=screen_geometry,
        )
        flyout = AcrylicFlyout(view, self._parent, isDeleteOnClose=True)
        self._flyout = cast(QWidget, flyout)
        flyout.move(placement.position)
        flyout.show()
        flyout.activateWindow()
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
    "AnchoredRowPickerItem",
    "AnchoredRowPickerRow",
    "AnchoredRowPickerTextMode",
    "AnchoredRowPickerView",
    "active_row_index_from_top",
]
