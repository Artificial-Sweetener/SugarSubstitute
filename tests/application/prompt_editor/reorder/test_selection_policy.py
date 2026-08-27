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

"""Verify application reorder selection capture policy."""

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.selection import (
    PromptReorderSelectionCapturePolicy,
)


def test_selection_capture_resolves_caret_inside_chip_with_relative_offsets() -> None:
    """A caret inside one chip should preserve its exact relative position."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=3,
        selection_start=3,
        selection_end=3,
        selection_empty=True,
    )

    assert capture.active_segment_index == 0
    assert capture.selection_start == 3
    assert capture.selection_end == 3
    assert capture.selection_start_offset_within_active_chip == 3
    assert capture.selection_end_offset_within_active_chip == 3


def test_selection_capture_uses_preceding_chip_at_separator_boundary() -> None:
    """A caret between chips should keep the preceding chip active."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=6,
        selection_start=6,
        selection_end=6,
        selection_empty=True,
    )

    assert capture.active_segment_index == 0
    assert capture.selection_start == 6
    assert capture.selection_end == 6
    assert capture.selection_start_offset_within_active_chip is None
    assert capture.selection_end_offset_within_active_chip is None


def test_selection_capture_preserves_self_contained_selection_offsets() -> None:
    """A selection within one chip should retain both relative boundaries."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=4,
        selection_start=1,
        selection_end=4,
        selection_empty=False,
    )

    assert capture.active_segment_index == 0
    assert capture.selection_start == 1
    assert capture.selection_end == 4
    assert capture.selection_start_offset_within_active_chip == 1
    assert capture.selection_end_offset_within_active_chip == 4


def test_selection_capture_rejects_relative_offsets_across_chips() -> None:
    """A cross-chip selection should not produce invalid chip-relative offsets."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=9,
        selection_start=2,
        selection_end=9,
        selection_empty=False,
    )

    assert capture.active_segment_index == 0
    assert capture.selection_start == 2
    assert capture.selection_end == 9
    assert capture.selection_start_offset_within_active_chip is None
    assert capture.selection_end_offset_within_active_chip is None


def test_selection_capture_prefers_containment_over_preceding_boundary() -> None:
    """Either selected endpoint inside a chip should outrank separator proximity."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=9,
        selection_start=6,
        selection_end=9,
        selection_empty=False,
    )

    assert capture.active_segment_index == 1
    assert capture.selection_start_offset_within_active_chip is None
    assert capture.selection_end_offset_within_active_chip is None


def test_selection_capture_before_first_chip_has_no_active_segment() -> None:
    """A caret before every chip should not invent an active segment."""

    capture = PromptReorderSelectionCapturePolicy().capture(
        _chips(),
        cursor_position=-1,
        selection_start=-1,
        selection_end=-1,
        selection_empty=True,
    )

    assert capture.active_segment_index is None
    assert capture.selection_start_offset_within_active_chip is None
    assert capture.selection_end_offset_within_active_chip is None


def _chips() -> tuple[PromptReorderChipView, ...]:
    """Return two chips separated by one non-chip source boundary."""

    return (
        _chip(index=0, selection_start=0, selection_end=5),
        _chip(index=1, selection_start=7, selection_end=11),
    )


def _chip(
    *,
    index: int,
    selection_start: int,
    selection_end: int,
) -> PromptReorderChipView:
    """Build one minimal immutable chip view for selection-policy tests."""

    text = f"chip-{index}"
    return PromptReorderChipView(
        index=index,
        partition_index=0,
        text=text,
        serialized_text=text,
        display_text=text,
        display_source_start=selection_start,
        display_source_end=selection_end,
        selection_start=selection_start,
        selection_end=selection_end,
        separator_text_after=", ",
        has_separator_after=True,
    )
