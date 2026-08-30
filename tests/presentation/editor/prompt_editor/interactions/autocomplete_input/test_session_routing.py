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

"""Verify autocomplete session keyboard and focus-routing contracts."""

from __future__ import annotations


from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    EmptyAutocompleteGateway,
    autocomplete_session_controller_with_session,
    import_autocomplete_module,
    key_event,
)


from tests.presentation.editor.prompt_editor.autocomplete.session_controller_support import (
    _VisibilityRecordingPresenter,
    _lora_candidate,
)


def test_autocomplete_handle_key_press_leaves_enter_to_editor_text_input() -> None:
    """Leave Enter key handling to the editor text input for tag autocomplete."""

    mod = import_autocomplete_module()
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    assert (
        autocomplete_stack.input_adapter.handle_key_press(key_event(Qt.Key.Key_Return))
        is False
    )
    assert (
        autocomplete_stack.input_adapter.handle_key_press(key_event(Qt.Key.Key_Enter))
        is False
    )


def test_lora_autocomplete_handle_key_press_leaves_enter_to_editor_text_input() -> None:
    """Leave Enter key handling to the editor text input for LoRA autocomplete."""

    mod = import_autocomplete_module()
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="lora",
            selected_index=0,
            lora_candidates=(_lora_candidate("midna"),),
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        SimpleNamespace(),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    assert (
        autocomplete_stack.input_adapter.handle_key_press(key_event(Qt.Key.Key_Return))
        is False
    )
    assert (
        autocomplete_stack.input_adapter.handle_key_press(key_event(Qt.Key.Key_Enter))
        is False
    )


def test_focus_lost_dismissal_keeps_session_when_panel_is_under_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep autocomplete alive while the pointer stays over the panel."""

    mod = import_autocomplete_module()
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: object()),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=_VisibilityRecordingPresenter(visible=True),
        autocomplete_session_controller=session_controller,
    )

    autocomplete_stack.input_adapter.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "active"


def test_focus_lost_dismissal_keeps_session_for_editor_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep autocomplete when the projection surface owns editor focus."""

    mod = import_autocomplete_module()
    projection_surface = object()
    editor = SimpleNamespace(
        isAncestorOf=lambda widget: widget is projection_surface,
    )
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: projection_surface),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    autocomplete_stack.input_adapter.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "active"


def test_focus_lost_dismissal_clears_when_focus_leaves_editor_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dismiss autocomplete when focus and pointer both leave the editor."""

    mod = import_autocomplete_module()
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: object()),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    autocomplete_stack.input_adapter.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "idle"
