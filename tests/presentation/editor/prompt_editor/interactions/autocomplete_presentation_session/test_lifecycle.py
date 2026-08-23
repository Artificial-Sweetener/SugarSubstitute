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

"""Verify autocomplete session presentation and ghost lifecycle contracts."""

from __future__ import annotations


from types import SimpleNamespace


from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    EmptyAutocompleteGateway,
    TextAutocompleteEditorDouble,
    autocomplete_session_controller_with_session,
    import_autocomplete_module,
)


from tests.presentation.editor.prompt_editor.autocomplete.session_controller_support import (
    _VisibilityRecordingPresenter,
)


def test_refresh_geometry_preserves_active_session_and_updates_surfaces() -> None:
    """Geometry refresh repositions live surfaces without clearing the session."""

    mod = import_autocomplete_module()
    session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("1girl", 5_889_398),),
        selected_index=0,
        word_start=0,
        word_end=2,
        prefix="1g",
    )
    session_controller = autocomplete_session_controller_with_session(mod, session)
    presenter = _VisibilityRecordingPresenter(visible=True)
    autocomplete_stack = build_test_autocomplete_stack(
        SimpleNamespace(
            set_autocomplete_preview_state=lambda _preview_state: None,
            viewport=lambda: SimpleNamespace(rect=lambda: "viewport-rect"),
        ),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=presenter,
        autocomplete_session_controller=session_controller,
    )

    autocomplete_stack.input_adapter.refresh_geometry()

    assert presenter.presented_sessions == [session]
    assert session_controller.session is session


def test_hidden_panel_prevents_autocomplete_ghost_publication() -> None:
    """Ghost text should not publish when panel presentation is unavailable."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1g")
    presenter = _VisibilityRecordingPresenter(visible=False)
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    session_controller._state.ghost_text_source_snapshot = (
        PromptAutocompleteGhostTextSourceSnapshot(
            source_revision=0,
            source_length=2,
            cursor_position=2,
            source_text="1g",
        )
    )
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=presenter,
        autocomplete_ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            publish_preview_state=editor.set_autocomplete_preview_state,
        ),
        autocomplete_session_controller=session_controller,
    )

    autocomplete_stack.input_adapter.refresh_geometry()

    assert editor.autocomplete_preview_state is None


def test_panel_hide_clears_existing_autocomplete_ghost_text() -> None:
    """A hidden autocomplete panel should immediately clear its ghost preview."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1g")
    presenter = _VisibilityRecordingPresenter(visible=True)
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    session_controller._state.ghost_text_source_snapshot = (
        PromptAutocompleteGhostTextSourceSnapshot(
            source_revision=0,
            source_length=2,
            cursor_position=2,
            source_text="1g",
        )
    )
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=presenter,
        autocomplete_ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            publish_preview_state=editor.set_autocomplete_preview_state,
        ),
        autocomplete_session_controller=session_controller,
    )
    autocomplete_stack.input_adapter.refresh_geometry()
    assert editor.autocomplete_preview_state is not None

    presenter.set_visible(False)

    assert editor.autocomplete_preview_state is None
