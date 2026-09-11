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

"""Verify editor projection for cube and direct workflow documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.workflows import (
    DIRECT_WORKFLOW_SECTION_KEY,
    WorkflowEditorProjectionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import CubeState, WorkflowDocumentKind, WorkflowState
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def test_workflow_document_kind_identifies_mutually_exclusive_authoring_model() -> None:
    """Workflow state should expose one typed source for document capabilities."""

    direct = DirectWorkflowState(
        source_path=Path("demo.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={"nodes": {}},
    )

    assert WorkflowState().document_kind is WorkflowDocumentKind.CUBE_STACK
    assert (
        WorkflowState(direct_workflow=direct).document_kind
        is WorkflowDocumentKind.DIRECT_COMFY
    )


def test_direct_workflow_projects_as_one_shared_editor_section() -> None:
    """A complete graph should enter the existing editor as one document section."""

    direct = DirectWorkflowState(
        source_path=Path("demo.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={"nodes": {"1": {"class_type": "KSampler", "inputs": {}}}},
    )
    projection = WorkflowEditorProjectionService().project(
        WorkflowState(direct_workflow=direct)
    )

    assert projection.order == (DIRECT_WORKFLOW_SECTION_KEY,)
    assert projection.states == {DIRECT_WORKFLOW_SECTION_KEY: direct}
    assert projection.entries == ((DIRECT_WORKFLOW_SECTION_KEY, direct),)


def test_cube_workflow_projection_preserves_existing_section_order() -> None:
    """The shared abstraction should retain normal cube-stack projection behavior."""

    first = _cube("A")
    second = _cube("B")
    projection = WorkflowEditorProjectionService().project(
        WorkflowState(cubes={"A": first, "B": second}, stack_order=["B", "A"])
    )

    assert projection.order == ("B", "A")
    assert projection.entries == (("B", second), ("A", first))


def test_graph_backed_cube_workflow_projects_embedded_cube_sections() -> None:
    """Canonical Cube nodes should use the existing stack editor without losing graph ownership."""

    workflow = graph_backed_cube_workflow("First", "Second")

    projection = WorkflowEditorProjectionService().project(workflow)

    assert workflow.document_kind is WorkflowDocumentKind.COMFY_CUBE_GRAPH
    assert projection.order == ("First", "Second")
    assert tuple(projection.states) == ("First", "Second")
    ui = workflow.cubes["First"].ui
    assert isinstance(ui, dict)
    document = ui["canonical_cube"]
    assert isinstance(document, dict)
    assert workflow.cubes["First"].original_cube is document
    assert workflow.cubes["First"].buffer is document["implementation"]


def test_graph_backed_field_edit_mutates_only_the_canonical_graph_value() -> None:
    """Write editor values directly into the embedded graph document."""

    workflow = graph_backed_cube_workflow("First")
    direct = workflow.direct_workflow
    assert direct is not None
    definitions = direct.source_workflow.get("definitions")
    assert isinstance(definitions, dict)
    subgraphs = definitions.get("subgraphs")
    assert isinstance(subgraphs, list)
    definition = subgraphs[0]
    assert isinstance(definition, dict)
    extra = definition.get("extra")
    assert isinstance(extra, dict)
    document = extra.get("sugarcubes_document")
    assert isinstance(document, dict)
    implementation = document.get("implementation")
    assert isinstance(implementation, dict)
    implementation["nodes"] = {
        "sampler": {"class_type": "Sampler", "inputs": {"batch_size": 1}}
    }
    workflow.refresh_direct_cube_projection()

    result = WorkflowGraphSectionService().set_input_value(
        workflow,
        section_key="First",
        node_name="sampler",
        field_key="batch_size",
        value=2,
    )

    assert result.changed is True
    assert workflow.cubes["First"].buffer is implementation
    nodes = implementation.get("nodes")
    assert isinstance(nodes, dict)
    sampler = nodes.get("sampler")
    assert isinstance(sampler, dict)
    assert sampler["inputs"] == {"batch_size": 2}


def test_direct_projection_rejects_malformed_mixed_document() -> None:
    """Projection should fail closed even if an external object violates the invariant."""

    direct = DirectWorkflowState(
        source_path=Path("demo.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={"nodes": {"1": {"class_type": "KSampler", "inputs": {}}}},
    )

    with pytest.raises(ValueError, match="cannot be mixed"):
        WorkflowEditorProjectionService().project(
            type(
                "MalformedWorkflow",
                (),
                {
                    "direct_workflow": direct,
                    "cubes": {"A": _cube("A")},
                    "stack_order": ["A"],
                },
            )()
        )


def _cube(alias: str) -> CubeState:
    """Return one minimal cube state for projection checks."""

    return CubeState(
        cube_id=f"owner/repo/{alias}.cube",
        version="1.0.0",
        alias=alias,
        original_cube={},
        buffer={"nodes": {}},
    )
