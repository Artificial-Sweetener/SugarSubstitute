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

"""Exercise workflow-tab switching through real Qt stacked widgets."""

from __future__ import annotations

from typing import cast

from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)
from tests.presentation.workflows.tabs.qt_smoke_support import (
    _Scheduler,
    _SmokeView,
    _app,
)


def test_qt_smoke_workflow_tabs_swap_widgets_and_shared_canvas() -> None:
    """Real Qt stacked widgets should route warm tabs without editor rebuilds."""

    _app()
    view = _SmokeView()
    scheduler = _Scheduler()
    coordinator = WorkflowWorkspaceCoordinator(
        cast(WorkflowWorkspaceView, view),
        surface_refresh_scheduler=scheduler,
    )
    editor_a = view.editor_panels["wf-a"]
    editor_b = view.editor_panels["wf-b"]
    editor_c = view.editor_panels["wf-c"]
    cube_a = view.cube_stacks["wf-a"]
    cube_b = view.cube_stacks["wf-b"]
    cube_c = view.cube_stacks["wf-c"]

    coordinator.activate_workflow("wf-b")
    coordinator.activate_workflow("wf-c")
    coordinator.activate_workflow("wf-a")

    assert view.editor_panels["wf-a"] is editor_a
    assert view.editor_panels["wf-b"] is editor_b
    assert view.editor_panels["wf-c"] is editor_c
    assert view.cube_stacks["wf-a"] is cube_a
    assert view.cube_stacks["wf-b"] is cube_b
    assert view.cube_stacks["wf-c"] is cube_c
    assert view.editor_panel_container.currentWidget() is editor_a
    assert view.cube_stack_container.currentWidget() is cube_a
    assert view.workflow_canvas_projection_coordinator.projected_workflow_ids == [
        "wf-b",
        "wf-c",
        "wf-a",
    ]
    assert scheduler.requests == ["wf-c"]
    assert editor_a.load_calls == []
    assert editor_b.load_calls == []
    assert editor_c.load_calls == []
