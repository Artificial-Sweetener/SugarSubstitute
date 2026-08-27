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

"""Verify autocomplete session state-controller contracts."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryState,
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextSourceSnapshot,
)


from tests.presentation.editor.prompt_editor.autocomplete.session_controller_support import (
    _lora_candidate,
)


def test_session_controller_preserves_selected_tag_across_result_replacement() -> None:
    """Tag result replacement should preserve the selected suggestion identity."""

    controller = PromptAutocompleteSessionController()
    source_identity = PromptSourceIdentity(source_revision=4, source_length=3)
    ghost_snapshot = PromptAutocompleteGhostTextSourceSnapshot(
        source_revision=4,
        source_length=3,
        cursor_position=3,
        source_text="1gi",
    )
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girls", 3_424),),
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
        source_identity=source_identity,
        ghost_text_source_snapshot=ghost_snapshot,
    )

    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("1girl", 5_889_398),
                PromptAutocompleteSuggestion("1girls", 3_424),
            ),
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
        source_identity=source_identity,
        ghost_text_source_snapshot=ghost_snapshot,
    )

    assert controller.session.selected_index == 1
    assert controller.source_identity is source_identity
    assert controller.ghost_text_source_snapshot is ghost_snapshot


def test_session_controller_moves_selection_and_clears_state() -> None:
    """Selection movement should wrap before clear resets transient state."""

    controller = PromptAutocompleteSessionController()
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("alpha"),
                PromptAutocompleteSuggestion("beta"),
            ),
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert controller.move_suggestion_selection(1) is True
    assert controller.session.selected_index == 1
    assert controller.move_suggestion_selection(1) is True
    assert controller.session.selected_index == 0
    assert controller.move_suggestion_selection(-1) is True
    assert controller.session.selected_index == 1

    controller.dismiss("escape")

    assert controller.session.mode == "none"
    assert controller.source_identity is None
    assert controller.ghost_text_source_snapshot is None


def test_session_controller_preserves_selected_lora_candidate() -> None:
    """LoRA result replacement should preserve the selected prompt name."""

    controller = PromptAutocompleteSessionController()
    midna = _lora_candidate("midna")
    other = _lora_candidate("other")
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
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(midna,),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(other, midna),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert controller.session.selected_index == 1
    assert controller.session.lora_candidates[1].item.prompt_name == "midna"


def test_session_controller_activation_index_can_force_missing_selection() -> None:
    """Presenter activation should mirror the index before acceptance validates it."""

    controller = PromptAutocompleteSessionController()
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("alpha"),),
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    controller.select_index(-1)

    assert controller.session.selected_index == -1
    assert not controller.has_active_session()


def test_session_controller_retargets_compatible_tag_without_replacing_rows() -> None:
    """Compatible typing should keep rows selected while updating query geometry."""

    controller = PromptAutocompleteSessionController()
    suggestions = (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=suggestions,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=PromptSourceIdentity(source_revision=1, source_length=2),
        ghost_text_source_snapshot=None,
    )
    controller.select_index(1)

    retargeted = controller.retarget(
        PromptAutocompleteQueryState(
            source_revision=2,
            source_length=3,
            source_text="1gi",
            cursor_position=3,
            has_selection=False,
            source_identity=PromptSourceIdentity(
                source_revision=2,
                source_length=3,
            ),
            tag_query=PromptAutocompleteQuery(
                prefix="1gi",
                word_start=0,
                word_end=3,
                active_tag_end=3,
            ),
        )
    )

    assert retargeted is True
    assert controller.state.lifecycle == "refreshing"
    assert controller.session.suggestions is suggestions
    assert controller.session.selected_index == 1
    assert controller.session.prefix == "1gi"
    assert controller.session.word_end == 3
    assert controller.ghost_text_source_snapshot is not None
    assert controller.ghost_text_source_snapshot.cursor_position == 3
