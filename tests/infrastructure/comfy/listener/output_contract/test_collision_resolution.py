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

"""Verify listener artifact persistence never overwrites an existing output."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from substitute.application.ports import OutputSavePlan
from tests.infrastructure.comfy.listener.output_contract_harness import (
    _cube_output_message,
    _run_cube_output_visual_messages,
)


def test_run_saves_cube_output_artifact_without_overwriting_existing_output(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Suffix a colliding rendered artifact path instead of overwriting it."""

    existing = tmp_path / "My Workflow" / "012_cubea.png"
    existing.parent.mkdir()
    existing.write_text("preserve", encoding="utf-8")
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        output_run_number=12,
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{workflow}\\{run}_{source}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
    )

    assert failures == []
    assert len(completed) == 1
    assert existing.read_text(encoding="utf-8") == "preserve"
    assert output_events[0].file_path == tmp_path / "My Workflow" / "012_cubea_002.png"
