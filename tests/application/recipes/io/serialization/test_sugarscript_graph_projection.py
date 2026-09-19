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

"""Verify SugarScript saves only losslessly representable Cube graph semantics."""

from __future__ import annotations

from dataclasses import replace

import pytest

from substitute.application.recipes.sugarscript_graph_projection import (
    explicit_sugarscript_connections,
)
from substitute.domain.comfy_workflow.cube_analysis import CubeGraphEdgeOrigin
from substitute.domain.recipes import SugarScriptCubeConnection
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def test_projects_only_sugarcubes_reported_explicit_edges() -> None:
    """Persist manual Cube wiring while leaving proximity implicit."""

    workflow = graph_backed_cube_workflow("First", "Second", "Third")
    direct = workflow.direct_workflow
    assert direct is not None and direct.cube_analysis is not None
    edges = direct.cube_analysis.edges
    direct.cube_analysis = replace(
        direct.cube_analysis,
        edges=(edges[0], replace(edges[1], origin=CubeGraphEdgeOrigin.PROXIMITY)),
    )

    result = explicit_sugarscript_connections(direct)

    assert result == (
        SugarScriptCubeConnection(
            source_alias="First",
            source_binding="output",
            target_alias="Second",
            target_binding="input",
        ),
    )


def test_rejects_sugarscript_conversion_of_non_cube_graph_segments() -> None:
    """Keep a mixed workflow native instead of silently dropping ordinary nodes."""

    workflow = graph_backed_cube_workflow("Cube")
    direct = workflow.direct_workflow
    assert direct is not None
    nodes = direct.source_workflow["nodes"]
    assert isinstance(nodes, list)
    nodes.append({"id": "ordinary", "type": "VendorNode", "properties": {}})

    with pytest.raises(ValueError, match="non-Cube graph segments"):
        explicit_sugarscript_connections(direct)


def test_legacy_stack_requires_no_explicit_connections() -> None:
    """Let SugarCubes reconstruct a legacy linear stack from declaration order."""

    assert explicit_sugarscript_connections(None) == ()
