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

"""Tests for cube-output event parsing and artifact transport helpers."""

from __future__ import annotations

from substitute.infrastructure.comfy.cube_output_event import (
    parse_cube_output_event,
)


def _payload() -> dict[str, object]:
    """Return a valid v1 cube-output event payload."""

    return {
        "version": 1,
        "prompt_id": "prompt-1",
        "node_id": "node-1",
        "list_index": 0,
        "cube_id": "owner/repo/demo.cube",
        "default_alias": "Demo",
        "instance_alias": "Demo Instance",
        "instance_id": "instance-1",
        "media_kind": "image",
        "value_type": "torch.Tensor",
        "artifacts": [
            {
                "filename": "ComfyUI temp 00001.png",
                "subfolder": "a folder",
                "type": "temp",
                "media_kind": "image",
                "mime_type": "image/png",
                "width": 64,
                "height": 32,
            }
        ],
    }


def test_parse_cube_output_event_image_payload() -> None:
    """Valid v1 image payloads should parse into typed events."""

    event = parse_cube_output_event(_payload())

    assert event is not None
    assert event.prompt_id == "prompt-1"
    assert event.node_id == "node-1"
    assert event.instance_alias == "Demo Instance"
    assert event.media_kind == "image"
    assert event.artifacts[0].filename == "ComfyUI temp 00001.png"
    assert event.artifacts[0].width == 64


def test_parse_cube_output_event_ignores_unsupported_version() -> None:
    """Unsupported event versions should be ignored."""

    payload = _payload()
    payload["version"] = 3

    assert parse_cube_output_event(payload) is None


def test_parse_cube_output_event_reads_v2_substitute_identity() -> None:
    """Valid v2 payloads should expose Backend-owned Substitute identity."""

    payload = _payload()
    payload["version"] = 2
    payload["substitute"] = {
        "schemaVersion": 1,
        "workflowId": "wf-1",
        "generationRunId": "run-1",
        "outputSessionId": "generate-click-1",
        "clientId": "client-1",
        "sourceKey": "wf-1:node-1",
        "sourceLabel": "Demo",
        "sceneKey": "portrait",
    }

    event = parse_cube_output_event(payload)

    assert event is not None
    assert event.version == 2
    assert event.substitute is not None
    assert event.substitute.workflow_id == "wf-1"
    assert event.substitute.generation_run_id == "run-1"
    assert event.substitute.output_session_id == "generate-click-1"
    assert event.substitute.client_id == "client-1"
    assert event.substitute.source_key == "wf-1:node-1"
    assert event.substitute.scene_key == "portrait"


def test_parse_cube_output_event_rejects_malformed_artifact() -> None:
    """Malformed artifacts should make the event invalid."""

    payload = _payload()
    payload["artifacts"] = [{"filename": "missing-type.png"}]

    assert parse_cube_output_event(payload) is None
