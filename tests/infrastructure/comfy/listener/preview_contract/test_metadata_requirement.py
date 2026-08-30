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

"""Verify listener preview publication requires Substitute source metadata."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.preview_contract_harness import (
    _binary_preview_image_message,
    _run_preview_messages,
)


def test_run_drops_metadata_less_binary_preview(monkeypatch: MonkeyPatch) -> None:
    """Fail closed for legacy preview frames that cannot prove an output source."""

    preview_events, output_events, failures, completed = _run_preview_messages(
        monkeypatch,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "ksampler", "prompt_id": "pid-1"},
                }
            ),
            _binary_preview_image_message(b"preview-data"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload={"save-node": {"class_type": "SugarCubes.CubeOutput"}},
        workflow_id="wf-preview",
    )

    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-preview"
    assert completed[0].prompt_id == "pid-1"
    assert output_events == []
    assert preview_events == []
