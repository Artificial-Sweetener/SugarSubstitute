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

"""Verify generation visual routing uses durable cube source identities."""

from __future__ import annotations

from substitute.application.generation.visual_run_context_builder import (
    VisualRunContextBuilder,
)
from substitute.domain.common import WorkflowId


def test_cube_visual_source_key_survives_compiled_node_id_changes() -> None:
    """Use the cube alias for preview and final routing across recompilations."""

    builder = VisualRunContextBuilder()
    first = builder.build(
        workflow_payload=_cube_payload(sampler_id="11", output_id="12"),
        workflow_id=WorkflowId("workflow-old"),
        generation_run_id="run-old",
        client_id="client-old",
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )
    second = builder.build(
        workflow_payload=_cube_payload(sampler_id="31", output_id="32"),
        workflow_id=WorkflowId("workflow-new"),
        generation_run_id="run-new",
        client_id="client-new",
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )

    assert {source["sourceKey"] for source in first.sources.values()} == {
        "cube:Text to Image"
    }
    assert {source["sourceKey"] for source in second.sources.values()} == {
        "cube:Text to Image"
    }


def test_chained_cube_nodes_use_their_nearest_output_source() -> None:
    """Route each stage preview to its nearest downstream CubeOutput tab."""

    context = VisualRunContextBuilder().build(
        workflow_payload=_chained_cube_payload(),
        workflow_id=WorkflowId("workflow"),
        generation_run_id="run",
        client_id="client",
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )

    assert {
        node_id: context.sources[node_id]["sourceKey"]
        for node_id in ("9", "11", "25", "32")
    } == {
        "9": "cube:Text to Image",
        "11": "cube:Diffusion Upscale",
        "25": "cube:Automask Detailer",
        "32": "cube:Automask Detailer 2",
    }


def _cube_payload(*, sampler_id: str, output_id: str) -> dict[str, object]:
    """Return one compiled cube whose executable ids may change per run."""

    return {
        sampler_id: {
            "class_type": "KSampler",
            "inputs": {},
            "_meta": {"title": "Text to Image.KSampler"},
        },
        output_id: {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"images": [sampler_id, 0]},
            "_meta": {"title": "Text to Image.Output"},
        },
    }


def _chained_cube_payload() -> dict[str, object]:
    """Return four sequential cubes whose early nodes reach every later output."""

    payload: dict[str, object] = {}
    previous_output_id: str | None = None
    for sampler_id, output_id, label in (
        ("9", "8", "Text to Image"),
        ("11", "17", "Diffusion Upscale"),
        ("25", "29", "Automask Detailer"),
        ("32", "36", "Automask Detailer 2"),
    ):
        sampler_inputs = (
            {} if previous_output_id is None else {"image": [previous_output_id, 0]}
        )
        payload[sampler_id] = {
            "class_type": "KSampler",
            "inputs": sampler_inputs,
            "_meta": {"title": f"{label}.KSampler"},
        }
        payload[output_id] = {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"images": [sampler_id, 0]},
            "_meta": {"title": f"{label}.Output"},
        }
        previous_output_id = output_id
    return payload
