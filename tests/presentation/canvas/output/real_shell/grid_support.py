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

"""Provide responsive-grid diagnostics shared by real-shell Output tests."""

from __future__ import annotations

from cutecanvas import ResponsiveGridSnapshot

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import CanvasFingerprint


def grid_dimensions(fingerprint: CanvasFingerprint) -> tuple[int, int] | None:
    """Infer grid columns and rows from fingerprinted layer placements."""

    placements = fingerprint.grid_target_frames
    if not placements:
        return None
    columns = len({round(layer[2], 6) for layer in placements})
    rows = len({round(layer[3], 6) for layer in placements})
    return columns, rows


def horizontal_gap_in_native_scene_units(
    snapshot: ResponsiveGridSnapshot,
    *,
    native_width: float,
) -> float:
    """Normalize the visible first-row gap to baseline scene coordinates."""

    frames = snapshot.frames
    assert len(frames) >= 2
    first, second = frames[:2]
    first_content = first.content
    second_content = second.content
    scale = first_content.width() / native_width
    assert scale > 0.0
    return (second_content.x() - first_content.right()) / scale


def wait_for_new_grid_snapshot(
    harness: RealShellOutputCanvasHarness,
    previous: ResponsiveGridSnapshot | None,
) -> ResponsiveGridSnapshot:
    """Await a grid layout object produced after the triggering transition."""

    observed: ResponsiveGridSnapshot | None = None

    def new_snapshot_is_available() -> bool:
        """Capture and recognize the next immutable grid snapshot."""

        nonlocal observed
        observed = harness.shell.output_canvas.workspace.gridSnapshot()
        return observed is not None and observed is not previous

    harness.wait_until(new_snapshot_is_available)
    assert observed is not None
    return observed
