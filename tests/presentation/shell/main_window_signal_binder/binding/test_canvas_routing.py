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

"""Verify canvas-output signal routing and selection autosave."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)

from .support import _Signal


def test_canvas_signals_route_output_events_and_canvas_selection_autosave() -> None:
    """Canvas wiring should route output events and categorize canvas autosaves."""

    events: list[tuple[str, object]] = []
    autosaves: list[SessionAutosaveRequestCategory] = []
    input_canvas = SimpleNamespace(
        inputImageLoaded=_Signal(),
    )
    output_canvas = SimpleNamespace(
        activeOutputChanged=_Signal(),
        activeOutputGridChanged=_Signal(),
        activeOutputSceneChanged=_Signal(),
        activeOutputCompareChanged=_Signal(),
    )
    shell = SimpleNamespace(
        workspace_canvas_actions=SimpleNamespace(
            on_active_output_changed=lambda uuid_str: events.append(
                ("active_output", uuid_str)
            ),
            on_active_output_grid_changed=lambda source_key: events.append(
                ("active_output_grid", source_key)
            ),
            on_active_output_scene_changed=lambda selection: events.append(
                ("active_output_scene", selection)
            ),
            on_output_compare_changed=lambda compare_key: events.append(
                ("compare", compare_key)
            ),
        ),
        session_autosave_controller=SimpleNamespace(
            request_categorized_session_autosave=autosaves.append
        ),
    )

    MainWindowSignalBinder(shell).connect_canvas_signals(
        input_canvas=input_canvas,
        output_canvas=output_canvas,
    )
    output_canvas.activeOutputChanged.fire("out-1")
    output_canvas.activeOutputGridChanged.fire("source-a")
    scene_selection = OutputSceneNavigationSelection(
        scene_key="scene-a",
        overview=False,
        source_key="source-a",
        set_index=0,
        image_id=None,
    )
    output_canvas.activeOutputSceneChanged.fire(scene_selection)
    output_canvas.activeOutputCompareChanged.fire("compare-a")
    input_canvas.inputImageLoaded.fire("node-1", "input.png")

    assert events == [
        ("active_output", "out-1"),
        ("active_output_grid", "source-a"),
        ("active_output_scene", scene_selection),
        ("compare", "compare-a"),
    ]
    assert autosaves == [
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
    ]
