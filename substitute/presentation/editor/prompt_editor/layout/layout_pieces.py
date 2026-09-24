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

"""Partition visible projection runs into canonical layout pieces."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer_registry import (
    PromptProjectionInlineObjectRendererRegistry,
)


@dataclass(frozen=True, slots=True)
class PromptTextLayoutPiece:
    """Describe one newline-free text slice prepared for line assembly."""

    run: PromptProjectionRun
    text: str
    projection_start: int
    source_positions: Sequence[int]


@dataclass(frozen=True, slots=True)
class PromptInlineObjectLayoutPiece:
    """Describe one measured inline object prepared for line assembly."""

    run: PromptProjectionRun
    size: QSizeF


@dataclass(frozen=True, slots=True)
class PromptParagraphBreakLayoutPiece:
    """Describe one explicit paragraph break from a projected newline."""

    projection_start: int
    projection_end: int
    source_start: int
    source_end: int


@dataclass(frozen=True, slots=True)
class PromptStructuralRowLayoutPiece:
    """Describe one renderer-free structural projection row."""

    run: PromptProjectionRun


type PromptLayoutPiece = (
    PromptTextLayoutPiece
    | PromptInlineObjectLayoutPiece
    | PromptParagraphBreakLayoutPiece
    | PromptStructuralRowLayoutPiece
)


class PromptLayoutPieceBuilder:
    """Build the ordered layout-piece stream for a projection window."""

    def __init__(
        self,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Retain the renderer registry that owns inline-object measurement."""

        self._inline_object_renderers = inline_object_renderers

    def build(
        self,
        projection_document: PromptProjectionDocument,
        *,
        base_font: QFont,
        source_split_positions: frozenset[int] = frozenset(),
        source_start: int = 0,
        source_limit: int | None = None,
    ) -> tuple[PromptLayoutPiece, ...]:
        """Partition visible runs around newlines and grouping boundaries."""

        pieces: list[PromptLayoutPiece] = []
        ordered_source_split_positions = tuple(sorted(source_split_positions))
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
                    PromptInlineObjectLayoutPiece(
                        run=run,
                        size=renderer.measure_inline_object(
                            run,
                            token,
                            base_font=base_font,
                        ),
                    )
                )
                continue
            if run.kind is PromptProjectionRunKind.STRUCTURAL_ROW:
                pieces.append(PromptStructuralRowLayoutPiece(run=run))
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
                newline_index = run.display_text.find("\n", piece_start, display_end)
                if newline_index < 0:
                    if piece_start < display_end:
                        pieces.extend(
                            self._split_text_piece(
                                run,
                                start=piece_start,
                                end=display_end,
                                source_split_positions=ordered_source_split_positions,
                            )
                        )
                    break
                if newline_index > piece_start:
                    pieces.extend(
                        self._split_text_piece(
                            run,
                            start=piece_start,
                            end=newline_index,
                            source_split_positions=ordered_source_split_positions,
                        )
                    )
                pieces.append(
                    PromptParagraphBreakLayoutPiece(
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
        source_split_positions: Sequence[int],
    ) -> tuple[PromptTextLayoutPiece, ...]:
        """Split one text slice at source positions needed by keep groups."""

        if not run.source_backed:
            return (
                PromptTextLayoutPiece(
                    run=run,
                    text=run.display_text[start:end],
                    projection_start=run.projection_start + start,
                    source_positions=run.source_positions[start : end + 1],
                ),
            )
        candidate_start = bisect_left(
            source_split_positions,
            run.source_positions[start + 1],
        )
        candidate_end = bisect_right(
            source_split_positions,
            run.source_positions[end - 1],
        )
        split_offsets: list[int] = []
        for source_position in source_split_positions[candidate_start:candidate_end]:
            matching_start = bisect_left(
                run.source_positions,
                source_position,
                start + 1,
                end,
            )
            matching_end = bisect_right(
                run.source_positions,
                source_position,
                matching_start,
                end,
            )
            split_offsets.extend(range(matching_start, matching_end))
        piece_offsets = (start, *split_offsets, end)
        pieces: list[PromptTextLayoutPiece] = []
        for piece_start, piece_end in zip(piece_offsets, piece_offsets[1:]):
            if piece_end <= piece_start:
                continue
            pieces.append(
                PromptTextLayoutPiece(
                    run=run,
                    text=run.display_text[piece_start:piece_end],
                    projection_start=run.projection_start + piece_start,
                    source_positions=run.source_positions[piece_start : piece_end + 1],
                )
            )
        return tuple(pieces)


__all__ = [
    "PromptInlineObjectLayoutPiece",
    "PromptLayoutPiece",
    "PromptLayoutPieceBuilder",
    "PromptParagraphBreakLayoutPiece",
    "PromptStructuralRowLayoutPiece",
    "PromptTextLayoutPiece",
]
