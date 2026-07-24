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

"""Verify bounded regional-structure updates across source edits."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.document.views import (
    PromptRegionPartitionView,
    PromptRegionSeparatorView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.editing.region_structure_edits import (
    rebuild_region_structure_after_edit,
    region_structure_edit_requires_rebuild,
    remap_region_structure_after_edit,
)


@pytest.mark.parametrize(
    ("previous_text", "next_text", "start", "expected_token_start"),
    (
        (
            "school uniform [SEP]\nregional",
            "school uniform \n[SEP]\nregional",
            len("school uniform "),
            len("school uniform \n"),
        ),
        (
            "global\n[SEP] regional",
            "global\n[SEP]\n regional",
            len("global\n[SEP]"),
            len("global\n"),
        ),
    ),
)
def test_rebuild_region_structure_promotes_edit_local_separator(
    previous_text: str,
    next_text: str,
    start: int,
    expected_token_start: int,
) -> None:
    """Promote an inline marker when one newline makes it canonical."""

    structure = rebuild_region_structure_after_edit(
        previous_text,
        next_text,
        PromptRegionStructureView.empty(len(previous_text)),
        start=start,
        end=start,
    )

    assert structure.separators == (
        PromptRegionSeparatorView(
            token_start=expected_token_start,
            token_end=expected_token_start + len("[SEP]"),
            line_start=expected_token_start,
            line_end=expected_token_start + len("[SEP]\n"),
        ),
    )
    assert structure.partitions == (
        PromptRegionPartitionView(
            index=0,
            source_start=0,
            source_end=expected_token_start,
            is_global=True,
        ),
        PromptRegionPartitionView(
            index=1,
            source_start=expected_token_start + len("[SEP]\n"),
            source_end=len(next_text),
            is_global=False,
        ),
    )


def test_rebuild_region_structure_demotes_separator_without_rescanning_others() -> None:
    """Demote one joined marker while shifting an untouched later separator."""

    previous_text = "global\n[SEP]\nred\n[SEP]\nblue"
    next_text = "global[SEP]\nred\n[SEP]\nblue"
    structure = PromptRegionStructureView(
        separators=(
            PromptRegionSeparatorView(7, 12, 7, 13),
            PromptRegionSeparatorView(17, 22, 17, 23),
        ),
        partitions=(
            PromptRegionPartitionView(0, 0, 7, True),
            PromptRegionPartitionView(1, 13, 17, False),
            PromptRegionPartitionView(2, 23, 27, False),
        ),
    )

    rebuilt = rebuild_region_structure_after_edit(
        previous_text,
        next_text,
        structure,
        start=len("global"),
        end=len("global\n"),
    )

    assert rebuilt.separators == (PromptRegionSeparatorView(16, 21, 16, 22),)
    assert rebuilt.partitions == (
        PromptRegionPartitionView(0, 0, 16, True),
        PromptRegionPartitionView(1, 22, len(next_text), False),
    )


def test_rebuild_region_structure_preserves_separator_before_inserted_blank_line() -> (
    None
):
    """Keep a separator when a newline is inserted after its consumed line break."""

    previous_text = "global\n[SEP]\nregional"
    next_text = "global\n[SEP]\n\nregional"
    structure = PromptRegionStructureView(
        separators=(PromptRegionSeparatorView(7, 12, 7, 13),),
        partitions=(
            PromptRegionPartitionView(0, 0, 7, True),
            PromptRegionPartitionView(1, 13, len(previous_text), False),
        ),
    )

    rebuilt = rebuild_region_structure_after_edit(
        previous_text,
        next_text,
        structure,
        start=len("global\n[SEP]\n"),
        end=len("global\n[SEP]\n"),
    )

    assert rebuilt.separators == structure.separators
    assert rebuilt.partitions == (
        PromptRegionPartitionView(0, 0, 7, True),
        PromptRegionPartitionView(1, 13, len(next_text), False),
    )


def test_rebuild_region_structure_preserves_crlf_separator_boundaries() -> None:
    """Keep CRLF line ownership exact when inserting a following blank line."""

    previous_text = "global\r\n[SEP]\r\nregional"
    next_text = "global\r\n[SEP]\r\n\r\nregional"
    structure = PromptRegionStructureView(
        separators=(PromptRegionSeparatorView(8, 13, 8, 15),),
        partitions=(
            PromptRegionPartitionView(0, 0, 8, True),
            PromptRegionPartitionView(1, 15, len(previous_text), False),
        ),
    )

    rebuilt = rebuild_region_structure_after_edit(
        previous_text,
        next_text,
        structure,
        start=len("global\r\n[SEP]\r\n"),
        end=len("global\r\n[SEP]\r\n"),
    )

    assert rebuilt.separators == structure.separators
    assert rebuilt.partitions == (
        PromptRegionPartitionView(0, 0, 8, True),
        PromptRegionPartitionView(1, 15, len(next_text), False),
    )


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_content_insertion_before_separator_line_break_remaps_without_rebuild(
    line_ending: str,
) -> None:
    """Ordinary content growth before a marker line should stay incremental."""

    previous_text = f"global{line_ending}[SEP]{line_ending}middle{line_ending}[SEP]"
    second_separator_start = previous_text.rindex("[SEP]")
    insertion_position = second_separator_start - len(line_ending)
    next_text = (
        previous_text[:insertion_position] + "x" + previous_text[insertion_position:]
    )
    first_separator_start = previous_text.index("[SEP]")
    first_separator_end = first_separator_start + len("[SEP]")
    first_line_end = first_separator_end + len(line_ending)
    second_separator_end = second_separator_start + len("[SEP]")
    structure = PromptRegionStructureView(
        separators=(
            PromptRegionSeparatorView(
                first_separator_start,
                first_separator_end,
                first_separator_start,
                first_line_end,
            ),
            PromptRegionSeparatorView(
                second_separator_start,
                second_separator_end,
                second_separator_start,
                second_separator_end,
            ),
        ),
        partitions=(
            PromptRegionPartitionView(0, 0, first_separator_start, True),
            PromptRegionPartitionView(
                1,
                first_line_end,
                second_separator_start,
                False,
            ),
            PromptRegionPartitionView(
                2,
                second_separator_end,
                len(previous_text),
                False,
            ),
        ),
    )

    assert not region_structure_edit_requires_rebuild(
        previous_text,
        next_text,
        structure,
        start=insertion_position,
        end=insertion_position,
    )


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_content_insertion_after_separator_line_keeps_its_boundary(
    line_ending: str,
) -> None:
    """Do not absorb following regional content into a separator source line."""

    previous_text = f"global{line_ending}[SEP]{line_ending}regional"
    separator_start = previous_text.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    separator_line_end = separator_end + len(line_ending)
    structure = PromptRegionStructureView(
        separators=(
            PromptRegionSeparatorView(
                separator_start,
                separator_end,
                separator_start,
                separator_line_end,
            ),
        ),
        partitions=(
            PromptRegionPartitionView(0, 0, separator_start, True),
            PromptRegionPartitionView(
                1,
                separator_line_end,
                len(previous_text),
                False,
            ),
        ),
    )

    remapped = remap_region_structure_after_edit(
        structure,
        start=separator_line_end,
        end=separator_line_end,
        replacement_text="x",
    )

    assert remapped.separators == structure.separators
    assert remapped.partitions == (
        structure.partitions[0],
        PromptRegionPartitionView(
            1,
            separator_line_end,
            len(previous_text) + 1,
            False,
        ),
    )


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_separator_preceding_line_break_deletion_requires_rebuild(
    line_ending: str,
) -> None:
    """Deleting either line-ending form before a marker must demote the marker."""

    previous_text = f"global{line_ending}[SEP]{line_ending}regional"
    separator_start = previous_text.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    separator_line_end = separator_end + len(line_ending)
    line_break_start = separator_start - len(line_ending)
    next_text = previous_text[:line_break_start] + previous_text[separator_start:]
    structure = PromptRegionStructureView(
        separators=(
            PromptRegionSeparatorView(
                separator_start,
                separator_end,
                separator_start,
                separator_line_end,
            ),
        ),
        partitions=(
            PromptRegionPartitionView(0, 0, separator_start, True),
            PromptRegionPartitionView(
                1,
                separator_line_end,
                len(previous_text),
                False,
            ),
        ),
    )

    assert region_structure_edit_requires_rebuild(
        previous_text,
        next_text,
        structure,
        start=line_break_start,
        end=separator_start,
    )
