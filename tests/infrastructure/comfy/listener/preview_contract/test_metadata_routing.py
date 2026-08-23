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

"""Verify listener metadata preview identity and source-label projection."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.preview_contract_harness import (
    _binary_metadata_preview_image_message,
    _run_preview_messages,
)


def test_run_emits_preview_with_source_metadata(monkeypatch: MonkeyPatch) -> None:
    """Publish the executing preview node's normalized source identity."""

    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "preview-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={"node_id": "preview-node", "prompt_id": "pid-1"},
                source_label="CubeA",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload={
            "preview-node": {
                "class_type": "KSampler",
                "_meta": {"title": "CubeA.KSampler"},
            }
        },
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].node_id == "preview-node"
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "CubeA"


def test_run_uses_comfy_binary_preview_metadata_node_id(
    monkeypatch: MonkeyPatch,
) -> None:
    """Use Comfy metadata node identities over the currently executing node."""

    workflow: JsonObject = {
        "running-node": {
            "class_type": "KSampler",
            "_meta": {"title": "Running.KSampler"},
        },
        "preview-node": {
            "class_type": "KSampler",
            "_meta": {"title": "Preview.KSampler"},
        },
    }
    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "running-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={
                    "node_id": "preview-node",
                    "display_node_id": "display-node",
                    "parent_node_id": "parent-node",
                    "real_node_id": "real-node",
                    "prompt_id": "pid-1",
                },
                source_label="Preview",
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
    assert preview_events[0].node_id == "preview-node"
    assert preview_events[0].metadata_node_id == "preview-node"
    assert preview_events[0].display_node_id == "display-node"
    assert preview_events[0].parent_node_id == "parent-node"
    assert preview_events[0].real_node_id == "real-node"
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "Preview"


def test_run_emits_preview_with_short_prefixed_source_label(
    monkeypatch: MonkeyPatch,
) -> None:
    """Strip legacy model prefixes from preview source labels."""

    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "preview-node", "prompt_id": "pid-1"},
                }
            ),
            _binary_metadata_preview_image_message(
                metadata={"node_id": "preview-node", "prompt_id": "pid-1"},
                source_label="Text to Image",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload={
            "preview-node": {
                "class_type": "KSampler",
                "_meta": {"title": "SDXL/Text to Image.KSampler"},
            }
        },
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "Text to Image"
