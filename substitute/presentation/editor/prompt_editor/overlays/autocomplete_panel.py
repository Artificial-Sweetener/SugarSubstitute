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
from typing import Final

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.geometry.autocomplete_panel import (
    compute_autocomplete_panel_rect,
)
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
)
from substitute.presentation.widgets.model_picker import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_MIN_HEIGHT,
    MODEL_PICKER_POPUP_MIN_WIDTH,
    MODEL_PICKER_POPUP_WIDTH,
)

from .autocomplete_contracts import (
    PromptAutocompleteActivationIntent,
    PromptAutocompleteLoraActivationSignal,
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
    PromptAutocompleteOverlay,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRowRenderState,
)
from .autocomplete_lora_wall_host import PromptAutocompleteLoraWallHost
from .autocomplete_row import (
    AUTOCOMPLETE_ROW_HEIGHT,
    PromptAutocompleteRow,
    format_prompt_autocomplete_popularity,
)

_MAX_VISIBLE_ITEMS: Final[int] = 10
_MIN_PANEL_WIDTH: Final[int] = 260
_MAX_PANEL_WIDTH: Final[int] = 520
_ROW_GUTTER_WIDTH: Final[int] = 40


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
        self._lora_wall_host = PromptAutocompleteLoraWallHost(
            parent=self,
            layout=layout,
            activated=self._activate_lora_index,
            selection_changed=self._publish_lora_selection,
            clear_content=self._clear_content,
        )

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

        self._lora_wall_host.set_wall(wall)

    def _set_row_states(
        self,
        rows: tuple[PromptAutocompleteRowRenderState, ...],
    ) -> None:
        """Rebuild panel rows for the supplied prepared row states."""

        previous_content_mode = self._content_mode
        self._content_mode = "tag"
        self._row_states = rows[:_MAX_VISIBLE_ITEMS]
        self._current_index = min(self._current_index, len(self._row_states) - 1)

        if previous_content_mode == "lora":
            self._clear_content()
        elif (lora_wall := self._lora_wall_host.widget()) is not None:
            lora_wall.hide()

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

        self._content_mode = "lora"
        self._row_states = ()
        self._rows = []
        self._current_index = self._lora_wall_host.render(state)

    def set_current_index(self, index: int) -> None:
        """Select the requested suggestion row when it exists."""

        if self._content_mode == "lora":
            self._current_index = self._lora_wall_host.set_current_index(index)
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

        if self._content_mode == "lora":
            return self._lora_wall_host.current_index()
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

        return self._lora_wall_host.widget()

    def _move_current_lora(self, direction: str) -> None:
        """Move current LoRA wall selection in one visual direction."""

        self._current_index = self._lora_wall_host.move_current(direction)

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
            + len(self._rows) * AUTOCOMPLETE_ROW_HEIGHT
            + max(0, len(self._rows) - 1) * self._layout.spacing()
        )

    def _clear_content(self) -> None:
        """Remove current content widgets while preserving a reusable LoRA wall."""

        lora_wall = self._lora_wall_host.widget()
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            if lora_wall is not None and widget is lora_wall:
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

    def _activate_lora_index(self, index: int, payload: object | None) -> None:
        """Relay one wall-owned activation through the panel overlay contract."""

        self.loraActivated.emit(index)
        if self._activation_handler is not None:
            self._activation_handler(
                PromptAutocompleteActivationIntent(index=index, payload=payload)
            )

    def _publish_lora_selection(self, index: int) -> None:
        """Relay wall-owned selection changes through the overlay contract."""

        if self._selection_changed_handler is not None:
            self._selection_changed_handler(index)

    def _has_content(self) -> bool:
        """Return whether the active panel mode has visible content."""

        if self._content_mode == "lora":
            return self._lora_wall_host.has_content()
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
