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

"""Verify listener preview routing through CubeOutput workflow relationships."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.preview_contract_harness import (
    _binary_metadata_preview_image_message,
    _run_preview_messages,
)


def test_run_maps_preview_source_to_downstream_cube_output(
    monkeypatch: MonkeyPatch,
) -> None:
    """Group a preview under its sole downstream CubeOutput source."""

    workflow: JsonObject = {
        "sampler-node": {
            "class_type": "KSampler",
            "_meta": {"title": "Sampler.KSampler"},
        },
        "output-node": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "CubeA.CubeOutput"},
            "inputs": {"value": ["sampler-node", 0]},
        },
    }
    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "sampler-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={"node_id": "sampler-node", "prompt_id": "pid-1"},
                source_key="wf-1:output-node",
                source_label="CubeA",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload=workflow,
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].node_id == "sampler-node"
    assert preview_events[0].source_key == "wf-1:output-node"
    assert preview_events[0].source_label == "CubeA"


def test_run_maps_preview_source_to_nearest_downstream_cube_output(
    monkeypatch: MonkeyPatch,
) -> None:
    """Choose the closest CubeOutput when a preview has multiple descendants."""

    workflow: JsonObject = {
        "sampler-node": {
            "class_type": "KSampler",
            "_meta": {"title": "Sampler.KSampler"},
        },
        "near-output": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "Text to Image.CubeOutput"},
            "inputs": {"value": ["sampler-node", 0]},
        },
        "upscale-node": {
            "class_type": "KSampler",
            "inputs": {"image": ["sampler-node", 0]},
        },
        "far-output": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "Diffusion Upscale.CubeOutput"},
            "inputs": {"value": ["upscale-node", 0]},
        },
    }
    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "sampler-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={"node_id": "sampler-node", "prompt_id": "pid-1"},
                source_key="wf-1:near-output",
                source_label="Text to Image",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload=workflow,
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "sampler-node"
    assert preview_events[0].source_key == "wf-1:near-output"
    assert preview_events[0].source_label == "Text to Image"


def test_run_uses_node_source_when_preview_maps_to_multiple_cube_outputs(
    monkeypatch: MonkeyPatch,
) -> None:
    """Keep the executing node source when equally close outputs are ambiguous."""

    workflow: JsonObject = {
        "shared-node": {
            "class_type": "KSampler",
            "_meta": {"title": "Shared.KSampler"},
        },
        "output-a": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["shared-node", 0]},
        },
        "output-b": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["shared-node", 0]},
        },
    }
    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "shared-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={"node_id": "shared-node", "prompt_id": "pid-1"},
                source_label="Shared",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload=workflow,
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "shared-node"
    assert preview_events[0].source_key == "wf-1:shared-node"
    assert preview_events[0].source_label == "Shared"
