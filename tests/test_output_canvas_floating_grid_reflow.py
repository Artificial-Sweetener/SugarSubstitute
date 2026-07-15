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

import os

from PySide6.QtCore import QRectF
import pytest

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "floating Output canvas harness requires serial Qt window ownership",
        allow_module_level=True,
    )


def test_floating_and_docked_hosts_choose_same_physical_grid_topology() -> None:
    """The same QPane extent should produce the same topology in either host."""

    harness = RealShellOutputCanvasHarness()
    window: FloatingCanvasWindow | None = None
    try:
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
            lambda: harness.fingerprint().pane_current_composition_id is not None
        )
        canvas = harness.shell.output_canvas
        extent = QRectF(0.0, 0.0, 1000.0, 500.0)
        canvas.pane.viewportRectChanged.emit(extent)
        harness.drain_events_for(30)
        docked = harness.fingerprint()

        window = FloatingCanvasWindow(
            canvas,
            "Output",
            lambda widget, _label: widget.setParent(harness.shell.canvas_tabs),
            backdrop_mode=None,
        )
        window.resize(1000, 500)
        window.show()
        harness.process_events(cycles=8)
        canvas.pane.viewportRectChanged.emit(extent)
        harness.drain_events_for(30)
        floating = harness.fingerprint()

        assert _topology(floating) == _topology(docked)
        assert floating.pane_current_composition_id == (
            docked.pane_current_composition_id
        )
        assert [placement[0] for placement in floating.scene_layer_placements] == [
            placement[0] for placement in docked.scene_layer_placements
        ]
    finally:
        if window is not None:
            window.close()
        harness.close()


def _topology(fingerprint: object) -> tuple[int, int]:
    """Infer row and column counts from public scene layer placements."""

    placements = getattr(fingerprint, "scene_layer_placements", ())
    x_values = {round(float(placement[2]), 6) for placement in placements}
    y_values = {round(float(placement[3]), 6) for placement in placements}
    return len(x_values), len(y_values)
