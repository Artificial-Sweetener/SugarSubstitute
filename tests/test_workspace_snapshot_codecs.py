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

"""Tests for version-only workspace snapshot cube persistence."""

from __future__ import annotations

from uuid import uuid4

import pytest

from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workspace_snapshot import SnapshotCodecError
from substitute.domain.workspace_snapshot.codecs import (
    workflow_state_from_json,
    workflow_state_to_json,
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    CanvasLayoutSnapshot,
    FloatingCanvasWindowSnapshot,
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
    WorkspaceSnapshot,
)


def test_workflow_state_codec_round_trips_cube_version_identity() -> None:
    """Workflow snapshots should persist cube id and version only."""

    state = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.7.0",
                alias="Demo",
                original_cube={"nodes": {}},
                buffer={"nodes": {}},
                bypassed=True,
            )
        },
        stack_order=["Demo"],
    )

    payload = workflow_state_to_json(state)
    restored = workflow_state_from_json(payload)

    cubes_payload = payload["cubes"]
    assert isinstance(cubes_payload, dict)
    cube_payload = cubes_payload["Demo"]
    assert isinstance(cube_payload, dict)
    assert "definition_ref" not in cube_payload
    assert cube_payload["bypassed"] is True
    assert restored.cubes["Demo"].cube_id == "owner/repo/demo.cube"
    assert restored.cubes["Demo"].version == "1.7.0"
    assert restored.cubes["Demo"].bypassed is True


def test_workflow_state_codec_defaults_missing_bypassed_to_false() -> None:
    """Older workflow snapshots should restore cubes as active by default."""

    state = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.7.0",
                alias="Demo",
                original_cube={"nodes": {}},
                buffer={"nodes": {}},
            )
        },
        stack_order=["Demo"],
    )
    payload = workflow_state_to_json(state)
    cubes_payload = payload["cubes"]
    assert isinstance(cubes_payload, dict)
    cube_payload = cubes_payload["Demo"]
    assert isinstance(cube_payload, dict)
    del cube_payload["bypassed"]

    restored = workflow_state_from_json(payload)

    assert restored.cubes["Demo"].bypassed is False


def test_workflow_state_codec_round_trips_seed_control_states() -> None:
    """Workflow snapshots should persist editor and override seed modes."""

    state = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.7.0",
                alias="Demo",
                original_cube={"nodes": {}},
                buffer={"nodes": {}},
                field_control_states={
                    "KSampler": {"seed": SeedControlState(SeedMode.FIXED)}
                },
            )
        },
        stack_order=["Demo"],
        override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
    )

    payload = workflow_state_to_json(state)
    restored = workflow_state_from_json(payload)

    cubes_payload = payload["cubes"]
    assert isinstance(cubes_payload, dict)
    cube_payload = cubes_payload["Demo"]
    assert isinstance(cube_payload, dict)
    assert cube_payload["field_control_states"] == {
        "KSampler": {"seed": {"mode": "fixed"}}
    }
    assert payload["override_control_states"] == {"seed": {"mode": "fixed"}}
    assert (
        restored.cubes["Demo"].field_control_states["KSampler"]["seed"].mode
        == SeedMode.FIXED
    )
    assert restored.override_control_states["seed"].mode == SeedMode.FIXED


def test_workflow_state_codec_defaults_missing_seed_control_states() -> None:
    """Older workflow snapshots should restore absent seed modes as implicit random."""

    state = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.7.0",
                alias="Demo",
                original_cube={"nodes": {}},
                buffer={"nodes": {}},
            )
        },
        stack_order=["Demo"],
    )
    payload = workflow_state_to_json(state)
    cubes_payload = payload["cubes"]
    assert isinstance(cubes_payload, dict)
    cube_payload = cubes_payload["Demo"]
    assert isinstance(cube_payload, dict)
    del cube_payload["field_control_states"]
    del payload["override_control_states"]

    restored = workflow_state_from_json(payload)

    assert restored.cubes["Demo"].field_control_states == {}
    assert restored.override_control_states == {}


def test_workflow_state_codec_round_trips_active_canvas_route() -> None:
    """Workflow snapshots should persist the selected attached canvas route."""

    state = WorkflowState()
    mask_id = uuid4()
    state.canvas.active_canvas_route = "Input"
    state.canvas.active_input_mask_uuid = mask_id

    payload = workflow_state_to_json(state)
    restored = workflow_state_from_json(payload)

    canvas_payload = payload["canvas"]
    assert isinstance(canvas_payload, dict)
    assert canvas_payload["active_canvas_route"] == "Input"
    assert canvas_payload["active_input_mask_uuid"] == str(mask_id)
    assert restored.canvas.active_canvas_route == "Input"
    assert restored.canvas.active_input_mask_uuid == mask_id


def test_workflow_state_codec_rejects_missing_cube_version() -> None:
    """Saved workflow cubes must have explicit versions."""

    payload = workflow_state_to_json(
        WorkflowState(
            cubes={
                "Demo": CubeState(
                    cube_id="owner/repo/demo.cube",
                    version="1.7.0",
                    alias="Demo",
                    original_cube={},
                    buffer={},
                )
            },
            stack_order=["Demo"],
        )
    )
    cubes_payload = payload["cubes"]
    assert isinstance(cubes_payload, dict)
    cube_payload = cubes_payload["Demo"]
    assert isinstance(cube_payload, dict)
    del cube_payload["version"]

    with pytest.raises(SnapshotCodecError, match="version"):
        workflow_state_from_json(payload)


def test_workspace_snapshot_codec_round_trips_floating_canvas_layout() -> None:
    """Workspace snapshots should persist floating canvas layout under shell state."""

    snapshot = WorkspaceSnapshot(
        schema_version="1",
        workflows=(),
        tab_order=(),
        active_route="settings",
        shell_layout=ShellLayoutSnapshot(
            canvas_layout=CanvasLayoutSnapshot(
                floating_windows=(
                    FloatingCanvasWindowSnapshot(
                        label="Input",
                        geometry=WindowGeometrySnapshot(
                            x=10,
                            y=20,
                            width=640,
                            height=480,
                        ),
                    ),
                    FloatingCanvasWindowSnapshot(
                        label="Output",
                        geometry=WindowGeometrySnapshot(
                            x=100,
                            y=120,
                            width=900,
                            height=700,
                        ),
                        window_display_state="maximized",
                        output_generation_controls_revealed=True,
                    ),
                )
            )
        ),
    )

    payload = workspace_snapshot_to_json(snapshot)
    restored = workspace_snapshot_from_json(payload)

    assert restored.shell_layout is not None
    expected_shell_layout = snapshot.shell_layout
    assert expected_shell_layout is not None
    assert restored.shell_layout.canvas_layout == expected_shell_layout.canvas_layout
    shell_layout_payload = payload["shell_layout"]
    assert isinstance(shell_layout_payload, dict)
    canvas_layout_payload = shell_layout_payload["canvas_layout"]
    assert isinstance(canvas_layout_payload, dict)
    assert canvas_layout_payload["floating_windows"] == [
        {
            "label": "Input",
            "geometry": {"x": 10, "y": 20, "width": 640, "height": 480},
            "window_display_state": "normal",
            "output_generation_controls_revealed": False,
        },
        {
            "label": "Output",
            "geometry": {"x": 100, "y": 120, "width": 900, "height": 700},
            "window_display_state": "maximized",
            "output_generation_controls_revealed": True,
        },
    ]


def test_workspace_snapshot_codec_tolerates_missing_canvas_layout() -> None:
    """Older shell layout payloads without canvas layout should still decode."""

    payload = workspace_snapshot_to_json(
        WorkspaceSnapshot(
            schema_version="1",
            workflows=(),
            tab_order=(),
            active_route="settings",
            shell_layout=ShellLayoutSnapshot(),
        )
    )
    shell_layout_payload = payload["shell_layout"]
    assert isinstance(shell_layout_payload, dict)
    del shell_layout_payload["canvas_layout"]

    restored = workspace_snapshot_from_json(payload)

    assert restored.shell_layout is not None
    assert restored.shell_layout.canvas_layout is None


def test_workspace_snapshot_codec_tolerates_floating_canvas_display_state() -> None:
    """Floating canvas display state should fall back instead of breaking restore."""

    payload = workspace_snapshot_to_json(
        WorkspaceSnapshot(
            schema_version="1",
            workflows=(),
            tab_order=(),
            active_route="settings",
            shell_layout=ShellLayoutSnapshot(
                canvas_layout=CanvasLayoutSnapshot(
                    floating_windows=(FloatingCanvasWindowSnapshot(label="Output"),)
                )
            ),
        )
    )
    shell_layout_payload = payload["shell_layout"]
    assert isinstance(shell_layout_payload, dict)
    canvas_layout_payload = shell_layout_payload["canvas_layout"]
    assert isinstance(canvas_layout_payload, dict)
    floating_windows = canvas_layout_payload["floating_windows"]
    assert isinstance(floating_windows, list)
    floating_windows[0]["window_display_state"] = "minimized"
    floating_windows[0]["geometry"] = None

    restored = workspace_snapshot_from_json(payload)

    assert restored.shell_layout is not None
    assert restored.shell_layout.canvas_layout is not None
    floating_window = restored.shell_layout.canvas_layout.floating_windows[0]
    assert floating_window.window_display_state == "normal"
    assert floating_window.geometry is None
