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

from decimal import Decimal

from substitute.domain.prompt import (
    PromptReorderState,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    SourceRange,
    apply_blank_line_drop_target_to_state,
    apply_line_drop_target_to_state,
    build_base_drag_state,
    build_reorder_chips,
    build_reorder_state,
    build_reorder_state_from_chips,
    decrease_emphasis,
    increase_emphasis,
    parse_prompt_document,
    reorder_segments,
    replace_span_content,
    set_emphasis_weight,
    serialize_reorder_state_for_chips,
    serialize_reorder_state,
)


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
        separator_slots=(",\n\n\n",),
        has_trailing_comma=False,
    )


def test_build_reorder_state_preserves_no_space_comma_separator_slots() -> None:
    """Reorder source state should not canonicalize inline comma spacing."""

    document = parse_prompt_document("alpha,beta,gamma")

    state = build_reorder_state(document)

    assert state == PromptReorderState(
        ordered_segment_indices=(0, 1, 2),
        separator_slots=(",", ","),
        has_trailing_comma=False,
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
        separator_slots=(", ",),
        has_trailing_comma=False,
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
        separator_slots=(",\n",),
        has_trailing_comma=False,
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


def test_reorder_serialization_middle_chip_owns_rendered_text_and_following_separator() -> (
    None
):
    """Middle-chip ownership should include the rendered chip shell plus its separator slot."""

    document = parse_prompt_document("alpha, beta, gamma")
    chips = build_reorder_chips(document)
    serialization = serialize_reorder_state_for_chips(
        build_reorder_state_from_chips(document, chips),
        chips_by_index=chips,
    )

    assert tuple(
        source_range.slice(serialization.text)
        for source_range in serialization.owned_ranges_by_index[1]
    ) == ("beta", ", ")


def test_reorder_serialization_final_chip_owns_only_its_rendered_text() -> None:
    """Final-chip ownership should not include a trailing separator slot."""

    document = parse_prompt_document("alpha, beta, gamma")
    chips = build_reorder_chips(document)
    serialization = serialize_reorder_state_for_chips(
        build_reorder_state_from_chips(document, chips),
        chips_by_index=chips,
    )

    assert tuple(
        source_range.slice(serialization.text)
        for source_range in serialization.owned_ranges_by_index[2]
    ) == ("gamma",)


def test_reorder_chips_split_uncommaed_hard_lines() -> None:
    """A hard source line break must terminate reorder chip ownership."""

    document = parse_prompt_document("test test\ntest test,")
    chips = build_reorder_chips(document)

    assert [chip.text for chip in chips] == ["test test", "test test"]
    assert [chip.separator_text(document.source_text) for chip in chips] == [
        "\n",
        ",",
    ]


def test_reorder_chips_keep_blank_line_breaks_as_separator_text() -> None:
    """Blank hard lines between chips should remain separator text, not empty chips."""

    document = parse_prompt_document("alpha\n\nbeta, gamma")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)

    assert [chip.text for chip in chips] == ["alpha", "beta", "gamma"]
    assert state.separator_slots == ("\n\n", ", ")


def test_reorder_chips_split_adjacent_loras_without_commas() -> None:
    """Adjacent inline LoRAs should be independently reorderable without commas."""

    document = parse_prompt_document("<lora:a:1.0> <lora:b:1.0>")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)
    serialization = serialize_reorder_state_for_chips(state, chips_by_index=chips)

    assert [chip.display_text for chip in chips] == [
        "<lora:a:1.0>",
        "<lora:b:1.0>",
    ]
    assert state.separator_slots == (" ",)
    assert serialization.text == "<lora:a:1.0> <lora:b:1.0>"


def test_reorder_chips_split_text_around_inline_lora() -> None:
    """Prompt words around one inline LoRA should become separate reorder chips."""

    document = parse_prompt_document("foo <lora:a:1.0> bar,")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)
    serialization = serialize_reorder_state_for_chips(state, chips_by_index=chips)

    assert [chip.display_text for chip in chips] == [
        "foo",
        "<lora:a:1.0>",
        "bar",
    ]
    assert state.separator_slots == (" ", " ")
    assert serialization.text == "foo <lora:a:1.0> bar, "


def test_reorder_chips_preserve_no_space_lora_boundaries() -> None:
    """No-space LoRA boundaries should not invent separators during serialization."""

    document = parse_prompt_document("foo<lora:a:1.0>bar")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)
    serialization = serialize_reorder_state_for_chips(state, chips_by_index=chips)

    assert [chip.display_text for chip in chips] == [
        "foo",
        "<lora:a:1.0>",
        "bar",
    ]
    assert state.separator_slots == ("", "")
    assert serialization.text == "foo<lora:a:1.0>bar"


def test_reorder_chips_move_inline_lora_without_forcing_commas() -> None:
    """Same-row LoRA movement should preserve space-style row separators."""

    document = parse_prompt_document("foo <lora:a:1.0> bar")
    chips = build_reorder_chips(document)
    base_drag_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=1,
    )
    updated_state = apply_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=1,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    serialization = serialize_reorder_state_for_chips(
        updated_state,
        chips_by_index=chips,
    )

    assert serialization.text == "<lora:a:1.0> foo bar"


def test_reorder_chips_split_loras_inside_hard_lines() -> None:
    """LoRA subdivision should preserve hard-line separator ownership."""

    document = parse_prompt_document("foo <lora:a:1.0>\nbar")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)

    assert [chip.display_text for chip in chips] == [
        "foo",
        "<lora:a:1.0>",
        "bar",
    ]
    assert state.separator_slots == (" ", "\n")


def test_reorder_chips_split_loras_inside_transparent_emphasis_shell() -> None:
    """LoRA-derived child chips should preserve transparent emphasis envelopes."""

    document = parse_prompt_document("(foo <lora:a:1.0>, bar:1.20)")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)
    serialization = serialize_reorder_state_for_chips(state, chips_by_index=chips)

    assert [chip.display_text for chip in chips] == [
        "foo",
        "<lora:a:1.0>",
        "bar",
    ]
    assert [len(chip.envelope_stack) for chip in chips] == [1, 1, 1]
    assert serialization.text == "(foo <lora:a:1.0>, bar:1.20)"


def test_reorder_chips_split_loras_inside_single_emphasis_segment() -> None:
    """A single emphasis segment should still expose contained LoRA reorder chips."""

    document = parse_prompt_document("(foo <lora:a:1.0>:1.20)")
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)
    serialization = serialize_reorder_state_for_chips(state, chips_by_index=chips)

    assert [chip.display_text for chip in chips] == ["foo", "<lora:a:1.0>"]
    assert [len(chip.envelope_stack) for chip in chips] == [1, 1]
    assert serialization.text == "(foo <lora:a:1.0>:1.20)"


def test_base_drag_state_hides_hard_line_split_chip_without_comma_separator() -> None:
    """Hiding a hard-line split chip should preserve the physical row boundary."""

    document = parse_prompt_document("alpha, test test\ntest test, beta")
    chips = build_reorder_chips(document)

    base_drag_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=1,
    )

    assert [chip.text for chip in chips] == [
        "alpha",
        "test test",
        "test test",
        "beta",
    ]
    assert base_drag_state == PromptReorderState(
        ordered_segment_indices=(0, 2, 3),
        separator_slots=("\n", ", "),
        has_trailing_comma=False,
    )


def test_reorder_serialization_preserves_owned_ranges_when_grouped_emphasis_chips_split() -> (
    None
):
    """Split grouped-emphasis chips should keep shell ownership and separator ownership explicit."""

    document = parse_prompt_document("(1girl, solo:1.20), blush")
    chips = build_reorder_chips(document)
    serialization = serialize_reorder_state_for_chips(
        PromptReorderState(
            ordered_segment_indices=(0, 2, 1),
            separator_slots=(", ", ", "),
            has_trailing_comma=False,
        ),
        chips_by_index=chips,
    )

    assert tuple(
        source_range.slice(serialization.text)
        for source_range in serialization.owned_ranges_by_index[0]
    ) == ("(1girl:1.20)", ", ")
    assert tuple(
        source_range.slice(serialization.text)
        for source_range in serialization.owned_ranges_by_index[2]
    ) == ("blush", ", ")
    assert tuple(
        source_range.slice(serialization.text)
        for source_range in serialization.owned_ranges_by_index[1]
    ) == ("(solo:1.20)",)


def test_increase_emphasis_wraps_plain_selection_with_default_weight() -> None:
    """Plain text selections should wrap into a new weighted emphasis span."""

    document = parse_prompt_document("cat")

    result = increase_emphasis(document, SourceRange(0, 3))

    assert result.text == "(cat:1.05)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)


def test_increase_emphasis_updates_existing_weight_in_place() -> None:
    """Existing emphasis should keep its content and update only its numeric weight."""

    document = parse_prompt_document("(cat:1.05)")

    result = increase_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:1.10)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_decrease_emphasis_updates_existing_weight_in_place() -> None:
    """Existing emphasis should decrease its weight deterministically."""

    document = parse_prompt_document("(cat:1.20)")

    result = decrease_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:1.15)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_decrease_emphasis_unwraps_when_weight_returns_to_neutral() -> None:
    """Neutral emphasis should remove the wrapping shell entirely."""

    document = parse_prompt_document("(cat:1.05)")

    result = decrease_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "cat"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (0, 3)


def test_increase_emphasis_updates_only_inner_nested_span() -> None:
    """Nested emphasis adjustments should target only the requested inner shell."""

    document = parse_prompt_document("((cat:1.20) dog:1.10)")
    inner_span = document.emphasis_spans[1]

    result = increase_emphasis(document, inner_span.content_range)

    assert result.text == "((cat:1.25) dog:1.10)"
    assert result.selection_range == inner_span.content_range
    updated_document = parse_prompt_document(result.text)
    assert [span.weight for span in updated_document.emphasis_spans] == [
        Decimal("1.10"),
        Decimal("1.25"),
    ]


def test_decrease_emphasis_updates_only_inner_nested_span() -> None:
    """Nested emphasis decreases should not disturb the enclosing shell."""

    document = parse_prompt_document("((cat:1.20) dog:1.10)")
    inner_span = document.emphasis_spans[1]

    result = decrease_emphasis(document, inner_span.content_range)

    assert result.text == "((cat:1.15) dog:1.10)"
    assert result.selection_range == inner_span.content_range
    updated_document = parse_prompt_document(result.text)
    assert [span.weight for span in updated_document.emphasis_spans] == [
        Decimal("1.10"),
        Decimal("1.15"),
    ]


def test_decrease_emphasis_neutral_unwrap_preserves_expected_plain_text_range() -> None:
    """Neutral unwrap should restore the inner plain text at the outer shell range."""

    document = parse_prompt_document("before, (cat:1.05), after")
    span = document.emphasis_spans[0]

    result = decrease_emphasis(document, span.content_range)

    assert result.text == "before, cat, after"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "cat"
    assert (result.selection_range.start, result.selection_range.end) == (8, 11)


def test_set_emphasis_weight_updates_existing_shell_to_exact_value() -> None:
    """Exact emphasis setting should replace only the existing numeric weight."""

    document = parse_prompt_document("(cat:1.05)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("1.20"),
    )

    assert result.text == "(cat:1.20)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_set_emphasis_weight_unwraps_existing_shell_at_neutral() -> None:
    """Exact neutral emphasis should unwrap the existing shell immediately."""

    document = parse_prompt_document("(cat:1.20)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("1.00"),
    )

    assert result.text == "cat"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "cat"


def test_set_emphasis_weight_wraps_plain_selection_at_exact_weight() -> None:
    """Exact-weight setting should wrap plain selected text when no shell exists."""

    document = parse_prompt_document("cat")

    result = set_emphasis_weight(
        document,
        SourceRange(0, 3),
        weight=Decimal("0.95"),
    )

    assert result.text == "(cat:0.95)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)


def test_set_emphasis_weight_clamps_values_below_the_supported_floor() -> None:
    """Exact-weight setting should clamp sub-floor values to the minimum emphasis."""

    document = parse_prompt_document("(cat:1.20)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("0.01"),
    )

    assert result.text == "(cat:0.05)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_replace_span_content_updates_inner_text_only() -> None:
    """Replacing emphasis content should preserve the existing shell and weight."""

    document = parse_prompt_document("(cat:1.20)")

    result = replace_span_content(document, document.emphasis_spans[0], "dog")

    assert result.text == "(dog:1.20)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)
