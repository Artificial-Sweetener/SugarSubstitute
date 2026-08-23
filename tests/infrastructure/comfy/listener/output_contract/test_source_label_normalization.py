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

"""Verify listener output labels remove model-prefix aliases."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.output_contract_harness import (
    _cube_output_message,
    _run_cube_output_visual_messages,
)


def test_run_saves_prefixed_cube_output_with_short_source_label(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Omit model prefixes from persisted CubeOutput labels and filenames."""

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _cube_output_message(
                node_id="output-node",
                instance_alias="SDXL/Text to Image",
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        workflow_payload={
            "output-node": {
                "class_type": "SugarCubes.CubeOutput",
                "_meta": {"title": "SDXL/Text to Image.CubeOutput"},
            }
        },
        fallback_job_started_at=datetime(2026, 5, 1, 14, 32, 9),
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events[0].file_path == (
        tmp_path / "2026-05-01" / "007_01_my_workflow_text_to_image.png"
    )
    assert output_events[0].source_key == "wf-1:output-node"
    assert output_events[0].source_label == "Text to Image"
    assert "sdxl_text_to_image" not in str(output_events[0].file_path)
