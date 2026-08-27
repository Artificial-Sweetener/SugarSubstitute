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

"""Cover autocomplete presentation lifecycle ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_presentation_lifecycle import (
    PromptAutocompletePresentationLifecycle,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)


class _PreviewSink:
    """Record projection preview states published by the lifecycle owner."""

    def __init__(self) -> None:
        """Initialize an empty preview-state record."""

        self.states: list[PromptAutocompletePreviewState | None] = []

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Record one projection preview replacement."""

        self.states.append(preview_state)


class _RecordingPresenter:
    """Expose deterministic panel presentation state for owner-level tests."""

    def __init__(self, *, visible: bool) -> None:
        """Initialize presenter visibility and empty interaction hooks."""

        self.visible = visible
        self.presented_sessions: list[AutocompleteSession] = []
        self.hide_calls = 0
        self.activation_handler: Callable[[object], None] | None = None
        self.selection_changed_handler: Callable[[int], None] | None = None
        self.visibility_changed_handler: Callable[[bool], None] | None = None

    @property
    def panel(self) -> None:
        """Return no live widget for focused lifecycle tests."""

        return None

    def present_session(self, session: AutocompleteSession) -> bool:
        """Record prepared presentation and return current visibility."""

        self.presented_sessions.append(session)
        return self.visible

    def set_activation_handler(self, handler: Callable[[Any], None] | None) -> None:
        """Store the typed presenter activation boundary."""

        self.activation_handler = handler

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Store the presenter selection boundary."""

        self.selection_changed_handler = handler

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Store the presenter visibility boundary."""

        self.visibility_changed_handler = handler

    def activate(self, intent: Any) -> None:
        """Forward one activation intent when a consumer is registered."""

        if self.activation_handler is not None:
            self.activation_handler(intent)

    def current_index(self) -> int:
        """Return the only selected index needed by this focused test double."""

        return 0

    def move_lora_selection(self, direction: str) -> int | None:
        """Accept supported movement without adding selection policy to the fake."""

        return 0 if direction in {"left", "right", "up", "down"} else None

    def panel_under_mouse(self) -> bool:
        """Mirror visible state for focus-retention queries."""

        return self.visible

    def panel_visible(self) -> bool:
        """Return the current deterministic presentation visibility."""

        return self.visible

    def hide(self) -> None:
        """Record explicit hide requests."""

        self.hide_calls += 1
        self.visible = False


def _active_sessions() -> PromptAutocompleteSessionController:
    """Build one source-safe active tag session for presentation tests."""

    sessions = PromptAutocompleteSessionController()
    sessions.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=(
            PromptAutocompleteGhostTextSourceSnapshot(
                source_revision=2,
                source_length=2,
                cursor_position=2,
                source_text="1g",
            )
        ),
    )
    return sessions


def test_geometry_refresh_reuses_prepared_session_without_query_work() -> None:
    """Reposition one active session without source reads or result generation."""

    sessions = _active_sessions()
    presenter = _RecordingPresenter(visible=True)
    sink = _PreviewSink()
    lifecycle = PromptAutocompletePresentationLifecycle(
        sessions=sessions,
        presenter=presenter,
        ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            publish_preview_state=sink.set_autocomplete_preview_state
        ),
        ghost_text_enabled=True,
    )

    lifecycle.refresh_geometry()

    assert presenter.presented_sessions == [sessions.session]
    assert sink.states[-1] is not None
    assert sessions.has_active_session() is True


def test_hidden_panel_clears_existing_ghost_preview() -> None:
    """Clear the projection preview if prepared panel presentation is unavailable."""

    sessions = _active_sessions()
    presenter = _RecordingPresenter(visible=True)
    sink = _PreviewSink()
    lifecycle = PromptAutocompletePresentationLifecycle(
        sessions=sessions,
        presenter=presenter,
        ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            publish_preview_state=sink.set_autocomplete_preview_state
        ),
        ghost_text_enabled=True,
    )
    lifecycle.refresh_geometry()
    presenter.visible = False

    lifecycle.refresh_geometry()

    assert presenter.presented_sessions == [sessions.session, sessions.session]
    assert sink.states[-1] is None


def test_inactive_geometry_refresh_does_not_request_panel_or_preview_work() -> None:
    """Keep geometry-only refresh inert when no presentation session exists."""

    presenter = _RecordingPresenter(visible=True)
    sink = _PreviewSink()
    lifecycle = PromptAutocompletePresentationLifecycle(
        sessions=PromptAutocompleteSessionController(),
        presenter=presenter,
        ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            publish_preview_state=sink.set_autocomplete_preview_state
        ),
        ghost_text_enabled=True,
    )

    lifecycle.refresh_geometry()

    assert presenter.presented_sessions == []
    assert sink.states == []
