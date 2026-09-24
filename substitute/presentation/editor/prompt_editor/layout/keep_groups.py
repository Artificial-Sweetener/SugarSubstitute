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

"""Plan atomic line-placement groups for decorated prompt content."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
)
from substitute.presentation.editor.prompt_editor.layout.layout_pieces import (
    PromptInlineObjectLayoutPiece,
    PromptLayoutPiece,
    PromptParagraphBreakLayoutPiece,
    PromptStructuralRowLayoutPiece,
    PromptTextLayoutPiece,
)
from substitute.presentation.editor.prompt_editor.layout.text_measurement import (
    PromptTextMeasurementCache,
)


@dataclass(frozen=True, slots=True)
class PromptKeepGroupRange:
    """Describe a piece-index range placed on one visual line when it fits."""

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


class PromptKeepGroupPlanner:
    """Own source splitting and atomic placement for decorated content."""

    def source_split_positions(
        self,
        projection_document: PromptProjectionDocument,
        *,
        tag_keep_ranges: tuple[tuple[int, int], ...],
        source_start: int,
        source_limit: int | None,
    ) -> frozenset[int]:
        """Return source positions where grouping requires distinct pieces."""

        split_positions = {
            boundary for keep_range in tag_keep_ranges for boundary in keep_range
        }
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

    def build(
        self,
        projection_document: PromptProjectionDocument,
        *,
        layout_pieces: tuple[PromptLayoutPiece, ...],
        tag_keep_ranges: tuple[tuple[int, int], ...],
        base_font: QFont,
        base_font_key: str,
        content_width: float,
        measurement_cache: PromptTextMeasurementCache,
    ) -> tuple[PromptKeepGroupRange, ...]:
        """Return fitting tag and decoration groups ordered by piece index."""

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
        groups: list[PromptKeepGroupRange] = []
        occupied_indices: set[int] = set()
        piece_ranges = _piece_source_ranges(layout_pieces)
        range_search_start = 0
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
        layout_pieces: tuple[PromptLayoutPiece, ...],
        *,
        piece_ranges: tuple[_PieceSourceRange, ...],
        search_start_index: int,
        source_start: int,
        source_end: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        reason: str,
    ) -> tuple[PromptKeepGroupRange | None, int]:
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
        return (
            self._piece_index_keep_group(
                layout_pieces,
                start_index=matching_indices[0],
                end_index=matching_indices[-1] + 1,
                piece_width_prefix_sums=piece_width_prefix_sums,
                content_width=content_width,
                reason=reason,
            ),
            start_range_index,
        )

    def _decoration_keep_groups(
        self,
        layout_pieces: tuple[PromptLayoutPiece, ...],
        *,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        occupied_indices: set[int],
    ) -> tuple[PromptKeepGroupRange, ...]:
        """Return non-overlapping decoration-to-content attachment groups."""

        groups: list[PromptKeepGroupRange] = []
        for index, piece in enumerate(layout_pieces):
            if not isinstance(piece, PromptInlineObjectLayoutPiece):
                continue
            if piece.run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
                group = self._leading_decoration_group(
                    layout_pieces,
                    decoration_index=index,
                    piece_width_prefix_sums=piece_width_prefix_sums,
                    content_width=content_width,
                )
            elif piece.run.role is PromptProjectionRunRole.TOKEN_TRAILING_DECORATION:
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
        layout_pieces: tuple[PromptLayoutPiece, ...],
        *,
        decoration_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
    ) -> PromptKeepGroupRange | None:
        """Bind a leading decoration to the following token content."""

        decoration_piece = layout_pieces[decoration_index]
        if not isinstance(decoration_piece, PromptInlineObjectLayoutPiece):
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
        layout_pieces: tuple[PromptLayoutPiece, ...],
        *,
        decoration_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
    ) -> PromptKeepGroupRange | None:
        """Bind a trailing decoration to preceding content and its separator."""

        decoration_piece = layout_pieces[decoration_index]
        if not isinstance(decoration_piece, PromptInlineObjectLayoutPiece):
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
        layout_pieces: tuple[PromptLayoutPiece, ...],
        *,
        start_index: int,
        end_index: int,
        piece_width_prefix_sums: tuple[float, ...],
        content_width: float,
        reason: str,
    ) -> PromptKeepGroupRange | None:
        """Return a fitting keep group for an explicit piece-index span."""

        if any(
            isinstance(
                piece,
                (PromptParagraphBreakLayoutPiece, PromptStructuralRowLayoutPiece),
            )
            for piece in layout_pieces[start_index:end_index]
        ):
            return None
        width = (
            piece_width_prefix_sums[end_index] - piece_width_prefix_sums[start_index]
        )
        if width > content_width:
            return None
        return PromptKeepGroupRange(start_index, end_index, width, reason)


def _piece_source_ranges(
    layout_pieces: tuple[PromptLayoutPiece, ...],
) -> tuple[_PieceSourceRange, ...]:
    """Return ordered source ranges for pieces that cover prompt text."""

    piece_ranges: list[_PieceSourceRange] = []
    for index, piece in enumerate(layout_pieces):
        piece_range = _piece_source_range(piece)
        if piece_range is None:
            continue
        start, end = piece_range
        if end > start:
            piece_ranges.append(_PieceSourceRange(index, start, end))
    return tuple(piece_ranges)


def _first_piece_range_candidate(
    piece_ranges: tuple[_PieceSourceRange, ...],
    *,
    source_start: int,
    search_start_index: int,
) -> int:
    """Return the first possible range index for sorted source content."""

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
    """Return piece indices intersecting one sorted half-open source range."""

    matching_indices: list[int] = []
    for piece_range in piece_ranges[start_range_index:]:
        if piece_range.start >= source_end:
            break
        if piece_range.end > source_start:
            matching_indices.append(piece_range.index)
    return tuple(matching_indices)


def _piece_source_range(piece: PromptLayoutPiece) -> tuple[int, int] | None:
    """Return the half-open source range covered by one layout piece."""

    if isinstance(
        piece,
        (PromptParagraphBreakLayoutPiece, PromptStructuralRowLayoutPiece),
    ):
        return None
    if isinstance(piece, PromptTextLayoutPiece):
        return (piece.source_positions[0], piece.source_positions[-1])
    return (piece.run.source_positions[0], piece.run.source_positions[-1])


def _piece_width_prefix_sums(piece_widths: tuple[float, ...]) -> tuple[float, ...]:
    """Return prefix sums for constant-time group width lookup."""

    prefix_sums = [0.0]
    for width in piece_widths:
        prefix_sums.append(prefix_sums[-1] + width)
    return tuple(prefix_sums)


def _piece_width(
    piece: PromptLayoutPiece,
    *,
    base_font: QFont,
    base_font_key: str,
    content_width: float,
    measurement_cache: PromptTextMeasurementCache,
) -> float:
    """Return the unwrapped visual width of one layout piece."""

    if isinstance(
        piece,
        (PromptParagraphBreakLayoutPiece, PromptStructuralRowLayoutPiece),
    ):
        return 0.0
    if isinstance(piece, PromptInlineObjectLayoutPiece):
        return min(piece.size.width(), content_width)
    return measurement_cache.text_width(
        piece.text,
        measurement_cache.font_for_run(
            piece.run,
            base_font,
            base_font_key=base_font_key,
        ),
    )


def _next_token_content_run(
    runs: Sequence[PromptProjectionRun],
    *,
    run_index: int,
    token_id: str | None,
) -> PromptProjectionRun | None:
    """Return the adjacent following content run belonging to one token."""

    candidate_index = run_index + 1
    if candidate_index >= len(runs):
        return None
    candidate = runs[candidate_index]
    return (
        candidate
        if candidate.token_id == token_id
        and candidate.role is PromptProjectionRunRole.DEFAULT
        else None
    )


def _previous_token_content_run(
    runs: Sequence[PromptProjectionRun],
    *,
    run_index: int,
    token_id: str | None,
) -> PromptProjectionRun | None:
    """Return the adjacent preceding content run belonging to one token."""

    candidate_index = run_index - 1
    if candidate_index < 0:
        return None
    candidate = runs[candidate_index]
    return (
        candidate
        if candidate.token_id == token_id
        and candidate.role is PromptProjectionRunRole.DEFAULT
        else None
    )


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
    layout_pieces: tuple[PromptLayoutPiece, ...],
    *,
    start_index: int,
    token_id: str | None,
) -> int | None:
    """Return the next content piece belonging to one token."""

    for index in range(start_index, len(layout_pieces)):
        piece = layout_pieces[index]
        if isinstance(piece, PromptParagraphBreakLayoutPiece):
            return None
        if (
            piece.run.token_id == token_id
            and piece.run.role is PromptProjectionRunRole.DEFAULT
        ):
            return index
    return None


def _previous_piece_index_for_token_content(
    layout_pieces: tuple[PromptLayoutPiece, ...],
    *,
    start_index: int,
    token_id: str | None,
) -> int | None:
    """Return the previous content piece belonging to one token."""

    for index in range(start_index, -1, -1):
        piece = layout_pieces[index]
        if isinstance(piece, PromptParagraphBreakLayoutPiece):
            return None
        if (
            piece.run.token_id == token_id
            and piece.run.role is PromptProjectionRunRole.DEFAULT
        ):
            return index
    return None


def _is_separator_text_piece(piece: PromptLayoutPiece) -> bool:
    """Return whether one text piece contains only comma separator text."""

    return (
        isinstance(piece, PromptTextLayoutPiece)
        and bool(piece.text)
        and all(character in ", \t" for character in piece.text)
    )


__all__ = ["PromptKeepGroupPlanner", "PromptKeepGroupRange"]
