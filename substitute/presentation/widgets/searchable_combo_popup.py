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

"""Render the filtered popup used by select-only searchable combo boxes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QGuiApplication,
    QHideEvent,
    QHoverEvent,
    QKeyEvent,
    QMouseEvent,
    QRegion,
)
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    IndicatorMenuItemDelegate,
    RoundMenu,
)

from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

from .searchable_combo_helpers import (
    AttachedPopupPlacement,
    attached_combo_popup_placement,
)

_COMBO_POPUP_ITEM_HEIGHT = 33
_COMBO_POPUP_MAX_VISIBLE_ITEMS = 10
_COMBO_POPUP_REVEAL_DURATION_MS = 250
_COMBO_POPUP_REVEAL_HEIGHT_PADDING = 5
_COMBO_POPUP_ANIMATION_EXTRA_WIDTH = 120
_COMBO_POPUP_ANIMATION_EXTRA_HEIGHT = 20
_COMBO_POPUP_PULL_UP_MASK_BOTTOM_TRIM = 28


class SearchableComboPopup(RoundMenu):  # type: ignore[misc]
    """Show allowed combo items and emit the source index for activations."""

    activatedIndex = Signal(int)
    dismissedByOutsideClick = Signal()
    highlightedIndexChanged = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        """Initialize the qfluent menu surface used for combo results."""

        super().__init__("", parent)
        self._source_indexes: list[int] = []
        self._global_mouse_filter_installed = False
        self._reveal_animation: QPropertyAnimation | None = None
        self._reveal_opens_down = True
        self.view.setViewportMargins(0, 2, 0, 6)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setItemDelegate(IndicatorMenuItemDelegate())
        self.view.setObjectName("searchableComboListWidget")
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.installEventFilter(self)
        self.view.installEventFilter(self)
        self.view.itemEntered.connect(self._on_item_entered)
        self.setItemHeight(_COMBO_POPUP_ITEM_HEIGHT)
        self.setMaxVisibleItems(_COMBO_POPUP_MAX_VISIBLE_ITEMS)

    def set_items(
        self,
        *,
        labels: Sequence[str],
        source_indexes: Sequence[int],
        preferred_source_index: int,
    ) -> None:
        """Replace visible rows and highlight the preferred source index."""

        self.clear()
        self._source_indexes = list(source_indexes)
        QFluentMenuRenderer(parent=self).populate_menu(
            self,
            MenuModel(
                entries=tuple(
                    MenuItem(
                        action_id=f"searchable_combo.activate.{source_index}",
                        label=label,
                        callback=self._activation_callback(source_index),
                    )
                    for label, source_index in zip(labels, source_indexes)
                )
            ).entries,
        )

        if not self._source_indexes:
            return

        try:
            row = self._source_indexes.index(preferred_source_index)
        except ValueError:
            row = 0
        self.view.setCurrentRow(row)
        self._emit_highlighted_index()

    def visible_texts(self) -> list[str]:
        """Return visible row text for tests and popup state synchronization."""

        return [self.view.item(row).text() for row in range(self.view.count())]

    def source_indexes(self) -> list[int]:
        """Return visible source indexes in row order."""

        return list(self._source_indexes)

    def highlighted_source_index(self) -> int | None:
        """Return the source index for the highlighted row, if any."""

        row = int(self.view.currentRow())
        if row < 0 or row >= len(self._source_indexes):
            return None
        return self._source_indexes[row]

    def highlight_next(self) -> None:
        """Move the highlighted row down by one item."""

        self._move_highlight(1)

    def highlight_previous(self) -> None:
        """Move the highlighted row up by one item."""

        self._move_highlight(-1)

    def activate_highlighted(self) -> bool:
        """Activate the highlighted item when one exists."""

        source_index = self.highlighted_source_index()
        if source_index is None:
            return False
        self._activate_index(source_index)
        return True

    def _activation_callback(self, source_index: int) -> Callable[[], None]:
        """Return a callback that activates one source index."""

        return lambda: self._activate_index(source_index)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        """Forward popup keys and dismiss on clicks outside combo surfaces."""

        if watched not in (self, self.view):
            self._dismiss_for_outside_mouse_event(event)
            return False

        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            parent = self.parent()
            if isinstance(parent, QWidget):
                forwarded = QKeyEvent(
                    event.type(),
                    event.key(),
                    event.modifiers(),
                    event.text(),
                    event.isAutoRepeat(),
                    event.count(),
                )
                QCoreApplication.sendEvent(parent, forwarded)
                return True
        self._dismiss_for_outside_mouse_event(event)
        return bool(super().eventFilter(watched, event))

    def _dismiss_for_outside_mouse_event(self, event: QEvent) -> None:
        """Close the popup when a watched mouse press lands outside it."""

        if (
            event.type()
            in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
            and isinstance(event, QMouseEvent)
            and self._global_mouse_filter_installed
            and self.isVisible()
            and self._mouse_event_is_outside_combo_surfaces(event)
        ):
            self.dismissedByOutsideClick.emit()
            self.close()

    def popup_for(self, field: QWidget) -> None:
        """Show this popup left-anchored to the field."""

        if not self._source_indexes:
            self.close()
            return

        placement = self._apply_attached_geometry(field)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._install_global_mouse_filter()
        self._start_qfluent_reveal_animation(opens_down=placement.opens_down)
        self.show()
        self.raise_()
        field.setFocus()

    def reflow_for(self, field: QWidget) -> None:
        """Resize and move the visible popup without re-executing it."""

        if not self.isVisible():
            self.popup_for(field)
            return
        if not self._source_indexes:
            self.close()
            return

        self._stop_qfluent_reveal_animation()
        self._apply_attached_geometry(field)
        self._install_global_mouse_filter()
        field.setFocus()

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop watching application clicks once the popup is hidden."""

        self._stop_qfluent_reveal_animation()
        self._remove_global_mouse_filter()
        super().hideEvent(event)

    def _apply_attached_geometry(self, field: QWidget) -> AttachedPopupPlacement:
        """Size and position this popup from an app-owned attachment policy."""

        field_top_left = field.mapToGlobal(QPoint(0, 0))
        screen = QGuiApplication.screenAt(field_top_left)
        if screen is None:
            window_handle = field.window().windowHandle()
            screen = window_handle.screen() if window_handle is not None else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("A screen is required to place combo popup.")

        self.setMaxVisibleItems(_COMBO_POPUP_MAX_VISIBLE_ITEMS)
        layout_margins = self.layout().contentsMargins()
        horizontal_chrome_width = layout_margins.left() + layout_margins.right()
        vertical_chrome_height = self._vertical_chrome_height()
        preferred_view_width = self._preferred_view_width(field.width())
        field_popup_anchor = QRect(
            field_top_left.x() - layout_margins.left(),
            field_top_left.y(),
            field.width() + horizontal_chrome_width,
            field.height(),
        )
        placement = attached_combo_popup_placement(
            field_global_rect=field_popup_anchor,
            screen_available_geometry=screen.availableGeometry(),
            preferred_popup_width=preferred_view_width,
            row_count=len(self._source_indexes),
            row_height=_COMBO_POPUP_ITEM_HEIGHT,
            max_visible_rows=_COMBO_POPUP_MAX_VISIBLE_ITEMS,
            vertical_chrome_height=vertical_chrome_height,
            horizontal_chrome_width=horizontal_chrome_width,
        )
        self.setMaxVisibleItems(placement.visible_row_count)
        view_size = QSize(
            max(1, placement.geometry.width() - horizontal_chrome_width),
            self._view_height_for_visible_rows(placement.visible_row_count),
        )
        popup_geometry = QRect(placement.geometry)
        if placement.opens_down:
            popup_geometry.moveTop(placement.geometry.top() - layout_margins.top())
        else:
            popup_geometry.moveTop(placement.geometry.top() + layout_margins.bottom())

        self.view.setFixedSize(view_size)
        self.setFixedSize(popup_geometry.size())
        self.move(popup_geometry.topLeft())
        return placement

    def _preferred_view_width(self, minimum_width: int) -> int:
        """Return the natural list width before screen clamping."""

        viewport_margins = self.view.viewportMargins()
        widest_item_width = max(
            (
                int(self.view.item(index).sizeHint().width())
                for index in range(self.view.count())
                if self.view.item(index) is not None
            ),
            default=minimum_width,
        )
        return max(
            minimum_width,
            widest_item_width
            + int(viewport_margins.left())
            + int(viewport_margins.right())
            + 2,
        )

    def _vertical_chrome_height(self) -> int:
        """Return popup height outside item rows for placement budgeting."""

        layout_margins = self.layout().contentsMargins()
        viewport_margins = self.view.viewportMargins()
        return (
            int(layout_margins.top())
            + int(layout_margins.bottom())
            + int(viewport_margins.top())
            + int(viewport_margins.bottom())
            + 3
        )

    def _view_height_for_visible_rows(self, visible_row_count: int) -> int:
        """Return the qfluent list height for a visible row budget."""

        viewport_margins = self.view.viewportMargins()
        return (
            max(1, visible_row_count) * _COMBO_POPUP_ITEM_HEIGHT
            + int(viewport_margins.top())
            + int(viewport_margins.bottom())
            + 3
        )

    def _start_qfluent_reveal_animation(self, *, opens_down: bool) -> None:
        """Animate from qfluent's reveal start offset to our final geometry."""

        self._stop_qfluent_reveal_animation()
        final_position = self.pos()
        reveal_offset = QPoint(
            0,
            int((self.height() + _COMBO_POPUP_REVEAL_HEIGHT_PADDING) / 2),
        )
        start_position = (
            final_position - reveal_offset
            if opens_down
            else final_position + reveal_offset
        )
        self._reveal_opens_down = opens_down
        self.move(start_position)

        animation = QPropertyAnimation(self, b"pos", self)
        animation.setDuration(_COMBO_POPUP_REVEAL_DURATION_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        animation.setStartValue(start_position)
        animation.setEndValue(final_position)
        animation.valueChanged.connect(self._on_qfluent_reveal_value_changed)
        animation.valueChanged.connect(self._update_qfluent_reveal_viewport)
        animation.finished.connect(self.clearMask)
        self._reveal_animation = animation
        self._on_qfluent_reveal_value_changed()
        animation.start()

    def _stop_qfluent_reveal_animation(self) -> None:
        """Stop any active reveal animation and restore an unmasked popup."""

        if self._reveal_animation is not None:
            self._reveal_animation.stop()
            self._reveal_animation = None
        self.clearMask()

    def _on_qfluent_reveal_value_changed(self) -> None:
        """Apply qfluent's animated reveal mask for the current popup position."""

        if self._reveal_animation is None:
            return

        current_position = self._reveal_animation.currentValue()
        end_position = self._reveal_animation.endValue()
        if not isinstance(current_position, QPoint) or not isinstance(
            end_position, QPoint
        ):
            return

        width, height = self._qfluent_animation_mask_size()
        y = end_position.y() - current_position.y()
        if self._reveal_opens_down:
            self.setMask(QRegion(0, y, width, height))
        else:
            self.setMask(
                QRegion(0, y, width, height - _COMBO_POPUP_PULL_UP_MASK_BOTTOM_TRIM)
            )

    def _update_qfluent_reveal_viewport(self) -> None:
        """Refresh hover state during reveal using qfluent's menu behavior."""

        self.view.viewport().update()
        self.view.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
        hover_event = QHoverEvent(
            QEvent.Type.HoverEnter,
            QPoint(0, 0),
            QPoint(1, 1),
        )
        QApplication.sendEvent(self.view, hover_event)

    def _qfluent_animation_mask_size(self) -> tuple[int, int]:
        """Return qfluent's oversized mask dimensions for menu reveal."""

        layout_margins = self.layout().contentsMargins()
        width = (
            self.view.width()
            + int(layout_margins.left())
            + int(layout_margins.right())
            + _COMBO_POPUP_ANIMATION_EXTRA_WIDTH
        )
        height = (
            self.view.height()
            + int(layout_margins.top())
            + int(layout_margins.bottom())
            + _COMBO_POPUP_ANIMATION_EXTRA_HEIGHT
        )
        return width, height

    def list_global_left(self) -> int:
        """Return the visible result-list left edge in global coordinates."""

        return int(
            self.mapToGlobal(QPoint(self.layout().contentsMargins().left(), 0)).x()
        )

    def list_global_top(self) -> int:
        """Return the visible result-list top edge in global coordinates."""

        return int(self.view.mapToGlobal(QPoint(0, 0)).y())

    def list_global_bottom(self) -> int:
        """Return the visible result-list bottom edge in global coordinates."""

        return self.list_global_top() + int(self.view.height())

    def _window_position_for_anchor(
        self, anchor: QPoint, animation_type: Any
    ) -> QPoint:
        """Return the menu top-left for a qfluent list-left anchor point."""

        margins = self.layout().contentsMargins()
        screen_rect = self._screen_geometry_for(anchor)
        width = self.width() + 5
        height = self.height()
        x = min(anchor.x() - margins.left(), screen_rect.right() - width)
        if animation_type == MenuAnimationType.PULL_UP:
            y = max(anchor.y() - height + 10, screen_rect.top() + 4)
        else:
            y = min(anchor.y() - 4, screen_rect.bottom() - height + 10)
        return QPoint(x, y)

    def _screen_geometry_for(self, point: QPoint) -> QRect:
        """Return available screen geometry for a global point."""

        screen = QGuiApplication.screenAt(point)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QRect(point, self.size())
        return screen.availableGeometry()

    def _move_highlight(self, delta: int) -> None:
        """Move the highlighted row by delta while clamping to visible rows."""

        count = self.view.count()
        if count <= 0:
            return
        next_row = self.view.currentRow()
        if next_row < 0:
            next_row = 0
        else:
            next_row = max(0, min(count - 1, next_row + delta))
        self.view.setCurrentRow(next_row)
        self._emit_highlighted_index()

    def _on_item_entered(self, item: object) -> None:
        """Track hovered rows as the active completion candidate."""

        row = self.view.row(item)
        if row < 0:
            return
        self.view.setCurrentRow(row)
        self._emit_highlighted_index()

    def _emit_highlighted_index(self) -> None:
        """Emit the source index for the current highlighted row."""

        source_index = self.highlighted_source_index()
        if source_index is not None:
            self.highlightedIndexChanged.emit(source_index)

    def _activate_index(self, source_index: int) -> None:
        """Emit activation for one source index and close the popup."""

        self.close()
        self.activatedIndex.emit(source_index)

    def _install_global_mouse_filter(self) -> None:
        """Watch application mouse presses while this transient popup is visible."""

        if self._global_mouse_filter_installed:
            return
        app = QCoreApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._global_mouse_filter_installed = True

    def _remove_global_mouse_filter(self) -> None:
        """Remove the application mouse filter if it is currently installed."""

        if not self._global_mouse_filter_installed:
            return
        app = QCoreApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._global_mouse_filter_installed = False

    def _mouse_event_is_outside_combo_surfaces(self, event: QMouseEvent) -> bool:
        """Return whether a mouse press is outside both popup and owning combo."""

        global_position = event.globalPosition().toPoint()
        if self.frameGeometry().contains(global_position):
            return False

        parent = self.parent()
        if isinstance(parent, QWidget):
            parent_position = parent.mapFromGlobal(global_position)
            if parent.rect().contains(parent_position):
                return False

        return True

    def exec(
        self,
        pos: QPoint,
        ani: bool = True,
        aniType: Any = MenuAnimationType.DROP_DOWN,
    ) -> object:
        """Show the menu after qfluent has recalculated list geometry."""

        self.view.adjustSize(pos, aniType)
        self.adjustSize()
        return super().exec(pos, ani, aniType)


__all__ = ["SearchableComboPopup"]
