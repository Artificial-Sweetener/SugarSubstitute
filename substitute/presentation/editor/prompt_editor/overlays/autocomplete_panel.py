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

"""Render prompt autocomplete panel overlays and define their narrow protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol, cast

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QFontMetrics,
    QHideEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.font import getFont  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.application.prompt_editor import PromptLoraCatalogItem
from substitute.presentation.editor.prompt_editor.geometry import (
    compute_autocomplete_panel_rect,
)
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
    fluent_menu_hover_fill,
    fluent_menu_selected_fill,
)
from substitute.presentation.widgets.model_picker import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_MIN_HEIGHT,
    MODEL_PICKER_POPUP_MIN_WIDTH,
    MODEL_PICKER_POPUP_WIDTH,
)

_ROW_HEIGHT: Final[int] = 33
_MAX_VISIBLE_ITEMS: Final[int] = 10
_MIN_PANEL_WIDTH: Final[int] = 260
_MAX_PANEL_WIDTH: Final[int] = 520
_ROW_GUTTER_WIDTH: Final[int] = 40
_SOURCE_LABEL_MAX_WIDTH: Final[int] = 160
_ROW_HORIZONTAL_MARGIN: Final[int] = 16
_ROW_COLUMN_GAP: Final[int] = 8


@dataclass(frozen=True, slots=True)
class PromptAutocompleteRowRenderState:
    """Describe one prepared autocomplete row for overlay rendering."""

    index: int
    title: str
    detail: str | None = None
    source_label: str | None = None
    is_selected: bool = False
    is_hovered: bool = False
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class PromptAutocompleteLoraWallRenderState:
    """Describe prepared LoRA wall content embedded in autocomplete chrome."""

    items: tuple[PromptLoraCatalogItem, ...]
    selected_index: int
    activation_payloads: tuple[object | None, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptAutocompletePanelRenderState:
    """Describe the complete prepared autocomplete panel view state."""

    rows: tuple[PromptAutocompleteRowRenderState, ...] = ()
    lora_wall: PromptAutocompleteLoraWallRenderState | None = None
    visible: bool = False
    anchor_rect: QRect | None = None
    minimum_size: QSize | None = None


@dataclass(frozen=True, slots=True)
class PromptAutocompleteActivationIntent:
    """Describe an autocomplete item activation emitted by the overlay."""

    index: int
    payload: object | None = None


class PromptAutocompleteOverlay(Protocol):
    """Render prepared autocomplete state and relay selection intent."""

    def set_render_state(self, state: PromptAutocompletePanelRenderState) -> None:
        """Replace the prepared state rendered by the autocomplete overlay."""

    def set_activation_handler(
        self,
        handler: Callable[[PromptAutocompleteActivationIntent], None] | None,
    ) -> None:
        """Set the callback used when the user activates a prepared item."""

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Set the callback used when overlay navigation changes selection."""

    def current_index(self) -> int:
        """Return the currently highlighted prepared item index."""

    def set_current_index(self, index: int) -> None:
        """Highlight one prepared item without accepting it."""

    def preferred_size(self) -> QSize:
        """Return the overlay's preferred size for the current render state."""

    def show_overlay(self, anchor_rect: QRect) -> None:
        """Show the overlay at the prepared editor-relative anchor rect."""

    def hide_overlay(self) -> None:
        """Hide the overlay without mutating editor source."""

    def is_panel_visible(self) -> bool:
        """Return whether the autocomplete panel is currently visible."""

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Set the callback used when overlay visibility changes."""


class PromptAutocompleteLoraActivationSignal(Protocol):
    """Describe the Qt signal used to relay LoRA wall activation."""

    def connect(self, slot: Callable[[object], object]) -> object:
        """Connect one activation callback."""


class PromptAutocompleteLoraWall(Protocol):
    """Describe the LoRA wall behavior consumed by the autocomplete panel."""

    loraActivated: PromptAutocompleteLoraActivationSignal

    def set_loras(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Replace the LoRA items rendered by the wall."""

    def set_current_index(self, index: int) -> None:
        """Highlight one prepared LoRA candidate."""

    def current_index(self) -> int:
        """Return the highlighted LoRA candidate index."""

    def move_current_left(self) -> None:
        """Move the highlighted LoRA candidate left."""

    def move_current_right(self) -> None:
        """Move the highlighted LoRA candidate right."""

    def move_current_up(self) -> None:
        """Move the highlighted LoRA candidate up."""

    def move_current_down(self) -> None:
        """Move the highlighted LoRA candidate down."""

    def activate_current(self) -> bool:
        """Activate the currently highlighted LoRA candidate."""

    def show(self) -> None:
        """Show the wall widget."""

    def hide(self) -> None:
        """Hide the wall widget."""

    def setParent(self, parent: QWidget | None) -> None:  # noqa: N802
        """Reparent the wall widget while preserving Qt ownership."""


def format_prompt_autocomplete_popularity(popularity: int | None) -> str:
    """Return human-readable popularity text for one autocomplete suggestion."""

    if popularity is None or popularity <= 0:
        return ""
    return f"{popularity:,}"


class PromptAutocompleteRow(QWidget):
    """Render one prompt autocomplete suggestion row."""

    clicked = Signal(int)

    def __init__(
        self,
        row_state: PromptAutocompleteRowRenderState,
        parent: QWidget | None = None,
    ) -> None:
        """Build the row-owned text metrics and interactive paint state."""

        super().__init__(parent)
        self._index = row_state.index
        self._full_tag_text = row_state.title
        self._full_secondary_text = row_state.source_label or row_state.detail or ""
        self._rendered_tag_text = ""
        self._rendered_secondary_text = ""
        self._tag_font = cast(QFont, getFont(14))
        self._secondary_font = cast(QFont, getFont(12))
        self._is_hovered = False
        self._is_selected = False

        self.setFixedHeight(_ROW_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setProperty("selected", False)

        self.set_selected(row_state.is_selected)
        self._update_rendered_text()

    def rendered_tag_text(self) -> str:
        """Return the row-owned tag text after width-aware elision."""

        return self._rendered_tag_text

    def rendered_secondary_text(self) -> str:
        """Return the row-owned secondary text after width-aware elision."""

        return self._rendered_secondary_text

    def natural_tag_width(self) -> int:
        """Return the unelided width required by the full tag text."""

        return int(QFontMetrics(self._tag_font).horizontalAdvance(self._full_tag_text))

    def natural_popularity_width(self) -> int:
        """Return the width required by the formatted popularity text."""

        if not self._full_secondary_text:
            return 0
        source_width = int(
            self._secondary_metrics().horizontalAdvance(self._full_secondary_text)
        )
        return min(source_width, _SOURCE_LABEL_MAX_WIDTH)

    def sizeHint(self) -> QSize:
        """Return the preferred row size before panel width constraints apply."""

        width = (
            self.natural_tag_width()
            + self.natural_popularity_width()
            + (2 * _ROW_HORIZONTAL_MARGIN)
            + _ROW_COLUMN_GAP
        )
        return QSize(width, _ROW_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Return the minimum row size equal to the preferred size."""

        return self.sizeHint()

    def set_render_state(
        self,
        row_state: PromptAutocompleteRowRenderState,
    ) -> None:
        """Replace row content while preserving the existing widget instance."""

        self._index = row_state.index
        self._full_tag_text = row_state.title
        self._full_secondary_text = row_state.source_label or row_state.detail or ""
        self.set_selected(row_state.is_selected)
        self._update_rendered_text()
        self.updateGeometry()
        self.update()

    def set_selected(self, is_selected: bool) -> None:
        """Apply selected-row paint state."""

        if self._is_selected == is_selected:
            return
        self._is_selected = is_selected
        self.setProperty("selected", is_selected)
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Elide long tag text when the panel narrows the row."""

        super().resizeEvent(event)
        self._update_rendered_text()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state for lightweight row affordances."""

        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the pointer leaves the row."""

        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit row activation without taking focus."""

        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw selected or hovered row backgrounds and row-owned text."""

        _ = event
        painter = QPainter(self)
        try:
            painter.setRenderHints(
                QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            )
            self._paint_row_background(painter)
            self._paint_row_text(painter)
        finally:
            painter.end()

    def _paint_row_background(self, painter: QPainter) -> None:
        """Paint the selected or hovered row fill."""

        if not (self._is_selected or self._is_hovered):
            return
        fill_rect = self.rect().adjusted(6, 4, -6, 0)
        if self._is_selected:
            fill = fluent_menu_selected_fill()
        else:
            fill = fluent_menu_hover_fill()
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fill_rect, 5, 5)

    def _paint_row_text(self, painter: QPainter) -> None:
        """Paint the tag and secondary columns within the row."""

        tag_rect, secondary_rect = self._text_rects()
        painter.setPen(self._text_color())
        if self._rendered_tag_text:
            painter.setFont(self._tag_font)
            painter.drawText(
                tag_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._rendered_tag_text,
            )
        if self._rendered_secondary_text and secondary_rect.width() > 0:
            painter.setFont(self._secondary_font)
            painter.drawText(
                secondary_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._rendered_secondary_text,
            )

    def _update_rendered_text(self) -> None:
        """Apply width-aware elision to row-owned text."""

        secondary_width = 0
        if self._full_secondary_text:
            secondary_width = min(
                self.natural_popularity_width(),
                _SOURCE_LABEL_MAX_WIDTH,
            )

        available_tag_width = self._available_tag_width(secondary_width)
        self._rendered_tag_text = self._tag_metrics().elidedText(
            self._full_tag_text,
            Qt.TextElideMode.ElideRight,
            available_tag_width,
        )
        self._rendered_secondary_text = self._secondary_metrics().elidedText(
            self._full_secondary_text,
            Qt.TextElideMode.ElideRight,
            _SOURCE_LABEL_MAX_WIDTH,
        )

    def _available_tag_width(self, secondary_width: int) -> int:
        """Return the current width available to the tag column."""

        reserved_secondary_width = 0
        if secondary_width > 0:
            reserved_secondary_width = secondary_width + _ROW_COLUMN_GAP
        return max(
            0,
            self.width() - (2 * _ROW_HORIZONTAL_MARGIN) - reserved_secondary_width,
        )

    def _text_rects(self) -> tuple[QRect, QRect]:
        """Return row-local text rectangles for tag and secondary columns."""

        secondary_width = self.natural_popularity_width()
        content_rect = self.rect().adjusted(
            _ROW_HORIZONTAL_MARGIN,
            0,
            -_ROW_HORIZONTAL_MARGIN,
            0,
        )
        if secondary_width <= 0:
            return content_rect, QRect(content_rect.right(), 0, 0, self.height())
        secondary_rect = QRect(
            content_rect.right() - secondary_width + 1,
            content_rect.top(),
            secondary_width,
            content_rect.height(),
        )
        tag_rect = QRect(
            content_rect.left(),
            content_rect.top(),
            max(0, content_rect.width() - secondary_width - _ROW_COLUMN_GAP),
            content_rect.height(),
        )
        return tag_rect, secondary_rect

    def _tag_metrics(self) -> QFontMetrics:
        """Return metrics for tag text rendering."""

        return QFontMetrics(self._tag_font)

    def _secondary_metrics(self) -> QFontMetrics:
        """Return metrics for secondary text rendering."""

        return QFontMetrics(self._secondary_font)

    @staticmethod
    def _text_color() -> QColor:
        """Return the qfluent label text color for the active theme."""

        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)


class PromptAutocompletePanel(AttachedFluentPopupFrame):
    """Render a modeless prompt autocomplete panel near the text caret."""

    suggestionActivated = Signal(int)
    loraActivated = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize one reusable autocomplete panel surface."""

        super().__init__(parent)
        self._row_states: tuple[PromptAutocompleteRowRenderState, ...] = ()
        self._rows: list[PromptAutocompleteRow] = []
        self._current_index = -1
        self._content_mode = "tag"
        self._lora_wall: PromptAutocompleteLoraWall | None = None
        self._lora_wall_items: tuple[PromptLoraCatalogItem, ...] = ()
        self._lora_activation_payloads: tuple[object | None, ...] = ()
        self._activation_handler: (
            Callable[[PromptAutocompleteActivationIntent], None] | None
        ) = None
        self._selection_changed_handler: Callable[[int], None] | None = None
        self._visibility_changed_handler: Callable[[bool], None] | None = None
        self._last_reported_visible = False

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.hide()

        layout = self.content_layout()
        layout.setContentsMargins(0, 2, 0, 6)
        layout.setSpacing(0)
        self._layout = layout

    def set_render_state(self, state: PromptAutocompletePanelRenderState) -> None:
        """Render a prepared autocomplete panel state."""

        if state.lora_wall is not None:
            self._set_lora_wall_state(state.lora_wall)
        else:
            self._set_row_states(state.rows)
            selected_index = next(
                (row.index for row in state.rows if row.is_selected),
                -1,
            )
            self.set_current_index(selected_index)
        if not state.visible:
            self.hide_overlay()

    def set_activation_handler(
        self,
        handler: Callable[[PromptAutocompleteActivationIntent], None] | None,
    ) -> None:
        """Set the activation callback used by the autocomplete presenter."""

        self._activation_handler = handler

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Set the selection callback used by the autocomplete presenter."""

        self._selection_changed_handler = handler

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Set the callback used by the autocomplete presenter for hide cleanup."""

        self._visibility_changed_handler = handler

    def preferred_size(self) -> QSize:
        """Return the preferred size for the current rendered content."""

        host = self.parentWidget()
        if host is None:
            return QSize(max(1, self.width()), max(1, self.height()))
        return QSize(
            self._calculate_panel_width(host),
            self._calculate_panel_height(),
        )

    def show_overlay(self, anchor_rect: QRect) -> None:
        """Show the panel relative to its parent host."""

        host = self.parentWidget()
        if host is None:
            self.hide_overlay()
            return
        self.show_for_editor(host, anchor_rect)

    def hide_overlay(self) -> None:
        """Hide the panel without mutating editor source."""

        self.hide_panel()

    def set_lora_wall(self, wall: PromptAutocompleteLoraWall | None) -> None:
        """Host a prepared LoRA wall widget supplied by the presenter."""

        if self._lora_wall is wall:
            return
        if self._lora_wall is not None:
            old_wall = cast(QWidget, self._lora_wall)
            old_wall.hide()
            old_wall.setParent(None)
        self._lora_wall = wall
        self._lora_wall_items = ()
        self._lora_activation_payloads = ()
        if wall is not None:
            wall_widget = cast(QWidget, wall)
            wall_widget.setParent(self)
            wall_widget.hide()
            wall.loraActivated.connect(self._activate_lora_item)

    def _set_row_states(
        self,
        rows: tuple[PromptAutocompleteRowRenderState, ...],
    ) -> None:
        """Rebuild panel rows for the supplied prepared row states."""

        previous_content_mode = self._content_mode
        self._content_mode = "tag"
        self._row_states = rows[:_MAX_VISIBLE_ITEMS]
        self._lora_activation_payloads = ()
        self._current_index = min(self._current_index, len(self._row_states) - 1)

        if previous_content_mode == "lora":
            self._clear_content()
        elif self._lora_wall is not None:
            cast(QWidget, self._lora_wall).hide()

        active_rows: list[PromptAutocompleteRow] = []
        for index, row_state in enumerate(self._row_states):
            if index < len(self._rows):
                row = self._rows[index]
                row.set_render_state(row_state)
            else:
                row = PromptAutocompleteRow(row_state, self)
                row.clicked.connect(self._activate_suggestion_item)
                self._layout.addWidget(row)
            row.show()
            active_rows.append(row)

        for stale_row in self._rows[len(active_rows) :]:
            self._layout.removeWidget(stale_row)
            stale_row.hide()
            stale_row.setParent(None)
            stale_row.deleteLater()

        self._rows = active_rows

        self.updateGeometry()

    def _set_lora_wall_state(
        self,
        state: PromptAutocompleteLoraWallRenderState,
    ) -> None:
        """Render prepared LoRA wall state through the injected wall."""

        self.geometry()
        self._content_mode = "lora"
        self._row_states = ()
        self._rows = []
        self._lora_activation_payloads = state.activation_payloads
        wall = self._lora_wall
        if wall is None:
            self._lora_wall_items = ()
            self.updateGeometry()
            return
        if state.items != self._lora_wall_items:
            self._clear_content()
            wall.set_loras(state.items)
            self._lora_wall_items = state.items
        elif self._layout.indexOf(cast(QWidget, wall)) < 0:
            self._clear_content()
        wall.show()
        wall_widget = cast(QWidget, wall)
        if self._layout.indexOf(wall_widget) < 0:
            self._layout.addWidget(wall_widget)
        self._current_index = 0 if state.items else -1
        self.updateGeometry()

    def set_current_index(self, index: int) -> None:
        """Select the requested suggestion row when it exists."""

        if self._content_mode == "lora":
            if self._lora_wall is not None:
                self._lora_wall.set_current_index(index)
                self._current_index = self._lora_wall.current_index()
            else:
                self._current_index = -1
            return

        if not self._rows or index < 0 or index >= len(self._rows):
            self._current_index = -1
            for row in self._rows:
                row.set_selected(False)
            return

        self._current_index = index
        for row_index, row in enumerate(self._rows):
            row.set_selected(row_index == index)

    def current_index(self) -> int:
        """Return the currently selected suggestion row index."""

        if self._content_mode == "lora" and self._lora_wall is not None:
            return self._lora_wall.current_index()
        return self._current_index

    def move_current_lora_left(self) -> None:
        """Move current LoRA wall selection left."""

        self._move_current_lora("left")

    def move_current_lora_right(self) -> None:
        """Move current LoRA wall selection right."""

        self._move_current_lora("right")

    def move_current_lora_up(self) -> None:
        """Move current LoRA wall selection up one visual row."""

        self._move_current_lora("up")

    def move_current_lora_down(self) -> None:
        """Move current LoRA wall selection down one visual row."""

        self._move_current_lora("down")

    def lora_wall(self) -> QWidget | None:
        """Return the LoRA wall content widget when panel is in LoRA mode."""

        if self._lora_wall is None:
            return None
        return cast(QWidget, self._lora_wall)

    def _move_current_lora(self, direction: str) -> None:
        """Move current LoRA wall selection in one visual direction."""

        if self._lora_wall is None:
            return
        if direction == "left":
            self._lora_wall.move_current_left()
        elif direction == "right":
            self._lora_wall.move_current_right()
        elif direction == "up":
            self._lora_wall.move_current_up()
        elif direction == "down":
            self._lora_wall.move_current_down()
        self._current_index = self._lora_wall.current_index()
        if self._selection_changed_handler is not None:
            self._selection_changed_handler(self._current_index)

    def show_for_editor(self, host: QWidget, anchor_rect: QRect) -> None:
        """Show the panel near one anchor rect while clamping it within the host."""

        if not self._has_content():
            self.hide_panel()
            return

        panel_rect = compute_autocomplete_panel_rect(
            host,
            anchor_rect,
            QSize(
                self._calculate_panel_width(host),
                self._calculate_panel_height(),
            ),
        )
        self.setGeometry(panel_rect)
        self.show()
        self.raise_()

    def hide_panel(self) -> None:
        """Hide the panel without discarding the current suggestion cache."""

        self.hide()

    def is_panel_visible(self) -> bool:
        """Return True when the panel is currently visible."""

        return bool(self.isVisible())

    def showEvent(self, event: QShowEvent) -> None:
        """Notify the presenter that autocomplete presentation became visible."""

        super().showEvent(event)
        self._notify_visibility_changed(True)

    def hideEvent(self, event: QHideEvent) -> None:
        """Notify the presenter that autocomplete presentation became hidden."""

        super().hideEvent(event)
        self._notify_visibility_changed(False)

    def _calculate_panel_width(self, viewport: QWidget) -> int:
        """Return the panel width constrained by content and viewport size."""

        if self._content_mode == "lora":
            available_width = max(1, viewport.width() - 8)
            return min(
                MODEL_PICKER_POPUP_WIDTH,
                max(MODEL_PICKER_POPUP_MIN_WIDTH, available_width),
            )

        widest_tag = max((row.natural_tag_width() for row in self._rows), default=0)
        widest_popularity = max(
            (row.natural_popularity_width() for row in self._rows),
            default=0,
        )
        content_width = widest_tag + widest_popularity + _ROW_GUTTER_WIDTH
        panel_width = min(max(content_width, _MIN_PANEL_WIDTH), _MAX_PANEL_WIDTH)
        available_width = max(1, viewport.width() - 8)
        return min(panel_width, available_width)

    def _calculate_panel_height(self) -> int:
        """Return the height required for the current row collection."""

        if self._content_mode == "lora":
            host = self.parentWidget()
            available_height = 0 if host is None else max(1, host.height() - 8)
            return min(
                MODEL_PICKER_POPUP_HEIGHT,
                max(MODEL_PICKER_POPUP_MIN_HEIGHT, available_height),
            )

        margins = self._layout.contentsMargins()
        if not self._rows:
            return 0
        return (
            margins.top()
            + margins.bottom()
            + len(self._rows) * _ROW_HEIGHT
            + max(0, len(self._rows) - 1) * self._layout.spacing()
        )

    def _clear_content(self) -> None:
        """Remove current content widgets while preserving a reusable LoRA wall."""

        lora_wall = self._lora_wall
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            if lora_wall is not None and widget is cast(QWidget, lora_wall):
                widget.hide()
                widget.setParent(self)
                continue
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._rows = []

    def _activate_suggestion_item(self, index: int) -> None:
        """Emit and relay one prepared suggestion activation."""

        self.suggestionActivated.emit(index)
        if self._activation_handler is not None:
            payload = next(
                (row.payload for row in self._row_states if row.index == index),
                None,
            )
            self._activation_handler(
                PromptAutocompleteActivationIntent(
                    index=index,
                    payload=payload,
                )
            )

    def _activate_lora_item(self, item: object) -> None:
        """Emit the index for one activated LoRA candidate."""

        if not isinstance(item, PromptLoraCatalogItem):
            return
        for index, lora_item in enumerate(self._lora_wall_items):
            if lora_item is item or lora_item.prompt_name == item.prompt_name:
                self.loraActivated.emit(index)
                if self._activation_handler is not None:
                    payload = (
                        self._lora_activation_payloads[index]
                        if 0 <= index < len(self._lora_activation_payloads)
                        else None
                    )
                    self._activation_handler(
                        PromptAutocompleteActivationIntent(
                            index=index,
                            payload=payload,
                        )
                    )
                return

    def _has_content(self) -> bool:
        """Return whether the active panel mode has visible content."""

        if self._content_mode == "lora":
            return bool(self._lora_wall_items)
        return bool(self._row_states)

    def _notify_visibility_changed(self, visible: bool) -> None:
        """Publish visibility changes once per visible-state transition."""

        if self._last_reported_visible == visible:
            return
        self._last_reported_visible = visible
        if self._visibility_changed_handler is not None:
            self._visibility_changed_handler(visible)


__all__ = [
    "PromptAutocompleteActivationIntent",
    "PromptAutocompleteLoraActivationSignal",
    "PromptAutocompleteLoraWall",
    "PromptAutocompleteLoraWallRenderState",
    "PromptAutocompleteOverlay",
    "PromptAutocompletePanel",
    "PromptAutocompletePanelRenderState",
    "PromptAutocompleteRow",
    "PromptAutocompleteRowRenderState",
    "format_prompt_autocomplete_popularity",
]
