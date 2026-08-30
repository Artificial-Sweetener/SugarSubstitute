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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations


from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from tests.support.prompt_editor.autocomplete_support import (
    RecordingPromptAutocompleteGateway,
    build_test_autocomplete_stack,
)


from tests.presentation.editor.prompt_editor.autocomplete.phase27_support import (
    _key_event,
    _lora_item,
)


def test_phase27_coordinator_focus_navigation_mouse_and_clear_state() -> None:
    """Coordinator session behavior should preserve keyboard, mouse, and clear semantics."""

    class _Presenter:
        """Record panel operations without constructing widgets."""

        def __init__(self) -> None:
            """Initialize presenter state."""

            self.hidden = 0
            self.presented: list[object] = []
            self.activation_handler: Callable[[object], None] | None = None
            self.selection_handler: Callable[[int], None] | None = None

        @property
        def panel(self) -> None:
            """Return no live panel widget."""

            return None

        def present_session(self, session: object) -> bool:
            """Record one rendered session and report visible presentation."""

            self.presented.append(session)
            return True

        def set_activation_handler(
            self,
            handler: Callable[[object], None] | None,
        ) -> None:
            """Store activation callback."""

            self.activation_handler = handler

        def set_selection_changed_handler(
            self,
            handler: Callable[[int], None] | None,
        ) -> None:
            """Store selection callback."""

            self.selection_handler = handler

        def set_visibility_changed_handler(
            self,
            handler: Callable[[bool], None] | None,
        ) -> None:
            """Accept visibility handler wiring."""

            _ = handler

        def current_index(self) -> int:
            """Return the first row as selected."""

            return 0

        def move_lora_selection(self, direction: str) -> int | None:
            """Decline LoRA wall movement in this baseline test."""

            _ = direction
            return None

        def panel_under_mouse(self) -> bool:
            """Return that the mouse is outside the panel."""

            return False

        def panel_visible(self) -> bool:
            """Return that panel presentation is visible during active sessions."""

            return True

        def hide(self) -> None:
            """Record one hide request."""

            self.hidden += 1

    class _Editor:
        """Provide focus and acceptance seams for coordinator tests."""

        def __init__(self) -> None:
            """Initialize command recording."""

            self.focus_calls = 0
            self.accepted: list[object] = []

        def setFocus(self) -> None:  # noqa: N802
            """Record focus restoration."""

            self.focus_calls += 1

        def execute_autocomplete_acceptance(self, acceptance: object) -> object:
            """Record accepted command payload."""

            self.accepted.append(acceptance)
            return PromptCommandResult.completed("accept_autocomplete")

        def prompt_command_source_identity(self) -> None:
            """Return no source identity."""

            return None

        def commit_lora_autocomplete_replacement(self) -> None:
            """Accept LoRA post-commit calls."""

    presenter = _Presenter()

    editor = _Editor()
    session_controller = PromptAutocompleteSessionController()
    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    autocomplete_stack = build_test_autocomplete_stack(
        cast(Any, editor),
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        autocomplete_presenter=cast(Any, presenter),
        autocomplete_session_controller=session_controller,
    )

    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Down))
        is True
    )
    assert session_controller.session.selected_index == 1
    assert presenter.presented

    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Down))
        is True
    )
    assert session_controller.session.selected_index == 0
    assert session_controller.session.mode == "tag"
    assert presenter.hidden == 0

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Left))
        is False
    )
    assert session_controller.session.mode == "none"
    assert presenter.hidden >= 1

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    autocomplete_stack.input_adapter.activate_suggestion(0)

    assert editor.focus_calls == 1
    assert editor.accepted
    assert presenter.hidden >= 1

    autocomplete_stack.input_adapter.dismiss_autocomplete("escape")

    assert session_controller.session.mode == "none"
    assert presenter.hidden >= 2


def test_phase27_coordinator_lora_vertical_boundaries_stay_handled() -> None:
    """LoRA autocomplete should keep vertical boundary arrows inside the picker."""

    class _Presenter:
        """Record panel operations while declining wall-owned movement."""

        def __init__(self) -> None:
            """Initialize hidden counter and handler storage."""

            self.hidden = 0

        @property
        def panel(self) -> None:
            """Return no live panel widget."""

            return None

        def present_session(self, session: object) -> bool:
            """Accept render requests and report visible presentation."""

            _ = session
            return True

        def set_activation_handler(
            self,
            handler: Callable[[object], None] | None,
        ) -> None:
            """Accept activation handler wiring."""

            _ = handler

        def set_selection_changed_handler(
            self,
            handler: Callable[[int], None] | None,
        ) -> None:
            """Accept selection handler wiring."""

            _ = handler

        def set_visibility_changed_handler(
            self,
            handler: Callable[[bool], None] | None,
        ) -> None:
            """Accept visibility handler wiring."""

            _ = handler

        def current_index(self) -> int:
            """Return the current first-row index."""

            return 0

        def move_lora_selection(self, direction: str) -> int | None:
            """Decline presenter-owned LoRA movement."""

            _ = direction
            return None

        def panel_under_mouse(self) -> bool:
            """Return that the pointer is outside the panel."""

            return False

        def panel_visible(self) -> bool:
            """Return that panel presentation is visible during active sessions."""

            return True

        def hide(self) -> None:
            """Record one hide request."""

            self.hidden += 1

    class _Editor:
        """Provide command seams required by the coordinator."""

        def execute_autocomplete_acceptance(self, acceptance: object) -> object:
            """Return a completed command result."""

            _ = acceptance
            return PromptCommandResult.completed("accept_autocomplete")

        def prompt_command_source_identity(self) -> None:
            """Return no source identity."""

            return None

        def commit_lora_autocomplete_replacement(self) -> None:
            """Accept LoRA post-commit calls."""

        def setFocus(self) -> None:  # noqa: N802
            """Accept focus restoration calls."""

    query = PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )
    session_controller = PromptAutocompleteSessionController()
    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(),
                    score=1,
                    display_text="Midna",
                    display_completion_suffix="na",
                    replacement_text="<lora:midna:1>",
                    match_kind="display",
                ),
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(prompt_name="midna_alt"),
                    score=2,
                    display_text="Midna Alt",
                    display_completion_suffix="na Alt",
                    replacement_text="<lora:midna_alt:1>",
                    match_kind="display",
                ),
            ),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    presenter = _Presenter()
    autocomplete_stack = build_test_autocomplete_stack(
        cast(Any, _Editor()),
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        autocomplete_presenter=cast(Any, presenter),
        autocomplete_session_controller=session_controller,
        lora_thumbnail_cache_available=True,
    )

    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Up))
        is True
    )
    assert session_controller.session.selected_index == 0
    assert session_controller.session.mode == "lora"
    assert presenter.hidden == 0

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(),
                    score=1,
                    display_text="Midna",
                    display_completion_suffix="na",
                    replacement_text="<lora:midna:1>",
                    match_kind="display",
                ),
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(prompt_name="midna_alt"),
                    score=2,
                    display_text="Midna Alt",
                    display_completion_suffix="na Alt",
                    replacement_text="<lora:midna_alt:1>",
                    match_kind="display",
                ),
            ),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Down))
        is True
    )
    assert session_controller.session.selected_index == 1
    assert (
        autocomplete_stack.input_adapter.handle_key_press(_key_event(Qt.Key.Key_Down))
        is True
    )
    assert session_controller.session.selected_index == 1
    assert session_controller.session.mode == "lora"
    assert presenter.hidden == 0
