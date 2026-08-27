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

"""Verify Comfy TEXT websocket events remain distinct from image artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.output_contract_harness import (
    _binary_text_message,
    _cube_output_message,
    _run_cube_output_visual_messages,
)


def test_run_ignores_comfy_binary_text_event(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Do not decode Comfy TEXT events as output images."""

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            json.dumps(
                {"type": "executing", "data": {"node": "26", "prompt_id": "pid-1"}}
            ),
            _binary_text_message(node_id="26"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload={"26": {"class_type": "GetImageSize"}},
    )

    assert failures == []
    assert output_events == []
    assert len(completed) == 1
    assert completed[0].prompt_id == "pid-1"


def test_run_persists_cube_output_after_comfy_binary_text_event(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Continue to persist later cube artifacts after a Comfy TEXT event."""

    workflow: JsonObject = {
        "26": {"class_type": "GetImageSize"},
        "output-node": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "CubeA.CubeOutput"},
        },
    }
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            json.dumps(
                {"type": "executing", "data": {"node": "26", "prompt_id": "pid-1"}}
            ),
            _binary_text_message(node_id="26"),
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload=workflow,
        output_run_number=7,
    )

    assert failures == []
    assert len(output_events) == 1
    assert output_events[0].node_id == "output-node"
    assert len(completed) == 1
