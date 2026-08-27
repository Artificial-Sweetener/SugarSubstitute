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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
    PromptLoraAutocompleteService,
)


from ..support.lora_catalog import _lora_item


def test_prompt_document_service_builds_empty_lora_autocomplete_query() -> None:
    """Typing the LoRA token prefix should activate LoRA autocomplete immediately."""

    document_service = PromptDocumentService()
    text = "<lora:"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query == PromptLoraAutocompleteQuery(
        query_text="",
        token_start=0,
        token_end=len(text),
        name_start=len("<lora:"),
        name_end=len(text),
        replacement_start=0,
        replacement_end=len(text),
        typed_weight_text=None,
        has_closing_bracket=False,
    )


def test_prompt_document_service_builds_lora_autocomplete_query_for_name_prefix() -> (
    None
):
    """LoRA autocomplete should expose the typed name prefix and token bounds."""

    document_service = PromptDocumentService()
    text = r"<lora:Min"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "Min"
    assert query.name_start == len("<lora:")
    assert query.name_end == len(text)
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)
    assert query.typed_weight_text is None


def test_prompt_document_service_preserves_lora_path_fragment_query() -> None:
    """Directory-qualified LoRA fragments should remain intact for matching."""

    document_service = PromptDocumentService()
    text = r"<lora:illustrious\characters\Min"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"illustrious\characters\Min"


def test_prompt_document_service_builds_lora_query_inside_closed_name_slot() -> None:
    """Editing a closed LoRA name should still allow replacing the whole token."""

    document_service = PromptDocumentService()
    text = "<lora:Mineru:0.8>"
    cursor_position = text.index("n")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "Mi"
    assert query.typed_weight_text == "0.8"
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)
    assert query.has_closing_bracket is True


def test_prompt_document_service_lora_query_ignores_nonnumeric_weight_suffix() -> None:
    """LoRA autocomplete must not preserve malformed suffixes as weights."""

    document_service = PromptDocumentService()
    text = r"<lora:Pony\Concept\springrider_Pony_v1:Pony\Style\cutedoodle_XL-000012>"
    cursor_position = text.index(":Pony\\Style")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"Pony\Concept\springrider_Pony_v1"
    assert query.typed_weight_text is None
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)


def test_prompt_document_service_lora_query_does_not_cross_later_lora_tag() -> None:
    """An incomplete LoRA query must not consume a following LoRA token."""

    document_service = PromptDocumentService()
    text = r"<lora:Pony\Concept\springrider_Pony_v1" + "\n<lora:testlora:1.00>"
    cursor_position = text.index("\n")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"Pony\Concept\springrider_Pony_v1"
    assert query.typed_weight_text is None
    assert query.replacement_start == 0
    assert query.replacement_end == cursor_position
    assert query.has_closing_bracket is False


def test_prompt_document_service_lora_query_ignores_weight_slot_and_closed_tail() -> (
    None
):
    """LoRA autocomplete should only activate while editing the name slot."""

    document_service = PromptDocumentService()
    text = "<lora:Mineru:0.8>"

    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=text.index("0.8") + 1,
            has_selection=False,
        )
        is None
    )
    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=len(text),
            has_selection=False,
        )
        is None
    )
    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=text.index("Mineru"),
            has_selection=True,
        )
        is None
    )


def test_lora_autocomplete_ranks_replaces_and_builds_friendly_ghost_text() -> None:
    """LoRA ranking should separate display completion from raw insertion text."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="Civit",
        token_start=0,
        token_end=11,
        name_start=6,
        name_end=11,
        replacement_start=0,
        replacement_end=11,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Other",
                basename="Other",
                prompt_name=r"illustrious\characters\civit_midna",
            ),
            _lora_item(
                display_name="CivitAI Midna",
                basename="raw_midna",
                prompt_name=r"illustrious\characters\raw_midna",
            ),
        ),
    )

    assert [candidate.display_text for candidate in candidates] == [
        "CivitAI Midna",
        "Other",
    ]
    assert candidates[0].display_completion_suffix == "AI Midna"
    assert (
        candidates[0].replacement_text
        == r"<lora:illustrious\characters\raw_midna:1.00>"
    )


def test_lora_autocomplete_matches_basename_and_preserves_existing_weight() -> None:
    """Basename matching should work when provider display names are unavailable."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="Mid",
        token_start=0,
        token_end=15,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=15,
        typed_weight_text="1.2",
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
            ),
        ),
    )

    assert candidates[0].display_text == "Midna"
    assert candidates[0].display_completion_suffix == "na"
    assert candidates[0].replacement_text == r"<lora:illustrious\characters\Midna:1.2>"


def test_lora_autocomplete_defaults_malformed_preserved_weight_text() -> None:
    """LoRA replacement text should remain scheduler-safe for malformed suffixes."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text=r"Pony\Concept\springrider_Pony_v1",
        token_start=0,
        token_end=48,
        name_start=6,
        name_end=38,
        replacement_start=0,
        replacement_end=48,
        typed_weight_text="testlora",
        has_closing_bracket=True,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Springrider Pony",
                basename="springrider_Pony_v1",
                prompt_name=r"Pony\Concept\springrider_Pony_v1",
            ),
        ),
    )

    assert candidates[0].replacement_text == (
        r"<lora:Pony\Concept\springrider_Pony_v1:1.00>"
    )


def test_lora_autocomplete_matches_directory_paths_and_keeps_collisions_safe() -> None:
    """Path queries should find colliding basenames and insert qualified names."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="sd15/characters/Mid",
        token_start=0,
        token_end=24,
        name_start=6,
        name_end=24,
        replacement_start=0,
        replacement_end=24,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
                collision_count=2,
            ),
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"sd15\characters\Midna",
                collision_count=2,
            ),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].display_completion_suffix == "na"
    assert candidates[0].replacement_text == r"<lora:sd15\characters\Midna:1.00>"


def test_lora_autocomplete_omits_ghost_suffix_for_substring_match() -> None:
    """Substring matches should not project misleading ghost text."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="dna",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
            ),
        ),
    )

    assert candidates[0].display_completion_suffix == ""


def test_lora_autocomplete_returns_all_ranked_matches_without_cap() -> None:
    """LoRA autocomplete should not hide matches behind a presentation cap."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="LoRA",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=10,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        tuple(
            _lora_item(
                display_name=f"LoRA {index:02}",
                basename=f"LoRA_{index:02}",
                prompt_name=rf"illustrious\characters\LoRA_{index:02}",
            )
            for index in range(55)
        ),
    )

    assert len(candidates) == 55
    assert candidates[0].display_text == "LoRA 00"
    assert candidates[-1].display_text == "LoRA 54"
