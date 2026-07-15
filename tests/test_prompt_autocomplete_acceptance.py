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

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptLoraAutocompleteCandidate,
    PromptLoraCatalogItem,
    PromptLoraAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.prompt_autocomplete_test_helpers import build_test_autocomplete_coordinator
from tests.prompt_editor_controller_test_helpers import (
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
    closed: list[bool] = []
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
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    setattr(coordinator, "dismiss_autocomplete", lambda _reason: closed.append(True))

    coordinator.accept_selection(add_comma=True)

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
    assert closed == [True]


def test_acceptance_controller_accepts_trigger_word_as_tag_command_request() -> None:
    """Accept LoRA trigger-word rows through the tag command request."""

    mod = import_autocomplete_acceptance_module()
    editor = AutocompleteEditorDouble(MenuCursorDouble(text="midna", position=5))
    controller = mod.PromptAutocompleteAcceptanceController(editor=editor)
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
    controller = mod.PromptAutocompleteAcceptanceController(editor=editor)
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
    closed: list[bool] = []
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
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    setattr(coordinator, "dismiss_autocomplete", lambda _reason: closed.append(True))

    coordinator.accept_selection(add_comma=True)

    assert editor.accepted_autocomplete == [
        PromptSceneAutocompleteAcceptance(
            title="portrait (close)",
            title_start=2,
            replacement_end=4,
        )
    ]
    assert closed == [True]


def test_acceptance_controller_rejects_stale_source_before_command_execution() -> None:
    """Fail closed when the prepared source identity is stale."""

    mod = import_autocomplete_acceptance_module()
    prepared_identity = PromptCommandSourceIdentity(source_revision=2, source_length=5)
    editor = AutocompleteEditorDouble(
        MenuCursorDouble(text="midna", position=5),
        source_identity=PromptCommandSourceIdentity(source_revision=3, source_length=5),
    )
    controller = mod.PromptAutocompleteAcceptanceController(editor=editor)
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
    controller = mod.PromptAutocompleteAcceptanceController(editor=editor)
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
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog(
            (prompt_lora_catalog_item(),)
        ),
        lora_thumbnail_cache_available=True,
    )
    setattr(coordinator, "_present_panel", lambda: None)
    setattr(coordinator, "_publish_inline_completion_preview", lambda: None)
    coordinator.refresh_for_lora_query(
        PromptLoraAutocompleteQuery(
            query_text="Civ",
            token_start=0,
            token_end=len("<lora:Civ:1.2>"),
            name_start=6,
            name_end=9,
            replacement_start=0,
            replacement_end=len("<lora:Civ:1.2>"),
            typed_weight_text="1.2",
            has_closing_bracket=True,
        )
    )

    coordinator.accept_lora_selection()

    assert editor.accepted_autocomplete == [
        PromptLoraAutocompleteAcceptance(
            replacement_text=r"<lora:illustrious\characters\raw_midna:1.2>",
            replacement_start=0,
            replacement_end=len("<lora:Civ:1.2>"),
        )
    ]
    assert editor.lora_autocomplete_commit_calls == 1
    assert coordinator._sessions.session.mode == "none"


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
