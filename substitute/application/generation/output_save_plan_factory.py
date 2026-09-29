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

"""Prepare immutable destination policy for a generation run."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from substitute.application.cubes import cube_alias_body
from substitute.application.generation.generation_models import (
    PreparedGenerationRequest,
)
from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.domain.workflow import active_cube_aliases


class OutputSavePlanFactory:
    """Own output numbering and persistence policy for one prepared request."""

    def __init__(
        self,
        *,
        output_dir: Path,
        preferences: OutputPreferenceService | None,
    ) -> None:
        """Bind the configured output root and optional user preferences."""

        self._output_dir = output_dir
        self._preferences = preferences

    def create(
        self,
        request: PreparedGenerationRequest,
        *,
        seed: str,
        explicit_output_aliases: tuple[str, ...] = (),
    ) -> OutputSavePlan:
        """Create immutable output organization settings for one queued run."""

        job_started_at = request.output_job_started_at or datetime.now().astimezone()
        cube_numbers = _cube_numbers_by_alias(request)
        if self._preferences is not None:
            return self._preferences.create_save_plan(
                workflow_name=request.workflow_name,
                output_run_number=request.output_run_number,
                job_started_at=job_started_at,
                seed=seed,
                cube_numbers_by_alias=cube_numbers,
                active_cube_aliases=(
                    explicit_output_aliases or _active_cube_aliases_for_request(request)
                ),
                muted_cube_aliases=_muted_cube_aliases_for_request(request),
            )
        return OutputSavePlan(
            output_root=self._output_dir,
            path_pattern="{date}\\{run}_{cube#}_{workflow}_{source}",
            workflow_name=request.workflow_name,
            output_run_number=request.output_run_number,
            job_started_at=job_started_at,
            seed=seed,
            cube_numbers_by_alias=cube_numbers,
        )


def _cube_numbers_by_alias(request: PreparedGenerationRequest) -> dict[str, int]:
    """Return lookup keys for cube order from detached workflow state."""

    aliases = _ordered_cube_aliases_from_workflow(request.workflow) or ()
    numbers: dict[str, int] = {}
    for index, alias in enumerate(aliases, start=1):
        _add_cube_number_aliases(numbers, alias, index)
    return numbers


def _active_cube_aliases_for_request(
    request: PreparedGenerationRequest,
) -> tuple[str, ...]:
    """Return topology-ordered active cube aliases for persistence policy."""

    return _ordered_cube_aliases_from_workflow(request.workflow) or ()


def _muted_cube_aliases_for_request(
    request: PreparedGenerationRequest,
) -> frozenset[str]:
    """Return workflow-local cube aliases whose outputs are memory-only."""

    cubes = getattr(request.workflow, "cubes", None)
    if isinstance(cubes, Mapping):
        return frozenset(
            alias
            for alias, cube in cubes.items()
            if isinstance(alias, str)
            and getattr(cube, "output_persistence_enabled", True) is False
        )
    return frozenset()


def _ordered_cube_aliases_from_workflow(
    workflow: object | None,
) -> tuple[str, ...] | None:
    """Return stack-order aliases from a workflow-like object when available."""

    stack_order = getattr(workflow, "stack_order", None)
    if not isinstance(stack_order, list | tuple):
        return None
    cubes = getattr(workflow, "cubes", None)
    if isinstance(cubes, Mapping):
        aliases = active_cube_aliases(cast(Any, workflow))
    else:
        aliases = tuple(
            alias for alias in stack_order if isinstance(alias, str) and alias
        )
    return aliases if aliases else None


def _add_cube_number_aliases(
    numbers: dict[str, int], alias: str, cube_number: int
) -> None:
    """Index raw and display-form aliases for save-time source lookup."""

    for key in {alias, cube_alias_body(alias)}:
        cleaned = key.strip()
        if cleaned and cleaned not in numbers:
            numbers[cleaned] = cube_number


__all__ = ["OutputSavePlanFactory"]
