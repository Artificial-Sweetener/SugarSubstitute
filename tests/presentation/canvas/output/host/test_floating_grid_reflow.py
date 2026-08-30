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

"""Verify responsive Output grids inside the production floating canvas host."""

from __future__ import annotations

from pathlib import Path

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import CanvasFingerprint, OutputSpec
from tests.support.qt.lifecycle import destroy_qt_object


def test_floating_and_docked_hosts_choose_same_physical_grid_topology(
    tmp_path: Path,
) -> None:
    """The same QPane extent should produce the same topology in either host."""

    harness = RealShellOutputCanvasHarness(output_root=tmp_path)
    window: FloatingCanvasWindow | None = None
    try:
        harness.shell.resize(1200, 800)
        harness.add_workflow("alpha", activate=True)
        run = harness.start_run("alpha")
        for index in range(5):
            harness.emit_output(
                run,
                OutputSpec(
                    "alpha-grid",
                    "Alpha Grid",
                    (20 + index * 20, 80, 160),
                    list_index=index,
                    width=96,
                    height=48,
                ),
            )
        harness.wait_for_output_count("alpha", 5)
        harness.wait_until(
            lambda: harness.fingerprint().active_composition_id is not None
        )
        canvas = harness.shell.output_canvas
        canvas.resize(1000, 500)
        canvas.workspace.resize(1000, 500)
        harness.wait_until(
            lambda: _has_complete_grid(harness.fingerprint(), item_count=5)
        )
        docked = harness.fingerprint()

        window = FloatingCanvasWindow(
            canvas,
            "Output",
            lambda widget, _label: widget.setParent(harness.shell.canvas_host),
            backdrop_mode=None,
        )
        window.resize(1000, 500)
        window.show()
        canvas.workspace.resize(1000, 500)
        harness.wait_until(lambda: _matches_grid(harness.fingerprint(), docked))
        floating = harness.fingerprint()

        assert _topology(floating) == _topology(docked)
        assert floating.active_composition_id == (docked.active_composition_id)
        assert [placement[0] for placement in floating.grid_target_frames] == [
            placement[0] for placement in docked.grid_target_frames
        ]
    finally:
        if window is not None:
            window.close()
            destroy_qt_object(window)
        harness.close()


def _has_complete_grid(fingerprint: CanvasFingerprint, *, item_count: int) -> bool:
    """Return whether the public grid snapshot contains every expected item."""

    return (
        fingerprint.grid_viewport is not None
        and len(fingerprint.grid_target_frames) == item_count
    )


def _matches_grid(
    fingerprint: CanvasFingerprint,
    expected: CanvasFingerprint,
) -> bool:
    """Return whether rehosting has settled to the docked grid contract."""

    return (
        _topology(fingerprint) == _topology(expected)
        and fingerprint.active_composition_id == expected.active_composition_id
        and tuple(frame[0] for frame in fingerprint.grid_target_frames)
        == tuple(frame[0] for frame in expected.grid_target_frames)
    )


def _topology(fingerprint: CanvasFingerprint) -> tuple[int, int]:
    """Infer row and column counts from public scene layer placements."""

    placements = fingerprint.grid_target_frames
    x_values = {round(float(placement[2]), 6) for placement in placements}
    y_values = {round(float(placement[3]), 6) for placement in placements}
    return len(x_values), len(y_values)
