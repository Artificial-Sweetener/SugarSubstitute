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

"""Own autocomplete panel and ghost-preview presentation lifecycle."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.editor.prompt_editor.debug_probe import (
    autocomplete_probe_state,
    log_prompt_editor_probe,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompleteActivationIntent,
    PromptAutocompletePanel,
    PromptAutocompletePresenter,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
)

from .autocomplete_session import PromptAutocompleteSessionController


class PromptAutocompletePresentationLifecycle:
    """Present prepared autocomplete state without owning query or selection policy."""

    def __init__(
        self,
        *,
        sessions: PromptAutocompleteSessionController,
        presenter: PromptAutocompletePresenter | None,
        ghost_text_publisher: PromptAutocompleteGhostTextPublisher | None,
        ghost_text_enabled: bool,
    ) -> None:
        """Store the presentation ports and retained session state."""

        self._sessions = sessions
        self._presenter = presenter
        self._ghost_text_publisher = ghost_text_publisher
        self._ghost_text_enabled = ghost_text_enabled

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live autocomplete panel when the presenter created it."""

        if self._presenter is None:
            return None
        return self._presenter.panel

    def install_interaction_handlers(
        self,
        *,
        activation_handler: Callable[[PromptAutocompleteActivationIntent], None],
        selection_changed_handler: Callable[[int], None],
        visibility_changed_handler: Callable[[bool], None],
    ) -> None:
        """Bind presenter input events to the application interaction coordinator."""

        if self._presenter is None:
            return
        self._presenter.set_activation_handler(activation_handler)
        self._presenter.set_selection_changed_handler(selection_changed_handler)
        self._presenter.set_visibility_changed_handler(visibility_changed_handler)

    def hide(self) -> None:
        """Hide panel presentation without changing the authoritative session."""

        if self._presenter is not None:
            self._presenter.hide()

    def panel_under_mouse(self) -> bool:
        """Return whether visible autocomplete presentation is under the pointer."""

        return self._presenter is not None and self._presenter.panel_under_mouse()

    def move_lora_selection(self, direction: str) -> int | None:
        """Move the presenter-owned LoRA selection when a panel exists."""

        if self._presenter is None:
            return None
        return self._presenter.move_lora_selection(direction)

    def refresh_geometry(self) -> None:
        """Reposition active presentation without querying or reading editor source."""

        if not self._sessions.has_active_session():
            return
        self.present_active_surfaces()

    def present_active_surfaces(self) -> None:
        """Present the panel and publish ghost text only for visible presentation."""

        log_prompt_editor_probe(
            "autocomplete.present_active_surfaces.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._present_panel():
            self._publish_inline_completion_preview()
            log_prompt_editor_probe(
                "autocomplete.present_active_surfaces.end",
                presented=True,
                autocomplete=autocomplete_probe_state(self),
            )
            return
        self.clear_inline_completion_preview()
        log_prompt_editor_probe(
            "autocomplete.present_active_surfaces.end",
            presented=False,
            autocomplete=autocomplete_probe_state(self),
        )

    def publish_inline_completion_preview_if_panel_visible(self) -> None:
        """Publish ghost text only while the existing panel remains visible."""

        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview_if_panel_visible.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._presenter is None or not self._presenter.panel_visible():
            self.clear_inline_completion_preview()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview_if_panel_visible.end",
                published=False,
                autocomplete=autocomplete_probe_state(self),
            )
            return
        self._publish_inline_completion_preview()
        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview_if_panel_visible.end",
            published=True,
            autocomplete=autocomplete_probe_state(self),
        )

    def clear_inline_completion_preview(self) -> None:
        """Clear the projection-owned ghost preview through its dedicated port."""

        log_prompt_editor_probe(
            "autocomplete.clear_inline_completion_preview.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._ghost_text_publisher is not None:
            self._ghost_text_publisher.clear()
        log_prompt_editor_probe(
            "autocomplete.clear_inline_completion_preview.end",
            autocomplete=autocomplete_probe_state(self),
        )

    def _present_panel(self) -> bool:
        """Present the retained session through the passive panel adapter."""

        if self._presenter is None:
            return False
        return self._presenter.present_session(self._sessions.session)

    def _publish_inline_completion_preview(self) -> None:
        """Publish a source-safe preview for the already prepared active session."""

        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        publisher = self._ghost_text_publisher
        if publisher is None:
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="no_publisher",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        if not self._ghost_text_enabled:
            publisher.clear()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="disabled",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        source_snapshot = self._sessions.ghost_text_source_snapshot
        if source_snapshot is None:
            publisher.clear()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="no_source_snapshot",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        publisher.publish_for_session(
            self._sessions.session,
            source_snapshot=source_snapshot,
        )
        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview.end",
            published=True,
            autocomplete=autocomplete_probe_state(self),
        )
