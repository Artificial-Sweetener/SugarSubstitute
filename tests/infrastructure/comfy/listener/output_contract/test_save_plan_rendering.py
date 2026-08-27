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

"""Verify listener artifact paths render immutable output-save-plan inputs."""

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


def test_run_saves_cube_output_artifact_with_custom_output_save_plan(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Use the save plan's root, path pattern, and fixed start time."""

    output_root = tmp_path / "external"
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
            output_root=output_root,
            path_pattern="{workflow}\\{date}\\{run}_{time}_{source}_{width}x{height}_{set}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
    )

    expected_path = (
        output_root / "My Workflow" / "2026-05-01" / "012_14-32-09_cubea_640x480_1.png"
    )
    assert failures == []
    assert len(completed) == 1
    assert output_events[0].file_path == expected_path


def test_run_saves_cube_output_artifact_with_seed_output_token(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Render the immutable save-plan seed token into the artifact path."""

    output_root = tmp_path / "external"
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
            output_root=output_root,
            path_pattern="{workflow}\\{seed}_{source}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
            seed="1234",
        ),
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events[0].file_path == output_root / "My Workflow" / "1234_cubea.png"


def test_run_saves_cube_output_artifact_with_folder_image_number_token(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Increment image-number tokens within the rendered target folder."""

    output_root = tmp_path / "external"
    existing = output_root / "2026-05-01" / "image_01_cubea.png"
    existing.parent.mkdir(parents=True)
    existing.write_text("", encoding="utf-8")
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
            output_root=output_root,
            path_pattern="{date}\\Image {image#}_{source}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
    )

    assert failures == []
    assert len(completed) == 1
    assert (
        output_events[0].file_path == output_root / "2026-05-01" / "image_02_cubea.png"
    )
