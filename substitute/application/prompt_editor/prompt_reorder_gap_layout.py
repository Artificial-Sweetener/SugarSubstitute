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

"""Build and inspect prompt reorder gap layout views."""

from __future__ import annotations

from dataclasses import replace

from substitute.domain.prompt import (
    blank_line_drop_offsets,
    split_gap_for_blank_line_insert,
)

from .prompt_reorder_views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)


def layout_view_from_rows_and_gaps(
    row_indices: list[tuple[int, ...]],
    *,
    between_separator_texts: tuple[str, ...],
    trailing_edge_separator_text: str,
) -> PromptReorderLayoutView:
    """Build one renumbered layout from row and gap primitives."""

    rows = tuple(
        PromptReorderRowView(row_index=row_index, chip_indices=chip_indices)
        for row_index, chip_indices in enumerate(row_indices)
    )
    gaps = tuple(
        gap_view(
            gap_index=gap_index,
            separator_text=separator_text,
            placement=PromptReorderGapPlacement.BETWEEN_ROWS,
        )
        for gap_index, separator_text in enumerate(between_separator_texts)
    )
    layout_view = PromptReorderLayoutView(rows=rows, gaps=gaps)
    return with_trailing_edge_gap(
        layout_view,
        separator_text=trailing_edge_separator_text,
    )


def split_after_last_row_gap_for_insert(
    separator_text: str,
    *,
    blank_line_index: int,
) -> tuple[str, str]:
    """Split a trailing blank-line gap for inserting a new final row."""

    if separator_text.startswith(","):
        return split_gap_for_blank_line_insert(
            separator_text,
            blank_line_index=blank_line_index,
        )

    offsets = blank_line_drop_offsets(separator_text)
    if not 0 <= blank_line_index < len(offsets):
        raise ValueError(
            "blank_line_index must reference an available blank-line target."
        )
    split_offset = offsets[blank_line_index]
    prefix_separator = f",{separator_text[:split_offset]}"
    suffix_separator = separator_text[split_offset:]
    return prefix_separator, suffix_separator


def with_edge_gaps_from_layout(
    layout_view: PromptReorderLayoutView,
    *,
    source_layout: PromptReorderLayoutView,
) -> PromptReorderLayoutView:
    """Copy transient edge gaps from one layout onto another."""

    return with_trailing_edge_gap(
        layout_view,
        separator_text=trailing_edge_separator_text(source_layout),
    )


def with_trailing_edge_gap(
    layout_view: PromptReorderLayoutView,
    *,
    separator_text: str,
) -> PromptReorderLayoutView:
    """Return a layout with one after-last-row gap when trailing text is visible."""

    if not separator_text:
        return layout_view
    return replace(
        layout_view,
        gaps=layout_view.gaps
        + (
            gap_view(
                gap_index=len(layout_view.gaps),
                separator_text=separator_text,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )


def gap_view(
    *,
    gap_index: int,
    separator_text: str,
    placement: PromptReorderGapPlacement,
) -> PromptReorderGapView:
    """Build one gap view with derived blank-line target count."""

    return PromptReorderGapView(
        gap_index=gap_index,
        separator_text=separator_text,
        blank_line_count=len(blank_line_drop_offsets(separator_text)),
        placement=placement,
    )


def trailing_edge_separator_text_for_hidden_chip(
    layout_view: PromptReorderLayoutView,
    *,
    dragged_segment_index: int,
    has_trailing_comma: bool,
) -> str:
    """Return edge separator text exposed by hiding the dragged chip."""

    exposed_separator_text = exposed_trailing_separator_text(
        layout_view,
        dragged_segment_index=dragged_segment_index,
    )
    existing_trailing_edge_separator_text = trailing_edge_separator_text(layout_view)
    if not exposed_separator_text:
        return existing_trailing_edge_separator_text

    exposed_edge_separator_text = edge_separator_text(
        exposed_separator_text,
        has_trailing_comma=has_trailing_comma,
    )
    exposed_edge_separator_text = (
        exposed_edge_separator_text
        + origin_placeholder_line_break(exposed_separator_text)
    )
    if not existing_trailing_edge_separator_text:
        return exposed_edge_separator_text
    return exposed_edge_separator_text + separator_text_suffix(
        existing_trailing_edge_separator_text
    )


def exposed_trailing_separator_text(
    layout_view: PromptReorderLayoutView,
    *,
    dragged_segment_index: int,
) -> str:
    """Return the final row gap that becomes trailing while its only chip is hidden."""

    gaps_between_rows = between_row_gaps(layout_view)
    if not layout_view.rows or not gaps_between_rows:
        return ""

    final_row = layout_view.rows[-1]
    if final_row.chip_indices != (dragged_segment_index,):
        return ""

    expected_gap_count = len(layout_view.rows) - 1
    if len(gaps_between_rows) != expected_gap_count:
        return ""

    return gaps_between_rows[-1].separator_text


def edge_separator_text(separator_text: str, *, has_trailing_comma: bool) -> str:
    """Return the visible trailing edge form of an exposed separator."""

    if has_trailing_comma:
        return separator_text
    return separator_text_suffix(separator_text)


def origin_placeholder_line_break(separator_text: str) -> str:
    """Return one line break that keeps a lifted edge-row origin addressable."""

    if "\r\n" in separator_text:
        return "\r\n"
    if "\r" in separator_text:
        return "\r"
    if "\n" in separator_text:
        return "\n"
    return ""


def between_row_gaps(
    layout_view: PromptReorderLayoutView,
) -> tuple[PromptReorderGapView, ...]:
    """Return layout gaps that separate two populated rows."""

    return tuple(
        gap
        for gap in layout_view.gaps
        if gap.placement is PromptReorderGapPlacement.BETWEEN_ROWS
    )


def trailing_edge_separator_text(layout_view: PromptReorderLayoutView) -> str:
    """Return visible trailing separator text from an after-last-row gap."""

    for gap in layout_view.gaps:
        if gap.placement is PromptReorderGapPlacement.AFTER_LAST_ROW:
            return gap.separator_text
    return ""


def gap_by_index(
    layout_view: PromptReorderLayoutView,
    gap_index: int,
) -> PromptReorderGapView | None:
    """Return a gap by stable in-layout index."""

    for gap in layout_view.gaps:
        if gap.gap_index == gap_index:
            return gap
    return None


def separator_text_suffix(separator_text: str) -> str:
    """Return the whitespace/decor suffix from one comma-owned separator string."""

    if separator_text.startswith(","):
        return separator_text[1:]
    return separator_text


__all__ = [
    "between_row_gaps",
    "edge_separator_text",
    "exposed_trailing_separator_text",
    "gap_by_index",
    "gap_view",
    "layout_view_from_rows_and_gaps",
    "origin_placeholder_line_break",
    "separator_text_suffix",
    "split_after_last_row_gap_for_insert",
    "trailing_edge_separator_text",
    "trailing_edge_separator_text_for_hidden_chip",
    "with_edge_gaps_from_layout",
    "with_trailing_edge_gap",
]
