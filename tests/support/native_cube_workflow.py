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

"""Build complete structural Cube workflow fixtures for native generation tests."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from substitute.domain.workflow import CubeState, WorkflowState
from tests.support.canonical_cube_graph import graph_backed_cube_workflow_from_states


def native_cube_workflow_stub(
    *,
    alias: str = "Text",
    buffer: dict[str, object] | None = None,
    **workflow_values: object,
) -> WorkflowState:
    """Return a complete graph-backed workflow accepted by native generation."""

    cube_buffer = deepcopy(buffer or {"nodes": {}})
    cube_buffer.setdefault("inputs", {})
    cube_buffer.setdefault("outputs", {})
    cube_buffer.setdefault("layout", {})
    cube_buffer.setdefault("definitions", {})
    cube_buffer.setdefault("subgraphs", [])
    cube_buffer.setdefault(
        "surface",
        {"default_flavor_id": "default", "controls": []},
    )
    cube_buffer.setdefault(
        "flavors",
        {"authored": [{"id": "default", "name": "Default", "values": {}}]},
    )
    cube = CubeState(
        cube_id=f"test/{alias}.cube",
        version="1.0.0",
        alias=alias,
        original_cube={},
        buffer=cube_buffer,
        ui={"canonical_cube": {"description": "", "metadata": {}}},
        bypassed=False,
        output_persistence_enabled=True,
    )
    workflow = graph_backed_cube_workflow_from_states(cube)
    workflow.metadata.update(workflow_values)
    return workflow


def native_cube_workflow_input(
    workflow: dict[str, object],
    *,
    node_name: str,
    input_name: str,
) -> object:
    """Return one input from the first embedded native Cube document."""

    definitions = cast(dict[str, object], workflow["definitions"])
    subgraphs = cast(list[dict[str, object]], definitions["subgraphs"])
    extra = cast(dict[str, object], subgraphs[0]["extra"])
    document = cast(dict[str, object], extra["sugarcubes_document"])
    implementation = cast(dict[str, object], document["implementation"])
    nodes = cast(dict[str, dict[str, object]], implementation["nodes"])
    inputs = cast(dict[str, object], nodes[node_name]["inputs"])
    return inputs[input_name]


__all__ = ["native_cube_workflow_input", "native_cube_workflow_stub"]
