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

"""Contract tests for prompt autocomplete acceptance commands."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.presentation.editor.prompt_editor.commands.autocomplete_commands import (
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance_lifecycle import (
    PromptAutocompleteAcceptanceLifecycle,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session_publication import (
    PromptAutocompleteSessionPublication,
)
from tests.support.prompt_editor.autocomplete_support import (
    build_autocomplete_query_state,
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    AutocompleteEditorDouble,
    EmptyAutocompleteGateway,
    MenuCursorDouble,
    autocomplete_session_controller_with_session,
    import_autocomplete_acceptance_module,
    import_autocomplete_module,
    prompt_lora_catalog_item,
)


def test_accept_autocomplete_prepares_tag_command_request() -> None:
    """Delegate selected autocomplete tags to a prepared command request."""

    mod = import_autocomplete_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="cat_", position=6))
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("cat_(animal)", 100),),
            selected_index=0,
            word_start=2,
            word_end=6,
            prefix="cat_",
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    autocomplete_stack.input_adapter.accept_selection(add_comma=True)

    assert editor.accepted_autocomplete == [
        PromptTagAutocompleteAcceptance(
            tag="cat_(animal)",
            prefix="cat_",
            word_start=2,
            word_end=6,
            active_tag_end=6,
            add_comma=True,
        )
    ]
    assert session_controller.has_active_session() is False


def test_acceptance_lifecycle_owns_command_and_session_closure() -> None:
    """Close the prepared session after routing its selected row to commands."""

    mod = import_autocomplete_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="cat_", position=6))
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("cat_(animal)", 100),),
            selected_index=0,
            word_start=2,
            word_end=6,
            prefix="cat_",
        ),
    )
    session_publication = PromptAutocompleteSessionPublication(
        sessions=session_controller,
        presenter=None,
        ghost_text_publisher=None,
        ghost_text_enabled=False,
    )
    lifecycle = PromptAutocompleteAcceptanceLifecycle(
        acceptance_controller=import_autocomplete_acceptance_module().PromptAutocompleteAcceptanceController(
            cursor_position=lambda: cast(Any, editor).textCursor().position(),
            current_source_identity=editor.prompt_command_source_identity,
            execute_acceptance=editor.execute_autocomplete_acceptance,
            complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
        ),
        session_publication=session_publication,
    )

    lifecycle.accept_selection(add_comma=True)

    assert editor.accepted_autocomplete == [
        PromptTagAutocompleteAcceptance(
            tag="cat_(animal)",
            prefix="cat_",
            word_start=2,
            word_end=6,
            active_tag_end=6,
            add_comma=True,
        )
    ]
    assert session_controller.has_active_session() is False


def test_acceptance_controller_accepts_trigger_word_as_tag_command_request() -> None:
    """Accept LoRA trigger-word rows through the tag command request."""

    mod = import_autocomplete_acceptance_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="midna", position=5))
    controller = mod.PromptAutocompleteAcceptanceController(
        cursor_position=lambda: cast(Any, editor).textCursor().position(),
        current_source_identity=editor.prompt_command_source_identity,
        execute_acceptance=editor.execute_autocomplete_acceptance,
        complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
    )
    session = AutocompleteSession(
        mode="tag",
        suggestions=(
            PromptAutocompleteSuggestion(
                "midna helmet",
                popularity=None,
                source_label="Friendly Midna",
                source_kind="lora_trigger",
            ),
        ),
        selected_index=0,
        word_start=0,
        word_end=5,
        active_tag_end=5,
        prefix="midna",
    )

    outcome = controller.accept_session(
        session,
        source_identity=None,
        add_comma=False,
    )

    assert outcome.status == "accepted"
    assert editor.accepted_autocomplete == [
        PromptTagAutocompleteAcceptance(
            tag="midna helmet",
            prefix="midna",
            word_start=0,
            word_end=5,
            active_tag_end=5,
            add_comma=False,
        )
    ]


def test_acceptance_controller_accepts_wildcard_command_request() -> None:
    """Accept wildcard rows through the wildcard command request."""

    mod = import_autocomplete_acceptance_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="{ani}", position=4))
    controller = mod.PromptAutocompleteAcceptanceController(
        cursor_position=lambda: cast(Any, editor).textCursor().position(),
        current_source_identity=editor.prompt_command_source_identity,
        execute_acceptance=editor.execute_autocomplete_acceptance,
        complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
    )
    session = AutocompleteSession(
        mode="wildcard",
        suggestions=(PromptAutocompleteSuggestion("animal"),),
        selected_index=0,
        prefix="ani",
        wildcard_query=PromptWildcardAutocompleteQuery(
            prefix="ani",
            opener_start=0,
            content_start=1,
            cursor_position=4,
            replacement_end=5,
        ),
    )

    outcome = controller.accept_session(
        session,
        source_identity=None,
        add_comma=True,
    )

    assert outcome.status == "accepted"
    assert editor.accepted_autocomplete == [
        PromptWildcardAutocompleteAcceptance(
            wildcard_name="animal",
            opener_start=0,
            replacement_end=5,
        )
    ]


def test_accept_scene_selection_prepares_scene_command_request() -> None:
    """Delegate selected scene titles to the marker-title command range."""

    mod = import_autocomplete_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="**po", position=4))
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="scene",
            suggestions=(PromptAutocompleteSuggestion("portrait (close)", None),),
            selected_index=0,
            word_start=2,
            word_end=4,
            prefix="po",
            scene_query=PromptSceneAutocompleteQuery(
                prefix="po",
                marker_start=0,
                title_start=2,
                cursor_position=4,
                replacement_end=4,
            ),
        ),
    )
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    autocomplete_stack.input_adapter.accept_selection(add_comma=True)

    assert editor.accepted_autocomplete == [
        PromptSceneAutocompleteAcceptance(
            title="portrait (close)",
            title_start=2,
            replacement_end=4,
        )
    ]
    assert session_controller.has_active_session() is False


def test_acceptance_controller_rejects_stale_source_before_command_execution() -> None:
    """Fail closed when the prepared source identity is stale."""

    mod = import_autocomplete_acceptance_module()
    prepared_identity = PromptSourceIdentity(source_revision=2, source_length=5)
    editor = AutocompleteEditorDouble(
        MenuCursorDouble(text="midna", position=5),
        source_identity=PromptSourceIdentity(source_revision=3, source_length=5),
    )
    controller = mod.PromptAutocompleteAcceptanceController(
        cursor_position=lambda: cast(Any, editor).textCursor().position(),
        current_source_identity=editor.prompt_command_source_identity,
        execute_acceptance=editor.execute_autocomplete_acceptance,
        complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
    )
    session = AutocompleteSession(
        mode="tag",
        suggestions=(PromptAutocompleteSuggestion("midna helmet"),),
        selected_index=0,
        word_start=0,
        word_end=5,
        active_tag_end=5,
        prefix="midna",
    )

    outcome = controller.accept_session(
        session,
        source_identity=prepared_identity,
        add_comma=False,
    )

    assert outcome.status == "rejected"
    assert outcome.reason == "stale_source"
    assert editor.accepted_autocomplete == []


def test_acceptance_controller_does_not_commit_lora_chip_after_rejection() -> None:
    """Materialize LoRA chips only after successful command execution."""

    mod = import_autocomplete_acceptance_module()
    editor = AutocompleteEditorDouble(
        MenuCursorDouble(text="<lora:mid", position=9),
        command_result=PromptCommandResult.rejected(
            "accept_lora_autocomplete",
            reason="stale_source",
        ),
    )
    controller = mod.PromptAutocompleteAcceptanceController(
        cursor_position=lambda: cast(Any, editor).textCursor().position(),
        current_source_identity=editor.prompt_command_source_identity,
        execute_acceptance=editor.execute_autocomplete_acceptance,
        complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
    )
    session = AutocompleteSession(
        mode="lora",
        selected_index=0,
        lora_candidates=(
            PromptLoraAutocompleteCandidate(
                item=prompt_lora_catalog_item(),
                score=10,
                display_text="CivitAI Midna",
                display_completion_suffix="AI Midna",
                replacement_text=r"<lora:illustrious\characters\raw_midna:1>",
                match_kind="display",
            ),
        ),
        lora_query=PromptLoraAutocompleteQuery(
            query_text="mid",
            token_start=0,
            token_end=9,
            name_start=6,
            name_end=9,
            replacement_start=0,
            replacement_end=9,
            typed_weight_text=None,
            has_closing_bracket=False,
        ),
    )

    outcome = controller.accept_session(
        session,
        source_identity=None,
        add_comma=False,
    )

    assert outcome.status == "rejected"
    assert editor.accepted_autocomplete == [
        PromptLoraAutocompleteAcceptance(
            replacement_text=r"<lora:illustrious\characters\raw_midna:1>",
            replacement_start=0,
            replacement_end=9,
        )
    ]
    assert editor.lora_autocomplete_commit_calls == 0


def test_accept_lora_autocomplete_prepares_lora_command_request() -> None:
    """LoRA accept delegates a scheduler-safe replacement command request."""

    cursor = MenuCursorDouble(text="<lora:Civ:1.2>", position=len("<lora:Civ"))
    editor = AutocompleteEditorDouble(cursor)
    autocomplete_stack = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog(
            (prompt_lora_catalog_item(),)
        ),
        lora_thumbnail_cache_available=True,
    )
    autocomplete_stack.query_result_lifecycle.refresh_results_for_query_state(
        build_autocomplete_query_state(
            source_text="<lora:Civ:1.2>",
            lora_query=PromptLoraAutocompleteQuery(
                query_text="Civ",
                token_start=0,
                token_end=len("<lora:Civ:1.2>"),
                name_start=6,
                name_end=9,
                replacement_start=0,
                replacement_end=len("<lora:Civ:1.2>"),
                typed_weight_text="1.2",
                has_closing_bracket=True,
            ),
        )
    )

    autocomplete_stack.input_adapter.accept_lora_selection()

    assert editor.accepted_autocomplete == [
        PromptLoraAutocompleteAcceptance(
            replacement_text=r"<lora:illustrious\characters\raw_midna:1.2>",
            replacement_start=0,
            replacement_end=len("<lora:Civ:1.2>"),
        )
    ]
    assert editor.lora_autocomplete_commit_calls == 1
    assert autocomplete_stack.session_controller.session.mode == "none"


class _StaticPromptLoraCatalog:
    """Return deterministic LoRA rows for coordinator tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store catalog rows."""

        self._items = items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows."""

        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured LoRA rows without simulating backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the configured LoRA row matching one prompt name."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None
