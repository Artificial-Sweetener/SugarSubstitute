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

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import cast

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont, QFontMetricsF, QTextLayout, QTextOption

from substitute.application.prompt_editor import PromptDocumentView

from .model import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
)
from .metrics import PromptProjectionMetrics, PromptProjectionMetricsFactory
from .snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .text_style import projection_text_run_font
from .tokens import PromptProjectionInlineObjectRendererRegistry


@dataclass(frozen=True, slots=True)
class _TextPiece:
    """Describe one text-only piece emitted while splitting runs around newlines."""

    run: PromptProjectionRun
    text: str
    projection_start: int
    source_positions: Sequence[int]


@dataclass(frozen=True, slots=True)
class _InlineObjectPiece:
    """Describe one inline object piece emitted for layout."""

    run: PromptProjectionRun
    size: QSizeF


@dataclass(frozen=True, slots=True)
class _ParagraphBreak:
    """Describe one explicit paragraph break emitted from a text run newline."""

    projection_start: int
    projection_end: int
    source_start: int
    source_end: int


_LayoutPiece = _TextPiece | _InlineObjectPiece | _ParagraphBreak


@dataclass(frozen=True, slots=True)
class _LineStartBoundary:
    """Describe a source-aware boundary that opens one visual line."""

    projection_position: int
    source_position: int | None = None


@dataclass(frozen=True, slots=True)
class _LineBoundary:
    """Describe a source-aware line-local caret boundary."""

    projection_position: int
    x_position: float
    source_position: int | None = None


@dataclass(frozen=True, slots=True)
class _KeepGroupRange:
    """Describe a piece-index range that should be line-broken as one unit."""

    start_index: int
    end_index: int
    width: float
    reason: str


@dataclass(frozen=True, slots=True)
class _PieceSourceRange:
    """Describe the source range covered by one layout piece."""

    index: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _TextBreakDecision:
    """Describe an accepted text break after enforcing word integrity."""

    consumed_length: int
    break_before_text: bool = False


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

_MAX_KEPT_SEGMENT_WORDS = 3
_WORD_JOINING_CHARACTERS = frozenset(("_", "-", "'"))
_WIDTH_EPSILON = 0.01
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


@dataclass(slots=True)
class _TextMeasurementCache:
    """Cache text measurements during one projection layout snapshot build."""

    no_wrap_option: QTextOption = field(default_factory=lambda: _text_option_no_wrap())
    wrap_option: QTextOption = field(default_factory=lambda: _text_option_word_wrap())
    offsets_by_key: dict[tuple[str, str], tuple[float, ...]] = field(
        default_factory=dict
    )
    width_by_key: dict[tuple[str, str], float] = field(default_factory=dict)
    word_fit_by_key: dict[tuple[str, str, int], bool] = field(default_factory=dict)
    font_by_run_key: dict[tuple[str, str, bool, str | None], QFont] = field(
        default_factory=dict
    )
    key_by_font_id: dict[int, tuple[QFont, str]] = field(default_factory=dict)

    def font_key(self, font: QFont) -> str:
        """Return one cached stable key for a retained Qt font wrapper."""

        font_id = id(font)
        cached = self.key_by_font_id.get(font_id)
        if cached is not None and cached[0] is font:
            return cached[1]
        key = font.toString()
        self.key_by_font_id[font_id] = (font, key)
        return key

    def font_for_run(
        self,
        run: PromptProjectionRun,
        base_font: QFont,
        *,
        base_font_key: str,
    ) -> QFont:
        """Return the projected font for one run using a per-snapshot cache."""

        key = (
            run.run_id,
            base_font_key,
            run.active,
            run.text_style_variant,
        )
        cached_font = self.font_by_run_key.get(key)
        if cached_font is not None:
            return cached_font
        font = projection_text_run_font(run, base_font)
        self.font_by_run_key[key] = font
        return font

    def unwrapped_text_offsets(self, text: str, font: QFont) -> tuple[float, ...]:
        """Return cached unwrapped cursor offsets for every text boundary."""

        if not text:
            return (0.0,)
        key = (text, self.font_key(font))
        cached_offsets = self.offsets_by_key.get(key)
        if cached_offsets is not None:
            return cached_offsets
        offsets = _unwrapped_text_offsets_uncached(
            text,
            font,
            no_wrap_option=self.no_wrap_option,
        )
        self.offsets_by_key[key] = offsets
        self.width_by_key[key] = offsets[-1]
        return offsets

    def text_width(self, text: str, font: QFont) -> float:
        """Return cached unwrapped text width."""

        key = (text, self.font_key(font))
        cached_width = self.width_by_key.get(key)
        if cached_width is not None:
            return cached_width
        return self.unwrapped_text_offsets(text, font)[-1]

    def word_fits_content_width(
        self,
        text: str,
        *,
        font: QFont,
        content_width: float,
    ) -> bool:
        """Return cached word-fit decisions for one snapshot."""

        key = (text, self.font_key(font), round(content_width * 100))
        cached_fit = self.word_fit_by_key.get(key)
        if cached_fit is not None:
            return cached_fit
        fits = self.text_width(text, font) <= content_width + _WIDTH_EPSILON
        self.word_fit_by_key[key] = fits
        return fits

    def entry_count(self) -> int:
        """Return the approximate number of cached measurement decisions."""

        return (
            len(self.offsets_by_key)
            + len(self.width_by_key)
            + len(self.word_fit_by_key)
            + len(self.font_by_run_key)
            + len(self.key_by_font_id)
        )

    def clear(self) -> None:
        """Discard cached text measurement decisions."""

        self.offsets_by_key.clear()
        self.width_by_key.clear()
        self.word_fit_by_key.clear()
        self.font_by_run_key.clear()
        self.key_by_font_id.clear()


class PromptProjectionLineLayoutBuilder:
    """Lay out one projection document into wrapped lines and fragment geometry."""

    def __init__(
        self,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Store the renderer registry used to measure inline object runs."""

        self._inline_object_renderers = inline_object_renderers
        self._measurement_cache = _TextMeasurementCache()

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
        source_split_positions = self._source_split_positions(
            projection_document,
            prompt_document_view=prompt_document_view,
            tag_keep_ranges=tag_keep_ranges,
            source_start=source_start,
            source_limit=source_limit,
        )
        layout_pieces = self._layout_pieces(
            projection_document,
            base_font=base_font,
            source_split_positions=source_split_positions,
            source_start=source_start,
            source_limit=source_limit,
        )
        keep_groups = self._keep_groups(
            projection_document,
            layout_pieces=layout_pieces,
            prompt_document_view=prompt_document_view,
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
        line_start_boundaries = [_LineStartBoundary(projection_start, source_start)]
        current_boundaries: list[_LineBoundary] = []
        pending_fragments: list[_PendingFragment] = []
        lines: list[PromptProjectionLineSnapshot] = []
        text_fragments: list[PromptProjectionTextFragment] = []
        inline_object_fragments: list[PromptProjectionInlineObjectFragment] = []
        caret_rects_by_projection_position: dict[int, QRectF] = {}
        reusable_previous_line_index: int | None = None

        def open_line(start_boundaries: list[_LineStartBoundary]) -> None:
            nonlocal line_height, line_width, line_start_boundaries, current_boundaries
            line_height = metrics.initial_row_height()
            line_width = 0.0
            line_start_boundaries = list(start_boundaries)
            current_boundaries = [
                _LineBoundary(
                    boundary.projection_position,
                    content_left,
                    boundary.source_position,
                )
                for boundary in line_start_boundaries
            ]

        def finish_line(next_start_boundaries: list[_LineStartBoundary] | None) -> None:
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

            (
                line_source_start,
                line_source_end,
                line_source_content_start,
                line_source_content_end,
                line_break_start,
                line_break_end,
            ) = _line_source_boundaries(
                projection_document,
                current_boundaries=current_boundaries,
                next_start_boundaries=next_start_boundaries,
            )
            completed_line = PromptProjectionLineSnapshot(
                top=line_top,
                height=line_height,
                source_start=line_source_start,
                source_end=line_source_end,
                source_content_start=line_source_content_start,
                source_content_end=line_source_content_end,
                line_break_start=line_break_start,
                line_break_end=line_break_end,
                fragments=tuple(realized_fragments),
                caret_stops=tuple(realized_caret_stops),
            )
            lines.append(completed_line)
            line_top += line_height
            pending_fragments = []
            if line_reuse_probe is not None:
                reusable_previous_line_index = line_reuse_probe(completed_line)
                if reusable_previous_line_index is not None:
                    return
            if next_start_boundaries is not None:
                open_line(next_start_boundaries)

        def append_inline_object_piece(piece: _InlineObjectPiece) -> None:
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
                _LineBoundary(
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
                _LineBoundary(
                    piece.run.projection_end,
                    content_left + line_width,
                    piece.run.source_positions[-1],
                )
            )

        def append_text_piece_unwrapped(piece: _TextPiece) -> None:
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
                    _LineBoundary(
                        piece.projection_start,
                        content_left + line_width,
                        piece.source_positions[0],
                    )
                )
                current_boundaries.append(
                    _LineBoundary(
                        piece.projection_start + len(piece.text),
                        content_left + line_width + consumed_width,
                        piece.source_positions[-1],
                    )
                )
            line_width += consumed_width

        def append_keep_group(group: _KeepGroupRange) -> None:
            """Append a fitting keep group on the current visual line."""

            for group_piece in layout_pieces[group.start_index : group.end_index]:
                if isinstance(group_piece, _InlineObjectPiece):
                    append_inline_object_piece(group_piece)
                    continue
                if isinstance(group_piece, _TextPiece):
                    append_text_piece_unwrapped(group_piece)

        def place_keep_group(group: _KeepGroupRange) -> None:
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
            if isinstance(piece, _ParagraphBreak):
                current_boundaries.append(
                    _LineBoundary(
                        piece.projection_start,
                        content_left + line_width,
                        piece.source_start,
                    )
                )
                finish_line(
                    [_LineStartBoundary(piece.projection_end, piece.source_end)]
                )
                piece_index += 1
                continue

            if isinstance(piece, _InlineObjectPiece):
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
                    _LineBoundary(
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
                    _LineBoundary(
                        piece.run.projection_end,
                        content_left + line_width,
                        piece.run.source_positions[-1],
                    )
                )
                piece_index += 1
                continue

            cluster: list[_TextPiece] = []
            cluster_font: QFont | None = None
            while piece_index < len(layout_pieces):
                if piece_index in keep_group_by_start:
                    break
                next_piece = layout_pieces[piece_index]
                if not isinstance(next_piece, _TextPiece):
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

                candidate_length = max(1, text_line.textLength())
                break_decision = _adjust_break_for_word_integrity(
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
                            _LineBoundary(
                                text_piece.projection_start + local_start,
                                content_left + line_width + boundary_offsets[0],
                                text_piece.source_positions[local_start],
                            )
                        )
                        current_boundaries.append(
                            _LineBoundary(
                                text_piece.projection_start + local_end,
                                content_left + line_width + boundary_offsets[-1],
                                text_piece.source_positions[local_end],
                            )
                        )

                line_width += consumed_width
                consumed_cluster_length += consumed_length
                if consumed_cluster_length < len(cluster_text):
                    finish_line([])

        if reusable_previous_line_index is None and (
            pending_fragments or line_start_boundaries or not lines
        ):
            finish_line(None)

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
            source_limited=(
                source_limit is not None
                and source_limit < len(projection_document.source_text)
            ),
        )

    def _layout_pieces(
        self,
        projection_document: PromptProjectionDocument,
        *,
        base_font: QFont,
        source_split_positions: frozenset[int] = frozenset(),
        source_start: int = 0,
        source_limit: int | None = None,
    ) -> tuple[_LayoutPiece, ...]:
        """Split visible runs into text pieces, inline objects, and paragraph breaks."""

        pieces: list[_LayoutPiece] = []
        for run in projection_document.runs:
            if (
                source_start > 0
                and run.source_end <= source_start
                and run.source_start < source_start
            ):
                continue
            if source_limit is not None and run.source_start > source_limit:
                break
            if run.kind is PromptProjectionRunKind.INLINE_OBJECT:
                token = projection_document.token_by_id(run.token_id)
                if token is None:
                    continue
                renderer = self._inline_object_renderers.renderer_for(run.renderer_key)
                if renderer is None:
                    continue
                pieces.append(
                    _InlineObjectPiece(
                        run=run,
                        size=renderer.measure_inline_object(
                            run,
                            token,
                            base_font=base_font,
                        ),
                    )
                )
                continue

            display_start = 0
            if (
                source_start > 0
                and run.source_backed
                and run.source_start < source_start
            ):
                display_start = min(
                    len(run.display_text),
                    bisect_left(run.source_positions, source_start),
                )
            display_end = len(run.display_text)
            if (
                source_limit is not None
                and run.source_backed
                and run.source_end > source_limit
            ):
                display_end = max(
                    0,
                    bisect_right(run.source_positions, source_limit) - 1,
                )
            piece_start = display_start
            while True:
                newline_index = run.display_text.find(
                    "\n",
                    piece_start,
                    display_end,
                )
                if newline_index < 0:
                    if piece_start < display_end:
                        pieces.extend(
                            self._split_text_piece(
                                run,
                                start=piece_start,
                                end=display_end,
                                source_split_positions=source_split_positions,
                            )
                        )
                    break
                if newline_index > piece_start:
                    pieces.extend(
                        self._split_text_piece(
                            run,
                            start=piece_start,
                            end=newline_index,
                            source_split_positions=source_split_positions,
                        )
                    )
                pieces.append(
                    _ParagraphBreak(
                        projection_start=run.projection_start + newline_index,
                        projection_end=run.projection_start + newline_index + 1,
                        source_start=run.source_positions[newline_index],
                        source_end=run.source_positions[newline_index + 1],
                    )
                )
                piece_start = newline_index + 1
        return tuple(pieces)

    def _split_text_piece(
        self,
        run: PromptProjectionRun,
        *,
        start: int,
        end: int,
        source_split_positions: frozenset[int],
    ) -> tuple[_TextPiece, ...]:
        """Split one text run slice at source boundaries needed by keep groups."""

        if not run.source_backed:
            return (
                _TextPiece(
                    run=run,
                    text=run.display_text[start:end],
                    projection_start=run.projection_start + start,
                    source_positions=run.source_positions[start : end + 1],
                ),
            )
        split_offsets = [
            offset
            for offset in range(start + 1, end)
            if run.source_positions[offset] in source_split_positions
        ]
        piece_offsets = (start, *split_offsets, end)
        pieces: list[_TextPiece] = []
        for piece_start, piece_end in zip(
            piece_offsets,
            piece_offsets[1:],
        ):
            if piece_end <= piece_start:
                continue
            pieces.append(
                _TextPiece(
                    run=run,
                    text=run.display_text[piece_start:piece_end],
                    projection_start=run.projection_start + piece_start,
                    source_positions=run.source_positions[piece_start : piece_end + 1],
                )
            )
        return tuple(pieces)

    def _source_split_positions(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None,
        tag_keep_ranges: tuple[tuple[int, int], ...],
        source_start: int,
        source_limit: int | None,
    ) -> frozenset[int]:
        """Return source positions where text pieces should split for grouping."""

        split_positions: set[int] = set()
        if prompt_document_view is not None:
            for keep_start, keep_end in tag_keep_ranges:
                split_positions.add(keep_start)
                split_positions.add(keep_end)

        for run_index, run in enumerate(projection_document.runs):
            if (
                source_start > 0
                and run.source_end <= source_start
                and run.source_start < source_start
            ):
                continue
            if source_limit is not None and run.source_start > source_limit:
                break
            if run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
                content_run = _next_token_content_run(
                    projection_document.runs,
                    run_index=run_index,
                    token_id=run.token_id,
                )
                if content_run is not None:
                    split_position = _first_word_end_source_position(content_run)
                    if split_position is not None:
                        split_positions.add(split_position)
            if run.role is PromptProjectionRunRole.TOKEN_TRAILING_DECORATION:
                content_run = _previous_token_content_run(
                    projection_document.runs,
                    run_index=run_index,
                    token_id=run.token_id,
                )
                if content_run is not None:
                    split_position = _last_word_start_source_position(content_run)
                    if split_position is not None:
                        split_positions.add(split_position)
        return frozenset(split_positions)

    def _keep_groups(
        self,
        projection_document: PromptProjectionDocument,
        *,
        layout_pieces: tuple[_LayoutPiece, ...],
        prompt_document_view: PromptDocumentView | None,
        tag_keep_ranges: tuple[tuple[int, int], ...],
        base_font: QFont,
        base_font_key: str,
        content_width: float,
        measurement_cache: _TextMeasurementCache,
    ) -> tuple[_KeepGroupRange, ...]:
        """Return fitting tag and decoration keep groups keyed by piece order."""

        if projection_document.display_mode is PromptProjectionDisplayMode.RAW:
            return ()

        piece_width_prefix_sums = _piece_width_prefix_sums(
            tuple(
                _piece_width(
                    piece,
                    base_font=base_font,
                    base_font_key=base_font_key,
                    content_width=content_width,
                    measurement_cache=measurement_cache,
                )
                for piece in layout_pieces
            )
        )
        groups: list[_KeepGroupRange] = []
        occupied_indices: set[int] = set()
        piece_ranges = _piece_source_ranges(layout_pieces)
        range_search_start = 0
        if prompt_document_view is not None:
            for source_start, source_end in tag_keep_ranges:
                group, range_search_start = self._source_range_keep_group(
                    layout_pieces,
                    piece_ranges=piece_ranges,
                    search_start_index=range_search_start,
                    source_start=source_start,
                    source_end=source_end,
                    piece_width_prefix_sums=piece_width_prefix_sums,
                    content_width=content_width,
                    reason="tag",
                )
                if group is None:
                    continue
                groups.append(group)
                occupied_indices.update(range(group.start_index, group.end_index))

        for group in self._decoration_keep_groups(
            layout_pieces,
            piece_width_prefix_sums=piece_width_prefix_sums,
            content_width=content_width,
            occupied_indices=occupied_indices,
        ):
            groups.append(group)
            occupied_indices.update(range(group.start_index, group.end_index))

        return tuple(sorted(groups, key=lambda group: group.start_index))

    def _source_range_keep_group(
        self,
        layout_pieces: tuple[_LayoutPiece, ...],
        *,
        piece_ranges: tuple[_PieceSourceRange, ...],
        search_start_index: int,
        source_start: int,
        source_end: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        reason: str,
    ) -> tuple[_KeepGroupRange | None, int]:
        """Return one fitting keep group for a source range when possible."""

        start_range_index = _first_piece_range_candidate(
            piece_ranges,
            source_start=source_start,
            search_start_index=search_start_index,
        )
        matching_indices = _piece_indices_for_source_range(
            piece_ranges,
            source_start=source_start,
            source_end=source_end,
            start_range_index=start_range_index,
        )
        if not matching_indices:
            return None, start_range_index
        start_index = matching_indices[0]
        end_index = matching_indices[-1] + 1
        return (
            self._piece_index_keep_group(
                layout_pieces,
                start_index=start_index,
                end_index=end_index,
                piece_width_prefix_sums=piece_width_prefix_sums,
                content_width=content_width,
                reason=reason,
            ),
            start_range_index,
        )

    def _decoration_keep_groups(
        self,
        layout_pieces: tuple[_LayoutPiece, ...],
        *,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        occupied_indices: set[int],
    ) -> tuple[_KeepGroupRange, ...]:
        """Return fitting decoration-to-content attachment groups."""

        groups: list[_KeepGroupRange] = []
        for index, piece in enumerate(layout_pieces):
            if not isinstance(piece, _InlineObjectPiece):
                continue
            role = piece.run.role
            if role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
                group = self._leading_decoration_group(
                    layout_pieces,
                    decoration_index=index,
                    piece_width_prefix_sums=piece_width_prefix_sums,
                    content_width=content_width,
                )
            elif role is PromptProjectionRunRole.TOKEN_TRAILING_DECORATION:
                group = self._trailing_decoration_group(
                    layout_pieces,
                    decoration_index=index,
                    piece_width_prefix_sums=piece_width_prefix_sums,
                    content_width=content_width,
                )
            else:
                group = None
            if group is None:
                continue
            group_indices = set(range(group.start_index, group.end_index))
            if group_indices & occupied_indices:
                continue
            groups.append(group)
            occupied_indices.update(group_indices)
        return tuple(groups)

    def _leading_decoration_group(
        self,
        layout_pieces: tuple[_LayoutPiece, ...],
        *,
        decoration_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
    ) -> _KeepGroupRange | None:
        """Return a keep group binding leading decoration to following content."""

        decoration_piece = layout_pieces[decoration_index]
        if not isinstance(decoration_piece, _InlineObjectPiece):
            return None
        content_index = _next_piece_index_for_token_content(
            layout_pieces,
            start_index=decoration_index + 1,
            token_id=decoration_piece.run.token_id,
        )
        if content_index is None:
            return None
        return self._piece_index_keep_group(
            layout_pieces,
            start_index=decoration_index,
            end_index=content_index + 1,
            piece_width_prefix_sums=piece_width_prefix_sums,
            content_width=content_width,
            reason="leading-decoration",
        )

    def _trailing_decoration_group(
        self,
        layout_pieces: tuple[_LayoutPiece, ...],
        *,
        decoration_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
    ) -> _KeepGroupRange | None:
        """Return a keep group binding trailing decoration to prior content."""

        decoration_piece = layout_pieces[decoration_index]
        if not isinstance(decoration_piece, _InlineObjectPiece):
            return None
        content_index = _previous_piece_index_for_token_content(
            layout_pieces,
            start_index=decoration_index - 1,
            token_id=decoration_piece.run.token_id,
        )
        if content_index is None:
            return None
        end_index = decoration_index + 1
        if end_index < len(layout_pieces) and _is_separator_text_piece(
            layout_pieces[end_index]
        ):
            end_index += 1
        return self._piece_index_keep_group(
            layout_pieces,
            start_index=content_index,
            end_index=end_index,
            piece_width_prefix_sums=piece_width_prefix_sums,
            content_width=content_width,
            reason="trailing-decoration",
        )

    def _piece_index_keep_group(
        self,
        layout_pieces: tuple[_LayoutPiece, ...],
        *,
        start_index: int,
        end_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        reason: str,
    ) -> _KeepGroupRange | None:
        """Return a fitting keep group for an explicit piece-index span."""

        if any(
            isinstance(piece, _ParagraphBreak)
            for piece in layout_pieces[start_index:end_index]
        ):
            return None
        width = self._piece_range_width(
            piece_width_prefix_sums,
            start_index=start_index,
            end_index=end_index,
        )
        if width > content_width:
            return None
        return _KeepGroupRange(
            start_index=start_index,
            end_index=end_index,
            width=width,
            reason=reason,
        )

    def _piece_range_width(
        self,
        piece_width_prefix_sums: tuple[float, ...],
        *,
        start_index: int,
        end_index: int,
    ) -> float:
        """Return the unwrapped width of a piece-index span."""

        return piece_width_prefix_sums[end_index] - piece_width_prefix_sums[start_index]


def tag_keep_source_ranges(
    prompt_document_view: PromptDocumentView,
    *,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Return parsed source ranges for short comma-delimited tags kept as a unit."""

    segment_count = len(prompt_document_view.segments)
    ranges: list[tuple[int, int]] = []
    for segment in prompt_document_view.segments:
        if source_limit is not None and segment.selection_start > source_limit:
            break
        if not _segment_is_comma_delimited(segment, segment_count=segment_count):
            continue
        if _segment_word_count(segment.display_text) > _MAX_KEPT_SEGMENT_WORDS:
            continue
        source_start = segment.selection_start
        source_end = segment.selection_end
        if segment.has_separator_after and segment.separator_text_after.startswith(","):
            source_end += 1
        if source_end > source_start and (source_start, source_end) not in ranges:
            ranges.append((source_start, source_end))
    return tuple(ranges)


def tag_keep_source_ranges_for_layout(
    prompt_document_view: PromptDocumentView,
    *,
    source_start: int = 0,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Return parsed and inferred kept-tag ranges for authoritative layout."""

    return _source_text_tag_keep_ranges(
        prompt_document_view.source_text,
        source_start=source_start,
        source_limit=source_limit,
    )


def tag_keep_source_ranges_in_source_line(
    source_text: str,
    *,
    line_start: int,
    line_end: int,
) -> tuple[tuple[int, int], ...]:
    """Return inferred kept-tag ranges in one hard source line."""

    bounded_line_start = max(0, min(line_start, len(source_text)))
    bounded_line_end = max(bounded_line_start, min(line_end, len(source_text)))
    return _source_text_line_tag_keep_ranges(
        source_text,
        line_start=bounded_line_start,
        line_end=bounded_line_end,
    )


def tag_keep_source_range_at_position(
    source_text: str,
    source_position: int,
) -> tuple[int, int] | None:
    """Return the short comma-tag range containing a source position."""

    if not source_text or "," not in source_text:
        return None
    anchor = max(0, min(source_position, len(source_text) - 1))
    line_start = source_text.rfind("\n", 0, anchor + 1) + 1
    line_end = source_text.find("\n", anchor)
    if line_end < 0:
        line_end = len(source_text)
    previous_comma = source_text.rfind(",", line_start, anchor + 1)
    next_comma = source_text.find(",", anchor, line_end)
    if previous_comma == anchor:
        next_comma = previous_comma
        previous_comma = source_text.rfind(",", line_start, previous_comma)
    if previous_comma < 0 and next_comma < 0:
        return None
    segment_start = line_start if previous_comma < 0 else previous_comma + 1
    segment_end = line_end if next_comma < 0 else next_comma
    selection_start = _skip_horizontal_whitespace_forward(
        source_text,
        segment_start,
        limit=segment_end,
    )
    selection_end = _skip_horizontal_whitespace_backward(
        source_text,
        segment_end,
        lower_limit=selection_start,
    )
    if selection_end <= selection_start:
        return None
    if _segment_word_count(source_text[selection_start:selection_end]) > 3:
        return None
    range_end = selection_end if next_comma < 0 else next_comma + 1
    return (selection_start, range_end)


def _source_text_tag_keep_ranges(
    source_text: str,
    *,
    source_start: int = 0,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Infer short comma-delimited tag ranges directly from source text."""

    ranges: list[tuple[int, int]] = []
    bounded_source_start = max(0, min(source_start, len(source_text)))
    line_start = source_text.rfind("\n", 0, bounded_source_start) + 1
    scan_end = (
        len(source_text)
        if source_limit is None
        else min(len(source_text), max(0, source_limit))
    )
    while line_start <= scan_end:
        line_end = source_text.find("\n", line_start, scan_end)
        if line_end < 0:
            line_end = scan_end
        ranges.extend(
            _source_text_line_tag_keep_ranges(
                source_text,
                line_start=line_start,
                line_end=line_end,
            )
        )
        if line_end == scan_end:
            break
        line_start = line_end + 1
    return tuple(ranges)


def _source_text_line_tag_keep_ranges(
    source_text: str,
    *,
    line_start: int,
    line_end: int,
) -> tuple[tuple[int, int], ...]:
    """Infer short comma-tag ranges inside one hard source line."""

    line_text = source_text[line_start:line_end]
    if "," not in line_text:
        return ()

    ranges: list[tuple[int, int]] = []
    segment_start = line_start
    while segment_start <= line_end:
        comma_index = source_text.find(",", segment_start, line_end)
        segment_end = line_end if comma_index < 0 else comma_index
        selection_start = _skip_horizontal_whitespace_forward(
            source_text,
            segment_start,
            limit=segment_end,
        )
        selection_end = _skip_horizontal_whitespace_backward(
            source_text,
            segment_end,
            lower_limit=selection_start,
        )
        if (
            selection_end > selection_start
            and _segment_word_count(source_text[selection_start:selection_end])
            <= _MAX_KEPT_SEGMENT_WORDS
        ):
            range_end = selection_end
            if comma_index >= 0:
                range_end = comma_index + 1
            ranges.append((selection_start, range_end))
        if comma_index < 0:
            break
        segment_start = comma_index + 1
    return tuple(ranges)


def _skip_horizontal_whitespace_forward(
    text: str,
    start: int,
    *,
    limit: int,
) -> int:
    """Return the first non-horizontal-whitespace position before limit."""

    index = start
    while index < limit and text[index] in {" ", "\t"}:
        index += 1
    return index


def _skip_horizontal_whitespace_backward(
    text: str,
    end: int,
    *,
    lower_limit: int,
) -> int:
    """Return the first non-horizontal-whitespace boundary after lower_limit."""

    index = end
    while index > lower_limit and text[index - 1] in {" ", "\t"}:
        index -= 1
    return index


def _segment_is_comma_delimited(
    segment: object,
    *,
    segment_count: int,
) -> bool:
    """Return whether one parsed segment participates in comma segmentation."""

    has_separator_after = bool(getattr(segment, "has_separator_after", False))
    return has_separator_after or segment_count > 1


def _segment_word_count(display_text: str) -> int:
    """Return the whitespace-delimited word count for one segment label."""

    return len(display_text.split())


def _piece_source_ranges(
    layout_pieces: tuple[_LayoutPiece, ...],
) -> tuple[_PieceSourceRange, ...]:
    """Return source ranges for layout pieces that cover prompt source text."""

    piece_ranges: list[_PieceSourceRange] = []
    for index, piece in enumerate(layout_pieces):
        piece_range = _piece_source_range(piece)
        if piece_range is None:
            continue
        start, end = piece_range
        if end <= start:
            continue
        piece_ranges.append(_PieceSourceRange(index=index, start=start, end=end))
    return tuple(piece_ranges)


def _first_piece_range_candidate(
    piece_ranges: tuple[_PieceSourceRange, ...],
    *,
    source_start: int,
    search_start_index: int,
) -> int:
    """Return the first possible piece-range index for a sorted source range."""

    candidate_index = max(0, min(search_start_index, len(piece_ranges)))
    while (
        candidate_index < len(piece_ranges)
        and piece_ranges[candidate_index].end <= source_start
    ):
        candidate_index += 1
    return candidate_index


def _piece_indices_for_source_range(
    piece_ranges: tuple[_PieceSourceRange, ...],
    *,
    source_start: int,
    source_end: int,
    start_range_index: int,
) -> tuple[int, ...]:
    """Return layout piece indices intersecting one sorted source range."""

    matching_indices: list[int] = []
    range_index = start_range_index
    while range_index < len(piece_ranges):
        piece_range = piece_ranges[range_index]
        if piece_range.start >= source_end:
            break
        if piece_range.end > source_start:
            matching_indices.append(piece_range.index)
        range_index += 1
    return tuple(matching_indices)


def _piece_intersects_source_range(
    piece: _LayoutPiece,
    *,
    source_start: int,
    source_end: int,
) -> bool:
    """Return whether one layout piece overlaps a half-open source range."""

    piece_range = _piece_source_range(piece)
    if piece_range is None:
        return False
    piece_start, piece_end = piece_range
    return piece_start < source_end and piece_end > source_start


def _piece_source_range(piece: _LayoutPiece) -> tuple[int, int] | None:
    """Return the source range covered by a layout piece when it has one."""

    if isinstance(piece, _ParagraphBreak):
        return None
    if isinstance(piece, _TextPiece):
        return (min(piece.source_positions), max(piece.source_positions))
    return (min(piece.run.source_positions), max(piece.run.source_positions))


def _piece_width_prefix_sums(piece_widths: tuple[float, ...]) -> tuple[float, ...]:
    """Return prefix sums so keep-group range widths are O(1)."""

    prefix_sums = [0.0]
    for width in piece_widths:
        prefix_sums.append(prefix_sums[-1] + width)
    return tuple(prefix_sums)


def _piece_width(
    piece: _LayoutPiece,
    *,
    base_font: QFont,
    base_font_key: str,
    content_width: float,
    measurement_cache: _TextMeasurementCache,
) -> float:
    """Return the unwrapped visual width of one layout piece."""

    if isinstance(piece, _ParagraphBreak):
        return 0.0
    if isinstance(piece, _InlineObjectPiece):
        return min(piece.size.width(), content_width)
    return measurement_cache.text_width(
        piece.text,
        measurement_cache.font_for_run(
            piece.run,
            base_font,
            base_font_key=base_font_key,
        ),
    )


def _text_width(text: str, font: QFont) -> float:
    """Return the unwrapped text width using the same layout engine as fragments."""

    return _unwrapped_text_offsets(text, font)[-1]


def _adjust_break_for_word_integrity(
    text: str,
    *,
    consumed_cluster_length: int,
    candidate_length: int,
    line_has_content: bool,
    font: QFont,
    content_width: float,
    measurement_cache: _TextMeasurementCache,
) -> _TextBreakDecision:
    """Return a break decision that never splits fitting words.

    Qt may propose an intra-word break when only a few characters fit at the end of
    the current line. Prompt layout treats that as a fallback reserved for words
    wider than the editor content area, so fitting words move as a whole.
    """

    remaining_length = len(text) - consumed_cluster_length
    candidate_length = min(max(1, candidate_length), remaining_length)
    candidate_break = consumed_cluster_length + candidate_length
    word_span = _word_span_at_break(text, candidate_break)
    if word_span is None:
        return _TextBreakDecision(consumed_length=candidate_length)

    word_start, word_end = word_span
    if not _word_fits_content_width(
        text[word_start:word_end],
        font=font,
        content_width=content_width,
        measurement_cache=measurement_cache,
    ):
        return _TextBreakDecision(consumed_length=candidate_length)

    if word_start <= consumed_cluster_length:
        if line_has_content:
            return _TextBreakDecision(consumed_length=0, break_before_text=True)
        return _TextBreakDecision(
            consumed_length=max(1, word_end - consumed_cluster_length)
        )

    prefix_before_word = text[consumed_cluster_length:word_start]
    if prefix_before_word.strip():
        return _TextBreakDecision(consumed_length=word_start - consumed_cluster_length)
    if line_has_content and prefix_before_word:
        return _TextBreakDecision(consumed_length=word_start - consumed_cluster_length)
    if line_has_content:
        return _TextBreakDecision(consumed_length=0, break_before_text=True)
    return _TextBreakDecision(consumed_length=word_end - consumed_cluster_length)


def _word_span_at_break(text: str, break_index: int) -> tuple[int, int] | None:
    """Return the whole word around one intra-word break candidate."""

    if break_index <= 0 or break_index >= len(text):
        return None
    if not (
        _is_word_wrap_character(text[break_index - 1])
        and _is_word_wrap_character(text[break_index])
    ):
        return None

    word_start = break_index - 1
    while word_start > 0 and _is_word_wrap_character(text[word_start - 1]):
        word_start -= 1

    word_end = break_index + 1
    while word_end < len(text) and _is_word_wrap_character(text[word_end]):
        word_end += 1
    return (word_start, word_end)


def _is_word_wrap_character(character: str) -> bool:
    """Return whether one character belongs to an unbreakable prompt word."""

    return character.isalnum() or character in _WORD_JOINING_CHARACTERS


def _word_fits_content_width(
    text: str,
    *,
    font: QFont,
    content_width: float,
    measurement_cache: _TextMeasurementCache,
) -> bool:
    """Return whether one word can fit on an empty prompt editor line."""

    return measurement_cache.word_fits_content_width(
        text,
        font=font,
        content_width=content_width,
    )


def _unwrapped_text_offsets(text: str, font: QFont) -> tuple[float, ...]:
    """Return unwrapped cursor offsets for every text boundary."""

    return _unwrapped_text_offsets_uncached(
        text,
        font,
        no_wrap_option=_text_option_no_wrap(),
    )


def _unwrapped_text_offsets_uncached(
    text: str,
    font: QFont,
    *,
    no_wrap_option: QTextOption,
) -> tuple[float, ...]:
    """Return unwrapped cursor offsets without using the per-snapshot cache."""

    if not text:
        return (0.0,)

    text_layout = QTextLayout(text, font)
    text_layout.setTextOption(no_wrap_option)
    text_layout.beginLayout()
    text_line = text_layout.createLine()
    if text_line.isValid():
        text_line.setLineWidth(
            max(1.0, QFontMetricsF(font).horizontalAdvance(text) + 1.0)
        )
    text_layout.endLayout()
    if not text_line.isValid():
        return (0.0,)
    offsets: list[float] = []
    for index in range(len(text) + 1):
        cursor_x = cast(tuple[float, int], text_line.cursorToX(index))
        offsets.append(float(cursor_x[0]))
    return tuple(offsets)


def _text_option_no_wrap() -> QTextOption:
    """Return a QTextOption configured for exact unwrapped measurement."""

    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.NoWrap)
    return text_option


def _text_option_word_wrap() -> QTextOption:
    """Return a QTextOption configured for prompt visual word wrapping."""

    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    return text_option


def _next_token_content_run(
    runs: Sequence[PromptProjectionRun],
    *,
    run_index: int,
    token_id: str | None,
) -> PromptProjectionRun | None:
    """Return the next text-content run for the supplied token."""

    for candidate in runs[run_index + 1 :]:
        if candidate.token_id != token_id:
            continue
        if candidate.role is PromptProjectionRunRole.DEFAULT:
            return candidate
    return None


def _previous_token_content_run(
    runs: Sequence[PromptProjectionRun],
    *,
    run_index: int,
    token_id: str | None,
) -> PromptProjectionRun | None:
    """Return the previous text-content run for the supplied token."""

    for candidate in reversed(runs[:run_index]):
        if candidate.token_id != token_id:
            continue
        if candidate.role is PromptProjectionRunRole.DEFAULT:
            return candidate
    return None


def _first_word_end_source_position(run: PromptProjectionRun) -> int | None:
    """Return the source boundary after a run's first visible word."""

    if run.kind is not PromptProjectionRunKind.TEXT:
        return None
    text = run.display_text
    word_start = len(text) - len(text.lstrip())
    if word_start >= len(text):
        return None
    word_end = word_start
    while word_end < len(text) and not text[word_end].isspace():
        word_end += 1
    if word_end >= len(text):
        return None
    return run.source_positions[word_end]


def _last_word_start_source_position(run: PromptProjectionRun) -> int | None:
    """Return the source boundary before a run's last visible word."""

    if run.kind is not PromptProjectionRunKind.TEXT:
        return None
    text = run.display_text
    word_end = len(text.rstrip())
    if word_end <= 0:
        return None
    word_start = word_end
    while word_start > 0 and not text[word_start - 1].isspace():
        word_start -= 1
    if word_start <= 0:
        return None
    return run.source_positions[word_start]


def _next_piece_index_for_token_content(
    layout_pieces: tuple[_LayoutPiece, ...],
    *,
    start_index: int,
    token_id: str | None,
) -> int | None:
    """Return the next content piece belonging to a token."""

    for index in range(start_index, len(layout_pieces)):
        piece = layout_pieces[index]
        if isinstance(piece, _ParagraphBreak):
            return None
        run = piece.run
        if run.token_id == token_id and run.role is PromptProjectionRunRole.DEFAULT:
            return index
    return None


def _previous_piece_index_for_token_content(
    layout_pieces: tuple[_LayoutPiece, ...],
    *,
    start_index: int,
    token_id: str | None,
) -> int | None:
    """Return the previous content piece belonging to a token."""

    for index in range(start_index, -1, -1):
        piece = layout_pieces[index]
        if isinstance(piece, _ParagraphBreak):
            return None
        run = piece.run
        if run.token_id == token_id and run.role is PromptProjectionRunRole.DEFAULT:
            return index
    return None


def _is_separator_text_piece(piece: _LayoutPiece) -> bool:
    """Return whether one text piece is only comma separator text."""

    if not isinstance(piece, _TextPiece):
        return False
    return bool(piece.text) and all(character in ", \t" for character in piece.text)


def _line_source_boundaries(
    projection_document: PromptProjectionDocument,
    *,
    current_boundaries: list[_LineBoundary],
    next_start_boundaries: list[_LineStartBoundary] | None,
) -> tuple[int, int, int, int, int | None, int | None]:
    """Return source content and hard line-break boundaries for one visual line."""

    if not projection_document.caret_map.stops:
        return (0, 0, 0, 0, None, None)
    first_projection_position = projection_document.caret_map.stops[
        0
    ].projection_position
    ordered_boundaries = tuple(current_boundaries)
    if ordered_boundaries:
        start_boundary = ordered_boundaries[0]
        content_end_boundary = ordered_boundaries[-1]
    else:
        fallback_boundary = (
            next_start_boundaries[0]
            if next_start_boundaries
            else _LineStartBoundary(first_projection_position)
        )
        start_boundary = _LineBoundary(
            fallback_boundary.projection_position,
            0.0,
            fallback_boundary.source_position,
        )
        content_end_boundary = start_boundary
    start_projection_position = max(
        start_boundary.projection_position, first_projection_position
    )
    content_end_projection_position = max(
        content_end_boundary.projection_position,
        first_projection_position,
    )
    start_source_position = _source_position_for_line_boundary(
        projection_document,
        projection_position=start_projection_position,
        source_position=start_boundary.source_position,
    )
    content_end_source_position = _source_position_for_line_boundary(
        projection_document,
        projection_position=content_end_projection_position,
        source_position=content_end_boundary.source_position,
    )
    if (
        start_boundary.projection_position < first_projection_position
        and start_boundary.source_position is not None
    ):
        start_source_position = start_boundary.source_position
    if (
        content_end_boundary.projection_position < first_projection_position
        and content_end_boundary.source_position is not None
    ):
        content_end_source_position = content_end_boundary.source_position
    source_end_position = max(start_source_position, content_end_source_position)
    line_break_start: int | None = None
    line_break_end: int | None = None
    if next_start_boundaries:
        next_boundary = next_start_boundaries[0]
        next_projection_position = max(
            next_boundary.projection_position,
            first_projection_position,
        )
        next_source_position = _source_position_for_line_boundary(
            projection_document,
            projection_position=next_projection_position,
            source_position=next_boundary.source_position,
        )
        if (
            next_boundary.projection_position < first_projection_position
            and next_boundary.source_position is not None
        ):
            next_source_position = next_boundary.source_position
        if next_source_position > content_end_source_position:
            line_break_start = content_end_source_position
            line_break_end = next_source_position
            source_end_position = max(source_end_position, next_source_position)
    return (
        start_source_position,
        source_end_position,
        start_source_position,
        max(start_source_position, content_end_source_position),
        line_break_start,
        line_break_end,
    )


def _source_position_for_line_boundary(
    projection_document: PromptProjectionDocument,
    *,
    projection_position: int,
    source_position: int | None,
) -> int:
    """Return a source boundary, honoring layout-owned source metadata first."""

    if source_position is not None:
        return source_position
    return projection_document.caret_map.state_for_projection_position(
        projection_position
    ).source_position


__all__ = [
    "PromptProjectionLineLayoutBuilder",
    "tag_keep_source_range_at_position",
    "tag_keep_source_ranges_in_source_line",
    "tag_keep_source_ranges",
    "tag_keep_source_ranges_for_layout",
]
