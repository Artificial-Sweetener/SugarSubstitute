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
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)


def test_prompt_mutation_service_returns_refreshed_document_view_after_full_reorder() -> (
    None
):
    """Full reorders should preserve trailing-comma intent in the refreshed semantic snapshot."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "beta, alpha, "
    assert result.document_view.source_text == "beta, alpha, "
    assert result.document_view.has_trailing_comma is True
    assert [segment.display_text for segment in result.document_view.segments] == [
        "beta",
        "alpha",
    ]


def test_prompt_document_service_builds_follow_up_reorder_from_current_layout_view() -> (
    None
):
    """In-session reorder transforms should use authoritative current state."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    session = document_service.build_reorder_session_view(document_view)
    first_base = document_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=2,
    )
    current = document_service.build_preview_drop_state(
        document_view,
        first_base,
        dragged_segment_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    follow_up_base = document_service.build_base_drag_state(
        document_view,
        current.reorder_state,
        current_layout_view=current.layout_view,
        dragged_segment_index=1,
    )
    follow_up = document_service.build_preview_drop_state(
        document_view,
        follow_up_base,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )
    follow_up_layout_view = follow_up.layout_view

    assert document_service.reorder_layout_chip_indices(follow_up_layout_view) == (
        2,
        1,
        0,
    )
    assert (
        document_service.serialize_reorder_layout_view(
            document_view,
            follow_up_layout_view,
        )
        == "gamma, beta, alpha"
    )


def test_prompt_document_service_builds_reorder_session_from_one_snapshot() -> None:
    """Reorder setup should expose chips and layout from one shared domain snapshot."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta\ngamma, delta")

    reorder_session = document_service.build_reorder_session_view(document_view)

    assert [chip.display_text for chip in reorder_session.chips] == [
        "alpha",
        "beta",
        "gamma",
        "delta",
    ]
    assert document_service.reorder_layout_chip_indices(
        reorder_session.layout_view
    ) == (0, 1, 2, 3)
    assert len(reorder_session.layout_view.rows) == 2


def test_prompt_document_service_preserves_lora_inline_separator_layout_slots() -> None:
    """Layout serialization should not force commas between no-comma LoRA chips."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("<lora:a:1.0> <lora:b:1.0>")

    reorder_session = document_service.build_reorder_session_view(document_view)
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        reorder_session.layout_view,
    )

    assert [chip.display_text for chip in reorder_session.chips] == [
        "<lora:a:1.0>",
        "<lora:b:1.0>",
    ]
    assert (
        document_service.serialize_reorder_layout_view(
            document_view,
            reorder_session.layout_view,
        )
        == "<lora:a:1.0> <lora:b:1.0>"
    )
    assert preview_snapshot.text == "<lora:a:1.0> <lora:b:1.0>"


def test_prompt_document_service_moves_lora_chip_without_forcing_commas() -> None:
    """In-session LoRA movement should preserve space-style same-row separators."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("foo <lora:a:1.0> bar")
    reorder_session = document_service.build_reorder_session_view(document_view)

    base = document_service.build_base_drag_state(
        document_view,
        reorder_session.reorder_state,
        current_layout_view=reorder_session.layout_view,
        dragged_segment_index=1,
    )
    preview = document_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_layout = preview.layout_view
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout,
    )

    assert (
        document_service.serialize_reorder_layout_view(document_view, preview_layout)
        == "<lora:a:1.0> foo bar"
    )
    assert preview_snapshot.text == "<lora:a:1.0> foo bar"


def test_prompt_document_service_keeps_exposed_trailing_gap_during_drag_preview() -> (
    None
):
    """Preview layouts should keep blank rows exposed by hiding the final dragged chip."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("1girl,\n\numbrella,")
    current_layout_view = document_service.build_reorder_layout_view(document_view)
    reorder_state = document_service.build_reorder_state_view(document_view)
    base = document_service.build_base_drag_state(
        document_view,
        reorder_state,
        current_layout_view=current_layout_view,
        dragged_segment_index=1,
    )
    preview = document_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )
    preview_layout_view = preview.layout_view
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert preview_layout_view.gaps == (
        PromptReorderGapView(
            gap_index=0,
            separator_text=",\n\n\n",
            blank_line_count=2,
            placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
        ),
    )
    assert preview_snapshot.text == "1girl, umbrella,\n\n\n"


def test_prompt_document_service_can_drop_into_exposed_trailing_gap() -> None:
    """Trailing blank rows should use the same blank-line target rules as row gaps."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("1girl,\n\numbrella,")
    current_layout_view = document_service.build_reorder_layout_view(document_view)
    reorder_state = document_service.build_reorder_state_view(document_view)
    base = document_service.build_base_drag_state(
        document_view,
        reorder_state,
        current_layout_view=current_layout_view,
        dragged_segment_index=1,
    )
    preview = document_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=1,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )
    preview_layout_view = preview.layout_view
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert preview_layout_view == PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1,)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n",
                blank_line_count=0,
            ),
            PromptReorderGapView(
                gap_index=1,
                separator_text=",\n\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )
    assert preview_snapshot.text == "1girl,\numbrella,\n\n"


def test_prompt_document_service_keeps_lifted_final_row_as_blank_target() -> None:
    """Lifting a final single-chip row should leave its origin row target visible."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(
        "1girl,\n\numbrella,\n\nraincoat"
    )
    current_layout_view = document_service.build_reorder_layout_view(document_view)
    reorder_state = document_service.build_reorder_state_view(document_view)
    base = document_service.build_base_drag_state(
        document_view,
        reorder_state,
        current_layout_view=current_layout_view,
        dragged_segment_index=2,
    )
    preview = document_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=2,
        drop_target=PromptGapBlankLineDropTarget(gap_index=1, blank_line_index=1),
    )
    base_drag_layout_view = base.layout_view
    preview_layout_view = preview.layout_view
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert base_drag_layout_view.gaps[-1] == PromptReorderGapView(
        gap_index=1,
        separator_text="\n\n\n",
        blank_line_count=2,
        placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
    )
    assert preview_snapshot.text == "1girl,\n\numbrella,\n\nraincoat\n"


def test_prompt_mutation_service_commits_current_reorder_layout_view() -> None:
    """Layout commits should serialize the full in-session order, not only the last move."""

    mutation_service = PromptMutationService()
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(2, 1, 0)),),
        gaps=(),
    )

    result = mutation_service.reorder_layout(
        "alpha, beta, gamma",
        layout_view=committed_layout_view,
        selected_chip_index=1,
    )

    assert result.text == "gamma, beta, alpha"
    assert result.document_view.source_text == "gamma, beta, alpha"
    assert (result.selection_start, result.selection_end) == (7, 11)


def test_prompt_mutation_service_trims_transient_trailing_gap_on_layout_commit() -> (
    None
):
    """Committing an Alt reorder session should drop preview-only trailing blank rows."""

    mutation_service = PromptMutationService()
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )

    result = mutation_service.reorder_layout(
        "1girl,\n\numbrella,",
        layout_view=committed_layout_view,
        selected_chip_index=1,
    )

    assert result.text == "1girl, umbrella,"
    assert result.document_view.source_text == "1girl, umbrella,"


def test_prompt_mutation_service_reorder_chips_splits_multi_tag_emphasis_shell() -> (
    None
):
    """Reordering one chip out of a grouped emphasis shell should duplicate the shell."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "(1girl, solo:1.20), blush",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    assert result.text == "(1girl:1.20), blush, (solo:1.20)"
    assert result.selection_start is not None
    assert result.selection_end is not None
    assert result.text[result.selection_start : result.selection_end] == "solo"


def test_prompt_mutation_service_reorder_segments_preserves_brace_placeholder_text() -> (
    None
):
    """Reorders should keep brace placeholder text intact inside moved segments."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "{animal, texture}, beta, gamma",
        dragged_chip_index=0,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )

    assert result.text == "beta, {animal, texture}, gamma"
    assert [segment.display_text for segment in result.document_view.segments] == [
        "beta",
        "{animal, texture}",
        "gamma",
    ]


def test_prompt_mutation_service_reorder_segments_preserves_base_separator_structure_under_line_drop() -> (
    None
):
    """Line-drop commits should preserve separator structure from the hidden base state."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "a, b, c,\nd, e, f",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=1, insertion_index=2),
    )

    assert result.text == "a, c,\nd, e, b, f"
    assert result.document_view.source_text == "a, c,\nd, e, b, f"
    assert (result.selection_start, result.selection_end) == (12, 13)


def test_prompt_mutation_service_reorder_segments_does_not_move_blank_line_gap_with_dragged_chip() -> (
    None
):
    """Line-drop commits should leave existing blank-line structure where it already lives."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,\n\nbeta, gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma, alpha,\n\nbeta"
    assert result.document_view.source_text == "gamma, alpha,\n\nbeta"
    assert (result.selection_start, result.selection_end) == (0, 5)


def test_prompt_mutation_service_reorder_segments_can_insert_into_blank_line_gap() -> (
    None
):
    """Blank-line drop targets should insert the moved segment onto the chosen empty row."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,\n\n\n\n\nbeta, gamma",
        dragged_chip_index=2,
        drop_target=PromptGapBlankLineDropTarget(
            gap_index=0,
            blank_line_index=1,
        ),
    )

    assert result.text == "alpha,\n\ngamma,\n\n\nbeta"
    assert result.document_view.source_text == "alpha,\n\ngamma,\n\n\nbeta"
    assert (result.selection_start, result.selection_end) == (8, 13)


def test_prompt_mutation_service_reorder_segments_restores_selection_for_selected_chip() -> (
    None
):
    """Full reorders should restore selection to the explicitly selected segment."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma,alpha,beta"
    assert (result.selection_start, result.selection_end) == (0, 5)


def test_prompt_mutation_service_reorder_segments_always_selects_the_moved_segment() -> (
    None
):
    """Typed drop-target reorders should restore selection to the moved segment."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma,alpha,beta"
    assert (result.selection_start, result.selection_end) == (0, 5)
