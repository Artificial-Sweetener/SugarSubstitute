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

"""Contract tests for cube stack alias orchestration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.application.cubes import CubeStackService
from substitute.domain.comfy_workflow.models import DirectWorkflowState
from substitute.domain.comfy_workflow.cube_analysis import CubeGraphEdgeOrigin
from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowState
from tests.support.canonical_cube_graph import graph_backed_cube_workflow
from tests.application.cubes.cube_stack.graph_backed_support import (
    _GraphGateway,
    _InvalidAnalysisGateway,
    _StructuralGraphGateway,
    _cube_state,
    _graph_stack_service,
)


def test_apply_cube_rename_resolves_collisions_and_updates_workflow_state() -> None:
    """Rename application should return the resolved alias and keep workflow state aligned."""
    old_cube_state = SimpleNamespace(alias="Old")
    taken_cube_state = SimpleNamespace(alias="Taken")
    canvas_renames: list[tuple[str, str]] = []
    service = CubeStackService()
    workflow = SimpleNamespace(
        cubes={"Old": old_cube_state, "Taken": taken_cube_state},
        stack_order=["Old", "Taken"],
        canvas=SimpleNamespace(
            rename_section=lambda old_alias, new_alias: canvas_renames.append(
                (old_alias, new_alias)
            )
        ),
    )

    resolution = service.apply_cube_rename(workflow, "Old", "Taken")

    assert resolution.old_alias == "Old"
    assert resolution.requested_alias == "Taken"
    assert resolution.resolved_alias == "Taken 2"
    assert workflow.cubes["Taken 2"] is old_cube_state
    assert old_cube_state.alias == "Taken 2"
    assert workflow.stack_order == ["Taken 2", "Taken"]
    assert canvas_renames == [("Old", "Taken 2")]


def test_resolve_cube_rename_excludes_current_alias_from_collision_check() -> None:
    """Rename planning should allow keeping a cube's current visible alias."""
    service = CubeStackService()
    workflow = SimpleNamespace(
        cubes={
            "Shared": SimpleNamespace(cube_id="cube_a"),
            "Shared 2": SimpleNamespace(cube_id="cube_b"),
        },
        stack_order=["Shared", "Shared 2"],
    )

    resolution = service.resolve_cube_rename(workflow, "Shared 2", "Shared 2")

    assert resolution.resolved_alias == "Shared 2"


def test_apply_cube_addition_targets_only_passed_workflow() -> None:
    """Cube addition should mutate only the explicitly supplied workflow."""

    service = CubeStackService()
    workflow_a = SimpleNamespace(cubes={}, stack_order=[])
    workflow_b = SimpleNamespace(cubes={}, stack_order=[])
    cube_state = SimpleNamespace(cube_id="cube_a", alias="Alias")

    service.apply_cube_addition(workflow_a, "cube_a", "Alias", cube_state)

    assert workflow_a.cubes == {"Alias": cube_state}
    assert workflow_a.stack_order == ["Alias"]
    assert workflow_b.cubes == {}
    assert workflow_b.stack_order == []


def test_set_cube_bypassed_updates_only_target_cube() -> None:
    """Bypass mutation should not alter stack order or neighboring cubes."""

    service = CubeStackService()
    target = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=False)
    neighbor = SimpleNamespace(cube_id="cube_b", alias="B", bypassed=False)
    workflow = SimpleNamespace(
        cubes={"A": target, "B": neighbor},
        stack_order=["A", "B"],
    )

    changed = service.set_cube_bypassed(workflow, "A", True)

    assert changed is True
    assert target.bypassed is True
    assert neighbor.bypassed is False
    assert workflow.stack_order == ["A", "B"]


def test_set_cube_bypassed_noops_when_value_is_unchanged() -> None:
    """Setting the current bypass value should report no mutation."""

    service = CubeStackService()
    cube_state = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=True)
    workflow = SimpleNamespace(cubes={"A": cube_state}, stack_order=["A"])

    changed = service.set_cube_bypassed(workflow, "A", True)

    assert changed is False
    assert cube_state.bypassed is True


def test_toggle_cube_bypassed_returns_new_value() -> None:
    """Toggle should flip the target cube and return the resulting state."""

    service = CubeStackService()
    cube_state = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=False)
    workflow = SimpleNamespace(cubes={"A": cube_state}, stack_order=["A"])

    first = service.toggle_cube_bypassed(workflow, "A")
    second = service.toggle_cube_bypassed(workflow, "A")

    assert first is True
    assert second is False
    assert cube_state.bypassed is False


def test_cube_bypass_mutation_ignores_missing_alias() -> None:
    """Missing aliases should not create cube state or disturb ordering."""

    service = CubeStackService()
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    changed = service.set_cube_bypassed(workflow, "Missing", True)
    toggled = service.toggle_cube_bypassed(workflow, "Missing")

    assert changed is False
    assert toggled is False
    assert workflow.cubes == {}
    assert workflow.stack_order == []


def test_graph_backed_reorder_applies_cached_sugarcubes_plan_without_network() -> None:
    """Stack order changes must not call the target during an interactive drag."""

    workflow = graph_backed_cube_workflow("First", "Second", "Third")
    assert workflow.direct_workflow is not None
    graph = workflow.direct_workflow.source_workflow
    nodes = graph["nodes"]
    assert isinstance(nodes, list)
    for index, node in enumerate(nodes):
        assert isinstance(node, dict)
        node["pos"] = [index * 344, 0]
        node["size"] = [320, 200]
    graph["links"] = []
    analysis = workflow.direct_workflow.cube_analysis
    assert analysis is not None
    proximity_edges = tuple(
        replace(edge, origin=CubeGraphEdgeOrigin.PROXIMITY) for edge in analysis.edges
    )
    workflow.direct_workflow.cube_analysis = replace(
        analysis,
        edges=proximity_edges,
        proximity_edges=proximity_edges,
        workflow=deepcopy(graph),
    )

    first_state = workflow.cubes["First"]
    first_state.undo_stack.append({"nodes": {"before": {}}})

    gateway = _GraphGateway(workflow)
    _graph_stack_service(gateway).apply_reordered_aliases(
        workflow,
        ["Third", "First", "Second"],
    )

    assert workflow.stack_order == ["Third", "First", "Second"]
    assert workflow.direct_workflow.source_workflow["links"] == []
    assert gateway.reorder_requests == []
    assert workflow.direct_workflow.dirty is True
    assert workflow.cubes["First"] is first_state
    assert workflow.cubes["First"].undo_stack == [{"nodes": {"before": {}}}]


def test_graph_backed_reorder_rejects_crossing_graph_boundaries() -> None:
    """A Cube may not move across an ordinary Comfy region."""

    workflow = graph_backed_cube_workflow("First", "Second")
    assert workflow.direct_workflow is not None
    graph = workflow.direct_workflow.source_workflow
    nodes = graph["nodes"]
    assert isinstance(nodes, list)
    nodes.insert(
        1,
        {
            "id": "ordinary",
            "type": "Ordinary",
            "inputs": [{"name": "input", "type": "*"}],
            "outputs": [{"name": "output", "type": "*"}],
            "properties": {},
        },
    )
    graph["links"] = [
        [1, 1, 0, "ordinary", 0, "*"],
        [2, "ordinary", 0, 2, 0, "*"],
    ]
    assert workflow.direct_workflow.cube_analysis is not None
    fixed = replace(
        workflow.direct_workflow.cube_analysis.segments[0],
        reorderable=False,
        boundary_node_ids=("ordinary",),
    )
    workflow.direct_workflow.cube_analysis = replace(
        workflow.direct_workflow.cube_analysis,
        segments=(fixed,),
    )
    workflow.refresh_direct_cube_projection()

    with pytest.raises(ValueError, match="boundary|Fixed"):
        _graph_stack_service(_GraphGateway(workflow)).apply_reordered_aliases(
            workflow, ["Second", "First"]
        )

    assert workflow.stack_order == ["First", "Second"]


def test_graph_backed_bypass_updates_authoritative_comfy_node_mode() -> None:
    """Bypass toggles must persist in the graph and survive projection refresh."""

    workflow = graph_backed_cube_workflow("First", "Second")
    first_state = workflow.cubes["First"]

    changed = _graph_stack_service(_GraphGateway(workflow)).set_cube_bypassed(
        workflow, "First", True
    )

    assert changed is True
    assert workflow.cubes["First"] is first_state
    assert workflow.cubes["First"].bypassed is True
    assert workflow.direct_workflow is not None
    nodes = workflow.direct_workflow.source_workflow["nodes"]
    assert isinstance(nodes, list)
    assert isinstance(nodes[0], dict)
    assert nodes[0]["mode"] == 4


def test_graph_backed_mutation_rejects_invalid_response_atomically() -> None:
    """A malformed canonical response must not partially replace mounted state."""

    workflow = graph_backed_cube_workflow("First", "Second")
    original_direct = workflow.direct_workflow
    original_cubes = dict(workflow.cubes)
    original_order = list(workflow.stack_order)

    with pytest.raises(ValueError, match="no embedded document"):
        _graph_stack_service(_InvalidAnalysisGateway(workflow)).set_cube_bypassed(
            workflow, "First", True
        )

    assert workflow.direct_workflow is original_direct
    assert workflow.cubes == original_cubes
    assert workflow.stack_order == original_order
    assert workflow.cubes["First"] is original_cubes["First"]
    assert workflow.cubes["First"].bypassed is False


def test_graph_backed_rename_updates_canonical_instance_alias() -> None:
    """Renaming a projected Cube must rename its graph identity and preserve state."""

    workflow = graph_backed_cube_workflow("First", "Second")
    first_state = workflow.cubes["First"]

    result = _graph_stack_service(_GraphGateway(workflow)).apply_cube_rename(
        workflow, "First", "Renamed"
    )

    assert result.resolved_alias == "Renamed"
    assert workflow.stack_order == ["Renamed", "Second"]
    assert workflow.cubes["Renamed"] is first_state
    assert workflow.direct_workflow is not None
    nodes = workflow.direct_workflow.source_workflow["nodes"]
    assert isinstance(nodes, list) and isinstance(nodes[0], dict)
    properties = nodes[0]["properties"]
    assert isinstance(properties, dict)
    marker = properties["sugarcubes_cube"]
    assert isinstance(marker, dict)
    assert marker["instance_alias"] == "Renamed"


def test_first_cube_addition_establishes_native_graph_authority() -> None:
    """A newly created stack must become graph-backed with its first Cube."""

    workflow = WorkflowState()
    gateway = _StructuralGraphGateway()
    cube = _cube_state("First")

    _graph_stack_service(gateway).apply_cube_addition(
        workflow,
        cube.cube_id,
        cube.alias,
        cube,
    )

    assert workflow.is_graph_backed_cube_workflow is True
    assert workflow.stack_order == ["First"]
    assert workflow.cubes["First"] is cube
    assert workflow.direct_workflow is not None
    assert workflow.direct_workflow.source_workflow["links"] == []
    assert gateway.analyzed_workflows == 1


def test_later_cube_addition_preserves_loaded_presentation_state() -> None:
    """Every appended Cube must retain the complete loaded presentation state."""

    workflow = WorkflowState()
    gateway = _StructuralGraphGateway()
    first = _cube_state("First")
    second = _cube_state("Second")
    second.display_name = "Diffusion Upscale"
    second.ui = {
        "cube_icon": {"kind": "image", "path": "icons/upscale.png"},
        "canonical_cube": {
            **second.original_cube,
            "metadata": {"target_model": "Anima"},
        },
        "content_hash": "second-content",
        "catalog_revision": "base-cubes-42",
        "source": {"kind": "pack", "pack_id": "base-cubes"},
    }

    service = _graph_stack_service(gateway)
    service.apply_cube_addition(workflow, first.cube_id, first.alias, first)
    service.apply_cube_addition(workflow, second.cube_id, second.alias, second)

    restored = workflow.cubes["Second"]
    assert restored is second
    assert restored.display_name == "Diffusion Upscale"
    assert restored.ui is not None
    assert restored.ui["cube_icon"] == {
        "kind": "image",
        "path": "icons/upscale.png",
    }
    assert restored.ui["content_hash"] == "second-content"
    assert restored.ui["catalog_revision"] == "base-cubes-42"
    assert restored.ui["source"] == {"kind": "pack", "pack_id": "base-cubes"}
    canonical = restored.ui["canonical_cube"]
    assert isinstance(canonical, dict)
    assert canonical["metadata"] == {"target_model": "Anima"}


def test_cube_addition_preserves_opaque_direct_graph_region() -> None:
    """Appending a Cube must leave an ordinary Comfy region untouched."""

    ordinary_graph: JsonObject = {
        "version": 0.4,
        "nodes": [
            {
                "id": "ordinary",
                "type": "VendorNode",
                "properties": {"vendor": {"opaque": True}},
            }
        ],
        "links": [[7, "external-a", 0, "ordinary", 0, "VENDOR"]],
        "definitions": {"subgraphs": []},
        "extra": {"vendor": [1, 2, 3]},
    }
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("ordinary.json"),
            source_workflow=deepcopy(ordinary_graph),
            buffer={"nodes": {}},
            cube_analysis=_StructuralGraphGateway().analyze(ordinary_graph),
        )
    )
    gateway = _StructuralGraphGateway()
    cube = _cube_state("Added")

    _graph_stack_service(gateway).apply_cube_addition(
        workflow,
        cube.cube_id,
        cube.alias,
        cube,
    )

    assert workflow.direct_workflow is not None
    graph = workflow.direct_workflow.source_workflow
    graph_nodes = graph["nodes"]
    ordinary_nodes = ordinary_graph["nodes"]
    assert isinstance(graph_nodes, list) and isinstance(ordinary_nodes, list)
    assert graph_nodes[0] == ordinary_nodes[0]
    assert graph["links"] == ordinary_graph["links"]
    assert graph["extra"] == ordinary_graph["extra"]
    assert workflow.stack_order == ["Added"]


def test_removing_last_cube_restores_no_cube_direct_graph_projection() -> None:
    """A mixed graph without remaining Cubes must expose no Cube stack."""

    ordinary_graph: JsonObject = {
        "version": 0.4,
        "nodes": [{"id": "ordinary", "type": "VendorNode", "properties": {}}],
        "links": [],
        "definitions": {"subgraphs": []},
    }
    gateway = _StructuralGraphGateway()
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("ordinary.json"),
            source_workflow=deepcopy(ordinary_graph),
            buffer={"nodes": {}},
            cube_analysis=gateway.analyze(ordinary_graph),
        )
    )
    cube = _cube_state("Temporary")
    service = _graph_stack_service(gateway)
    service.apply_cube_addition(
        workflow,
        cube.cube_id,
        cube.alias,
        cube,
    )

    service.apply_cube_removal(workflow, "Temporary")

    assert workflow.is_direct_workflow is True
    assert workflow.cubes == {}
    assert workflow.stack_order == []
    assert workflow.direct_workflow is not None
    assert workflow.direct_workflow.source_workflow == ordinary_graph
