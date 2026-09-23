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

"""Represent canonical projection caret stops without per-boundary allocation."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Sequence
from typing import overload

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
)
from substitute.presentation.editor.prompt_editor.projection.caret_stop_spans import (
    AtomicTokenCaretSpan,
    CaretSpan,
    ExplicitCaretSpan,
)


class PromptProjectionCaretStopSequence(Sequence[PromptProjectionCaretStop]):
    """Expose a flat canonical stop sequence backed by immutable run spans."""

    __slots__ = (
        "_length",
        "_projection_starts",
        "_span_starts",
        "_spans",
        "_spans_by_run_id",
    )

    def __init__(self, spans: tuple[CaretSpan, ...]) -> None:
        """Index immutable caret spans without materializing their boundaries."""

        span_starts: list[int] = []
        length = 0
        for span in spans:
            span_starts.append(length)
            length += len(span)
        self._spans = spans
        self._span_starts = tuple(span_starts)
        self._length = length
        self._projection_starts = tuple(span.projection_start for span in spans)
        spans_by_run_id: dict[str, list[int]] = {}
        for span_index, span in enumerate(spans):
            run_id = (
                span.run_id if isinstance(span, ExplicitCaretSpan) else span.run.run_id
            )
            if run_id is not None:
                spans_by_run_id.setdefault(run_id, []).append(span_index)
        self._spans_by_run_id = {
            run_id: tuple(indexes) for run_id, indexes in spans_by_run_id.items()
        }

    def __len__(self) -> int:
        """Return the canonical visual stop count."""

        return self._length

    @property
    def span_count(self) -> int:
        """Return the bounded run-span count used by structural performance checks."""

        return len(self._spans)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionCaretStop: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionCaretStop, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionCaretStop | tuple[PromptProjectionCaretStop, ...]:
        """Materialize only the requested stop or slice."""

        if isinstance(index, slice):
            return tuple(
                self[position] for position in range(*index.indices(len(self)))
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        span_index = bisect_right(self._span_starts, normalized_index) - 1
        span = self._spans[span_index]
        return span.stop_at(
            normalized_index - self._span_starts[span_index],
            visual_index=normalized_index,
        )

    def __iter__(self) -> Iterator[PromptProjectionCaretStop]:
        """Yield canonical stops while allocating each only at iteration demand."""

        for span_start, span in zip(self._span_starts, self._spans, strict=True):
            for local_index in range(len(span)):
                yield span.stop_at(
                    local_index,
                    visual_index=span_start + local_index,
                )

    def has_projection_position(self, projection_position: int) -> bool:
        """Return whether any span owns the exact projection boundary."""

        if not self._spans:
            return False
        rightmost = bisect_right(self._projection_starts, projection_position) - 1
        if rightmost < 0:
            return False
        first = rightmost
        while (
            first > 0 and self._spans[first - 1].projection_end >= projection_position
        ):
            first -= 1
        for span_index in range(first, rightmost + 1):
            if (
                self._spans[span_index].local_index_for_projection_position(
                    projection_position
                )
                is not None
            ):
                return True
        return False

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the projection boundary for one exact state."""

        located = self._locate_state(state)
        if located is None:
            resolved_state = self.state_for_source_position(
                state.source_position,
                prefer_after=state.placement
                is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
            )
            if resolved_state is None:
                return None
            located = self._locate_state(resolved_state)
            if located is None:
                return None
        span_start, span, local_index = located
        return span.stop_at(
            local_index,
            visual_index=span_start + local_index,
        ).projection_position

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return the first or last state at an exact projection boundary."""

        matches = self._states_for_projection_position(projection_position)
        if not matches:
            return None
        return matches[-1] if prefer_after else matches[0]

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return the first or last state at an exact source boundary."""

        matches: list[PromptProjectionCaretState] = []
        for span_start, span in zip(self._span_starts, self._spans, strict=True):
            local_index = span.local_index_for_source_position(source_position)
            if local_index is None:
                continue
            matches.append(
                span.stop_at(
                    local_index,
                    visual_index=span_start + local_index,
                ).state
            )
        if not matches:
            return None
        return matches[-1] if prefer_after else matches[0]

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Resolve an exact state without constructing a document-wide index."""

        located = self._locate_state(state)
        if located is None:
            return self.state_for_source_position(
                state.source_position,
                prefer_after=state.placement
                is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
            )
        span_start, span, local_index = located
        return span.stop_at(
            local_index,
            visual_index=span_start + local_index,
        ).state

    def matching_token_state(
        self,
        token_id: str,
        *,
        placement: PromptProjectionCaretPlacement,
        token_slot: int | None,
    ) -> PromptProjectionCaretState | None:
        """Return the first state matching one token navigation slot."""

        for span_start, span in zip(self._span_starts, self._spans, strict=True):
            if isinstance(span, ExplicitCaretSpan):
                if (
                    span.token_id == token_id
                    and span.placement is placement
                    and span.token_slot == token_slot
                ):
                    return span.stop_at(0, visual_index=span_start).state
                continue
            if isinstance(span, AtomicTokenCaretSpan):
                if span.token.token_id != token_id or token_slot is not None:
                    continue
                local_index = (
                    0
                    if placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
                    else 1
                    if placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                    else None
                )
                if local_index is not None:
                    return span.stop_at(
                        local_index,
                        visual_index=span_start + local_index,
                    ).state
                continue
            if (
                span.token_id != token_id
                or span.placement is not placement
                or token_slot is None
                or not span.boundary_start <= token_slot < span.boundary_end
            ):
                continue
            return span.stop_at(
                token_slot - span.boundary_start,
                visual_index=span_start + token_slot - span.boundary_start,
            ).state
        return None

    def next_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Return the visual state following an exact state."""

        visual_index = self._visual_index_for_state(state)
        if visual_index is None:
            return None
        return self[min(visual_index + 1, len(self) - 1)].state

    def previous_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Return the visual state preceding an exact state."""

        visual_index = self._visual_index_for_state(state)
        if visual_index is None:
            return None
        return self[max(visual_index - 1, 0)].state

    def visual_index_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the visual index for one exact or resolvable state."""

        return self._visual_index_for_state(state)

    def _states_for_projection_position(
        self,
        projection_position: int,
    ) -> tuple[PromptProjectionCaretState, ...]:
        """Return all exact states at one projection boundary in visual order."""

        matches: list[PromptProjectionCaretState] = []
        for span_index in self._span_indexes_for_projection_position(
            projection_position
        ):
            span_start = self._span_starts[span_index]
            span = self._spans[span_index]
            local_index = span.local_index_for_projection_position(projection_position)
            if local_index is None:
                continue
            matches.append(
                span.stop_at(
                    local_index,
                    visual_index=span_start + local_index,
                ).state
            )
        return tuple(matches)

    def _span_indexes_for_projection_position(
        self,
        projection_position: int,
    ) -> tuple[int, ...]:
        """Return the small ordered span set that can own one boundary."""

        if not self._spans:
            return ()
        rightmost = bisect_right(self._projection_starts, projection_position) - 1
        if rightmost < 0:
            return ()
        first = rightmost
        while (
            first > 0 and self._spans[first - 1].projection_end >= projection_position
        ):
            first -= 1
        return tuple(
            span_index
            for span_index in range(first, rightmost + 1)
            if self._spans[span_index].projection_end >= projection_position
        )

    def _locate_state(
        self,
        state: PromptProjectionCaretState,
    ) -> tuple[int, CaretSpan, int] | None:
        """Return the span and local index owning an exact state."""

        candidate_indexes: Sequence[int]
        if state.run_id is None:
            candidate_indexes = range(len(self._spans))
        else:
            candidate_indexes = self._spans_by_run_id.get(state.run_id, ())
        for span_index in candidate_indexes:
            span_start = self._span_starts[span_index]
            span = self._spans[span_index]
            local_index = span.local_index_for_state(state)
            if local_index is not None:
                return span_start, span, local_index
        return None

    def _visual_index_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the canonical visual index for one exact state."""

        located = self._locate_state(state)
        if located is None:
            resolved_state = self.resolve_state(state)
            if resolved_state is None:
                return None
            located = self._locate_state(resolved_state)
            if located is None:
                return None
        span_start, _span, local_index = located
        return span_start + local_index


__all__ = ["PromptProjectionCaretStopSequence"]
