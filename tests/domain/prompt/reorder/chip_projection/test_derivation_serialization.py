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


import pytest

from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.domain.prompt.reorder.derivation import (
    build_reorder_chips,
    build_reorder_state_from_chips,
)
from substitute.domain.prompt.reorder.serialization import (
    serialize_reorder_state_for_chips,
)
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


def test_reorder_chips_exclude_region_separator_and_preserve_partition_boundary() -> (
    None
):
    """Regional separators should remain structural boundaries rather than drag chips."""

    document = parse_prompt_document(
        "global one, global two\n[SEP]\nregion one, region two"
    )
    chips = build_reorder_chips(document)
    state = build_reorder_state_from_chips(document, chips)

    assert [chip.text for chip in chips] == [
        "global one",
        "global two",
        "region one",
        "region two",
    ]
    assert [chip.partition_index for chip in chips] == [0, 0, 1, 1]
    assert state.separator_slots == (", ", "\n[SEP]\n", ", ")
    assert (
        serialize_reorder_state_for_chips(state, chips_by_index=chips).text
        == document.source_text
    )


def test_reorder_chips_move_across_regional_partition() -> None:
    """A moved chip should join the destination partition without moving its separator."""

    document = parse_prompt_document("global a, global b\n[SEP]\nregion a, region b")
    chips = build_reorder_chips(document)
    base_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=2,
    )

    updated_state = apply_line_drop_target_to_state(
        base_state,
        dragged_segment_index=2,
        target=PromptLineDropTarget(row_index=1, insertion_index=1),
    )
    assert (
        serialize_reorder_state_for_chips(updated_state, chips_by_index=chips).text
        == "global a, global b\n[SEP]\nregion b, region a"
    )

    cross_partition_state = apply_line_drop_target_to_state(
        base_state,
        dragged_segment_index=2,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert cross_partition_state.partition_index_by_segment_index == (0, 0, 0, 1)
    assert (
        serialize_reorder_state_for_chips(
            cross_partition_state,
            chips_by_index=chips,
        ).text
        == "region a, global a, global b\n[SEP]\nregion b"
    )


def test_reorder_only_chip_out_of_trailing_region_preserves_empty_partition() -> None:
    """Moving the sole trailing-region chip should retain the trailing separator."""

    document = parse_prompt_document("global a, global b\n[SEP]\nregion a")
    chips = build_reorder_chips(document)
    base_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=2,
    )

    updated_state = apply_line_drop_target_to_state(
        base_state,
        dragged_segment_index=2,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert (
        serialize_reorder_state_for_chips(updated_state, chips_by_index=chips).text
        == "region a, global a, global b\n[SEP]"
    )


def test_reorder_only_chip_out_of_leading_region_preserves_empty_partition() -> None:
    """Moving the sole leading-region chip should retain the leading separator."""

    document = parse_prompt_document("global a\n[SEP]\nregion a, region b")
    chips = build_reorder_chips(document)
    base_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=0,
    )

    updated_state = apply_line_drop_target_to_state(
        base_state,
        dragged_segment_index=0,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert (
        serialize_reorder_state_for_chips(updated_state, chips_by_index=chips).text
        == "[SEP]\nglobal a, region a, region b"
    )


def test_reorder_chip_crosses_multiple_regional_partitions() -> None:
    """A chip should reach any structural row without disturbing either separator."""

    document = parse_prompt_document(
        "global a\n[SEP]\nregion a, region b\n[SEP]\nregion c, region d"
    )
    chips = build_reorder_chips(document)
    base_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=3,
    )

    updated_state = apply_line_drop_target_to_state(
        base_state,
        dragged_segment_index=3,
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert updated_state.partition_index_by_segment_index == (0, 1, 1, 0, 2)
    assert (
        serialize_reorder_state_for_chips(updated_state, chips_by_index=chips).text
        == "region c, global a\n[SEP]\nregion a, region b\n[SEP]\nregion d"
    )


def test_reorder_chip_crosses_partition_into_blank_line() -> None:
    """A blank-line target should adopt the destination partition like a row target."""

    document = parse_prompt_document("global a\n\nglobal b\n[SEP]\nregion a, region b")
    chips = build_reorder_chips(document)
    base_state = build_base_drag_state(
        build_reorder_state_from_chips(document, chips),
        dragged_segment_index=2,
    )

    updated_state = apply_blank_line_drop_target_to_state(
        base_state,
        dragged_segment_index=2,
        target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )

    assert updated_state.partition_index_by_segment_index == (0, 0, 0, 1)
    assert (
        serialize_reorder_state_for_chips(updated_state, chips_by_index=chips).text
        == "global a\nregion a,\nglobal b\n[SEP]\nregion b"
    )


@pytest.mark.parametrize(
    "source_text",
    (
        "[SEP]\nregion",
        "global\n[SEP]",
        "[SEP]\n[SEP]\nregion",
        "global\n[SEP]\n[SEP]",
    ),
)
def test_reorder_serialization_preserves_empty_regional_partitions(
    source_text: str,
) -> None:
    """Leading, adjacent, and trailing empty partitions should remain exact source."""

    document = parse_prompt_document(source_text)
    chips = build_reorder_chips(document)

    assert (
        serialize_reorder_state_for_chips(
            build_reorder_state_from_chips(document, chips),
            chips_by_index=chips,
        ).text
        == source_text
    )


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
        partition_index_by_segment_index=(0, 0, 0, 0),
        separator_slots=("\n", ", "),
        has_trailing_comma=False,
        prefix_text="",
        suffix_text="",
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
            partition_index_by_segment_index=(0, 0, 0),
            separator_slots=(", ", ", "),
            has_trailing_comma=False,
            prefix_text="",
            suffix_text="",
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
