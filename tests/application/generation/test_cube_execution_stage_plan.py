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

"""Verify graph-backed Cube execution follows authored stack order."""

from __future__ import annotations

from dataclasses import replace

import pytest

from substitute.application.generation.cube_execution_stage_plan import (
    cube_execution_stage_ids,
    cube_execution_stages,
)
from substitute.domain.comfy_workflow.cube_analysis import AnalyzedCubeSegment

from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def test_disconnected_cubes_follow_visible_order_not_instance_id() -> None:
    """Freeze the order even when the later Cube's identity sorts first."""

    workflow = graph_backed_cube_workflow("z-image", "a-video")
    document = workflow.direct_workflow
    assert document is not None
    analysis = document.cube_analysis
    assert analysis is not None
    document.cube_analysis = replace(analysis, edges=())

    assert cube_execution_stage_ids(workflow) == ("z-image", "a-video")
    assert cube_execution_stages(workflow) == (("z-image",), ("a-video",))


def test_connected_cubes_remain_one_execution_stage() -> None:
    """Existing graph dependencies execute together without replaying producers."""

    workflow = graph_backed_cube_workflow("First", "Second")
    assert cube_execution_stages(workflow) == (("First", "Second"),)


def test_execution_order_rejects_dependency_against_visible_order() -> None:
    """Reject an impossible schedule instead of silently running out of order."""

    workflow = graph_backed_cube_workflow("First", "Second")
    document = workflow.direct_workflow
    assert document is not None
    analysis = document.cube_analysis
    assert analysis is not None
    document.cube_analysis = replace(
        analysis,
        segments=(
            AnalyzedCubeSegment(
                instance_ids=("Second", "First"),
                reorderable=False,
                boundary_node_ids=(),
            ),
        ),
    )
    workflow.stack_order = ["Second", "First"]

    with pytest.raises(ValueError, match="graph dependencies"):
        cube_execution_stage_ids(workflow)


def test_execution_order_requires_complete_analysis() -> None:
    """Do not guess the run order when a Cube is absent from analysis."""

    workflow = graph_backed_cube_workflow("First", "Second")
    document = workflow.direct_workflow
    assert document is not None
    analysis = document.cube_analysis
    assert analysis is not None
    document.cube_analysis = replace(
        analysis,
        segments=(
            AnalyzedCubeSegment(
                instance_ids=("First",),
                reorderable=False,
                boundary_node_ids=(),
            ),
        ),
    )

    with pytest.raises(ValueError, match="does not cover"):
        cube_execution_stage_ids(workflow)
