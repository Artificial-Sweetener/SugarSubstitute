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

"""Pure mutation tests for prompt-domain operations."""

from __future__ import annotations


from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.domain.prompt.reorder.mutations import reorder_segments
from substitute.domain.prompt.reorder.derivation import build_reorder_state
from substitute.domain.prompt.reorder.models import (
    PromptReorderState,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
)
from substitute.domain.prompt.reorder.mutations import (
    apply_blank_line_drop_target_to_state,
    apply_line_drop_target_to_state,
    build_base_drag_state,
)
from substitute.domain.prompt.reorder.serialization import serialize_reorder_state


def test_reorder_segments_preserves_nested_content_and_restores_selection() -> None:
    """Reordering should move only segment order and return the moved segment selection."""

    document = parse_prompt_document('alpha, "beta,gamma", (delta,epsilon)')

    result = reorder_segments(
        document,
        dragged_segment_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == '(delta,epsilon), alpha, "beta,gamma"'
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (0, 15)


def test_reorder_segments_splits_multi_tag_emphasis_shell_when_one_chip_moves() -> None:
    """Reordering one chip out of a multi-tag emphasis shell should duplicate the shell."""

    document = parse_prompt_document("(1girl, solo:1.20), blush")

    result = reorder_segments(
        document,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    assert result.text == "(1girl:1.20), blush, (solo:1.20)"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "solo"


def test_reorder_segments_preserves_negative_emphasis_shells() -> None:
    """Reordering emphasized chips should retain their signed shell weights."""

    document = parse_prompt_document("(1girl, solo:-0.05), blush")

    result = reorder_segments(
        document,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    assert result.text == "(1girl:-0.05), blush, (solo:-0.05)"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "solo"


def test_reorder_segments_preserves_base_multiline_separator_structure_under_line_drop() -> (
    None
):
    """Line-drop reorders should preserve multiline separator structure from the hidden base state."""

    document = parse_prompt_document("a, b, c,\nd, e, f")

    result = reorder_segments(
        document,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=1, insertion_index=2),
    )

    assert result.text == "a, c,\nd, e, b, f"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "b"


def test_reorder_segments_can_insert_onto_a_blank_line_inside_a_gap() -> None:
    """Blank-line gap drops should create a new row on the chosen blank line."""

    document = parse_prompt_document("a, b, c,\n\nd, e, f")

    result = reorder_segments(
        document,
        dragged_segment_index=1,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )

    assert result.text == "a, c,\nb,\nd, e, f"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "b"


def test_reorder_segments_targets_each_blank_line_inside_the_user_reported_gap() -> (
    None
):
    """Blank-line drops should land on the exact empty line chosen by the user."""

    document = parse_prompt_document(
        "1girl, detailed eyes, solo, portrait, looking at viewer,\n\n\n\n\n"
        "soft lighting, pastel colors, clean lineart, highres"
    )

    expected_by_blank_line_index = {
        0: "1girl, detailed eyes, portrait, looking at viewer,\nsolo,\n\n\n\n"
        "soft lighting, pastel colors, clean lineart, highres",
        1: "1girl, detailed eyes, portrait, looking at viewer,\n\nsolo,\n\n\n"
        "soft lighting, pastel colors, clean lineart, highres",
        2: "1girl, detailed eyes, portrait, looking at viewer,\n\n\nsolo,\n\n"
        "soft lighting, pastel colors, clean lineart, highres",
        3: "1girl, detailed eyes, portrait, looking at viewer,\n\n\n\nsolo,\n"
        "soft lighting, pastel colors, clean lineart, highres",
    }

    for blank_line_index, expected_text in expected_by_blank_line_index.items():
        result = reorder_segments(
            document,
            dragged_segment_index=2,
            drop_target=PromptGapBlankLineDropTarget(
                gap_index=0,
                blank_line_index=blank_line_index,
            ),
        )

        assert result.text == expected_text
        assert result.selection_range is not None
        assert result.selection_range.slice(result.text) == "solo"


def test_reorder_segments_does_not_move_blank_lines_with_the_dragged_chip() -> None:
    """Line-drop reorders should leave existing blank-line structure in place."""

    document = parse_prompt_document("alpha,\n\nbeta, gamma")

    result = reorder_segments(
        document,
        dragged_segment_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma, alpha,\n\nbeta"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "gamma"


def test_build_base_drag_state_merges_adjacent_separator_slots_when_hiding_an_internal_chip() -> (
    None
):
    """Hiding one internal chip should merge its neighboring separator slots into one slot."""

    document = parse_prompt_document("alpha,\n\nbeta,\ngamma")

    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=1,
    )

    assert base_drag_state == PromptReorderState(
        ordered_segment_indices=(0, 2),
        partition_index_by_segment_index=(0, 0, 0),
        separator_slots=(",\n\n\n",),
        has_trailing_comma=False,
        prefix_text="",
        suffix_text="",
    )


def test_build_reorder_state_preserves_no_space_comma_separator_slots() -> None:
    """Reorder source state should not canonicalize inline comma spacing."""

    document = parse_prompt_document("alpha,beta,gamma")

    state = build_reorder_state(document)

    assert state == PromptReorderState(
        ordered_segment_indices=(0, 1, 2),
        partition_index_by_segment_index=(0, 0, 0),
        separator_slots=(",", ","),
        has_trailing_comma=False,
        prefix_text="",
        suffix_text="",
    )


def test_build_base_drag_state_drops_exposed_edge_separator_when_hiding_first_chip() -> (
    None
):
    """Hiding the first chip should discard the exposed leading separator slot."""

    document = parse_prompt_document("alpha,\nbeta, gamma")

    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=0,
    )

    assert base_drag_state == PromptReorderState(
        ordered_segment_indices=(1, 2),
        partition_index_by_segment_index=(0, 0, 0),
        separator_slots=(", ",),
        has_trailing_comma=False,
        prefix_text="",
        suffix_text="",
    )


def test_build_base_drag_state_drops_exposed_edge_separator_when_hiding_last_chip() -> (
    None
):
    """Hiding the last chip should discard the exposed trailing separator slot."""

    document = parse_prompt_document("alpha,\nbeta, gamma")

    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=2,
    )

    assert base_drag_state == PromptReorderState(
        ordered_segment_indices=(0, 1),
        partition_index_by_segment_index=(0, 0, 0),
        separator_slots=(",\n",),
        has_trailing_comma=False,
        prefix_text="",
        suffix_text="",
    )


def test_line_drop_inserts_default_separator_inside_row_without_splitting_multiline_gap() -> (
    None
):
    """Line-drop should add canonical row separators without splitting multiline gaps."""

    document = parse_prompt_document("a, b, c,\nd, e, f")
    segment_texts = tuple(segment.text for segment in document.segments)
    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=1,
    )

    updated_state = apply_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=1,
        target=PromptLineDropTarget(row_index=1, insertion_index=2),
    )

    assert updated_state.separator_slots == (", ", ",\n", ", ", ", ", ", ")
    assert (
        serialize_reorder_state(updated_state, segment_texts_by_index=segment_texts)
        == "a, c,\nd, e, b, f"
    )


def test_line_drop_uses_existing_no_space_inline_separator_style() -> None:
    """Line-drop insertion should follow the row's source comma spacing."""

    document = parse_prompt_document("alpha,beta,gamma")
    segment_texts = tuple(segment.text for segment in document.segments)
    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=2,
    )

    updated_state = apply_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=2,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert updated_state.separator_slots == (",", ",")
    assert (
        serialize_reorder_state(updated_state, segment_texts_by_index=segment_texts)
        == "gamma,alpha,beta"
    )


def test_blank_line_drop_is_the_only_operation_that_splits_a_multiline_separator() -> (
    None
):
    """Only explicit blank-line targets should split one multiline separator slot into two."""

    document = parse_prompt_document("alpha,\n\n\nbeta, gamma")
    segment_texts = tuple(segment.text for segment in document.segments)
    base_drag_state = build_base_drag_state(
        build_reorder_state(document),
        dragged_segment_index=2,
    )

    line_drop_state = apply_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=2,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    blank_line_drop_state = apply_blank_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=2,
        target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=1),
    )

    assert line_drop_state.separator_slots == (", ", ",\n\n\n")
    assert (
        serialize_reorder_state(line_drop_state, segment_texts_by_index=segment_texts)
        == "gamma, alpha,\n\n\nbeta"
    )
    assert blank_line_drop_state.separator_slots == (",\n\n", ",\n")
    assert (
        serialize_reorder_state(
            blank_line_drop_state,
            segment_texts_by_index=segment_texts,
        )
        == "alpha,\n\ngamma,\nbeta"
    )
