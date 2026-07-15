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

"""Contract tests for application-level cube add orchestration."""

from __future__ import annotations

from substitute.application.cubes import CubeStackService, CubeWorkflowAddService
from substitute.domain.workflow import CubeState, WorkflowState


def _cube_state(alias: str) -> CubeState:
    """Build one minimal cube state for workflow-add service tests."""

    return CubeState(
        cube_id="base",
        version="1.0.0",
        alias=alias,
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
        display_name=alias,
    )


def test_add_loaded_cube_resolves_alias_and_updates_workflow_atomically() -> None:
    """Loaded cube additions should resolve aliases and update workflow state once."""

    workflow = WorkflowState()
    existing_state = _cube_state("Loader")
    workflow.cubes["Loader"] = existing_state
    workflow.stack_order = ["Loader"]
    cube_state = _cube_state("Loader")
    service = CubeWorkflowAddService(CubeStackService())

    result = service.add_loaded_cube(
        workflow,
        cube_id="base",
        requested_alias="Loader",
        cube_state=cube_state,
    )

    assert result.requested_alias == "Loader"
    assert result.alias == "Loader 2"
    assert result.added_index == 1
    assert result.stack_order == ["Loader", "Loader 2"]
    assert result.requires_input_canvas_materialization is True
    assert workflow.stack_order == ["Loader", "Loader 2"]
    assert workflow.cubes["Loader 2"] is cube_state
    assert cube_state.alias == "Loader 2"


def test_add_loaded_cube_preserves_unique_alias_without_suffix() -> None:
    """Unique aliases should be inserted without unnecessary renaming."""

    workflow = WorkflowState()
    cube_state = _cube_state("Unique")
    service = CubeWorkflowAddService(CubeStackService())

    result = service.add_loaded_cube(
        workflow,
        cube_id="base",
        requested_alias="Unique",
        cube_state=cube_state,
    )

    assert result.alias == "Unique"
    assert result.added_index == 0
    assert workflow.cubes == {"Unique": cube_state}
    assert workflow.stack_order == ["Unique"]
