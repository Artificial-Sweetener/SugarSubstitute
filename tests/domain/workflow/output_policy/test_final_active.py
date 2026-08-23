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

"""Protect topological selection of the workflow's final active cube."""

from __future__ import annotations

from substitute.domain.workflow import CubeState, WorkflowState, final_active_cube_alias


def test_final_active_cube_is_topological_and_skips_bypassed_tail() -> None:
    """Final-cube policy must never depend on output callback arrival order."""

    workflow = WorkflowState(
        cubes={
            "First": cube("First"),
            "Final Active": cube("Final Active"),
            "Bypassed Tail": cube("Bypassed Tail", bypassed=True),
        },
        stack_order=["First", "Final Active", "Bypassed Tail"],
    )

    assert final_active_cube_alias(workflow) == "Final Active"


def cube(alias: str, *, bypassed: bool = False) -> CubeState:
    """Build one minimal workflow cube state."""

    return CubeState(
        cube_id=f"cube-{alias}",
        version="1.0.0",
        alias=alias,
        original_cube={},
        buffer={},
        bypassed=bypassed,
    )
