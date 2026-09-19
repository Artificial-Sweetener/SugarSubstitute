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

"""Verify direct workflow loading across ordinary and Cube-owned graph regions."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.domain.comfy_workflow import ComfyWorkflowConverter, DirectWorkflowState
from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
    CanonicalCubeGraphAnalysis,
)
from substitute.domain.common import JsonObject
from tests.support.passthrough_cube_analysis import PassthroughCubeWorkflowAnalyzer


class _Repository:
    """Return one in-memory workflow document."""

    def __init__(self, workflow: JsonObject) -> None:
        """Store the detached workflow fixture."""

        self._workflow = deepcopy(workflow)

    def can_load(self, _path: Path) -> bool:
        """Report the synthetic document as available."""

        return True

    def load(self, _path: Path) -> JsonObject:
        """Return a detached workflow document."""

        return deepcopy(self._workflow)


class _CubeAnalyzer:
    """Recognize the fixture node as one SugarCubes-owned graph region."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return one canonical Cube analysis without ordinary executable nodes."""

        return CanonicalCubeGraphAnalysis(
            workflow_semantic_hash="cube-only",
            instances=(
                AnalyzedCubeInstance(
                    instance_id="instance-1",
                    node_id="cube-1",
                    definition_id="definition-1",
                    cube_id="example/cube",
                    cube_version="1.0.0",
                    alias="Example",
                    execution_mode=0,
                ),
            ),
            edges=(),
            proximity_edges=(),
            segments=(
                AnalyzedCubeSegment(
                    instance_ids=("instance-1",),
                    reorderable=True,
                    boundary_node_ids=(),
                ),
            ),
            workflow=deepcopy(workflow),
        )


def test_load_accepts_cube_only_graph_without_ordinary_editor_nodes(
    tmp_path: Path,
) -> None:
    """A valid Cube graph should not require an unrelated ordinary-node buffer."""

    workflow: JsonObject = {
        "nodes": [
            {
                "id": "cube-1",
                "type": "definition-1",
                "inputs": [],
                "outputs": [],
            }
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "definition-1",
                    "nodes": [],
                    "links": [],
                    "inputs": [],
                    "outputs": [],
                }
            ]
        },
    }
    service = DirectWorkflowLoadService(_Repository(workflow), _CubeAnalyzer())

    document = service.load(tmp_path / "cube-only.json")

    assert document.buffer == {"nodes": {}}
    assert document.cube_analysis is not None
    assert document.cube_analysis.instances[0].alias == "Example"
    assert document.source_workflow == workflow


def test_direct_editor_value_updates_its_canonical_comfy_widget(tmp_path: Path) -> None:
    """An ordinary editor projection must never diverge from graph authority."""

    workflow: JsonObject = {
        "nodes": [
            {
                "id": 1,
                "type": "EmptyImage",
                "inputs": [
                    {
                        "name": "width",
                        "type": "INT",
                        "widget": {"name": "width"},
                        "link": None,
                    },
                    {
                        "name": "height",
                        "type": "INT",
                        "widget": {"name": "height"},
                        "link": None,
                    },
                    {
                        "name": "batch_size",
                        "type": "INT",
                        "widget": {"name": "batch_size"},
                        "link": None,
                    },
                ],
                "outputs": [],
                "widgets_values": [64, 48, 2],
            }
        ],
        "links": [],
    }
    service = DirectWorkflowLoadService(
        _Repository(workflow),
        PassthroughCubeWorkflowAnalyzer(),
    )
    document = service.load(tmp_path / "ordinary.json")

    changed = document.set_editor_value(
        "1",
        field_key="batch_size",
        value=3,
    )

    assert changed is True
    assert document.buffer["nodes"]["1"]["inputs"]["batch_size"] == 3  # type: ignore[index]
    assert document.source_workflow["nodes"][0]["widgets_values"] == [64, 48, 3]  # type: ignore[index]


def test_direct_editor_value_preserves_numeric_control_companion() -> None:
    """Write the named numeric field without mistaking Comfy's control for it."""

    workflow: JsonObject = {
        "nodes": [
            {
                "id": 2,
                "type": "KSampler",
                "inputs": [
                    {
                        "name": "seed",
                        "type": "INT",
                        "widget": {"name": "seed"},
                        "link": None,
                    },
                    {
                        "name": "steps",
                        "type": "INT",
                        "widget": {"name": "steps"},
                        "link": None,
                    },
                ],
                "outputs": [],
                "widgets_values": [123, "randomize", 20],
            }
        ],
        "links": [],
    }
    node_definitions = {
        "KSampler": {
            "input": {
                "required": {
                    "seed": ["INT", {"control_after_generate": True}],
                    "steps": ["INT", {}],
                }
            }
        }
    }
    buffer = ComfyWorkflowConverter().convert(
        workflow,
        node_definitions=node_definitions,
    )
    document = DirectWorkflowState(
        source_path=Path("numeric.json"),
        source_workflow=workflow,
        buffer=buffer,
    )

    assert document.set_editor_value("2", field_key="steps", value=33) is True

    assert document.source_workflow["nodes"][0]["widgets_values"] == [  # type: ignore[index]
        123,
        "randomize",
        33,
    ]


def test_direct_editor_value_writes_through_subgraph_proxy() -> None:
    """Keep an editable flattened value anchored to its outer proxy widget."""

    subgraph_id = "31d70bc1-12a1-4af4-8a84-c335621fe232"
    workflow: JsonObject = {
        "nodes": [
            {
                "id": 7,
                "type": subgraph_id,
                "title": "Text to Image",
                "inputs": [],
                "outputs": [],
                "widgets_values": ["outer prompt"],
                "properties": {"proxyWidgets": [["12", "text"]]},
            }
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": subgraph_id,
                    "nodes": [
                        {
                            "id": 12,
                            "type": "CLIPTextEncode",
                            "inputs": [
                                {
                                    "name": "text",
                                    "type": "STRING",
                                    "widget": {"name": "text"},
                                    "link": None,
                                }
                            ],
                            "outputs": [],
                            "widgets_values": ["internal prompt"],
                        }
                    ],
                    "links": [],
                    "inputs": [],
                    "outputs": [],
                }
            ]
        },
    }
    buffer = ComfyWorkflowConverter().convert(workflow)
    document = DirectWorkflowState(
        source_path=Path("subgraph.json"),
        source_workflow=workflow,
        buffer=buffer,
    )

    assert (
        document.set_editor_value(
            "7:12",
            field_key="text",
            value="edited prompt",
        )
        is True
    )

    assert document.source_workflow["nodes"][0]["widgets_values"] == [  # type: ignore[index]
        "edited prompt"
    ]
