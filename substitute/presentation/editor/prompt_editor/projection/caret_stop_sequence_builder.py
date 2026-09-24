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

"""Build canonical projection caret-stop sequences from projected runs."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence

from substitute.application.prompt_editor.editing.grapheme_boundary_policy import (
    simple_code_point_boundaries,
)
from substitute.presentation.text_coordinates import TextCoordinateMap

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.editor.prompt_editor.projection.caret_stop_sequence import (
    PromptProjectionCaretStopSequence,
)
from substitute.presentation.editor.prompt_editor.projection.caret_stop_spans import (
    AtomicTokenCaretSpan,
    CaretSpan,
    ExplicitCaretSpan,
    TextCaretSpan,
)


class PromptProjectionCaretStopSequenceBuilder:
    """Build one flat run-backed caret sequence using canonical boundary rules."""

    __slots__ = ("_length", "_spans")

    def __init__(self) -> None:
        """Initialize an empty ordered span collection."""

        self._spans: list[CaretSpan] = []
        self._length = 0

    @property
    def has_stops(self) -> bool:
        """Return whether any caret stop has been appended."""

        return bool(self._spans)

    def last_boundary_matches(
        self,
        *,
        projection_position: int | None = None,
        source_position: int | None = None,
        placement: PromptProjectionCaretPlacement | None = None,
    ) -> bool:
        """Match the final boundary without materializing its public stop state."""

        if not self._spans:
            return False
        last_span = self._spans[-1]
        if isinstance(last_span, ExplicitCaretSpan):
            last_projection_position = last_span.projection_position
            last_source_position = last_span.source_position
            last_placement = last_span.placement
        elif isinstance(last_span, AtomicTokenCaretSpan):
            last_projection_position = last_span.run.projection_end
            last_source_position = last_span.token.source_end
            last_placement = PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
        else:
            boundary_index = last_span.boundary_indexes[last_span.boundary_end - 1]
            last_projection_position = last_span.run.projection_start + boundary_index
            last_source_position = last_span.run.source_positions[boundary_index]
            last_placement = last_span.placement
        return (
            (
                projection_position is None
                or last_projection_position == projection_position
            )
            and (source_position is None or last_source_position == source_position)
            and (placement is None or last_placement is placement)
        )

    def append_boundary(
        self,
        projection_position: int,
        *,
        source_position: int,
        placement: PromptProjectionCaretPlacement = (
            PromptProjectionCaretPlacement.PLAIN_TEXT
        ),
        token_id: str | None = None,
        run_id: str | None = None,
        token_slot: int | None = None,
    ) -> None:
        """Append one explicit edge state."""

        self._spans.append(
            ExplicitCaretSpan(
                projection_position=projection_position,
                source_position=source_position,
                placement=placement,
                token_id=token_id,
                run_id=run_id,
                token_slot=token_slot,
            )
        )
        self._length += 1

    def append_plain_text_run(
        self,
        run: PromptProjectionRun,
        *,
        boundary_start_index: int,
        omit_trailing_boundary: bool = False,
    ) -> None:
        """Append all selected plain-text boundaries for one run."""

        boundary_indexes = _caret_boundary_indexes(run.display_text)
        boundary_start = bisect_left(boundary_indexes, boundary_start_index)
        boundary_end = len(boundary_indexes) - int(omit_trailing_boundary)
        if boundary_start >= boundary_end:
            return
        span = TextCaretSpan(
            run=run,
            boundary_indexes=boundary_indexes,
            boundary_start=boundary_start,
            boundary_end=boundary_end,
            placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
            token_id=None,
        )
        self._spans.append(span)
        self._length += len(span)

    def append_atomic_token(
        self,
        run: PromptProjectionRun,
        *,
        token: PromptProjectionToken,
    ) -> None:
        """Append both navigation edges of one atomic inline token."""

        self._spans.append(AtomicTokenCaretSpan(run=run, token=token))
        self._length += 2

    def append_token_text_run(
        self,
        run: PromptProjectionRun,
        *,
        token: PromptProjectionToken,
    ) -> None:
        """Append all visible content boundaries for one token-owned text run."""

        boundary_indexes = _caret_boundary_indexes(run.display_text)
        span = TextCaretSpan(
            run=run,
            boundary_indexes=boundary_indexes,
            boundary_start=0,
            boundary_end=len(boundary_indexes),
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_id=token.token_id,
        )
        self._spans.append(span)
        self._length += len(span)

    def pop_plain_boundary_if_present(
        self,
        *,
        projection_position: int,
        source_position: int,
    ) -> None:
        """Remove a conflicting final plain boundary before a token edge."""

        if not self.last_boundary_matches(
            projection_position=projection_position,
            source_position=source_position,
            placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
        ):
            return
        last_span = self._spans[-1]
        if isinstance(last_span, (ExplicitCaretSpan, AtomicTokenCaretSpan)):
            self._spans.pop()
            self._length -= len(last_span)
            return
        shortened = last_span.without_last_stop()
        if shortened is None:
            self._spans.pop()
        else:
            self._spans[-1] = shortened
        self._length -= 1

    def build(self) -> PromptProjectionCaretStopSequence:
        """Return the immutable flat canonical sequence."""

        return PromptProjectionCaretStopSequence(tuple(self._spans))


def _caret_boundary_indexes(text: str) -> Sequence[int]:
    """Return a compact sequence of valid grapheme boundaries for one text run."""

    direct_boundaries = simple_code_point_boundaries(text)
    if direct_boundaries is not None:
        return direct_boundaries
    boundaries = TextCoordinateMap(text).grapheme_boundaries()
    if len(boundaries) == len(text) + 1:
        return range(len(text) + 1)
    return boundaries


__all__ = ["PromptProjectionCaretStopSequenceBuilder"]
