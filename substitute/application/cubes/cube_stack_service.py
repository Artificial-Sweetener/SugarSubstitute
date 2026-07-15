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

"""Application-level orchestration service for cube stack alias and ordering policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Protocol

from substitute.domain.workflow import StackManager


class WorkflowStateProtocol(Protocol):
    """Describe workflow state shape synchronized by the cube stack service."""

    cubes: dict[str, Any]
    stack_order: list[str]


@dataclass(frozen=True)
class CubeRenameResolution:
    """Describe one centrally resolved cube rename outcome."""

    old_alias: str
    requested_alias: str
    resolved_alias: str


class CubeStackService:
    """Coordinate workflow-explicit cube alias and ordering mutations."""

    def resolve_unique_alias(
        self,
        workflow: WorkflowStateProtocol,
        requested_alias: str,
        *,
        exclude_alias: str | None = None,
    ) -> str:
        """Resolve one unique cube alias against a target workflow state."""

        return self._manager_for_workflow(workflow).resolve_unique_alias(
            requested_alias,
            exclude_alias=exclude_alias,
        )

    def apply_cube_addition(
        self,
        workflow: WorkflowStateProtocol,
        cube_id: str,
        alias_name: str,
        cube_state: Any,
    ) -> None:
        """Add cube alias to a target workflow state."""

        manager = self._manager_for_workflow(workflow)
        manager.add_cube(cube_id, alias_name, cube_state)
        workflow.cubes[alias_name] = cube_state
        workflow.stack_order = list(manager.stack_order)

    def resolve_cube_rename(
        self,
        workflow: WorkflowStateProtocol,
        old_alias: str,
        requested_alias: str,
    ) -> CubeRenameResolution:
        """Resolve one rename request through the shared alias policy."""

        return CubeRenameResolution(
            old_alias=old_alias,
            requested_alias=requested_alias,
            resolved_alias=self.resolve_unique_alias(
                workflow,
                requested_alias,
                exclude_alias=old_alias,
            ),
        )

    def apply_reordered_aliases(
        self,
        workflow: WorkflowStateProtocol,
        new_order: list[str],
    ) -> None:
        """Synchronize reordered cube aliases into target workflow state."""

        manager = self._manager_for_workflow(workflow)
        manager.stack_order = list(new_order)
        workflow.stack_order = list(manager.stack_order)

    def apply_cube_removal(
        self,
        workflow: WorkflowStateProtocol,
        alias_name: str,
    ) -> None:
        """Remove one cube alias from target workflow state."""

        manager = self._manager_for_workflow(workflow)
        manager.remove_cube(alias_name)
        workflow.cubes.pop(alias_name, None)
        workflow.stack_order = list(manager.stack_order)

    def set_cube_bypassed(
        self,
        workflow: WorkflowStateProtocol,
        alias_name: str,
        bypassed: bool,
    ) -> bool:
        """Set one cube bypass state and return whether it changed."""

        cube_state = workflow.cubes.get(alias_name)
        if cube_state is None:
            return False
        previous = getattr(cube_state, "bypassed", False) is True
        if previous == bypassed:
            return False
        setattr(cube_state, "bypassed", bypassed)
        return True

    def toggle_cube_bypassed(
        self,
        workflow: WorkflowStateProtocol,
        alias_name: str,
    ) -> bool:
        """Toggle one cube bypass state and return the new bypass value."""

        cube_state = workflow.cubes.get(alias_name)
        if cube_state is None:
            return False
        next_value = getattr(cube_state, "bypassed", False) is not True
        setattr(cube_state, "bypassed", next_value)
        return next_value

    def apply_cube_rename(
        self,
        workflow: WorkflowStateProtocol,
        old_alias: str,
        requested_alias: str,
    ) -> CubeRenameResolution:
        """Rename one cube alias in target workflow state."""

        resolution = self.resolve_cube_rename(workflow, old_alias, requested_alias)
        manager = self._manager_for_workflow(workflow)
        manager.rename_cube(old_alias, resolution.resolved_alias)
        cube_state = workflow.cubes.pop(old_alias, None)
        if cube_state is not None:
            setattr(cube_state, "alias", resolution.resolved_alias)
            workflow.cubes[resolution.resolved_alias] = cube_state
        workflow.stack_order = list(manager.stack_order)
        return resolution

    def _manager_for_workflow(self, workflow: WorkflowStateProtocol) -> StackManager:
        """Build a short-lived stack manager from one workflow snapshot."""

        manager = StackManager()
        manager.set_state(
            {
                alias: str(getattr(cube_state, "cube_id", ""))
                for alias, cube_state in workflow.cubes.items()
            },
            workflow.cubes,
            workflow.stack_order,
        )
        return manager


__all__ = [
    "CubeRenameResolution",
    "CubeStackService",
]
