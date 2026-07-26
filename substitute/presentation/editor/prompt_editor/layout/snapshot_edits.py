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

"""Apply bounded same-line edits and coordinate remapping to layout snapshots."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from ..projection.text_style import projection_text_run_font
from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .reused_semantics import PromptReusedLineSemanticResolver
from .shifted_snapshot import (
    ShiftedLineSnapshot,
)
from .text_shaping import text_boundary_offsets


def plain_text_run_for_empty_line_insert(
    projection_document: PromptProjectionDocument,
    *,
    line: PromptProjectionLineSnapshot,
    edit_start: int,
    replacement_text: str,
) -> PromptProjectionRun | None:
    """Return the new plain text run created by typing into an empty line."""

    if (
        not replacement_text
        or line.fragments
        or line.source_content_start != edit_start
        or line.source_content_end != edit_start
    ):
        return None
    for run in projection_document.runs:
        if run.kind is not PromptProjectionRunKind.TEXT or run.token_id is not None:
            continue
        try:
            local_start = run.source_positions.index(edit_start)
        except ValueError:
            continue
        local_end = local_start + len(replacement_text)
        if run.display_text[local_start:local_end] == replacement_text and tuple(
            run.source_positions[local_start : local_end + 1]
        ) == tuple(range(edit_start, edit_start + len(replacement_text) + 1)):
            return run
    return None


def text_fragment_for_empty_line_insert(
    line: PromptProjectionLineSnapshot,
    *,
    next_run: PromptProjectionRun,
    edit_start: int,
    replacement_text: str,
    content_left: float,
    base_font: QFont,
) -> PromptProjectionTextFragment | None:
    """Return a laid-out text fragment for the first character in an empty line."""

    if (
        line.fragments
        or next_run.kind is not PromptProjectionRunKind.TEXT
        or next_run.token_id is not None
    ):
        return None
    try:
        local_start = next_run.source_positions.index(edit_start)
    except ValueError:
        return None
    local_end = local_start + len(replacement_text)
    if next_run.display_text[local_start:local_end] != replacement_text or tuple(
        next_run.source_positions[local_start : local_end + 1]
    ) != tuple(range(edit_start, edit_start + len(replacement_text) + 1)):
        return None
    fragment_font = projection_text_run_font(next_run, base_font)
    boundary_offsets = text_boundary_offsets(replacement_text, fragment_font)
    if len(boundary_offsets) != len(replacement_text) + 1:
        return None
    font_metrics = QFontMetricsF(fragment_font)
    text_height = float(font_metrics.height())
    text_top = line.top + max(0.0, (line.height - text_height) / 2.0)
    return PromptProjectionTextFragment(
        run_id=next_run.run_id,
        token_id=None,
        projection_start=next_run.projection_start + local_start,
        projection_end=next_run.projection_start + local_end,
        text=replacement_text,
        source_positions=next_run.source_positions[local_start : local_end + 1],
        rect=QRectF(
            content_left,
            text_top,
            max(1.0, boundary_offsets[-1]),
            max(1.0, text_height),
        ),
        baseline=text_top + float(font_metrics.ascent()),
        boundary_offsets=boundary_offsets,
        active=next_run.active,
    )


def content_right(
    *,
    text_width: float,
    document_margin: float,
    content_left_inset: float,
) -> float:
    """Return the right edge available to wrapped prompt content."""

    content_left = document_margin + max(0.0, content_left_inset)
    content_width = max(
        1.0,
        text_width - (document_margin * 2.0) - max(0.0, content_left_inset),
    )
    return content_left + content_width


def remap_lines_for_same_line_plain_edit(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    projection_document: PromptProjectionDocument,
    dirty_line_index: int,
    affected_fragment: PromptProjectionTextFragment,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    width_delta: float,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return lines remapped after a same-line plain text edit."""

    next_lines: list[PromptProjectionLineSnapshot] = list(lines[:dirty_line_index])
    if dirty_line_index < len(lines):
        dirty_line = lines[dirty_line_index]
        next_lines.append(
            remap_dirty_line_for_same_line_plain_edit(
                dirty_line,
                projection_document=projection_document,
                affected_fragment=affected_fragment,
                next_fragment=next_fragment,
                edit_start=edit_start,
                edit_end=edit_end,
                source_delta=source_delta,
                projection_delta=projection_delta,
                width_delta=width_delta,
            )
        )
    downstream_lines = lines[dirty_line_index + 1 :]
    if downstream_lines:
        next_lines.extend(
            remap_downstream_lines_after_plain_edit(
                downstream_lines,
                projection_document=projection_document,
                source_delta=source_delta,
                projection_delta=projection_delta,
            )
        )
    return tuple(next_lines)


def remap_lines_for_empty_line_plain_insert(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    projection_document: PromptProjectionDocument,
    dirty_line_index: int,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return lines remapped after adding the first text fragment to an empty line."""

    next_lines: list[PromptProjectionLineSnapshot] = list(lines[:dirty_line_index])
    if dirty_line_index < len(lines):
        line = lines[dirty_line_index]
        next_fragments = (next_fragment,)
        next_lines.append(
            PromptProjectionLineSnapshot(
                top=line.top,
                height=line.height,
                source_start=line.source_start,
                source_end=line.source_end + source_delta,
                source_content_start=line.source_content_start,
                source_content_end=line.source_content_end + source_delta,
                line_break_start=remap_optional_source_position_for_layout(
                    line.line_break_start,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    delta=source_delta,
                ),
                line_break_end=remap_optional_source_position_for_layout(
                    line.line_break_end,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    delta=source_delta,
                ),
                fragments=next_fragments,
                caret_stops=caret_stops_for_line_fragments(
                    next_fragments,
                    projection_document=projection_document,
                    line_top=line.top,
                    line_height=line.height,
                ),
            )
        )
    next_lines.extend(
        remap_downstream_lines_after_plain_edit(
            lines[dirty_line_index + 1 :],
            projection_document=projection_document,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
    )
    return tuple(next_lines)


def line_fragment_count_without_materializing(
    line: PromptProjectionLineSnapshot,
) -> int:
    """Return a line fragment count without expanding lazy shifted fragments."""

    if isinstance(line, ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is not None:
            return len(fragments)
        base_line = object.__getattribute__(line, "_line")
        return line_fragment_count_without_materializing(base_line)
    return len(line.fragments)


def line_text_fragment_count(line: PromptProjectionLineSnapshot) -> int:
    """Return the number of text fragments on one line."""

    if isinstance(line, ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is None:
            base_line = object.__getattribute__(line, "_line")
            return line_text_fragment_count(base_line)
    return sum(
        isinstance(fragment, PromptProjectionTextFragment)
        for fragment in line.fragments
    )


def line_inline_fragment_count(line: PromptProjectionLineSnapshot) -> int:
    """Return the number of inline object fragments on one line."""

    if isinstance(line, ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is None:
            base_line = object.__getattribute__(line, "_line")
            return line_inline_fragment_count(base_line)
    return sum(
        isinstance(fragment, PromptProjectionInlineObjectFragment)
        for fragment in line.fragments
    )


def remap_dirty_line_for_same_line_plain_edit(
    line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    affected_fragment: PromptProjectionTextFragment,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    width_delta: float,
) -> PromptProjectionLineSnapshot:
    """Return the visual line that directly contains the edit."""

    next_fragments: list[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ] = []
    seen_affected = False
    for fragment in line.fragments:
        if fragment == affected_fragment:
            next_fragments.append(next_fragment)
            seen_affected = True
            continue
        if seen_affected:
            next_fragments.append(
                remap_fragment_after_plain_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    source_delta=source_delta,
                    projection_delta=projection_delta,
                    x_delta=width_delta,
                )
            )
            continue
        next_fragments.append(fragment)
    return PromptProjectionLineSnapshot(
        top=line.top,
        height=line.height,
        source_start=line.source_start,
        source_end=line.source_end + source_delta,
        source_content_start=line.source_content_start,
        source_content_end=line.source_content_end + source_delta,
        line_break_start=remap_optional_source_position_for_layout(
            line.line_break_start,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        ),
        line_break_end=remap_optional_source_position_for_layout(
            line.line_break_end,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        ),
        fragments=tuple(next_fragments),
        caret_stops=caret_stops_for_line_fragments(
            next_fragments,
            projection_document=projection_document,
            line_top=line.top,
            line_height=line.height,
        ),
    )


def remap_downstream_lines_after_plain_edit(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    projection_document: PromptProjectionDocument,
    source_delta: int,
    projection_delta: int,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Shift downstream lines and refresh only existing semantic bindings."""

    semantic_resolver: PromptReusedLineSemanticResolver | None = None
    shifted_lines: list[PromptProjectionLineSnapshot] = []
    for line in lines:
        line_resolver = None
        if shifted_line_has_semantic_resolver(line):
            if semantic_resolver is None:
                semantic_resolver = PromptReusedLineSemanticResolver(
                    projection_document
                )
            line_resolver = semantic_resolver
        shifted_lines.append(
            remap_downstream_line_after_plain_edit(
                line,
                source_delta=source_delta,
                projection_delta=projection_delta,
                semantic_resolver=line_resolver,
            )
        )
    return tuple(shifted_lines)


def remap_downstream_line_after_plain_edit(
    line: PromptProjectionLineSnapshot,
    *,
    source_delta: int,
    projection_delta: int,
    semantic_resolver: PromptReusedLineSemanticResolver | None,
) -> PromptProjectionLineSnapshot:
    """Return a downstream line shifted logically but not geometrically."""

    return ShiftedLineSnapshot(
        line,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=0.0,
        semantic_resolver=semantic_resolver,
    )


def remap_downstream_lines_after_hard_line_edit(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    projection_document: PromptProjectionDocument,
    source_delta: int,
    projection_delta: int,
    y_delta: float,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Shift hard-line suffixes while retaining current semantic ownership."""

    semantic_resolver: PromptReusedLineSemanticResolver | None = None
    shifted_lines: list[PromptProjectionLineSnapshot] = []
    for line in lines:
        line_resolver = None
        if shifted_line_has_semantic_resolver(line):
            if semantic_resolver is None:
                semantic_resolver = PromptReusedLineSemanticResolver(
                    projection_document
                )
            line_resolver = semantic_resolver
        shifted_lines.append(
            remap_downstream_line_after_hard_line_edit(
                line,
                source_delta=source_delta,
                projection_delta=projection_delta,
                y_delta=y_delta,
                semantic_resolver=line_resolver,
            )
        )
    return tuple(shifted_lines)


def remap_downstream_line_after_hard_line_edit(
    line: PromptProjectionLineSnapshot,
    *,
    source_delta: int,
    projection_delta: int,
    y_delta: float,
    semantic_resolver: PromptReusedLineSemanticResolver | None,
) -> PromptProjectionLineSnapshot:
    """Return a downstream line shifted lazily after a hard-line insert/delete."""

    return ShiftedLineSnapshot(
        line,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=y_delta,
        semantic_resolver=semantic_resolver,
    )


def shifted_line_has_semantic_resolver(
    line: PromptProjectionLineSnapshot,
) -> bool:
    """Return whether one lazy line must rebind fragments to current semantics."""

    return bool(
        isinstance(line, ShiftedLineSnapshot)
        and object.__getattribute__(line, "_semantic_resolver") is not None
    )


def remap_fragment_after_plain_edit(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one fragment shifted after an edit."""

    next_rect = QRectF(fragment.rect)
    next_rect.translate(x_delta, 0.0)
    source_positions = tuple(
        remap_source_position_for_layout(
            position,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        )
        for position in fragment.source_positions
    )
    if isinstance(fragment, PromptProjectionTextFragment):
        return PromptProjectionTextFragment(
            run_id=fragment.run_id,
            token_id=fragment.token_id,
            projection_start=fragment.projection_start + projection_delta,
            projection_end=fragment.projection_end + projection_delta,
            text=fragment.text,
            source_positions=source_positions,
            rect=next_rect,
            baseline=fragment.baseline,
            boundary_offsets=fragment.boundary_offsets,
            active=fragment.active,
        )
    return PromptProjectionInlineObjectFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        renderer_key=fragment.renderer_key,
        projection_start=fragment.projection_start + projection_delta,
        projection_end=fragment.projection_end + projection_delta,
        source_positions=source_positions,
        rect=next_rect,
        active=fragment.active,
    )


def remap_fragment_after_hard_line_edit(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
    y_delta: float,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one fragment shifted logically and geometrically across a line edit."""

    next_rect = QRectF(fragment.rect)
    next_rect.translate(x_delta, y_delta)
    source_positions = tuple(
        remap_source_position_for_layout(
            position,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        )
        for position in fragment.source_positions
    )
    if isinstance(fragment, PromptProjectionTextFragment):
        return PromptProjectionTextFragment(
            run_id=fragment.run_id,
            token_id=fragment.token_id,
            projection_start=fragment.projection_start + projection_delta,
            projection_end=fragment.projection_end + projection_delta,
            text=fragment.text,
            source_positions=source_positions,
            rect=next_rect,
            baseline=fragment.baseline + y_delta,
            boundary_offsets=fragment.boundary_offsets,
            active=fragment.active,
        )
    return PromptProjectionInlineObjectFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        renderer_key=fragment.renderer_key,
        projection_start=fragment.projection_start + projection_delta,
        projection_end=fragment.projection_end + projection_delta,
        source_positions=source_positions,
        rect=next_rect,
        active=fragment.active,
    )


def caret_stops_for_line_fragments(
    fragments: Sequence[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ],
    *,
    projection_document: PromptProjectionDocument,
    line_top: float,
    line_height: float,
    extra_boundaries: Sequence[tuple[int, float]] = (),
) -> tuple[PromptProjectionLineCaretStopSnapshot, ...]:
    """Return source-ordered caret stops implied by one visual line."""

    caret_stops: list[PromptProjectionLineCaretStopSnapshot] = []
    seen_positions: set[int] = set()
    for projection_position, x_position in extra_boundaries:
        if not projection_document.caret_map.has_projection_position(
            projection_position
        ):
            continue
        seen_positions.add(projection_position)
        caret_stops.append(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=projection_position,
                rect=QRectF(x_position, line_top, 1.0, line_height),
            )
        )
    for fragment in fragments:
        if isinstance(fragment, PromptProjectionTextFragment):
            for boundary_index, boundary_offset in enumerate(fragment.boundary_offsets):
                projection_position = fragment.projection_start + boundary_index
                if (
                    projection_position in seen_positions
                    or not projection_document.caret_map.has_projection_position(
                        projection_position
                    )
                ):
                    continue
                seen_positions.add(projection_position)
                caret_stops.append(
                    PromptProjectionLineCaretStopSnapshot(
                        projection_position=projection_position,
                        rect=QRectF(
                            fragment.rect.left() + boundary_offset,
                            line_top,
                            1.0,
                            line_height,
                        ),
                    )
                )
            continue
        for projection_position, x_position in (
            (fragment.projection_start, fragment.rect.left()),
            (fragment.projection_end, fragment.rect.right()),
        ):
            if projection_position in seen_positions:
                continue
            seen_positions.add(projection_position)
            caret_stops.append(
                PromptProjectionLineCaretStopSnapshot(
                    projection_position=projection_position,
                    rect=QRectF(x_position, line_top, 1.0, line_height),
                )
            )
    return tuple(
        sorted(
            caret_stops,
            key=lambda caret_stop: caret_stop.projection_position,
        )
    )


def remap_optional_source_position_for_layout(
    position: int | None,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
) -> int | None:
    """Return an optional source position shifted across a layout edit."""

    if position is None:
        return None
    return remap_source_position_for_layout(
        position,
        edit_start=edit_start,
        edit_end=edit_end,
        delta=delta,
    )


def remap_source_position_for_layout(
    position: int,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
) -> int:
    """Return a source position shifted across a non-overlapping edit."""

    if edit_start == edit_end:
        if position >= edit_start:
            return position + delta
        return position
    if position >= edit_end:
        return position + delta
    if position > edit_start:
        return edit_start
    return position


__all__ = [
    "plain_text_run_for_empty_line_insert",
    "text_fragment_for_empty_line_insert",
    "content_right",
    "remap_lines_for_same_line_plain_edit",
    "remap_lines_for_empty_line_plain_insert",
    "line_fragment_count_without_materializing",
    "line_text_fragment_count",
    "line_inline_fragment_count",
    "remap_dirty_line_for_same_line_plain_edit",
    "remap_downstream_lines_after_plain_edit",
    "remap_downstream_line_after_plain_edit",
    "remap_downstream_lines_after_hard_line_edit",
    "remap_downstream_line_after_hard_line_edit",
    "shifted_line_has_semantic_resolver",
    "remap_fragment_after_plain_edit",
    "remap_fragment_after_hard_line_edit",
    "caret_stops_for_line_fragments",
    "remap_optional_source_position_for_layout",
    "remap_source_position_for_layout",
]
