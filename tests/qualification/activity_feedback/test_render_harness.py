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

"""Verify the offscreen activity-feedback evidence harness."""

from __future__ import annotations

import json
from pathlib import Path

from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
)
from tools.qualify_activity_feedback import run_activity_feedback_qualification


def test_all_long_running_surfaces_render_live_hidden_console_feedback(
    tmp_path: Path,
) -> None:
    """Require raster and semantic proof for every scoped progress surface."""

    evidence_path = run_activity_feedback_qualification(tmp_path / "activity")
    records = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert {record["name"] for record in records} == {
        "startup",
        "update",
        "installation",
        "repair-preparation",
        "repair-execution",
        "comfy-setup",
    }
    assert all(record["activity_running"] for record in records)
    assert all(not record["details_visible"] for record in records)
    assert all(Path(record["image"]).stat().st_size > 0 for record in records)
    assert (
        next(record for record in records if record["name"] == "startup")[
            "visible_fraction"
        ]
        >= 0.5
    )
    assert next(record for record in records if record["name"] == "installation")[
        "transcript_lines"
    ] == [
        "Installing SugarSubstitute",
        "Verified application archive",
    ]
    setup_transcript = next(
        record for record in records if record["name"] == "comfy-setup"
    )["transcript_lines"]
    setup_record = next(record for record in records if record["name"] == "comfy-setup")
    assert setup_record["width"] == INSTALLER_WINDOW_WIDTH
    assert setup_record["height"] == INSTALLER_WINDOW_HEIGHT
    assert len(setup_transcript) == 12
    assert all("Requirement already satisfied" not in line for line in setup_transcript)
    assert "(0%)" in setup_transcript[0]
    assert "(100%)" in setup_transcript[-2]
    assert setup_transcript[-1] == "Verified model transfer block"
