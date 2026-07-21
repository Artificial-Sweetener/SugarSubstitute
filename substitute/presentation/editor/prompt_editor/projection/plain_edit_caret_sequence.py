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

"""Transform canonical caret stops lazily across one plain source edit."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import overload

from .model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
    PromptProjectionRun,
)
from .plain_edit_coordinates import PromptProjectionPlainEditCoordinates


MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH = 8


class PromptProjectionPlainEditCaretStopSequence(Sequence[PromptProjectionCaretStop]):
    """Expose edited plain-text caret stops without rebuilding the full map."""

    __slots__ = (
        "_coordinates",
        "_edited_run",
        "_lazy_depth",
        "_previous_caret_map",
        "_previous_stops",
        "_pivot_visual_index",
    )
    _coordinates: PromptProjectionPlainEditCoordinates
    _edited_run: PromptProjectionRun
    _lazy_depth: int
    _previous_caret_map: PromptProjectionCaretMap
    _previous_stops: Sequence[PromptProjectionCaretStop]
    _pivot_visual_index: int

    def __init__(
        self,
        previous_caret_map: PromptProjectionCaretMap,
        *,
        edited_run: PromptProjectionRun,
        coordinates: PromptProjectionPlainEditCoordinates,
    ) -> None:
        """Anchor the coordinate transform at the edited plain-run boundary."""

        previous_stops = previous_caret_map.stops
        previous_sequence = (
            previous_stops
            if isinstance(previous_stops, PromptProjectionPlainEditCaretStopSequence)
            else None
        )
        combined_edit = (
            None
            if previous_sequence is None
            else previous_sequence._combined_contiguous_edit(
                edited_run=edited_run,
                coordinates=coordinates,
            )
        )
        if previous_sequence is not None and combined_edit is not None:
            combined_coordinates, combined_pivot_visual_index = combined_edit
            self._previous_caret_map = previous_sequence._previous_caret_map
            self._previous_stops = previous_sequence._previous_stops
            self._coordinates = combined_coordinates
            self._edited_run = edited_run
            self._pivot_visual_index = combined_pivot_visual_index
            self._lazy_depth = previous_sequence._lazy_depth
            return

        self._previous_caret_map = previous_caret_map
        self._previous_stops = previous_stops
        self._edited_run = edited_run
        self._coordinates = coordinates
        self._lazy_depth = (
            1 if previous_sequence is None else previous_sequence._lazy_depth + 1
        )
        pivot_state = PromptProjectionCaretState(
            source_position=coordinates.source_start,
            placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
            run_id=edited_run.run_id,
        )
        pivot_visual_index = _visual_index_for_state(
            self._previous_stops,
            pivot_state,
        )
        if pivot_visual_index is None:
            resolved_pivot = previous_caret_map.state_for_source_position(
                coordinates.source_start,
                prefer_after=False,
            )
            pivot_visual_index = _visual_index_for_state(
                self._previous_stops,
                resolved_pivot,
            )
        if pivot_visual_index is None:
            raise ValueError("Plain edit caret pivot is absent from the previous map.")
        self._pivot_visual_index = pivot_visual_index

    @property
    def transform_depth(self) -> int:
        """Return the bounded number of unresolved edit transforms."""

        return self._lazy_depth

    def _combined_contiguous_edit(
        self,
        *,
        edited_run: PromptProjectionRun,
        coordinates: PromptProjectionPlainEditCoordinates,
    ) -> tuple[PromptProjectionPlainEditCoordinates, int] | None:
        """Combine adjacent insertion or deletion runs into one transform."""

        current = self._coordinates
        if self._edited_run.run_id != edited_run.run_id:
            return None
        source_delta = current.source_delta + coordinates.source_delta
        projection_delta = current.projection_delta + coordinates.projection_delta
        appends_insertion = bool(
            current.source_delta >= 0
            and current.projection_delta >= 0
            and coordinates.source_delta > 0
            and coordinates.projection_delta > 0
            and coordinates.source_start == current.source_start + current.source_delta
            and coordinates.projection_start
            == current.projection_start + current.projection_delta
        )
        prepends_insertion = bool(
            current.source_delta >= 0
            and current.projection_delta >= 0
            and coordinates.source_delta > 0
            and coordinates.projection_delta > 0
            and coordinates.source_start == current.source_start
            and coordinates.projection_start == current.projection_start
        )
        if appends_insertion or prepends_insertion:
            return (
                PromptProjectionPlainEditCoordinates(
                    source_start=current.source_start,
                    source_end=current.source_end,
                    source_delta=source_delta,
                    projection_start=current.projection_start,
                    projection_delta=projection_delta,
                ),
                self._pivot_visual_index,
            )

        deletes_before = bool(
            current.source_delta < 0
            and current.projection_delta < 0
            and coordinates.source_delta < 0
            and coordinates.projection_delta < 0
            and coordinates.source_end == current.source_start
            and coordinates.projection_start - coordinates.projection_delta
            == current.projection_start
        )
        if deletes_before:
            return (
                PromptProjectionPlainEditCoordinates(
                    source_start=coordinates.source_start,
                    source_end=current.source_end,
                    source_delta=source_delta,
                    projection_start=coordinates.projection_start,
                    projection_delta=projection_delta,
                ),
                self._pivot_visual_index + coordinates.source_delta,
            )

        deletes_after = bool(
            current.source_delta < 0
            and current.projection_delta < 0
            and coordinates.source_delta < 0
            and coordinates.projection_delta < 0
            and coordinates.source_start == current.source_start
            and coordinates.projection_start == current.projection_start
        )
        if deletes_after:
            return (
                PromptProjectionPlainEditCoordinates(
                    source_start=current.source_start,
                    source_end=current.source_end - coordinates.source_delta,
                    source_delta=source_delta,
                    projection_start=current.projection_start,
                    projection_delta=projection_delta,
                ),
                self._pivot_visual_index,
            )
        return None

    def __len__(self) -> int:
        """Return the previous stop count adjusted by the plain edit delta."""

        return len(self._previous_stops) + self._coordinates.source_delta

    @overload
    def __getitem__(self, index: int) -> PromptProjectionCaretStop: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionCaretStop, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionCaretStop | tuple[PromptProjectionCaretStop, ...]:
        """Materialize one transformed stop or requested slice."""

        if isinstance(index, slice):
            return tuple(
                self[position] for position in range(*index.indices(len(self)))
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        delta = self._coordinates.source_delta
        pivot = self._pivot_visual_index
        if delta > 0 and pivot < normalized_index <= pivot + delta:
            local_delta = normalized_index - pivot
            return PromptProjectionCaretStop(
                visual_index=normalized_index,
                projection_position=(self._coordinates.projection_start + local_delta),
                state=PromptProjectionCaretState(
                    source_position=self._coordinates.source_start + local_delta,
                    placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                    run_id=self._edited_run.run_id,
                ),
            )
        previous_index = (
            normalized_index if normalized_index <= pivot else normalized_index - delta
        )
        previous_stop = self._previous_stops[previous_index]
        return self._transform_previous_stop(
            previous_stop,
            previous_visual_index=previous_index,
            next_visual_index=normalized_index,
        )

    def __iter__(self) -> Iterator[PromptProjectionCaretStop]:
        """Yield transformed stops on demand."""

        for index in range(len(self)):
            yield self[index]

    def has_projection_position(self, projection_position: int) -> bool:
        """Return whether the edited sequence owns one projection boundary."""

        coordinates = self._coordinates
        delta = coordinates.projection_delta
        if delta > 0 and (
            coordinates.projection_start
            < projection_position
            <= coordinates.projection_start + delta
        ):
            return True
        previous_position = (
            projection_position
            if projection_position <= coordinates.projection_start
            else projection_position - delta
        )
        lookup = getattr(self._previous_stops, "has_projection_position", None)
        if callable(lookup):
            return bool(lookup(previous_position))
        return any(
            stop.projection_position == previous_position
            for stop in self._previous_stops
        )

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the transformed projection boundary for one caret state."""

        visual_index = self.visual_index_for_state(state)
        if visual_index is None:
            return None
        return self[visual_index].projection_position

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a canonical state at one transformed projection boundary."""

        coordinates = self._coordinates
        delta = coordinates.projection_delta
        if delta > 0 and (
            coordinates.projection_start
            < projection_position
            <= coordinates.projection_start + delta
        ):
            return PromptProjectionCaretState(
                source_position=(
                    coordinates.source_start
                    + projection_position
                    - coordinates.projection_start
                ),
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id=self._edited_run.run_id,
            )
        previous_position = (
            projection_position
            if projection_position <= coordinates.projection_start
            else projection_position - delta
        )
        previous_state = self._previous_caret_map.state_for_projection_position(
            previous_position,
            prefer_after=prefer_after,
        )
        return self._transform_previous_state(previous_state)

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a canonical state at one transformed source boundary."""

        coordinates = self._coordinates
        delta = coordinates.source_delta
        if delta > 0 and (
            coordinates.source_start
            < source_position
            <= coordinates.source_start + delta
        ):
            return PromptProjectionCaretState(
                source_position=source_position,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id=self._edited_run.run_id,
            )
        previous_position = (
            source_position
            if source_position <= coordinates.source_start
            else source_position - delta
        )
        previous_state = self._previous_caret_map.state_for_source_position(
            previous_position,
            prefer_after=prefer_after,
        )
        return self._transform_previous_state(previous_state)

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Resolve one possibly stale state in the edited coordinate space."""

        if state.token_id is not None:
            matching = self.matching_token_state(
                state.token_id,
                placement=state.placement,
                token_slot=state.token_slot,
            )
            if matching is not None:
                return matching
        return self.state_for_source_position(
            state.source_position,
            prefer_after=(
                state.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
            ),
        )

    def matching_token_state(
        self,
        token_id: str,
        *,
        placement: PromptProjectionCaretPlacement,
        token_slot: int | None,
    ) -> PromptProjectionCaretState | None:
        """Return one transformed token-owned state by its stable slot."""

        lookup = getattr(self._previous_stops, "matching_token_state", None)
        if not callable(lookup):
            return None
        previous_state = lookup(
            token_id,
            placement=placement,
            token_slot=token_slot,
        )
        return self._transform_previous_state(previous_state)

    def next_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Return the next visual state in the edited sequence."""

        visual_index = self.visual_index_for_state(state)
        if visual_index is None:
            return None
        return self[min(visual_index + 1, len(self) - 1)].state

    def previous_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Return the previous visual state in the edited sequence."""

        visual_index = self.visual_index_for_state(state)
        if visual_index is None:
            return None
        return self[max(visual_index - 1, 0)].state

    def visual_index_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the transformed visual index for one caret state."""

        coordinates = self._coordinates
        delta = coordinates.source_delta
        if (
            delta > 0
            and state.run_id == self._edited_run.run_id
            and state.placement is PromptProjectionCaretPlacement.PLAIN_TEXT
            and coordinates.source_start
            < state.source_position
            <= coordinates.source_start + delta
        ):
            return self._pivot_visual_index + (
                state.source_position - coordinates.source_start
            )
        previous_state = _state_in_previous_coordinates(state, coordinates)
        previous_index = _visual_index_for_state(
            self._previous_stops,
            previous_state,
        )
        if previous_index is None:
            return None
        if previous_index <= self._pivot_visual_index:
            return previous_index
        next_index = previous_index + delta
        if next_index <= self._pivot_visual_index:
            return self._pivot_visual_index
        return next_index

    def _transform_previous_stop(
        self,
        stop: PromptProjectionCaretStop,
        *,
        previous_visual_index: int,
        next_visual_index: int,
    ) -> PromptProjectionCaretStop:
        """Return one previous stop shifted when it follows the edit pivot."""

        if previous_visual_index <= self._pivot_visual_index:
            if stop.visual_index == next_visual_index:
                return stop
            return PromptProjectionCaretStop(
                visual_index=next_visual_index,
                projection_position=stop.projection_position,
                state=stop.state,
            )
        return PromptProjectionCaretStop(
            visual_index=next_visual_index,
            projection_position=(
                stop.projection_position + self._coordinates.projection_delta
            ),
            state=_shift_state(
                stop.state,
                delta=self._coordinates.source_delta,
            ),
        )

    def _transform_previous_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState:
        """Shift a previous state only when it follows the edit pivot."""

        previous_index = _visual_index_for_state(self._previous_stops, state)
        if previous_index is None or previous_index <= self._pivot_visual_index:
            return state
        return _shift_state(state, delta=self._coordinates.source_delta)


def _visual_index_for_state(
    stops: Sequence[PromptProjectionCaretStop],
    state: PromptProjectionCaretState,
) -> int | None:
    """Return one sequence's optimized or scanned visual index."""

    lookup = getattr(stops, "visual_index_for_state", None)
    if callable(lookup):
        result = lookup(state)
        return int(result) if result is not None else None
    for stop in stops:
        if stop.state == state:
            return stop.visual_index
    return None


def _state_in_previous_coordinates(
    state: PromptProjectionCaretState,
    coordinates: PromptProjectionPlainEditCoordinates,
) -> PromptProjectionCaretState:
    """Return a next-document state mapped back across the plain edit."""

    source_position = state.source_position
    if source_position > coordinates.source_start:
        source_position -= coordinates.source_delta
    if source_position == state.source_position:
        return state
    return PromptProjectionCaretState(
        source_position=source_position,
        placement=state.placement,
        token_id=state.token_id,
        run_id=state.run_id,
        token_slot=state.token_slot,
    )


def _shift_state(
    state: PromptProjectionCaretState,
    *,
    delta: int,
) -> PromptProjectionCaretState:
    """Return one caret state shifted by a uniform downstream delta."""

    if delta == 0:
        return state
    return PromptProjectionCaretState(
        source_position=state.source_position + delta,
        placement=state.placement,
        token_id=state.token_id,
        run_id=state.run_id,
        token_slot=state.token_slot,
    )


__all__ = [
    "MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH",
    "PromptProjectionPlainEditCaretStopSequence",
]
