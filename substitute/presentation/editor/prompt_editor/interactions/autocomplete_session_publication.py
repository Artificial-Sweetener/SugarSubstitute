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

"""Own autocomplete session transitions and their prepared presentation."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryState,
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompleteActivationIntent,
    PromptAutocompletePanel,
    PromptAutocompletePresenter,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)

from .autocomplete_presentation_lifecycle import (
    PromptAutocompletePresentationLifecycle,
)
from .autocomplete_session import (
    PromptAutocompleteDismissReason,
    PromptAutocompleteSessionController,
    PromptAutocompleteSessionState,
)


class PromptAutocompleteSessionPublication:
    """Publish immutable results through the sole session and presentation owner."""

    def __init__(
        self,
        *,
        sessions: PromptAutocompleteSessionController,
        presenter: PromptAutocompletePresenter | None,
        ghost_text_publisher: PromptAutocompleteGhostTextPublisher | None,
        ghost_text_enabled: bool,
    ) -> None:
        """Store session truth and create its passive presentation lifecycle."""

        self._sessions = sessions
        self._presentation = PromptAutocompletePresentationLifecycle(
            sessions=sessions,
            presenter=presenter,
            ghost_text_publisher=ghost_text_publisher,
            ghost_text_enabled=ghost_text_enabled,
        )

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the presentation panel when the presenter created one."""

        return self._presentation.panel

    @property
    def session(self) -> AutocompleteSession:
        """Return the current renderable session for acceptance and input routing."""

        return self._sessions.session

    @property
    def source_identity(self) -> PromptSourceIdentity | None:
        """Return the source identity paired with the current session."""

        return self._sessions.source_identity

    @property
    def state(self) -> PromptAutocompleteSessionState:
        """Return session state for owner diagnostics without exposing mutation APIs."""

        return self._sessions.state

    def install_interaction_handlers(
        self,
        *,
        activation_handler: Callable[[PromptAutocompleteActivationIntent], None],
        selection_changed_handler: Callable[[int], None],
        visibility_changed_handler: Callable[[bool], None],
    ) -> None:
        """Bind presenter events to the thin Qt interaction adapter."""

        self._presentation.install_interaction_handlers(
            activation_handler=activation_handler,
            selection_changed_handler=selection_changed_handler,
            visibility_changed_handler=visibility_changed_handler,
        )

    def publish_result(
        self,
        result: PromptAutocompleteResultSnapshot,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Replace session state and present its prepared surfaces."""

        self._sessions.replace_result(
            result,
            source_identity=cast(
                PromptSourceIdentity | None, query_state.source_identity
            ),
            ghost_text_source_snapshot=PromptAutocompleteGhostTextSourceSnapshot(
                source_revision=query_state.source_revision,
                source_length=query_state.source_length,
                cursor_position=query_state.cursor_position,
                source_text=query_state.source_text,
            ),
        )
        self._presentation.present_active_surfaces()

    def retarget_from_query_state(
        self, query_state: PromptAutocompleteQueryState
    ) -> bool:
        """Retarget compatible session state and refresh prepared presentation."""

        if not self._sessions.retarget(query_state):
            if self._sessions.has_active_session() and not query_state.has_selection:
                self.dismiss_autocomplete("incompatible_query")
            elif query_state.has_selection:
                self.dismiss_autocomplete("selection_started")
            return False
        self._presentation.present_active_surfaces()
        return True

    def dismiss_autocomplete(self, reason: PromptAutocompleteDismissReason) -> None:
        """Clear visible presentation and authoritative session state together."""

        self._presentation.hide()
        self._presentation.clear_inline_completion_preview()
        self._sessions.dismiss(reason)

    def has_active_session(self) -> bool:
        """Return whether session state has selectable content."""

        return self._sessions.has_active_session()

    def select_index(self, index: int) -> None:
        """Apply one presenter or input selection to session truth."""

        self._sessions.select_index(index)

    def move_suggestion_selection(self, delta: int) -> None:
        """Move the suggestion selection and update prepared presentation."""

        self._sessions.move_suggestion_selection(delta)
        self._presentation.present_active_surfaces()

    def move_lora_selection(self, direction: str, fallback_delta: int) -> None:
        """Move LoRA selection through the panel or session fallback and publish preview."""

        presenter_index = self._presentation.move_lora_selection(direction)
        if presenter_index is None:
            self._sessions.move_lora_selection_linear(fallback_delta)
        else:
            self._sessions.select_index(presenter_index)
        self._presentation.publish_inline_completion_preview_if_panel_visible()

    def panel_under_mouse(self) -> bool:
        """Return whether presentation retains pointer ownership after focus loss."""

        return self._presentation.panel_under_mouse()

    def panel_visible(self) -> bool:
        """Return whether prepared autocomplete presentation is visibly active."""

        panel = self._presentation.panel
        return panel is not None and panel.isVisible()

    def refresh_geometry(self) -> None:
        """Refresh active presentation geometry without source or query work."""

        self._presentation.refresh_geometry()

    def publish_inline_completion_preview_if_panel_visible(self) -> None:
        """Refresh ghost text after a selection-only transition."""

        self._presentation.publish_inline_completion_preview_if_panel_visible()

    def clear_inline_completion_preview(self) -> None:
        """Clear ghost text after presentation visibility changes."""

        self._presentation.clear_inline_completion_preview()


__all__ = ["PromptAutocompleteSessionPublication"]
