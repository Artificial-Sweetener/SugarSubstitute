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
)


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
