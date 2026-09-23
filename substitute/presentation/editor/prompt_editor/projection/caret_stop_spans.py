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

"""Represent compact caret-stop spans for projected prompt runs."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)


@dataclass(frozen=True, slots=True)
class ExplicitCaretSpan:
    """Store one non-text caret stop without assigning its visual index early."""

    projection_position: int
    source_position: int
    placement: PromptProjectionCaretPlacement
    token_id: str | None
    run_id: str | None
    token_slot: int | None

    def __len__(self) -> int:
        """Return the single represented stop."""

        return 1

    def stop_at(
        self, local_index: int, *, visual_index: int
    ) -> PromptProjectionCaretStop:
        """Materialize the represented stop at its canonical visual index."""

        if local_index not in {0, -1}:
            raise IndexError(local_index)
        return PromptProjectionCaretStop(
            visual_index=visual_index,
            projection_position=self.projection_position,
            state=PromptProjectionCaretState(
                source_position=self.source_position,
                placement=self.placement,
                token_id=self.token_id,
                run_id=self.run_id,
                token_slot=self.token_slot,
            ),
        )

    def local_index_for_state(self, state: PromptProjectionCaretState) -> int | None:
        """Return the local index for an exact state."""

        return (
            0
            if state.source_position == self.source_position
            and state.placement is self.placement
            and state.token_id == self.token_id
            and state.run_id == self.run_id
            and state.token_slot == self.token_slot
            else None
        )

    def local_index_for_projection_position(self, position: int) -> int | None:
        """Return the local index for an exact projection boundary."""

        return 0 if position == self.projection_position else None

    def local_index_for_source_position(self, position: int) -> int | None:
        """Return the local index for an exact source boundary."""

        return 0 if position == self.source_position else None

    @property
    def projection_start(self) -> int:
        """Return the first represented projection boundary."""

        return self.projection_position

    @property
    def projection_end(self) -> int:
        """Return the last represented projection boundary."""

        return self.projection_position


@dataclass(frozen=True, slots=True)
class AtomicTokenCaretSpan:
    """Represent both navigation edges of one atomic inline token."""

    run: PromptProjectionRun
    token: PromptProjectionToken

    def __len__(self) -> int:
        """Return the leading and trailing token stop count."""

        return 2

    def stop_at(
        self, local_index: int, *, visual_index: int
    ) -> PromptProjectionCaretStop:
        """Materialize one atomic token edge at its canonical visual index."""

        normalized_index = local_index + 2 if local_index < 0 else local_index
        if normalized_index not in {0, 1}:
            raise IndexError(local_index)
        leading = normalized_index == 0
        return PromptProjectionCaretStop(
            visual_index=visual_index,
            projection_position=(
                self.run.projection_start if leading else self.run.projection_end
            ),
            state=PromptProjectionCaretState(
                source_position=(
                    self.token.source_start if leading else self.token.source_end
                ),
                placement=(
                    PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
                    if leading
                    else PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                ),
                token_id=self.token.token_id,
                run_id=self.run.run_id,
            ),
        )

    def local_index_for_state(self, state: PromptProjectionCaretState) -> int | None:
        """Return the local edge index for one exact atomic state."""

        if state.token_id != self.token.token_id or state.run_id != self.run.run_id:
            return None
        if (
            state.placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
            and state.source_position == self.token.source_start
            and state.token_slot is None
        ):
            return 0
        if (
            state.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
            and state.source_position == self.token.source_end
            and state.token_slot is None
        ):
            return 1
        return None

    def local_index_for_projection_position(self, position: int) -> int | None:
        """Return the local edge index for one exact projection boundary."""

        if position == self.run.projection_start:
            return 0
        return 1 if position == self.run.projection_end else None

    def local_index_for_source_position(self, position: int) -> int | None:
        """Return the local edge index for one exact source boundary."""

        if position == self.token.source_start:
            return 0
        return 1 if position == self.token.source_end else None

    @property
    def projection_start(self) -> int:
        """Return the token's leading projection boundary."""

        return self.run.projection_start

    @property
    def projection_end(self) -> int:
        """Return the token's trailing projection boundary."""

        return self.run.projection_end


@dataclass(frozen=True, slots=True)
class TextCaretSpan:
    """Derive the ordered caret stops for one source-backed text run on demand."""

    run: PromptProjectionRun
    boundary_indexes: Sequence[int]
    boundary_start: int
    boundary_end: int
    placement: PromptProjectionCaretPlacement
    token_id: str | None

    def __len__(self) -> int:
        """Return the represented source-boundary count."""

        return self.boundary_end - self.boundary_start

    def stop_at(
        self, local_index: int, *, visual_index: int
    ) -> PromptProjectionCaretStop:
        """Materialize one run boundary at its canonical visual index."""

        boundary_index = self._boundary_index(local_index)
        return PromptProjectionCaretStop(
            visual_index=visual_index,
            projection_position=self.run.projection_start + boundary_index,
            state=PromptProjectionCaretState(
                source_position=self.run.source_positions[boundary_index],
                placement=self.placement,
                token_id=self.token_id,
                run_id=self.run.run_id,
                token_slot=(
                    boundary_index
                    if self.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
                    else None
                ),
            ),
        )

    def local_index_for_state(self, state: PromptProjectionCaretState) -> int | None:
        """Return the local index for an exact run-backed state."""

        if (
            state.run_id != self.run.run_id
            or state.placement is not self.placement
            or state.token_id != self.token_id
        ):
            return None
        if self.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT:
            boundary_index = state.token_slot
            if boundary_index is None:
                return None
        else:
            boundary_index = _source_position_index(
                self.run.source_positions,
                state.source_position,
            )
            if boundary_index is None:
                return None
        if not 0 <= boundary_index < len(self.run.source_positions):
            return None
        if self.run.source_positions[boundary_index] != state.source_position:
            return None
        return self._local_index_for_boundary(boundary_index)

    def local_index_for_projection_position(self, position: int) -> int | None:
        """Return the local index for an exact projection boundary."""

        boundary_index = position - self.run.projection_start
        return self._local_index_for_boundary(boundary_index)

    def local_index_for_source_position(self, position: int) -> int | None:
        """Return the local index for an exact source boundary."""

        boundary_index = _source_position_index(self.run.source_positions, position)
        if boundary_index is None:
            return None
        return self._local_index_for_boundary(boundary_index)

    def without_last_stop(self) -> TextCaretSpan | None:
        """Return this span without its last boundary when one remains."""

        next_end = self.boundary_end - 1
        if next_end <= self.boundary_start:
            return None
        return TextCaretSpan(
            run=self.run,
            boundary_indexes=self.boundary_indexes,
            boundary_start=self.boundary_start,
            boundary_end=next_end,
            placement=self.placement,
            token_id=self.token_id,
        )

    @property
    def projection_start(self) -> int:
        """Return the first represented projection boundary."""

        return self.run.projection_start + self.boundary_indexes[self.boundary_start]

    @property
    def projection_end(self) -> int:
        """Return the last represented projection boundary."""

        return self.run.projection_start + self.boundary_indexes[self.boundary_end - 1]

    def _boundary_index(self, local_index: int) -> int:
        """Resolve one positive or negative local index to a run boundary."""

        span_length = len(self)
        normalized_index = local_index + span_length if local_index < 0 else local_index
        if normalized_index < 0 or normalized_index >= span_length:
            raise IndexError(local_index)
        return self.boundary_indexes[self.boundary_start + normalized_index]

    def _local_index_for_boundary(self, boundary_index: int) -> int | None:
        """Return the local stop index for one exact grapheme boundary."""

        boundary_ordinal = bisect_left(
            self.boundary_indexes,
            boundary_index,
            self.boundary_start,
            self.boundary_end,
        )
        if (
            boundary_ordinal >= self.boundary_end
            or self.boundary_indexes[boundary_ordinal] != boundary_index
        ):
            return None
        return boundary_ordinal - self.boundary_start


CaretSpan = ExplicitCaretSpan | AtomicTokenCaretSpan | TextCaretSpan


def _source_position_index(
    positions: Sequence[int],
    source_position: int,
) -> int | None:
    """Return an exact boundary index without assuming one sequence type."""

    if isinstance(positions, range):
        if source_position not in positions:
            return None
        return positions.index(source_position)
    try:
        return positions.index(source_position)
    except ValueError:
        return None


__all__ = [
    "AtomicTokenCaretSpan",
    "CaretSpan",
    "ExplicitCaretSpan",
    "TextCaretSpan",
]
