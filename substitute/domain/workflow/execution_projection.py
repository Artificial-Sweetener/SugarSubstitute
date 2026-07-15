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

"""Project workflow cube stacks into active execution order."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class WorkflowExecutionState(Protocol):
    """Describe workflow state required for cube execution projection."""

    stack_order: list[str]
    cubes: Mapping[str, object]


def is_cube_bypassed(cube_state: object) -> bool:
    """Return whether one cube state is bypassed for workflow execution."""

    return getattr(cube_state, "bypassed", False) is True


def active_cube_aliases(workflow: WorkflowExecutionState) -> tuple[str, ...]:
    """Return stack-order aliases that should be emitted to active Sugar."""

    return tuple(
        alias
        for alias in workflow.stack_order
        if alias in workflow.cubes and not is_cube_bypassed(workflow.cubes[alias])
    )


def bypassed_cube_aliases(workflow: WorkflowExecutionState) -> tuple[str, ...]:
    """Return stack-order aliases that should be serialized as bypass comments."""

    return tuple(
        alias
        for alias in workflow.stack_order
        if alias in workflow.cubes and is_cube_bypassed(workflow.cubes[alias])
    )


def active_adjacent_alias_pairs(
    workflow: WorkflowExecutionState,
) -> tuple[tuple[str, str], ...]:
    """Return adjacent active aliases for generated Sugar connect statements."""

    aliases = active_cube_aliases(workflow)
    return tuple(zip(aliases, aliases[1:]))


__all__ = [
    "WorkflowExecutionState",
    "active_adjacent_alias_pairs",
    "active_cube_aliases",
    "bypassed_cube_aliases",
    "is_cube_bypassed",
]
