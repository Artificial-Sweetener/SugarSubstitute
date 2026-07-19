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

"""Behavior tests for workflow-local cube output persistence policy."""

from __future__ import annotations

from substitute.application.cubes import CubeStackService
from substitute.domain.recipes.recipe_buffers import strip_recipe_buffers
from substitute.domain.recipes.sugar_script_parser import parse_sugar_script_document
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptSerializationRequest,
    SugarScriptSerializer,
)
from substitute.domain.workflow import CubeState, WorkflowState, final_active_cube_alias


def test_cube_output_mute_changes_persistence_only_and_round_trips_recipe() -> None:
    """Muting output saves should not bypass execution and must survive Sugar files."""

    workflow = WorkflowState(
        cubes={
            "First": _cube("First"),
            "Final": _cube("Final"),
        },
        stack_order=["First", "Final"],
    )
    service = CubeStackService()

    enabled = service.toggle_cube_output_persistence(workflow, "First")

    assert enabled is False
    assert workflow.cubes["First"].bypassed is False
    assert final_active_cube_alias(workflow) == "Final"
    buffers = strip_recipe_buffers(workflow.stack_order, workflow.cubes)
    script = SugarScriptSerializer().serialize(
        SugarScriptSerializationRequest(
            buffers=buffers,
            ordered_aliases=tuple(workflow.stack_order),
        )
    )
    parsed = parse_sugar_script_document(script)
    assert parsed.buffers["First"]["save_outputs"] is False
    assert parsed.buffers["Final"]["save_outputs"] is True


def test_final_active_cube_is_topological_and_skips_bypassed_tail() -> None:
    """Final-cube policy must never depend on output callback arrival order."""

    workflow = WorkflowState(
        cubes={
            "First": _cube("First"),
            "Final Active": _cube("Final Active"),
            "Bypassed Tail": _cube("Bypassed Tail", bypassed=True),
        },
        stack_order=["First", "Final Active", "Bypassed Tail"],
    )

    assert final_active_cube_alias(workflow) == "Final Active"


def _cube(alias: str, *, bypassed: bool = False) -> CubeState:
    """Return one minimal workflow cube state."""

    return CubeState(
        cube_id=f"cube-{alias}",
        version="1.0.0",
        alias=alias,
        original_cube={},
        buffer={},
        bypassed=bypassed,
    )
