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

"""Own application-level workflow mutation for loaded cube additions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from substitute.application.cubes.cube_stack_service import CubeStackService


class WorkflowStateProtocol(Protocol):
    """Describe workflow state required to add a loaded cube."""

    cubes: dict[str, Any]
    stack_order: list[str]


@dataclass(frozen=True)
class CubeAddResult:
    """Describe one loaded cube addition applied to workflow state."""

    cube_id: str
    requested_alias: str
    alias: str
    cube_state: Any
    stack_order: list[str]
    added_index: int
    requires_input_canvas_materialization: bool = True


class CubeWorkflowAddService:
    """Apply loaded cube additions through shared workflow stack policy."""

    def __init__(self, cube_stack_service: CubeStackService) -> None:
        """Store the stack service used for alias and ordering policy."""

        self._cube_stack_service = cube_stack_service

    def add_loaded_cube(
        self,
        workflow: WorkflowStateProtocol,
        *,
        cube_id: str,
        requested_alias: str,
        cube_state: Any,
    ) -> CubeAddResult:
        """Add one loaded cube to a workflow and return resolved projection metadata."""

        resolved_alias = self._cube_stack_service.resolve_unique_alias(
            workflow,
            requested_alias,
        )
        try:
            setattr(cube_state, "alias", resolved_alias)
        except (AttributeError, TypeError):
            pass
        self._cube_stack_service.apply_cube_addition(
            workflow,
            cube_id,
            resolved_alias,
            cube_state,
        )
        added_index = (
            workflow.stack_order.index(resolved_alias)
            if resolved_alias in workflow.stack_order
            else max(0, len(workflow.stack_order) - 1)
        )
        return CubeAddResult(
            cube_id=cube_id,
            requested_alias=requested_alias,
            alias=resolved_alias,
            cube_state=cube_state,
            stack_order=list(workflow.stack_order),
            added_index=added_index,
        )


__all__ = ["CubeAddResult", "CubeWorkflowAddService"]
