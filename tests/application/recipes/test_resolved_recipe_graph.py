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

"""Verify resolved legacy model identity enters canonical graph authority."""

from __future__ import annotations

from collections import OrderedDict

from substitute.application.recipes.resolved_recipe_graph import (
    project_resolved_recipe_model_fields,
)
from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
    CanonicalCubeGraphAnalysis,
)
from substitute.domain.recipes import ParsedSugarScript


def test_resolved_model_filename_and_hash_are_projected_to_stable_graph_field() -> None:
    """Keep executable filename and portable identity together after legacy import."""

    analysis = _analysis("old-name.safetensors")
    parsed = _parsed("renamed/model.safetensors", "A" * 64)

    projected = project_resolved_recipe_model_fields(analysis, parsed)

    assert projected is not None
    assert _model_value(projected) == "renamed/model.safetensors"
    assert projected.workflow["links"] == []
    composition = projected.workflow["extra"]["sugarcubes_composition"]  # type: ignore[index]
    assert composition == {
        "schema_version": 1,
        "field_annotations": [
            {
                "annotation_id": "substitute.model_asset:instance-a:loader:ckpt_name",
                "namespace": "substitute.model_asset",
                "endpoint": {
                    "instance_id": "instance-a",
                    "node_symbol": "loader",
                    "input_name": "ckpt_name",
                },
                "payload": {"sha256": "A" * 64},
            }
        ],
    }
    assert _model_value(analysis) == "old-name.safetensors"


def _analysis(value: str) -> CanonicalCubeGraphAnalysis:
    """Build one graph-backed Cube analysis fixture with a model field."""

    document = {
        "cube_id": "owner/repo/model.cube",
        "version": "1.0.0",
        "implementation": {
            "nodes": {
                "loader": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": value},
                }
            },
            "inputs": {},
            "outputs": {},
        },
    }
    return CanonicalCubeGraphAnalysis(
        workflow_semantic_hash="before",
        instances=(
            AnalyzedCubeInstance(
                instance_id="instance-a",
                node_id="1",
                definition_id="definition-a",
                cube_id="owner/repo/model.cube",
                cube_version="1.0.0",
                alias="A",
                execution_mode=0,
            ),
        ),
        edges=(),
        proximity_edges=(),
        segments=(AnalyzedCubeSegment(("instance-a",), False, ()),),
        workflow={
            "version": 0.4,
            "nodes": [],
            "links": [],
            "definitions": {
                "subgraphs": [
                    {
                        "id": "definition-a",
                        "extra": {"sugarcubes_document": document},
                    }
                ]
            },
            "extra": {},
        },
    )


def _parsed(value: str, sha256: str) -> ParsedSugarScript:
    """Build one resolved parsed recipe fixture."""

    return ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "nodes": {
                            "loader": {
                                "class_type": "CheckpointLoaderSimple",
                                "inputs": {"ckpt_name": value},
                            }
                        }
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={("A", "loader", "ckpt_name"): sha256},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )


def _model_value(analysis: CanonicalCubeGraphAnalysis) -> object:
    """Read the embedded model field from one fixture analysis."""

    definitions = analysis.workflow["definitions"]
    assert isinstance(definitions, dict)
    subgraphs = definitions["subgraphs"]
    assert isinstance(subgraphs, list)
    definition = subgraphs[0]
    assert isinstance(definition, dict)
    extra = definition["extra"]
    assert isinstance(extra, dict)
    document = extra["sugarcubes_document"]
    assert isinstance(document, dict)
    implementation = document["implementation"]
    assert isinstance(implementation, dict)
    nodes = implementation["nodes"]
    assert isinstance(nodes, dict)
    loader = nodes["loader"]
    assert isinstance(loader, dict)
    inputs = loader["inputs"]
    assert isinstance(inputs, dict)
    return inputs["ckpt_name"]
