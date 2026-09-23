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

"""Resolve canonical visual-line boundaries into source document spans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)


@dataclass(frozen=True, slots=True)
class PromptLineStartBoundary:
    """Describe a source-aware boundary that opens one visual line."""

    projection_position: int
    source_position: int | None = None


@dataclass(frozen=True, slots=True)
class PromptLineBoundary:
    """Describe one source-aware caret boundary on a visual line."""

    projection_position: int
    x_position: float
    source_position: int | None = None


@dataclass(frozen=True, slots=True)
class PromptLineSourceSpan:
    """Describe one visual line's complete source ownership."""

    source_start: int
    source_end: int
    source_content_start: int
    source_content_end: int
    line_break_start: int | None
    line_break_end: int | None


def resolve_line_source_span(
    projection_document: PromptProjectionDocument,
    *,
    current_boundaries: Sequence[PromptLineBoundary],
    next_start_boundaries: Sequence[PromptLineStartBoundary] | None,
) -> PromptLineSourceSpan:
    """Resolve source content and hard-break spans for one visual line."""

    if not projection_document.caret_map.stops:
        return PromptLineSourceSpan(0, 0, 0, 0, None, None)
    first_projection_position = projection_document.caret_map.stops[
        0
    ].projection_position
    if current_boundaries:
        start_boundary = current_boundaries[0]
        content_end_boundary = current_boundaries[-1]
    else:
        fallback_boundary = (
            next_start_boundaries[0]
            if next_start_boundaries
            else PromptLineStartBoundary(first_projection_position)
        )
        start_boundary = PromptLineBoundary(
            fallback_boundary.projection_position,
            0.0,
            fallback_boundary.source_position,
        )
        content_end_boundary = start_boundary
    start_source_position = _resolve_source_position(
        projection_document,
        boundary=start_boundary,
        first_projection_position=first_projection_position,
    )
    content_end_source_position = _resolve_source_position(
        projection_document,
        boundary=content_end_boundary,
        first_projection_position=first_projection_position,
    )
    source_end_position = max(start_source_position, content_end_source_position)
    line_break_start: int | None = None
    line_break_end: int | None = None
    if next_start_boundaries:
        next_boundary = next_start_boundaries[0]
        next_source_position = _resolve_source_position(
            projection_document,
            boundary=next_boundary,
            first_projection_position=first_projection_position,
        )
        if next_source_position > content_end_source_position:
            line_break_start = content_end_source_position
            line_break_end = next_source_position
            source_end_position = max(source_end_position, next_source_position)
    return PromptLineSourceSpan(
        source_start=start_source_position,
        source_end=source_end_position,
        source_content_start=start_source_position,
        source_content_end=max(start_source_position, content_end_source_position),
        line_break_start=line_break_start,
        line_break_end=line_break_end,
    )


def _resolve_source_position(
    projection_document: PromptProjectionDocument,
    *,
    boundary: PromptLineBoundary | PromptLineStartBoundary,
    first_projection_position: int,
) -> int:
    """Resolve one layout boundary through explicit metadata or the caret map."""

    if (
        boundary.projection_position < first_projection_position
        and boundary.source_position is not None
    ):
        return boundary.source_position
    if boundary.source_position is not None:
        return boundary.source_position
    return projection_document.caret_map.state_for_projection_position(
        max(boundary.projection_position, first_projection_position)
    ).source_position


__all__ = [
    "PromptLineBoundary",
    "PromptLineSourceSpan",
    "PromptLineStartBoundary",
    "resolve_line_source_span",
]
