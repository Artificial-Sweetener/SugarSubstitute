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

"""Contract tests for prompt autocomplete ghost-text projection."""

from __future__ import annotations

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.prompt_editor_controller_test_helpers import (
    TextAutocompleteEditorDouble,
    autocomplete_ghost_text_source_snapshot,
    import_autocomplete_ghost_text_module,
    prompt_lora_catalog_item,
)


def test_selected_autocomplete_suffix_uses_literal_prefix_matching() -> None:
    """Accept underscores as an alternate typing form for spaces."""

    mod = import_autocomplete_ghost_text_module()
    session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("long hair", 3_424),),
        selected_index=0,
        prefix="long_ha",
    )

    assert mod.selected_autocomplete_suffix(session) == "ir"


def test_selected_autocomplete_suffix_clears_when_prefix_no_longer_matches() -> None:
    """Hide ghost text when the selected suggestion no longer matches."""

    mod = import_autocomplete_ghost_text_module()
    session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("apple", 10),),
        selected_index=0,
        prefix="1gi",
    )

    assert mod.selected_autocomplete_suffix(session) == ""


def test_autocomplete_ghost_text_publisher_publishes_tag_preview() -> None:
    """Publish a source-safe tag preview state."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("long ha")
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)

    publisher.publish_for_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("long hair", 3_424),),
            selected_index=0,
            word_start=0,
            word_end=7,
            active_tag_end=7,
            prefix="long ha",
        ),
        source_snapshot=autocomplete_ghost_text_source_snapshot(mod, "long ha"),
    )

    assert editor.autocomplete_preview_state == mod.PromptAutocompletePreviewState(
        source_position=7,
        suffix_text="ir",
    )


def test_autocomplete_ghost_text_publisher_clears_stale_tag_cursor() -> None:
    """Clear previews when the cursor leaves the query."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("long hair")
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)

    publisher.publish_for_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("long hair", 3_424),),
            selected_index=0,
            word_start=0,
            word_end=4,
            active_tag_end=4,
            prefix="long",
        ),
        source_snapshot=autocomplete_ghost_text_source_snapshot(mod, "long hair"),
    )

    assert editor.autocomplete_preview_state is None


def test_autocomplete_ghost_text_publisher_trims_existing_right_text() -> None:
    """Avoid duplicating source text right of the caret."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("long hair")
    editor.cursor_position = 6
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)

    publisher.publish_for_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("long hair", 3_424),),
            selected_index=0,
            word_start=0,
            word_end=6,
            active_tag_end=9,
            prefix="long h",
        ),
        source_snapshot=autocomplete_ghost_text_source_snapshot(
            mod,
            "long hair",
            cursor_position=6,
        ),
    )

    assert editor.autocomplete_preview_state is None


def test_autocomplete_ghost_text_publisher_publishes_wildcard_preview() -> None:
    """Publish wildcard completion with the closing brace."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("{an")
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)

    publisher.publish_for_session(
        AutocompleteSession(
            mode="wildcard",
            suggestions=(PromptAutocompleteSuggestion("animal"),),
            selected_index=0,
            prefix="an",
            wildcard_query=PromptWildcardAutocompleteQuery(
                prefix="an",
                opener_start=0,
                content_start=1,
                cursor_position=3,
                replacement_end=3,
            ),
        ),
        source_snapshot=autocomplete_ghost_text_source_snapshot(mod, "{an"),
    )

    assert editor.autocomplete_preview_state == mod.PromptAutocompletePreviewState(
        source_position=3,
        suffix_text="imal}",
    )


def test_autocomplete_ghost_text_publisher_publishes_lora_preview() -> None:
    """Publish the selected LoRA display suffix."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("<lora:mid")
    item = prompt_lora_catalog_item(
        display_name="Midna Helmet",
        basename="midnaHelmet",
        prompt_name="characters/midnaHelmet",
    )
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)

    publisher.publish_for_session(
        AutocompleteSession(
            mode="lora",
            selected_index=0,
            lora_candidates=(
                PromptLoraAutocompleteCandidate(
                    item=item,
                    score=10,
                    display_text="Midna Helmet",
                    display_completion_suffix="na Helmet",
                    replacement_text="<lora:characters/midnaHelmet:1>",
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
        ),
        source_snapshot=autocomplete_ghost_text_source_snapshot(mod, "<lora:mid"),
    )

    assert editor.autocomplete_preview_state == mod.PromptAutocompletePreviewState(
        source_position=9,
        suffix_text="na Helmet",
    )


def test_autocomplete_ghost_text_publisher_skips_duplicate_publication() -> None:
    """Avoid republishing identical prepared state."""

    mod = import_autocomplete_ghost_text_module()
    editor = TextAutocompleteEditorDouble("1gi")
    publisher = mod.PromptAutocompleteGhostTextPublisher(preview_sink=editor)
    session = AutocompleteSession(
        mode="tag",
        suggestions=(PromptAutocompleteSuggestion("1girl", 5_889_398),),
        selected_index=0,
        word_start=0,
        word_end=3,
        active_tag_end=3,
        prefix="1gi",
    )

    source_snapshot = autocomplete_ghost_text_source_snapshot(mod, "1gi")
    publisher.publish_for_session(session, source_snapshot=source_snapshot)
    publisher.publish_for_session(session, source_snapshot=source_snapshot)

    assert editor.autocomplete_preview_updates == [
        mod.PromptAutocompletePreviewState(
            source_position=3,
            suffix_text="rl",
        )
    ]
