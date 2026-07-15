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

"""Present prepared autocomplete sessions through the autocomplete overlay."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.geometry import (
    autocomplete_panel_host,
    map_cursor_rect_to_host,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession

from .autocomplete_panel import (
    PromptAutocompleteActivationIntent,
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
    PromptAutocompletePanel,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRowRenderState,
    format_prompt_autocomplete_popularity,
)


class PromptAutocompletePresentationEditor(Protocol):
    """Describe editor geometry needed by autocomplete presentation."""

    def cursorRect(self) -> QRect:
        """Return the caret rectangle in viewport coordinates."""

    def viewport(self) -> QWidget:
        """Return the editor viewport used for autocomplete geometry placement."""


class PromptAutocompletePresenter(Protocol):
    """Present prepared autocomplete overlay state and relay user intent."""

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live panel widget when it has been created."""

    def present_session(self, session: AutocompleteSession) -> bool:
        """Render one prepared autocomplete session and report visible presentation."""

    def set_activation_handler(
        self,
        handler: Callable[[PromptAutocompleteActivationIntent], None] | None,
    ) -> None:
        """Set the callback that receives item activation intent."""

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Set the callback that receives overlay selection changes."""

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Set the callback that receives overlay visibility changes."""

    def activate(self, intent: PromptAutocompleteActivationIntent) -> None:
        """Relay one prepared activation intent to the controller."""

    def current_index(self) -> int:
        """Return the current overlay selection index."""

    def move_lora_selection(self, direction: str) -> int | None:
        """Move LoRA wall selection and return the current index."""

    def panel_under_mouse(self) -> bool:
        """Return whether visible autocomplete presentation is under the pointer."""

    def panel_visible(self) -> bool:
        """Return whether autocomplete presentation is currently visible."""

    def hide(self) -> None:
        """Hide autocomplete presentation without mutating source."""


class PromptAutocompletePanelFactory(Protocol):
    """Create autocomplete panel overlays for the active host widget."""

    def __call__(self, parent: QWidget) -> PromptAutocompletePanel:
        """Return one autocomplete panel parented to the supplied host."""


class PromptAutocompleteLoraWallFactory(Protocol):
    """Create presenter-supplied LoRA wall widgets for autocomplete panels."""

    def __call__(
        self,
        parent: QWidget,
        *,
        thumbnail_cache: object,
    ) -> PromptAutocompleteLoraWall:
        """Return a LoRA wall for the supplied autocomplete panel parent."""


class PromptAutocompletePanelPresenter:
    """Prepare autocomplete panel render state and drive the overlay."""

    def __init__(
        self,
        *,
        editor: PromptAutocompletePresentationEditor,
        panel_factory: PromptAutocompletePanelFactory,
        lora_wall_factory: PromptAutocompleteLoraWallFactory | None = None,
        lora_thumbnail_cache: object | None = None,
    ) -> None:
        """Store panel dependencies without owning autocomplete query policy."""

        self._editor = editor
        self._panel_factory = panel_factory
        self._lora_wall_factory = lora_wall_factory
        self._lora_thumbnail_cache = lora_thumbnail_cache
        self._panel: PromptAutocompletePanel | None = None
        self._lora_wall: PromptAutocompleteLoraWall | None = None
        self._activation_handler: (
            Callable[[PromptAutocompleteActivationIntent], None] | None
        ) = None
        self._selection_changed_handler: Callable[[int], None] | None = None
        self._visibility_changed_handler: Callable[[bool], None] | None = None

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live panel widget when it has been created."""

        return self._panel

    def present_session(self, session: AutocompleteSession) -> bool:
        """Render the prepared panel state for one autocomplete session."""

        if not self._has_active_session(session):
            self.hide()
            return False

        panel = self._ensure_panel()
        state = self._render_state_for_session(session)
        panel.set_render_state(state)
        if state.anchor_rect is None or not state.visible:
            panel.hide_overlay()
            return False
        panel.show_overlay(state.anchor_rect)
        if session.mode == "lora":
            panel.set_current_index(session.selected_index)
        return panel.is_panel_visible()

    def set_activation_handler(
        self,
        handler: Callable[[PromptAutocompleteActivationIntent], None] | None,
    ) -> None:
        """Set the callback that receives overlay activation intent."""

        self._activation_handler = handler
        if self._panel is not None:
            self._panel.set_activation_handler(self.activate)

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Set the callback that receives overlay selection changes."""

        self._selection_changed_handler = handler
        if self._panel is not None:
            self._panel.set_selection_changed_handler(handler)

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Set the callback that receives overlay visibility changes."""

        self._visibility_changed_handler = handler
        if self._panel is not None:
            self._panel.set_visibility_changed_handler(handler)

    def activate(self, intent: PromptAutocompleteActivationIntent) -> None:
        """Relay one overlay activation intent to the autocomplete owner."""

        if self._activation_handler is not None:
            self._activation_handler(intent)

    def current_index(self) -> int:
        """Return the current overlay selection index."""

        if self._panel is None:
            return -1
        return self._panel.current_index()

    def move_lora_selection(self, direction: str) -> int | None:
        """Move LoRA wall selection and return the current index."""

        panel = self._panel
        if panel is None:
            return None
        if direction == "left":
            panel.move_current_lora_left()
        elif direction == "right":
            panel.move_current_lora_right()
        elif direction == "up":
            panel.move_current_lora_up()
        elif direction == "down":
            panel.move_current_lora_down()
        else:
            return None
        return panel.current_index()

    def panel_under_mouse(self) -> bool:
        """Return whether visible autocomplete presentation is under the pointer."""

        panel = self._panel
        return bool(
            panel is not None and panel.is_panel_visible() and panel.underMouse()
        )

    def panel_visible(self) -> bool:
        """Return whether autocomplete presentation is currently visible."""

        panel = self._panel
        return bool(panel is not None and panel.is_panel_visible())

    def hide(self) -> None:
        """Hide autocomplete presentation without mutating source."""

        if self._panel is not None:
            self._panel.hide_overlay()

    def _ensure_panel(self) -> PromptAutocompletePanel:
        """Create or reparent the autocomplete panel for the current host."""

        panel_host = autocomplete_panel_host(cast(QWidget, self._editor))
        if self._panel is None or self._panel.parentWidget() is not panel_host:
            if self._panel is not None:
                self._panel.deleteLater()
            self._panel = self._panel_factory(panel_host)
            self._panel.set_activation_handler(self.activate)
            self._panel.set_selection_changed_handler(self._selection_changed_handler)
            self._panel.set_visibility_changed_handler(self._visibility_changed_handler)
            self._panel.set_lora_wall(self._ensure_lora_wall())
        return self._panel

    def _ensure_lora_wall(self) -> PromptAutocompleteLoraWall | None:
        """Return the prepared LoRA wall widget when wall dependencies exist."""

        if self._lora_wall is not None:
            return self._lora_wall
        if self._lora_wall_factory is None or self._lora_thumbnail_cache is None:
            return None
        panel = self._panel
        if panel is None:
            return None
        self._lora_wall = self._lora_wall_factory(
            panel,
            thumbnail_cache=self._lora_thumbnail_cache,
        )
        return self._lora_wall

    def _render_state_for_session(
        self,
        session: AutocompleteSession,
    ) -> PromptAutocompletePanelRenderState:
        """Build one prepared panel render state for the active session."""

        anchor_rect = self._anchor_rect()
        if session.mode == "lora":
            if self._ensure_lora_wall() is None:
                return PromptAutocompletePanelRenderState(
                    visible=False,
                    anchor_rect=anchor_rect,
                )
            return PromptAutocompletePanelRenderState(
                lora_wall=PromptAutocompleteLoraWallRenderState(
                    items=tuple(
                        candidate.item for candidate in session.lora_candidates
                    ),
                    activation_payloads=session.lora_candidates,
                    selected_index=session.selected_index,
                ),
                visible=True,
                anchor_rect=anchor_rect,
            )
        return PromptAutocompletePanelRenderState(
            rows=tuple(
                PromptAutocompleteRowRenderState(
                    index=index,
                    title=suggestion.tag,
                    source_label=(
                        suggestion.source_label
                        if suggestion.source_label is not None
                        else format_prompt_autocomplete_popularity(
                            suggestion.popularity
                        )
                    ),
                    is_selected=index == session.selected_index,
                    payload=suggestion,
                )
                for index, suggestion in enumerate(session.suggestions)
            ),
            visible=True,
            anchor_rect=anchor_rect,
        )

    def _anchor_rect(self) -> QRect:
        """Return the current caret rect mapped into the panel host."""

        panel_host = autocomplete_panel_host(cast(QWidget, self._editor))
        return map_cursor_rect_to_host(
            self._editor.viewport(),
            self._editor.cursorRect(),
            panel_host,
        )

    @staticmethod
    def _has_active_session(session: AutocompleteSession) -> bool:
        """Return whether the session has content worth presenting."""

        if session.mode == "lora":
            return session.selected_index >= 0 and bool(session.lora_candidates)
        return session.selected_index >= 0 and bool(session.suggestions)


__all__ = [
    "PromptAutocompletePanelFactory",
    "PromptAutocompletePanelPresenter",
    "PromptAutocompleteLoraWallFactory",
    "PromptAutocompletePresentationEditor",
    "PromptAutocompletePresenter",
]
