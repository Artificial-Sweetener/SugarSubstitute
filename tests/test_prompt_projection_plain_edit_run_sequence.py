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

"""Verify bounded lookup in the incremental projection-run sequence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.plain_edit_coordinates import (
    PromptProjectionPlainEditCoordinates,
)
from substitute.presentation.editor.prompt_editor.projection.plain_edit_run_sequence import (
    PromptProjectionPlainEditRunSequence,
)


class _CountingRunSequence(Sequence[PromptProjectionRun]):
    """Expose ordered runs while counting indexed materialization requests."""

    def __init__(self, runs: tuple[PromptProjectionRun, ...]) -> None:
        """Retain immutable runs and initialize the read count."""

        self._runs = runs
        self.read_count = 0

    def __len__(self) -> int:
        """Return the run count."""

        return len(self._runs)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionRun: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionRun, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionRun | tuple[PromptProjectionRun, ...]:
        """Return requested runs and count integer access."""

        if isinstance(index, slice):
            return self._runs[index]
        self.read_count += 1
        return self._runs[index]


def _run(index: int) -> PromptProjectionRun:
    """Return one single-character source-backed run."""

    return PromptProjectionRun(
        run_id=f"run:{index}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=index,
        source_end=index + 1,
        display_text="x",
        source_positions=range(index, index + 2),
        projection_start=index,
        projection_end=index + 1,
    )


def test_position_lookup_materializes_logarithmic_run_count() -> None:
    """Current-run rebinding must not scan a long document per fragment."""

    run_count = 4096
    edited_index = run_count // 2
    base_runs = _CountingRunSequence(tuple(_run(index) for index in range(run_count)))
    edited_run = PromptProjectionRun(
        run_id=f"run:{edited_index}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=edited_index,
        source_end=edited_index + 2,
        display_text="xx",
        source_positions=range(edited_index, edited_index + 3),
        projection_start=edited_index,
        projection_end=edited_index + 2,
    )
    runs = PromptProjectionPlainEditRunSequence(
        base_runs,
        edited_run_index=edited_index,
        edited_run=edited_run,
        coordinates=PromptProjectionPlainEditCoordinates(
            source_start=edited_index,
            source_end=edited_index,
            source_delta=1,
            projection_start=edited_index,
            projection_delta=1,
        ),
    )
    mapping = PromptProjectionMapping(
        runs=runs,
        source_length=run_count + 1,
        projection_length=run_count + 1,
    )

    resolved = mapping.run_at_projection_position(run_count - 10)

    assert resolved is not None
    assert resolved.run_id == f"run:{run_count - 11}"
    assert base_runs.read_count <= 16


def test_position_lookup_honors_shared_run_boundary_preference() -> None:
    """Boundary lookup must select the next or previous run as requested."""

    base_runs = tuple(_run(index) for index in range(4))
    edited_run = PromptProjectionRun(
        run_id="run:1",
        kind=PromptProjectionRunKind.TEXT,
        source_start=1,
        source_end=3,
        display_text="xx",
        source_positions=range(1, 4),
        projection_start=1,
        projection_end=3,
    )
    runs = PromptProjectionPlainEditRunSequence(
        base_runs,
        edited_run_index=1,
        edited_run=edited_run,
        coordinates=PromptProjectionPlainEditCoordinates(
            source_start=1,
            source_end=1,
            source_delta=1,
            projection_start=1,
            projection_delta=1,
        ),
    )
    mapping = PromptProjectionMapping(
        runs=runs,
        source_length=5,
        projection_length=5,
    )

    next_run = mapping.run_at_projection_position(3)
    previous_run = mapping.run_at_projection_position(3, prefer_previous=True)

    assert next_run is not None
    assert previous_run is not None
    assert next_run.run_id == "run:2"
    assert previous_run.run_id == "run:1"
