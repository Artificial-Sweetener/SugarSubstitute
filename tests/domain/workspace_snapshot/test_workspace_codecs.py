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

"""Tests for workspace snapshot codec contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.workspace_snapshot.codecs import (
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)
from substitute.domain.workspace_snapshot import (
    CanvasLayoutSnapshot,
    FloatingCanvasWindowSnapshot,
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
    WorkspaceSnapshot,
    WorkflowSnapshot,
)
from substitute.domain.workflow import WorkflowState


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


def test_workspace_snapshot_round_trips_authoritative_document_state() -> None:
    """Recovery must retain dirty status and the last explicit save destination."""

    source_path = Path("projects") / "portrait.sugar"
    snapshot = WorkspaceSnapshot(
        schema_version="1",
        workflows=(
            WorkflowSnapshot(
                workflow_id="workflow-1",
                tab_label="Portrait",
                workflow=WorkflowState(),
                document_dirty=True,
                document_source_path=source_path,
            ),
        ),
        tab_order=("workflow-1",),
        active_route="workflow-1",
    )

    payload = workspace_snapshot_to_json(snapshot)
    restored = workspace_snapshot_from_json(payload)

    workflow_payload = payload["workflows"]
    assert isinstance(workflow_payload, list)
    assert workflow_payload[0]["document_dirty"] is True
    assert workflow_payload[0]["document_source_path"] == str(source_path)
    assert restored.workflows[0].document_dirty is True
    assert restored.workflows[0].document_source_path == source_path


def test_workspace_snapshot_defaults_legacy_document_state_to_clean() -> None:
    """Snapshots written before dirty-state ownership should remain restorable."""

    payload = workspace_snapshot_to_json(
        WorkspaceSnapshot(
            schema_version="1",
            workflows=(
                WorkflowSnapshot(
                    workflow_id="workflow-1",
                    tab_label="Legacy",
                    workflow=WorkflowState(),
                ),
            ),
            tab_order=("workflow-1",),
            active_route="workflow-1",
        )
    )
    workflows = payload["workflows"]
    assert isinstance(workflows, list)
    del workflows[0]["document_dirty"]
    del workflows[0]["document_source_path"]

    restored = workspace_snapshot_from_json(payload)

    assert restored.workflows[0].document_dirty is False
    assert restored.workflows[0].document_source_path is None
