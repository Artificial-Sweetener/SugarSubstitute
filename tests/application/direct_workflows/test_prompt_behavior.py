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

"""Verify prompt behavior derived from converted direct workflows."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.node_behavior import CardMode, FieldPresentation, PromptRole
from substitute.domain.comfy_workflow import ComfyWorkflowConverter, DirectWorkflowState
from tests.support.node_behavior import build_behavior_snapshot


def test_direct_workflow_prompt_detection_uses_upstream_primitive_owner() -> None:
    """Resolve prompt behavior through a converted upstream value proxy."""
    definitions: dict[str, Mapping[str, object]] = {
        "ThirdPartyTextEncoder": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            },
            "output": ["CONDITIONING"],
        },
        "ThirdPartySampler": {
            "input": {
                "required": {
                    "positive": ["CONDITIONING", {}],
                }
            }
        },
    }
    workflow = {
        "nodes": [
            {
                "id": 45,
                "type": "PrimitiveNode",
                "title": "Text",
                "inputs": [],
                "outputs": [
                    {
                        "name": "STRING",
                        "type": "STRING",
                        "widget": {"name": "text"},
                        "links": [1],
                    }
                ],
                "widgets_values": ["a lighthouse"],
            },
            {
                "id": 2,
                "type": "ThirdPartyTextEncoder",
                "inputs": [{"name": "text", "type": "STRING", "link": 1}],
                "outputs": [
                    {
                        "name": "CONDITIONING",
                        "type": "CONDITIONING",
                        "links": [2],
                    }
                ],
                "widgets_values": [],
            },
            {
                "id": 3,
                "type": "ThirdPartySampler",
                "inputs": [{"name": "positive", "type": "CONDITIONING", "link": 2}],
                "outputs": [],
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 45, 0, 2, 0, "STRING"],
            [2, 2, 0, 3, 0, "CONDITIONING"],
        ],
    }
    graph = ComfyWorkflowConverter().convert(workflow, node_definitions=definitions)
    state = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow=workflow,
        buffer=graph,
    )

    snapshot = build_behavior_snapshot(
        cube_states={"direct": state},
        stack_order=["direct"],
        definitions_by_class=definitions,
    )

    primitive = snapshot.resolved_nodes_by_alias["direct"]["45"]
    assert primitive.card.card_mode == CardMode.PROMPT
    assert primitive.fields["text"].presentation == FieldPresentation.PROMPT_BOX
    assert primitive.fields["text"].prompt is not None
    assert primitive.fields["text"].prompt.role == PromptRole.POSITIVE
