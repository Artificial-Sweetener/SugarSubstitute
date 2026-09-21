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

"""Build immutable layout snapshots directly from visible projection runs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont, QTextLayout

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.presentation.text_coordinates import TextCoordinateMap
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from ..projection.metrics import (
    PromptProjectionMetrics,
    PromptProjectionMetricsFactory,
)
from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from .keep_groups import PromptKeepGroupPlanner, PromptKeepGroupRange
from .layout_pieces import (
    PromptInlineObjectLayoutPiece,
    PromptLayoutPieceBuilder,
    PromptParagraphBreakLayoutPiece,
    PromptStructuralRowLayoutPiece,
    PromptTextLayoutPiece,
)
from .region_rows import PromptRegionStructuralRowLayoutBuilder
from .source_boundaries import (
    PromptLineBoundary,
    PromptLineStartBoundary,
    resolve_line_source_span,
)
from .tag_keep_policy import tag_keep_source_ranges_for_layout
from .text_measurement import PromptTextMeasurementCache
from .wrap_policy import adjust_break_for_word_integrity, visible_wrap_candidate_length


@dataclass(slots=True)
class _PendingTextFragment:
    """Track one text fragment before line height and caret rects are finalized."""

    run: PromptProjectionRun
    text: str
    projection_start: int
    projection_end: int
    source_positions: Sequence[int]
    x_left: float
    width: float
    boundary_offsets: tuple[float, ...]


@dataclass(slots=True)
class _PendingInlineObjectFragment:
    """Track one inline object before line height and caret rects are finalized."""

    run: PromptProjectionRun
    x_left: float
    size: QSizeF


_PendingFragment = _PendingTextFragment | _PendingInlineObjectFragment

_MEASUREMENT_CACHE_ENTRY_LIMIT = 8192

type PromptProjectionLineReuseProbe = Callable[
    [PromptProjectionLineSnapshot], int | None
]


@dataclass(frozen=True, slots=True)
class PromptProjectionLineLayoutBuildResult:
    """Carry a built prefix and the reusable previous suffix boundary."""

    snapshot: PromptProjectionLayoutSnapshot
    reusable_previous_line_index: int | None = None
    source_limited: bool = False


class PromptProjectionLineLayoutBuilder:
    """Lay out one projection document into wrapped lines and fragment geometry."""

    def __init__(
        self,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Store the renderer registry used to measure inline object runs."""

        self._piece_builder = PromptLayoutPieceBuilder(inline_object_renderers)
        self._keep_group_planner = PromptKeepGroupPlanner()
        self._measurement_cache = PromptTextMeasurementCache()
        self._region_row_layout = PromptRegionStructuralRowLayoutBuilder()

    @prompt_editor_work_event(PromptEditorWorkEvent.LAYOUT_SNAPSHOT)
    def build_snapshot(
        self,
        projection_document: PromptProjectionDocument,
        *,
        wrap_width: float,
        base_font: QFont,
        document_margin: float,
        content_left_inset: float = 0.0,
        prompt_document_view: PromptDocumentView | None = None,
        metrics: PromptProjectionMetrics | None = None,
    ) -> PromptProjectionLayoutSnapshot:
        """Build one immutable layout snapshot for the supplied projection document."""

        return self._build_snapshot(
            projection_document,
            wrap_width=wrap_width,
            base_font=base_font,
            document_margin=document_margin,
            content_left_inset=content_left_inset,
            prompt_document_view=prompt_document_view,
            metrics=metrics,
            line_reuse_probe=None,
            source_limit=None,
        ).snapshot

    def build_snapshot_until_reusable_suffix(
        self,
        projection_document: PromptProjectionDocument,
        *,
        wrap_width: float,
        base_font: QFont,
        document_margin: float,
        content_left_inset: float,
        prompt_document_view: PromptDocumentView,
        metrics: PromptProjectionMetrics,
        line_reuse_probe: PromptProjectionLineReuseProbe,
        source_start: int,
        projection_start: int,
        line_top: float,
        source_limit: int,
    ) -> PromptProjectionLineLayoutBuildResult:
        """Build one dirty-line window through the first reusable suffix line."""

        return self._build_snapshot(
            projection_document,
            wrap_width=wrap_width,
            base_font=base_font,
            document_margin=document_margin,
            content_left_inset=content_left_inset,
            prompt_document_view=prompt_document_view,
            metrics=metrics,
            line_reuse_probe=line_reuse_probe,
            source_start=source_start,
            projection_start=projection_start,
            initial_line_top=line_top,
            source_limit=source_limit,
        )

    def _build_snapshot(
        self,
        projection_document: PromptProjectionDocument,
        *,
        wrap_width: float,
        base_font: QFont,
        document_margin: float,
        content_left_inset: float,
        prompt_document_view: PromptDocumentView | None,
        metrics: PromptProjectionMetrics | None,
        line_reuse_probe: PromptProjectionLineReuseProbe | None,
        source_start: int = 0,
        projection_start: int = 0,
        initial_line_top: float | None = None,
        source_limit: int | None = None,
    ) -> PromptProjectionLineLayoutBuildResult:
        """Build projection lines, stopping when a supplied suffix converges."""

        if metrics is None:
            metrics = PromptProjectionMetricsFactory().create(
                base_font=base_font,
                document_margin=document_margin,
                wrap_width=wrap_width,
                content_left_inset=content_left_inset,
            )
        base_font_key = metrics.base_font_key
        content_left = metrics.content_left
        content_width = metrics.content_width
        measurement_cache = self._measurement_cache
        tag_keep_ranges = (
            tag_keep_source_ranges_for_layout(
                prompt_document_view,
                source_start=source_start,
                source_limit=source_limit,
            )
            if prompt_document_view is not None
            else ()
        )
        source_split_positions = self._keep_group_planner.source_split_positions(
            projection_document,
            tag_keep_ranges=tag_keep_ranges,
            source_start=source_start,
            source_limit=source_limit,
        )
        layout_pieces = self._piece_builder.build(
            projection_document,
            base_font=base_font,
            source_split_positions=source_split_positions,
            source_start=source_start,
            source_limit=source_limit,
        )
        keep_groups = self._keep_group_planner.build(
            projection_document,
            layout_pieces=layout_pieces,
            tag_keep_ranges=tag_keep_ranges,
            base_font=base_font,
            base_font_key=base_font_key,
            content_width=content_width,
            measurement_cache=measurement_cache,
        )
        keep_group_by_start = {group.start_index: group for group in keep_groups}

        line_top = (
            metrics.initial_line_top() if initial_line_top is None else initial_line_top
        )
        line_height = metrics.initial_row_height()
        line_width = 0.0
        line_start_boundaries = [
            PromptLineStartBoundary(projection_start, source_start)
        ]
        current_boundaries: list[PromptLineBoundary] = []
        pending_fragments: list[_PendingFragment] = []
        lines: list[PromptProjectionLineSnapshot] = []
        text_fragments: list[PromptProjectionTextFragment] = []
        inline_object_fragments: list[PromptProjectionInlineObjectFragment] = []
        caret_rects_by_projection_position: dict[int, QRectF] = {}
        reusable_previous_line_index: int | None = None

        def open_line(start_boundaries: list[PromptLineStartBoundary]) -> None:
            nonlocal line_height, line_width, line_start_boundaries, current_boundaries
            line_height = metrics.initial_row_height()
            line_width = 0.0
            line_start_boundaries = list(start_boundaries)
            current_boundaries = [
                PromptLineBoundary(
                    boundary.projection_position,
                    content_left,
                    boundary.source_position,
                )
                for boundary in line_start_boundaries
            ]

        def finish_line(
            next_start_boundaries: list[PromptLineStartBoundary] | None,
            *,
            allow_reuse: bool = True,
        ) -> None:
            nonlocal line_top, pending_fragments, reusable_previous_line_index

            realized_fragments: list[
                PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
            ] = []
            realized_caret_stops: list[PromptProjectionLineCaretStopSnapshot] = []
            realized_caret_positions: set[int] = set()

            text_baseline = metrics.text_baseline_for_row(
                row_top=line_top,
                row_height=line_height,
            )

            for pending_fragment in pending_fragments:
                if isinstance(pending_fragment, _PendingTextFragment):
                    fragment_rect = metrics.text_fragment_rect(
                        x_left=pending_fragment.x_left,
                        row_top=line_top,
                        row_height=line_height,
                        width=pending_fragment.width,
                    )
                    realized_text_fragment = PromptProjectionTextFragment(
                        run_id=pending_fragment.run.run_id,
                        token_id=pending_fragment.run.token_id,
                        projection_start=pending_fragment.projection_start,
                        projection_end=pending_fragment.projection_end,
                        text=pending_fragment.text,
                        source_positions=pending_fragment.source_positions,
                        rect=fragment_rect,
                        baseline=text_baseline,
                        boundary_offsets=pending_fragment.boundary_offsets,
                        active=pending_fragment.run.active,
                    )
                    realized_fragments.append(realized_text_fragment)
                    text_fragments.append(realized_text_fragment)
                    if pending_fragment.run.source_backed:
                        for boundary_index, boundary_offset in enumerate(
                            pending_fragment.boundary_offsets
                        ):
                            projection_position = (
                                pending_fragment.projection_start + boundary_index
                            )
                            caret_rect = metrics.caret_rect(
                                x_left=pending_fragment.x_left + boundary_offset,
                                row_top=line_top,
                                row_height=line_height,
                            )
                            caret_rects_by_projection_position[projection_position] = (
                                caret_rect
                            )
                            if projection_position not in realized_caret_positions:
                                realized_caret_positions.add(projection_position)
                                realized_caret_stops.append(
                                    PromptProjectionLineCaretStopSnapshot(
                                        projection_position=projection_position,
                                        rect=caret_rect,
                                    )
                                )
                    continue

                object_rect = metrics.inline_object_rect(
                    x_left=pending_fragment.x_left,
                    row_top=line_top,
                    row_height=line_height,
                    size=pending_fragment.size,
                )
                realized_object_fragment = PromptProjectionInlineObjectFragment(
                    run_id=pending_fragment.run.run_id,
                    token_id=pending_fragment.run.token_id,
                    renderer_key=cast(str, pending_fragment.run.renderer_key),
                    projection_start=pending_fragment.run.projection_start,
                    projection_end=pending_fragment.run.projection_end,
                    source_positions=pending_fragment.run.source_positions,
                    rect=object_rect,
                    active=pending_fragment.run.active,
                )
                realized_fragments.append(realized_object_fragment)
                inline_object_fragments.append(realized_object_fragment)
                caret_rects_by_projection_position[
                    pending_fragment.run.projection_start
                ] = metrics.caret_rect(
                    x_left=object_rect.left(),
                    row_top=line_top,
                    row_height=line_height,
                )
                caret_rects_by_projection_position[
                    pending_fragment.run.projection_end
                ] = metrics.caret_rect(
                    x_left=object_rect.right(),
                    row_top=line_top,
                    row_height=line_height,
                )

            for boundary in current_boundaries:
                projection_position = boundary.projection_position
                caret_rect = metrics.caret_rect(
                    x_left=boundary.x_position,
                    row_top=line_top,
                    row_height=line_height,
                )
                if projection_position not in realized_caret_positions:
                    realized_caret_positions.add(projection_position)
                    realized_caret_stops.append(
                        PromptProjectionLineCaretStopSnapshot(
                            projection_position=projection_position,
                            rect=caret_rect,
                        )
                    )
                caret_rects_by_projection_position.setdefault(
                    projection_position,
                    caret_rect,
                )

            source_span = resolve_line_source_span(
                projection_document,
                current_boundaries=current_boundaries,
                next_start_boundaries=next_start_boundaries,
            )
            completed_line = PromptProjectionLineSnapshot(
                top=line_top,
                height=line_height,
                source_start=source_span.source_start,
                source_end=source_span.source_end,
                source_content_start=source_span.source_content_start,
                source_content_end=source_span.source_content_end,
                line_break_start=source_span.line_break_start,
                line_break_end=source_span.line_break_end,
                fragments=tuple(realized_fragments),
                caret_stops=tuple(realized_caret_stops),
            )
            lines.append(completed_line)
            line_top += line_height
            pending_fragments = []
            if allow_reuse and line_reuse_probe is not None:
                reusable_previous_line_index = line_reuse_probe(completed_line)
                if reusable_previous_line_index is not None:
                    return
            if next_start_boundaries is not None:
                open_line(next_start_boundaries)

        def append_inline_object_piece(piece: PromptInlineObjectLayoutPiece) -> None:
            """Append one inline object piece without adding a line break."""

            nonlocal line_height, line_width

            object_size = QSizeF(
                min(piece.size.width(), content_width),
                piece.size.height(),
            )
            pending_fragments.append(
                _PendingInlineObjectFragment(
                    run=piece.run,
                    x_left=content_left + line_width,
                    size=object_size,
                )
            )
            current_boundaries.append(
                PromptLineBoundary(
                    piece.run.projection_start,
                    content_left + line_width,
                    piece.run.source_positions[0],
                )
            )
            line_width += object_size.width()
            line_height = metrics.row_height_with_inline_object(
                line_height,
                object_size,
            )
            current_boundaries.append(
                PromptLineBoundary(
                    piece.run.projection_end,
                    content_left + line_width,
                    piece.run.source_positions[-1],
                )
            )

        def append_text_piece_unwrapped(piece: PromptTextLayoutPiece) -> None:
            """Append one text piece as a single unwrapped visual fragment."""

            nonlocal line_height, line_width

            piece_font = measurement_cache.font_for_run(
                piece.run,
                base_font,
                base_font_key=base_font_key,
            )
            boundary_offsets = measurement_cache.unwrapped_text_offsets(
                piece.text,
                piece_font,
            )
            consumed_width = boundary_offsets[-1]
            pending_fragments.append(
                _PendingTextFragment(
                    run=piece.run,
                    text=piece.text,
                    projection_start=piece.projection_start,
                    projection_end=piece.projection_start + len(piece.text),
                    source_positions=piece.source_positions,
                    x_left=content_left + line_width,
                    width=max(1.0, consumed_width),
                    boundary_offsets=boundary_offsets,
                )
            )
            if piece.run.source_backed:
                current_boundaries.append(
                    PromptLineBoundary(
                        piece.projection_start,
                        content_left + line_width,
                        piece.source_positions[0],
                    )
                )
                current_boundaries.append(
                    PromptLineBoundary(
                        piece.projection_start + len(piece.text),
                        content_left + line_width + consumed_width,
                        piece.source_positions[-1],
                    )
                )
            line_width += consumed_width

        def append_keep_group(group: PromptKeepGroupRange) -> None:
            """Append a fitting keep group on the current visual line."""

            for group_piece in layout_pieces[group.start_index : group.end_index]:
                if isinstance(group_piece, PromptInlineObjectLayoutPiece):
                    append_inline_object_piece(group_piece)
                    continue
                if isinstance(group_piece, PromptTextLayoutPiece):
                    append_text_piece_unwrapped(group_piece)

        def place_keep_group(group: PromptKeepGroupRange) -> None:
            """Place one keep group, moving it to the next line when needed."""

            if line_width > 0.0 and group.width > content_width - line_width:
                finish_line([])
                if reusable_previous_line_index is not None:
                    return
            append_keep_group(group)

        open_line(line_start_boundaries)
        piece_index = 0
        while piece_index < len(layout_pieces):
            if reusable_previous_line_index is not None:
                break
            keep_group = keep_group_by_start.get(piece_index)
            if keep_group is not None:
                place_keep_group(keep_group)
                piece_index = keep_group.end_index
                continue

            piece = layout_pieces[piece_index]
            if isinstance(piece, PromptParagraphBreakLayoutPiece):
                next_piece = (
                    layout_pieces[piece_index + 1]
                    if piece_index + 1 < len(layout_pieces)
                    else None
                )
                current_boundaries.append(
                    PromptLineBoundary(
                        piece.projection_start,
                        content_left + line_width,
                        piece.source_start,
                    )
                )
                if isinstance(next_piece, PromptStructuralRowLayoutPiece):
                    current_boundaries.append(
                        PromptLineBoundary(
                            piece.projection_end,
                            content_left + line_width,
                            next_piece.run.source_start,
                        )
                    )
                finish_line(
                    [
                        PromptLineStartBoundary(
                            piece.projection_end,
                            piece.source_end,
                        )
                    ]
                )
                piece_index += 1
                continue

            if isinstance(piece, PromptStructuralRowLayoutPiece):
                follows_structural_row = piece_index > 0 and isinstance(
                    layout_pieces[piece_index - 1], PromptStructuralRowLayoutPiece
                )
                leading_caret_rect = caret_rects_by_projection_position.get(
                    piece.run.projection_start
                )
                if leading_caret_rect is None or follows_structural_row:
                    finish_line(None)
                    leading_caret_rect = caret_rects_by_projection_position[
                        piece.run.projection_start
                    ]
                structural_layout = self._region_row_layout.build(
                    piece.run,
                    top=line_top,
                    content_left=content_left,
                    leading_caret_rect=leading_caret_rect,
                    metrics=metrics,
                )
                lines.append(structural_layout.line)
                caret_rects_by_projection_position.setdefault(
                    piece.run.projection_start,
                    leading_caret_rect,
                )
                caret_rects_by_projection_position[piece.run.projection_end] = (
                    structural_layout.trailing_caret_rect
                )
                line_top += structural_layout.line.height
                pending_fragments = []
                open_line(
                    [
                        PromptLineStartBoundary(
                            piece.run.projection_end,
                            structural_layout.following_line_source_start,
                        )
                    ]
                )
                piece_index += 1
                continue

            if isinstance(piece, PromptInlineObjectLayoutPiece):
                object_size = QSizeF(
                    min(piece.size.width(), content_width),
                    piece.size.height(),
                )
                available_width = content_width - line_width
                if line_width > 0.0 and object_size.width() > available_width:
                    finish_line([])
                    continue
                pending_fragments.append(
                    _PendingInlineObjectFragment(
                        run=piece.run,
                        x_left=content_left + line_width,
                        size=object_size,
                    )
                )
                current_boundaries.append(
                    PromptLineBoundary(
                        piece.run.projection_start,
                        content_left + line_width,
                        piece.run.source_positions[0],
                    )
                )
                line_width += object_size.width()
                line_height = metrics.row_height_with_inline_object(
                    line_height,
                    object_size,
                )
                current_boundaries.append(
                    PromptLineBoundary(
                        piece.run.projection_end,
                        content_left + line_width,
                        piece.run.source_positions[-1],
                    )
                )
                piece_index += 1
                continue

            cluster: list[PromptTextLayoutPiece] = []
            cluster_font: QFont | None = None
            while piece_index < len(layout_pieces):
                if piece_index in keep_group_by_start:
                    break
                next_piece = layout_pieces[piece_index]
                if not isinstance(next_piece, PromptTextLayoutPiece):
                    break
                next_piece_font = measurement_cache.font_for_run(
                    next_piece.run,
                    base_font,
                    base_font_key=base_font_key,
                )
                if cluster_font is None:
                    cluster_font = next_piece_font
                elif next_piece_font != cluster_font:
                    break
                cluster.append(next_piece)
                piece_index += 1
            if cluster_font is None:
                continue
            cluster_text = "".join(text_piece.text for text_piece in cluster)
            cluster_offsets: list[int] = []
            cluster_offset = 0
            for text_piece in cluster:
                cluster_offsets.append(cluster_offset)
                cluster_offset += len(text_piece.text)

            consumed_cluster_length = 0
            while consumed_cluster_length < len(cluster_text):
                if reusable_previous_line_index is not None:
                    break
                if line_width >= content_width and line_width > 0.0:
                    finish_line([])
                    continue
                remaining_text = cluster_text[consumed_cluster_length:]
                text_layout = QTextLayout(remaining_text, cluster_font)
                text_layout.setTextOption(measurement_cache.wrap_option)
                text_layout.beginLayout()
                text_line = text_layout.createLine()
                if not text_line.isValid():
                    text_layout.endLayout()
                    break
                text_line.setLineWidth(max(1.0, content_width - line_width))
                text_layout.endLayout()

                candidate_length = max(
                    1,
                    TextCoordinateMap(remaining_text).utf16_to_python(
                        text_line.textLength(),
                        prefer_after=False,
                    ),
                )
                available_width = max(1.0, content_width - line_width)
                candidate_length = visible_wrap_candidate_length(
                    remaining_text,
                    candidate_length=candidate_length,
                    available_width=available_width,
                    font=cluster_font,
                    measurement_cache=measurement_cache,
                )
                if candidate_length == 0:
                    if line_width > 0.0:
                        finish_line([])
                        continue
                    candidate_length = 1
                break_decision = adjust_break_for_word_integrity(
                    cluster_text,
                    consumed_cluster_length=consumed_cluster_length,
                    candidate_length=candidate_length,
                    line_has_content=line_width > 0.0,
                    font=cluster_font,
                    content_width=content_width,
                    measurement_cache=measurement_cache,
                )
                if break_decision.break_before_text:
                    finish_line([])
                    continue

                consumed_length = max(1, break_decision.consumed_length)
                line_start = consumed_cluster_length
                line_end = consumed_cluster_length + consumed_length
                line_boundary_offsets = measurement_cache.unwrapped_text_offsets(
                    cluster_text[line_start:line_end],
                    cluster_font,
                )
                consumed_width = line_boundary_offsets[-1]
                for piece_offset, text_piece in zip(
                    cluster_offsets, cluster, strict=True
                ):
                    piece_start = piece_offset
                    piece_end = piece_offset + len(text_piece.text)
                    overlap_start = max(line_start, piece_start)
                    overlap_end = min(line_end, piece_end)
                    if overlap_end <= overlap_start:
                        continue

                    local_start = overlap_start - piece_start
                    local_end = overlap_end - piece_start
                    line_local_start = overlap_start - consumed_cluster_length
                    boundary_offsets = line_boundary_offsets[
                        line_local_start : line_local_start
                        + (local_end - local_start)
                        + 1
                    ]
                    fragment_x_left = content_left + line_width + boundary_offsets[0]
                    fragment_width = max(
                        1.0,
                        boundary_offsets[-1] - boundary_offsets[0],
                    )
                    pending_fragments.append(
                        _PendingTextFragment(
                            run=text_piece.run,
                            text=text_piece.text[local_start:local_end],
                            projection_start=(
                                text_piece.projection_start + local_start
                            ),
                            projection_end=text_piece.projection_start + local_end,
                            source_positions=text_piece.source_positions[
                                local_start : local_end + 1
                            ],
                            x_left=fragment_x_left,
                            width=fragment_width,
                            boundary_offsets=tuple(
                                offset - boundary_offsets[0]
                                for offset in boundary_offsets
                            ),
                        ),
                    )
                    if text_piece.run.source_backed:
                        current_boundaries.append(
                            PromptLineBoundary(
                                text_piece.projection_start + local_start,
                                content_left + line_width + boundary_offsets[0],
                                text_piece.source_positions[local_start],
                            )
                        )
                        current_boundaries.append(
                            PromptLineBoundary(
                                text_piece.projection_start + local_end,
                                content_left + line_width + boundary_offsets[-1],
                                text_piece.source_positions[local_end],
                            )
                        )

                line_width += consumed_width
                consumed_cluster_length += consumed_length
                if consumed_cluster_length < len(cluster_text):
                    finish_line([])

        source_limited = source_limit is not None and source_limit < len(
            projection_document.source_text
        )
        if reusable_previous_line_index is None and (
            pending_fragments or line_start_boundaries or not lines
        ):
            finish_line(None, allow_reuse=not source_limited)

        content_height = line_top + document_margin
        snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(max(1.0, wrap_width), max(1.0, content_height)),
            lines=tuple(lines),
            text_fragments=tuple(text_fragments),
            inline_object_fragments=tuple(inline_object_fragments),
            caret_rects_by_projection_position=caret_rects_by_projection_position,
        )
        measurement_cache_entries_after = measurement_cache.entry_count()
        if measurement_cache_entries_after > _MEASUREMENT_CACHE_ENTRY_LIMIT:
            measurement_cache.clear()
        return PromptProjectionLineLayoutBuildResult(
            snapshot=snapshot,
            reusable_previous_line_index=reusable_previous_line_index,
            source_limited=source_limited,
        )


__all__ = [
    "PromptProjectionLineLayoutBuilder",
]
