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

"""Map source boundaries onto immutable visible projection runs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .runs import PromptProjectionRun


@dataclass(frozen=True, slots=True)
class PromptProjectionMapping:
    """Map raw source indices onto the ordered projection run stream."""

    runs: Sequence[PromptProjectionRun]
    source_length: int
    projection_length: int
    _runs_by_id: dict[str, PromptProjectionRun] | None = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Index runs for efficient lookup."""

        object.__setattr__(self, "_runs_by_id", None)

    def run_by_id(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return the run with the supplied identifier when it exists."""

        if run_id is None:
            return None
        optimized_lookup = getattr(self.runs, "run_by_id", None)
        if callable(optimized_lookup):
            run = optimized_lookup(run_id)
            return run if isinstance(run, PromptProjectionRun) else None
        runs_by_id = self._runs_by_id
        if runs_by_id is None:
            runs_by_id = {run.run_id: run for run in self.runs}
            object.__setattr__(self, "_runs_by_id", runs_by_id)
        return runs_by_id.get(run_id)

    def runs_for_token(
        self,
        token_id: str,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return the visible runs owned by one semantic token."""

        return tuple(run for run in self.runs if run.token_id == token_id)

    def run_at_projection_position(
        self,
        projection_position: int,
        *,
        prefer_previous: bool = False,
    ) -> PromptProjectionRun | None:
        """Return the run adjacent to one projection boundary."""

        clamped_position = max(0, min(projection_position, self.projection_length))
        optimized_lookup = getattr(self.runs, "run_at_projection_position", None)
        if callable(optimized_lookup):
            run = optimized_lookup(
                clamped_position,
                prefer_previous=prefer_previous,
            )
            return run if isinstance(run, PromptProjectionRun) else None
        if prefer_previous:
            for run in reversed(self.runs):
                if run.projection_start < clamped_position <= run.projection_end:
                    return run
        for run in self.runs:
            if run.projection_start <= clamped_position < run.projection_end:
                return run
        return None

    def text_projection_ranges_for_source_range(
        self,
        start: int,
        end: int,
    ) -> tuple[tuple[int, int], ...]:
        """Return text-only projection ranges covering one raw source range."""

        selection_start = max(0, min(start, end))
        selection_end = min(self.source_length, max(start, end))
        if selection_end <= selection_start:
            return ()

        ranges: list[tuple[int, int]] = []
        for run in self.runs:
            if not run.is_text or not run.source_backed:
                continue
            run_source_start = run.source_positions[0]
            run_source_end = run.source_positions[-1]
            overlap_start = max(selection_start, run_source_start)
            overlap_end = min(selection_end, run_source_end)
            if overlap_end <= overlap_start:
                continue
            start_index = run.source_positions.index(overlap_start)
            end_index = run.source_positions.index(overlap_end)
            ranges.append(
                (
                    run.projection_start + start_index,
                    run.projection_start + end_index,
                )
            )

        if not ranges:
            return ()

        merged_ranges: list[tuple[int, int]] = []
        current_start, current_end = ranges[0]
        for next_start, next_end in ranges[1:]:
            if next_start == current_end:
                current_end = next_end
                continue
            merged_ranges.append((current_start, current_end))
            current_start, current_end = next_start, next_end
        merged_ranges.append((current_start, current_end))
        return tuple(merged_ranges)
