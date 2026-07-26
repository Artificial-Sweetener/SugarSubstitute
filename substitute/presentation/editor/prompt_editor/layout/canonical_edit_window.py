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

"""Compose bounded canonical edit windows and validate reusable suffixes."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSizeF

from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .reused_lines import PromptProjectionReusedLineSequence
from .reused_semantics import PromptReusedLineSemanticResolver
from .shifted_snapshot import (
    LineCaretRectMapping,
    LineInlineObjectFragmentSequence,
    LineTextFragmentSequence,
    ShiftedLineSnapshot,
)


def caret_hosted_reflow_start_line_index(
    lines: Sequence[PromptProjectionLineSnapshot],
    candidate_index: int,
) -> int:
    """Move recovery before structural rows whose edge caret belongs to prior text."""

    if not lines:
        return 0
    line_index = min(max(0, candidate_index), len(lines) - 1)
    while line_index > 0 and not lines[line_index].caret_stops:
        line_index -= 1
    return line_index


def snapshot_with_rebuilt_plain_edit_window(
    partial_snapshot: PromptProjectionLayoutSnapshot,
    *,
    previous_snapshot: PromptProjectionLayoutSnapshot,
    first_rebuilt_line_index: int,
    previous_match_index: int | None,
    source_delta: int,
    projection_delta: int,
    semantic_resolver: PromptReusedLineSemanticResolver,
) -> PromptProjectionLayoutSnapshot:
    """Compose a stable prefix, rebuilt dirty window, and reusable suffix."""

    previous_prefix = previous_snapshot.lines[:first_rebuilt_line_index]
    rebuilt_prefix = tuple(previous_prefix) + tuple(partial_snapshot.lines)
    previous_suffix = (
        ()
        if previous_match_index is None
        else previous_snapshot.lines[previous_match_index + 1 :]
    )
    if not previous_prefix and not previous_suffix:
        return partial_snapshot
    y_delta = 0.0
    if previous_suffix:
        prefix_bottom = (
            rebuilt_prefix[-1].top + rebuilt_prefix[-1].height
            if rebuilt_prefix
            else previous_suffix[0].top
        )
        y_delta = prefix_bottom - previous_suffix[0].top
        next_lines: Sequence[PromptProjectionLineSnapshot] = (
            PromptProjectionReusedLineSequence(
                rebuilt_prefix,
                previous_suffix,
                shift_line=lambda line, shifted_source_delta, shifted_projection_delta, shifted_y_delta: (
                    ShiftedLineSnapshot(
                        line,
                        source_delta=shifted_source_delta,
                        projection_delta=shifted_projection_delta,
                        y_delta=shifted_y_delta,
                        semantic_resolver=semantic_resolver,
                    )
                ),
                source_delta=source_delta,
                projection_delta=projection_delta,
                y_delta=y_delta,
            )
        )
    else:
        next_lines = rebuilt_prefix
    previous_consumed_lines = (
        previous_snapshot.lines
        if previous_match_index is None
        else previous_snapshot.lines[: previous_match_index + 1]
    )
    previous_prefix_text_count = sum(
        isinstance(fragment, PromptProjectionTextFragment)
        for line in previous_prefix
        for fragment in line.fragments
    )
    previous_prefix_inline_count = sum(
        isinstance(fragment, PromptProjectionInlineObjectFragment)
        for line in previous_prefix
        for fragment in line.fragments
    )
    previous_consumed_text_count = sum(
        isinstance(fragment, PromptProjectionTextFragment)
        for line in previous_consumed_lines
        for fragment in line.fragments
    )
    previous_consumed_inline_count = sum(
        isinstance(fragment, PromptProjectionInlineObjectFragment)
        for line in previous_consumed_lines
        for fragment in line.fragments
    )
    text_fragment_count = (
        previous_prefix_text_count
        + len(partial_snapshot.text_fragments)
        + len(previous_snapshot.text_fragments)
        - previous_consumed_text_count
    )
    inline_fragment_count = (
        previous_prefix_inline_count
        + len(partial_snapshot.inline_object_fragments)
        + len(previous_snapshot.inline_object_fragments)
        - previous_consumed_inline_count
    )
    return PromptProjectionLayoutSnapshot(
        content_size=QSizeF(
            partial_snapshot.content_size.width(),
            (
                previous_snapshot.content_size.height() + y_delta
                if previous_suffix
                else partial_snapshot.content_size.height()
            ),
        ),
        lines=next_lines,
        text_fragments=LineTextFragmentSequence(
            next_lines,
            fragment_count=text_fragment_count,
        ),
        inline_object_fragments=LineInlineObjectFragmentSequence(
            next_lines,
            fragment_count=inline_fragment_count,
        ),
        caret_rects_by_projection_position=LineCaretRectMapping(
            next_lines,
            caret_count=max(
                0,
                len(previous_snapshot.caret_rects_by_projection_position)
                + projection_delta,
            ),
        ),
    )


def line_matches_shifted_plain_edit(
    next_line: PromptProjectionLineSnapshot,
    previous_line: PromptProjectionLineSnapshot,
    *,
    source_delta: int,
    projection_delta: int,
) -> bool:
    """Return whether a rebuilt line proves deterministic suffix convergence."""

    if (
        abs(next_line.height - previous_line.height) > 0.01
        or next_line.source_start != previous_line.source_start + source_delta
        or next_line.source_end != previous_line.source_end + source_delta
        or next_line.source_content_start
        != previous_line.source_content_start + source_delta
        or next_line.source_content_end
        != previous_line.source_content_end + source_delta
        or shifted_optional_position(previous_line.line_break_start, source_delta)
        != next_line.line_break_start
        or shifted_optional_position(previous_line.line_break_end, source_delta)
        != next_line.line_break_end
        or len(next_line.fragments) != len(previous_line.fragments)
        or len(next_line.caret_stops) != len(previous_line.caret_stops)
    ):
        return False
    if not all(
        fragment_matches_shifted_plain_edit(
            next_fragment,
            previous_fragment,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
        for next_fragment, previous_fragment in zip(
            next_line.fragments,
            previous_line.fragments,
            strict=True,
        )
    ):
        return False
    return all(
        next_stop.projection_position
        == previous_stop.projection_position + projection_delta
        and abs(next_stop.rect.left() - previous_stop.rect.left()) <= 0.01
        and abs(next_stop.rect.width() - previous_stop.rect.width()) <= 0.01
        for next_stop, previous_stop in zip(
            next_line.caret_stops,
            previous_line.caret_stops,
            strict=True,
        )
    )


def fragment_matches_shifted_plain_edit(
    next_fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    previous_fragment: (
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ),
    *,
    source_delta: int,
    projection_delta: int,
) -> bool:
    """Return whether one fragment is unchanged apart from logical offsets."""

    if isinstance(next_fragment, PromptProjectionTextFragment) != isinstance(
        previous_fragment,
        PromptProjectionTextFragment,
    ):
        return False
    if (
        next_fragment.run_id != previous_fragment.run_id
        or next_fragment.token_id != previous_fragment.token_id
        or next_fragment.projection_start
        != previous_fragment.projection_start + projection_delta
        or next_fragment.projection_end
        != previous_fragment.projection_end + projection_delta
        or next_fragment.active != previous_fragment.active
        or abs(next_fragment.rect.left() - previous_fragment.rect.left()) > 0.01
        or abs(next_fragment.rect.width() - previous_fragment.rect.width()) > 0.01
        or abs(next_fragment.rect.height() - previous_fragment.rect.height()) > 0.01
        or len(next_fragment.source_positions)
        != len(previous_fragment.source_positions)
        or any(
            next_position != previous_position + source_delta
            for next_position, previous_position in zip(
                next_fragment.source_positions,
                previous_fragment.source_positions,
                strict=True,
            )
        )
    ):
        return False
    if isinstance(next_fragment, PromptProjectionTextFragment) and isinstance(
        previous_fragment,
        PromptProjectionTextFragment,
    ):
        return bool(
            next_fragment.text == previous_fragment.text
            and next_fragment.boundary_offsets == previous_fragment.boundary_offsets
        )
    if isinstance(next_fragment, PromptProjectionInlineObjectFragment) and isinstance(
        previous_fragment,
        PromptProjectionInlineObjectFragment,
    ):
        return next_fragment.renderer_key == previous_fragment.renderer_key
    return False


def shifted_optional_position(position: int | None, delta: int) -> int | None:
    """Return an optional position shifted by one uniform suffix delta."""

    return None if position is None else position + delta


__all__ = [
    "caret_hosted_reflow_start_line_index",
    "fragment_matches_shifted_plain_edit",
    "line_matches_shifted_plain_edit",
    "shifted_optional_position",
    "snapshot_with_rebuilt_plain_edit_window",
]
