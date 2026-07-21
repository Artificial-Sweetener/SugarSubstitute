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

"""Expose one edited projection run and a compact shifted suffix."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import overload

from .model import PromptProjectionRun
from .plain_edit_coordinates import PromptProjectionPlainEditCoordinates


class PromptProjectionPlainEditRunSequence(Sequence[PromptProjectionRun]):
    """Retain stable runs and materialize shifted suffix entries at most once."""

    __slots__ = (
        "_base_runs",
        "_cache",
        "_edited_run",
        "_edited_run_index",
        "_index_by_id",
        "_projection_delta",
        "_source_delta",
    )
    _base_runs: Sequence[PromptProjectionRun]
    _cache: dict[int, PromptProjectionRun]
    _edited_run: PromptProjectionRun
    _edited_run_index: int
    _index_by_id: dict[str, int] | None
    _projection_delta: int
    _source_delta: int

    def __init__(
        self,
        base_runs: Sequence[PromptProjectionRun],
        *,
        edited_run_index: int,
        edited_run: PromptProjectionRun,
        coordinates: PromptProjectionPlainEditCoordinates,
    ) -> None:
        """Flatten consecutive edits of one run onto one immutable base."""

        if (
            isinstance(base_runs, PromptProjectionPlainEditRunSequence)
            and base_runs._edited_run_index == edited_run_index
            and base_runs._edited_run.run_id == edited_run.run_id
        ):
            self._base_runs = base_runs._base_runs
            self._source_delta = base_runs._source_delta + coordinates.source_delta
            self._projection_delta = (
                base_runs._projection_delta + coordinates.projection_delta
            )
        else:
            self._base_runs = base_runs
            self._source_delta = coordinates.source_delta
            self._projection_delta = coordinates.projection_delta
        self._edited_run_index = edited_run_index
        self._edited_run = edited_run
        self._cache: dict[int, PromptProjectionRun] = {edited_run_index: edited_run}
        self._index_by_id: dict[str, int] | None = None

    def __len__(self) -> int:
        """Return the stable run count."""

        return len(self._base_runs)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionRun: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionRun, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionRun | tuple[PromptProjectionRun, ...]:
        """Return one prepared run or a materialized slice."""

        if isinstance(index, slice):
            return tuple(
                self[position] for position in range(*index.indices(len(self)))
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        return self._run_at(normalized_index)

    def __iter__(self) -> Iterator[PromptProjectionRun]:
        """Traverse the base directly without repeated indexed dispatch."""

        for index in range(len(self._base_runs)):
            yield self._run_at(index)

    def __reversed__(self) -> Iterator[PromptProjectionRun]:
        """Traverse the base backward without Sequence fallback dispatch."""

        for index in range(len(self._base_runs) - 1, -1, -1):
            yield self._run_at(index)

    def run_by_id(self, run_id: str) -> PromptProjectionRun | None:
        """Return one run by stable identifier without scanning shifted values."""

        if run_id == self._edited_run.run_id:
            return self._edited_run
        index_by_id = self._index_by_id
        if index_by_id is None:
            index_by_id = {
                run.run_id: index for index, run in enumerate(self._base_runs)
            }
            self._index_by_id = index_by_id
        index = index_by_id.get(run_id)
        return None if index is None else self._run_at(index)

    def run_at_projection_position(
        self,
        projection_position: int,
        *,
        prefer_previous: bool = False,
    ) -> PromptProjectionRun | None:
        """Return one adjacent run while materializing only logarithmic entries."""

        lower_bound = 0
        upper_bound = len(self)
        while lower_bound < upper_bound:
            middle = (lower_bound + upper_bound) // 2
            middle_start = self._run_at(middle).projection_start
            starts_before_boundary = (
                middle_start < projection_position
                if prefer_previous
                else middle_start <= projection_position
            )
            if starts_before_boundary:
                lower_bound = middle + 1
            else:
                upper_bound = middle
        candidate_index = lower_bound - 1
        if candidate_index < 0:
            return None
        candidate = self._run_at(candidate_index)
        if prefer_previous:
            return (
                candidate
                if candidate.projection_start
                < projection_position
                <= candidate.projection_end
                else None
            )
        return (
            candidate
            if candidate.projection_start
            <= projection_position
            < candidate.projection_end
            else None
        )

    def _run_at(self, index: int) -> PromptProjectionRun:
        """Return one cached stable, edited, or coordinate-shifted run."""

        cached = self._cache.get(index)
        if cached is not None:
            return cached
        base_run = self._base_runs[index]
        run = (
            base_run
            if index < self._edited_run_index
            else _shift_run(
                base_run,
                source_delta=self._source_delta,
                projection_delta=self._projection_delta,
            )
        )
        self._cache[index] = run
        return run


def _shift_run(
    run: PromptProjectionRun,
    *,
    source_delta: int,
    projection_delta: int,
) -> PromptProjectionRun:
    """Shift one unchanged suffix run into current source coordinates."""

    source_positions: Sequence[int]
    if isinstance(run.source_positions, range):
        source_positions = range(
            run.source_positions.start + source_delta,
            run.source_positions.stop + source_delta,
            run.source_positions.step,
        )
    else:
        source_positions = tuple(
            position + source_delta for position in run.source_positions
        )
    return replace(
        run,
        source_start=run.source_start + source_delta,
        source_end=run.source_end + source_delta,
        source_positions=source_positions,
        projection_start=run.projection_start + projection_delta,
        projection_end=run.projection_end + projection_delta,
    )


__all__ = ["PromptProjectionPlainEditRunSequence"]
