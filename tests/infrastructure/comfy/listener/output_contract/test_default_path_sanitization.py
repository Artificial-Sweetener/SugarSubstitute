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

"""Verify default listener output paths cannot escape their output root."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.output_contract_harness import (
    _cube_output_message,
    _run_cube_output_visual_messages,
)


@pytest.mark.parametrize(
    ("workflow_name", "expected_relative_path"),
    [
        ("../escape", Path("2026-05-01") / "001_01_escape_cubea.png"),
        ("..", Path("2026-05-01") / "001_01_cubea.png"),
    ],
)
def test_run_sanitizes_default_workflow_name_path_tokens(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    workflow_name: str,
    expected_relative_path: Path,
) -> None:
    """Keep traversal-like names inside the default listener output root."""

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        output_run_number=1,
        workflow_name=workflow_name,
        fallback_job_started_at=datetime(2026, 5, 1, 14, 32, 9),
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events[0].file_path == tmp_path / expected_relative_path
    assert output_events[0].file_path.is_relative_to(tmp_path)
