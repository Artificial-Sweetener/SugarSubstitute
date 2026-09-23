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

"""Materialize persisted workflow cube state into its live tab surface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from substitute.presentation.resources import cube_icon_resolver
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeStackProtocol,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.workflow_cube_stack_materializer")


class WorkflowCubeStackMaterializationView(Protocol):
    """Describe shell state required to rebuild a workflow cube stack."""

    cube_stacks: Mapping[str, object]
    cube_icon_factory: cube_icon_resolver.CubeIconFactoryProtocol


class WorkflowCubeStackMaterializer:
    """Rebuild live cube-stack tabs from authoritative workflow state."""

    def __init__(self, view: WorkflowCubeStackMaterializationView) -> None:
        """Store the shell view that owns workflow cube-stack widgets."""

        self._view = view

    def materialize(
        self,
        workflow_id: str,
        workflow: object,
        *,
        active_cube_alias: str | None,
    ) -> None:
        """Populate one workflow cube stack while preserving active-cube intent."""

        cube_stack = self._view.cube_stacks.get(workflow_id)
        if cube_stack is None:
            log_warning(
                _LOGGER,
                "Skipped workflow cube-stack materialization because stack was missing",
                workflow_id=workflow_id,
            )
            return
        cubes = getattr(workflow, "cubes", {})
        stack_order = list(getattr(workflow, "stack_order", ()) or [])
        if not isinstance(cubes, dict):
            log_warning(
                _LOGGER,
                "Skipped workflow cube-stack materialization because cube state was invalid",
                workflow_id=workflow_id,
                cube_state_type=type(cubes).__name__,
            )
            return

        log_info(
            _LOGGER,
            "Workflow cube-stack materialization started",
            workflow_id=workflow_id,
            cube_count=len(cubes),
            stack_order_count=len(stack_order),
        )
        resolved_active_cube_alias = active_cube_alias
        if resolved_active_cube_alias not in stack_order:
            resolved_active_cube_alias = stack_order[-1] if stack_order else None
        result = CubeStackPresenter(
            icon_resolver=cube_icon_resolver.CubeIconResolver(
                cube_icon_factory=getattr(self._view, "cube_icon_factory", None),
            ),
        ).rebuild_stack(
            cast(CubeStackProtocol, cube_stack),
            workflow_id=workflow_id,
            workflow=workflow,
            active_cube_alias=resolved_active_cube_alias,
        )
        log_info(
            _LOGGER,
            "Materialized workflow cube stack",
            workflow_id=workflow_id,
            inserted_count=result.inserted_count,
            stack_order_count=len(stack_order),
            warning_count=len(result.warnings),
        )


__all__ = [
    "WorkflowCubeStackMaterializationView",
    "WorkflowCubeStackMaterializer",
]
