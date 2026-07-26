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

"""Build bounded line splits and joins for hard-line source edits."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

from .snapshot_edits import (
    caret_stops_for_line_fragments,
    remap_fragment_after_hard_line_edit,
    remap_optional_source_position_for_layout,
    remap_source_position_for_layout,
)
from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)


def split_plain_line_for_newline_insert(
    line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    edit_start: int,
    first_dirty_projection_position: int,
    content_left: float,
    content_right: float,
) -> tuple[PromptProjectionLineSnapshot, PromptProjectionLineSnapshot] | None:
    """Return two visual lines produced by inserting one hard line break."""

    split_x = x_position_for_source_boundary(line, edit_start)
    if split_x is None:
        return None
    left_fragments: list[PromptProjectionTextFragment] = []
    right_fragments: list[PromptProjectionTextFragment] = []
    right_x_delta = content_left - split_x
    y_delta = line.height
    for fragment in line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            return None
        split_fragments = split_text_fragment_for_newline_insert(
            fragment,
            edit_start=edit_start,
            right_x_delta=right_x_delta,
            y_delta=y_delta,
        )
        if split_fragments is None:
            return None
        left_fragment, right_fragment = split_fragments
        if left_fragment is not None:
            left_fragments.append(left_fragment)
        if right_fragment is not None:
            right_fragments.append(right_fragment)
    right_line_right = max(
        (fragment.rect.right() for fragment in right_fragments),
        default=content_left,
    )
    if right_line_right > content_right + 0.01:
        return None
    left_line = PromptProjectionLineSnapshot(
        top=line.top,
        height=line.height,
        source_start=line.source_start,
        source_end=edit_start + 1,
        source_content_start=line.source_content_start,
        source_content_end=edit_start,
        line_break_start=edit_start,
        line_break_end=edit_start + 1,
        fragments=tuple(left_fragments),
        caret_stops=caret_stops_for_line_fragments(
            left_fragments,
            projection_document=projection_document,
            line_top=line.top,
            line_height=line.height,
            extra_boundaries=((first_dirty_projection_position, split_x),),
        ),
    )
    right_line = PromptProjectionLineSnapshot(
        top=line.top + line.height,
        height=line.height,
        source_start=edit_start + 1,
        source_end=remap_source_position_for_layout(
            line.source_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        source_content_start=edit_start + 1,
        source_content_end=remap_source_position_for_layout(
            line.source_content_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        line_break_start=remap_optional_source_position_for_layout(
            line.line_break_start,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        line_break_end=remap_optional_source_position_for_layout(
            line.line_break_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        fragments=tuple(right_fragments),
        caret_stops=caret_stops_for_line_fragments(
            right_fragments,
            projection_document=projection_document,
            line_top=line.top + line.height,
            line_height=line.height,
            extra_boundaries=((first_dirty_projection_position + 1, content_left),),
        ),
    )
    return left_line, right_line


def join_plain_lines_after_newline_delete(
    first_line: PromptProjectionLineSnapshot,
    second_line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    edit_start: int,
    content_left: float,
    content_right: float,
) -> PromptProjectionLineSnapshot | None:
    """Return one visual line produced by deleting a hard line break."""

    if first_line.line_break_start != edit_start:
        return None
    join_x = line_content_right(first_line, default=content_left)
    second_x_delta = join_x - content_left
    next_fragments: list[PromptProjectionTextFragment] = [
        fragment
        for fragment in first_line.fragments
        if isinstance(fragment, PromptProjectionTextFragment)
    ]
    if len(next_fragments) != len(first_line.fragments):
        return None
    for fragment in second_line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            return None
        next_fragments.append(
            cast(
                PromptProjectionTextFragment,
                remap_fragment_after_hard_line_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_start + 1,
                    source_delta=-1,
                    projection_delta=-1,
                    x_delta=second_x_delta,
                    y_delta=-second_line.height,
                ),
            )
        )
    if line_content_right_for_fragments(next_fragments, default=content_left) > (
        content_right + 0.01
    ):
        return None
    line_break_start = remap_optional_source_position_for_layout(
        second_line.line_break_start,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        delta=-1,
    )
    line_break_end = remap_optional_source_position_for_layout(
        second_line.line_break_end,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        delta=-1,
    )
    return PromptProjectionLineSnapshot(
        top=first_line.top,
        height=max(first_line.height, second_line.height),
        source_start=first_line.source_start,
        source_end=remap_source_position_for_layout(
            second_line.source_end,
            edit_start=edit_start,
            edit_end=edit_start + 1,
            delta=-1,
        ),
        source_content_start=first_line.source_content_start,
        source_content_end=remap_source_position_for_layout(
            second_line.source_content_end,
            edit_start=edit_start,
            edit_end=edit_start + 1,
            delta=-1,
        ),
        line_break_start=line_break_start,
        line_break_end=line_break_end,
        fragments=tuple(next_fragments),
        caret_stops=caret_stops_for_line_fragments(
            next_fragments,
            projection_document=projection_document,
            line_top=first_line.top,
            line_height=max(first_line.height, second_line.height),
            extra_boundaries=empty_joined_line_caret_boundaries(
                first_line,
                next_fragments=next_fragments,
                content_left=content_left,
            ),
        ),
    )


def empty_joined_line_caret_boundaries(
    first_line: PromptProjectionLineSnapshot,
    *,
    next_fragments: Sequence[PromptProjectionTextFragment],
    content_left: float,
) -> tuple[tuple[int, float], ...]:
    """Return a synthetic caret boundary when a line join leaves an empty line."""

    if next_fragments or not first_line.caret_stops:
        return ()
    return ((first_line.caret_stops[0].projection_position, content_left),)


def x_position_for_source_boundary(
    line: PromptProjectionLineSnapshot,
    source_position: int,
) -> float | None:
    """Return the x coordinate for a source boundary on one visual line."""

    for fragment in line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            continue
        try:
            boundary_index = fragment.source_positions.index(source_position)
        except ValueError:
            continue
        return fragment.rect.left() + fragment.boundary_offsets[boundary_index]
    editable_start_x = line_start_x(line)
    if source_position == line.source_content_end:
        return line_content_right(line, default=editable_start_x)
    if source_position == line.source_content_start:
        return editable_start_x
    return None


def line_start_x(line: PromptProjectionLineSnapshot) -> float:
    """Return the editable start x coordinate for one visual line."""

    if line.fragments:
        return line.rect.left()
    if line.caret_stops:
        return line.caret_stops[0].rect.left()
    return line.rect.left()


def split_text_fragment_for_newline_insert(
    fragment: PromptProjectionTextFragment,
    *,
    edit_start: int,
    right_x_delta: float,
    y_delta: float,
) -> (
    tuple[PromptProjectionTextFragment | None, PromptProjectionTextFragment | None]
    | None
):
    """Split one text fragment around an inserted hard line break."""

    try:
        split_index = fragment.source_positions.index(edit_start)
    except ValueError:
        if fragment.source_positions[-1] <= edit_start:
            return fragment, None
        if fragment.source_positions[0] >= edit_start:
            return None, cast(
                PromptProjectionTextFragment,
                remap_fragment_after_hard_line_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_start,
                    source_delta=1,
                    projection_delta=1,
                    x_delta=right_x_delta,
                    y_delta=y_delta,
                ),
            )
        return None

    left_fragment: PromptProjectionTextFragment | None = None
    right_fragment: PromptProjectionTextFragment | None = None
    if split_index > 0:
        left_fragment = slice_text_fragment(
            fragment,
            local_start=0,
            local_end=split_index,
            source_delta=0,
            projection_delta=0,
            x_delta=0.0,
            y_delta=0.0,
        )
    if split_index < len(fragment.text):
        split_x = fragment.rect.left() + fragment.boundary_offsets[split_index]
        right_fragment = slice_text_fragment(
            fragment,
            local_start=split_index,
            local_end=len(fragment.text),
            source_delta=1,
            projection_delta=1,
            x_delta=right_x_delta,
            y_delta=y_delta,
            rect_left_override=split_x + right_x_delta,
        )
    return left_fragment, right_fragment


def slice_text_fragment(
    fragment: PromptProjectionTextFragment,
    *,
    local_start: int,
    local_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
    y_delta: float,
    rect_left_override: float | None = None,
) -> PromptProjectionTextFragment:
    """Return a concrete slice of one text fragment with shifted coordinates."""

    boundary_offsets = fragment.boundary_offsets[local_start : local_end + 1]
    normalized_offsets = tuple(
        offset - boundary_offsets[0] for offset in boundary_offsets
    )
    rect = QRectF(fragment.rect)
    rect.setLeft(
        rect_left_override
        if rect_left_override is not None
        else fragment.rect.left() + boundary_offsets[0] + x_delta
    )
    rect.moveTop(fragment.rect.top() + y_delta)
    rect.setWidth(max(1.0, normalized_offsets[-1]))
    return PromptProjectionTextFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        projection_start=fragment.projection_start + local_start + projection_delta,
        projection_end=fragment.projection_start + local_end + projection_delta,
        text=fragment.text[local_start:local_end],
        source_positions=tuple(
            position + source_delta
            for position in fragment.source_positions[local_start : local_end + 1]
        ),
        rect=rect,
        baseline=fragment.baseline + y_delta,
        boundary_offsets=normalized_offsets,
        active=fragment.active,
    )


def line_content_right(
    line: PromptProjectionLineSnapshot,
    *,
    default: float,
) -> float:
    """Return the right edge of visible content on one line."""

    return line_content_right_for_fragments(line.fragments, default=default)


def line_content_right_for_fragments(
    fragments: Sequence[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ],
    *,
    default: float,
) -> float:
    """Return the right edge of a fragment sequence."""

    return max((fragment.rect.right() for fragment in fragments), default=default)


__all__ = [
    "empty_joined_line_caret_boundaries",
    "join_plain_lines_after_newline_delete",
    "line_content_right",
    "line_content_right_for_fragments",
    "line_start_x",
    "slice_text_fragment",
    "split_plain_line_for_newline_insert",
    "split_text_fragment_for_newline_insert",
    "x_position_for_source_boundary",
]
