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
