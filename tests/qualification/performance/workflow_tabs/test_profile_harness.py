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

"""Tests for workflow tab-switch profile artifact schema."""

from __future__ import annotations

import json
from pathlib import Path

from tools.profile_workflow_tab_switch import (
    SWITCH_SEQUENCE,
    build_profile_artifact,
    write_profile_artifacts,
)


def test_profile_artifact_contains_required_diagnostic_fields() -> None:
    """Profile rows should contain stable diagnostics without timing assertions."""

    artifact = build_profile_artifact()

    assert [run["workflow_id"] for run in artifact["runs"]] == list(SWITCH_SEQUENCE)
    assert any(run["route_ms"] > 0.0 for run in artifact["runs"])
    for run in artifact["runs"]:
        assert set(run) == {
            "workflow_id",
            "route_ms",
            "canvas_ms",
            "ensure_workflow_ui_ms",
            "show_route_ms",
            "tab_select_ms",
            "cube_stack_swap_ms",
            "editor_panel_swap_ms",
            "override_projection_ms",
            "input_canvas_availability_ms",
            "overlay_refresh_ms",
            "activity_badge_ms",
            "overrides_projected",
            "widgets_created",
            "editor_rebuilt",
            "deferred_requests",
            "info_logs",
        }
        assert run["overrides_projected"]
        assert not run["editor_rebuilt"]
        assert run["info_logs"] == 0


def test_profile_harness_writes_latest_and_manifest(tmp_path: Path) -> None:
    """Profile helper should write JSON artifacts for manual validation."""

    write_profile_artifacts(tmp_path)

    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert len(latest["runs"]) == len(SWITCH_SEQUENCE)
    assert any(run["route_ms"] > 0.0 for run in latest["runs"])
    assert "generated_session_path" in manifest
    assert "launch_command" in manifest
    assert "validation_steps" in manifest
    assert "observed_route_ms" in manifest
    assert "observed_canvas_ms" in manifest
