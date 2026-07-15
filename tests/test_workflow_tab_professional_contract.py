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

"""Professional workflow-tab behavior contract tests."""

from __future__ import annotations

import logging

import pytest

from substitute.domain.workflow import CubeState
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)

from tests.test_workflow_tab_actions_contract import (
    _DeferredSurfaceRefreshScheduler,
    _ProjectionAwareEditorPanel,
    _build_view,
    _import_module,
)


def test_clean_warm_tab_switch_is_route_projection_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Clean warm tab selection should not rebuild or synchronously persist."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    refresh_calls: list[str] = []
    autosaves: list[str] = []
    view.refresh_active_workflow_surface = lambda **_kwargs: refresh_calls.append(
        "refresh"
    )
    view.request_session_autosave = lambda: autosaves.append("snapshot")
    caplog.set_level(logging.INFO, logger="sugarsubstitute.presentation.shell")

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b", source="workflow_tab")

    assert view.workflow_session_service.active_workflow_id == "wf-b"
    assert view.workflow_tabbar.selected == [("wf-b", False)]
    assert f"cube:set:{id(view.cube_stacks['wf-b'])}" in view.calls
    assert f"editor:set:{id(view.editor_panels['wf-b'])}" in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert refresh_calls == []
    assert autosaves == []
    assert scheduler.requests == []
    assert caplog.records == []


def test_unprojected_warm_tab_switch_projects_canvas_and_defers_editor() -> None:
    """Unprojected warm tabs should show route and canvas before editor work."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    view.workflow_session_service.workflows["wf-b"].cubes["CubeA"] = CubeState(
        cube_id="Owner/Repo/CubeA.cube",
        version="1.0.0",
        alias="CubeA",
        original_cube={},
        buffer={},
    )
    view.workflow_session_service.workflows["wf-b"].stack_order.append("CubeA")
    view.editor_panels["wf-b"] = _ProjectionAwareEditorPanel(clean=False)

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b", source="workflow_tab")

    assert "canvas:project:wf-b" in view.calls
    assert "refresh" not in view.calls
    assert scheduler.requests == [
        {
            "workflow_id": "wf-b",
            "force_refresh": False,
            "reason": "workflow_tab",
            "on_complete": None,
        }
    ]


def test_dirty_tab_switch_schedules_one_latest_route_maintenance() -> None:
    """Dirty tab selection should route immediately and schedule one refresh."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.EDITOR, WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CUBE_LOADED,
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
        surface_invalidation_service=invalidation,
    ).activate_workflow("wf-b", source="workflow_tab")

    assert "canvas:project:wf-b" in view.calls
    assert "refresh" not in view.calls
    assert len(scheduler.requests) == 1
    assert scheduler.requests[0]["workflow_id"] == "wf-b"


def test_tab_selection_does_not_call_main_window_refresh_delegate() -> None:
    """Workflow tab activation must not use MainWindow refresh as a shortcut."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    def fail_refresh(**_kwargs: object) -> None:
        """Fail if tab selection reaches the public compatibility delegate."""

        raise AssertionError("tab selection called refresh_active_workflow_surface")

    view.refresh_active_workflow_surface = fail_refresh

    mod.WorkflowWorkspaceCoordinator(view).activate_workflow(
        "wf-b",
        source="workflow_tab",
    )

    assert view.workflow_session_service.active_workflow_id == "wf-b"


def test_tab_structure_changes_request_autosave_without_dirtying_surfaces() -> None:
    """Rename-style tab structure edits should not dirty presentation surfaces."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    invalidation = WorkflowSurfaceInvalidationService()

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_invalidation_service=invalidation,
    ).rename_workflow("wf-b", "Workflow B")

    assert invalidation.is_clean("wf-b")
    assert invalidation.is_clean("Workflow B")
