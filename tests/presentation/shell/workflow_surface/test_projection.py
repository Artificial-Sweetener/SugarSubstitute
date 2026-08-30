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

"""Workflow surface projection and invalidation contracts."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from substitute.domain.workflow import CubeState
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _ProjectionAwareEditorPanel,
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _DeferredSurfaceRefreshScheduler,
    _build_view,
)


def test_unprojected_workflow_tab_activation_schedules_refresh_without_dirty_flag() -> (
    None
):
    """A missing dirty flag must not skip an editor panel that is not clean yet."""

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
    editor_panel = _ProjectionAwareEditorPanel(clean=False)
    view.editor_panels["wf-b"] = editor_panel

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert editor_panel.signature_requests
    assert "canvas:project:wf-b" in view.calls
    assert scheduler.requests == [
        {
            "workflow_id": "wf-b",
            "force_refresh": False,
            "reason": "workflow_tab",
            "on_complete": None,
        }
    ]
    assert "refresh" not in view.calls


def test_unprojected_workflow_tab_activation_uses_full_refresh_with_other_dirty_surface() -> (
    None
):
    """A non-editor dirty flag must not hide a newly materialized editor panel."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.GENERATION_AVAILABILITY},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )
    view.workflow_session_service.workflows["wf-b"].cubes["CubeA"] = CubeState(
        cube_id="Owner/Repo/CubeA.cube",
        version="1.0.0",
        alias="CubeA",
        original_cube={},
        buffer={},
    )
    view.workflow_session_service.workflows["wf-b"].stack_order.append("CubeA")
    editor_panel = _ProjectionAwareEditorPanel(clean=False)
    view.editor_panels["wf-b"] = editor_panel

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
        surface_invalidation_service=invalidation,
    ).activate_workflow("wf-b")

    assert editor_panel.signature_requests
    assert scheduler.requests == [
        {
            "workflow_id": "wf-b",
            "force_refresh": True,
            "reason": "workflow_tab",
            "on_complete": None,
        }
    ]


def test_projected_workflow_tab_activation_skips_refresh_when_editor_is_clean() -> None:
    """A clean editor projection can use the cached workflow surface immediately."""

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
    view.editor_panels["wf-b"] = _ProjectionAwareEditorPanel(clean=True)

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert "canvas:project:wf-b" in view.calls
    assert scheduler.requests == []
    assert "refresh" not in view.calls


def test_clean_workflow_tab_activation_emits_no_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Routine clean tab switching should not spam INFO logs."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_workspace_coordinator",
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert caplog.records == []


def test_dirty_workflow_tab_activation_schedules_deferred_surface_refresh() -> None:
    """Dirty workflow tab activation should show route first and defer refresh."""

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
    ).activate_workflow("wf-b")

    assert view.workflow_session_service.active_workflow_id == "wf-b"
    assert view.workflow_tabbar.selected == [("wf-b", False)]
    assert f"cube:set:{id(view.cube_stacks['wf-b'])}" in view.calls
    assert f"editor:set:{id(view.editor_panels['wf-b'])}" in view.calls
    assert "refresh" not in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert scheduler.requests == [
        {
            "workflow_id": "wf-b",
            "force_refresh": False,
            "reason": "workflow_tab",
            "on_complete": None,
        }
    ]


def test_canvas_only_dirty_refresh_skips_editor_surface_refresh() -> None:
    """Canvas-only dirty maintenance should not rebuild editor surfaces."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-b")
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_invalidation_service=invalidation,
    ).project_workflow("wf-b", source="workspace_projection")

    assert "refresh" not in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert invalidation.is_clean("wf-b")


def test_canvas_only_dirty_workflow_tab_switch_projects_without_deferred_refresh() -> (
    None
):
    """Tab switching should satisfy canvas-only dirtiness during route activation."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
        surface_invalidation_service=invalidation,
    ).activate_workflow("wf-b")

    assert "canvas:project:wf-b" in view.calls
    assert "refresh" not in view.calls
    assert scheduler.requests == []
    assert invalidation.is_clean("wf-b")


def test_override_only_dirty_refresh_uses_typed_override_reconciliation() -> None:
    """Override-only dirty maintenance should avoid legacy broad refresh hooks."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-b")
    targeted: list[frozenset[WorkflowSurface]] = []
    view.refresh_active_workflow_surfaces = lambda surfaces: targeted.append(
        frozenset(surfaces)
    )
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.OVERRIDES},
        WorkflowInvalidationReason.GLOBAL_OVERRIDES_CHANGED,
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_invalidation_service=invalidation,
    ).project_workflow("wf-b", source="workspace_projection")

    assert targeted == []
    assert "refresh" not in view.calls
    assert "canvas:project:wf-b" not in view.calls
    assert not invalidation.is_clean("wf-b")


def test_workspace_projection_with_completion_refreshes_surface_inline() -> None:
    """Completion-dependent workflow projection should keep synchronous semantics."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    completions: list[str] = []

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow(
        "wf-b",
        source="workspace_projection",
        force_refresh=True,
        on_surface_complete=lambda: completions.append("done"),
    )

    assert scheduler.requests == []
    assert "refresh" in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert completions == ["done"]


def test_project_workflow_refreshes_input_canvas_availability() -> None:
    """Workflow projection should refresh input-canvas capability after canvas state."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view.canvas_route_controller = SimpleNamespace(
        refresh_input_canvas_availability=lambda: view.calls.append(
            "input_canvas:availability"
        )
    )

    mod.WorkflowWorkspaceCoordinator(view).project_workflow(
        "wf-a",
        force_refresh=True,
    )

    assert view.calls.index("canvas:project:wf-a") < view.calls.index(
        "input_canvas:availability"
    )


def test_project_workflow_clears_unread_activity() -> None:
    """Workflow projection should clear unread result activity for the active tab."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    unread: set[str] = {"wf-a"}
    tab_updates: list[tuple[str, bool]] = []

    def mark_seen(workflow_id: str) -> bool:
        """Record seen workflow activity and report whether unread state changed."""

        if workflow_id not in unread:
            return False
        unread.remove(workflow_id)
        return True

    view.workflow_activity_service = SimpleNamespace(mark_seen=mark_seen)
    view.workflow_tabbar.set_workflow_unread_result = lambda workflow_id, state: (
        tab_updates.append((workflow_id, state))
    )

    mod.WorkflowWorkspaceCoordinator(view).project_workflow(
        "wf-a",
        force_refresh=True,
    )

    assert tab_updates == [("wf-a", False)]


def test_clean_workflow_tab_activation_clears_unread_activity() -> None:
    """Clean tab selection should clear unread badges without heavy refresh."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    unread: set[str] = {"wf-b"}
    tab_updates: list[tuple[str, bool]] = []

    def mark_seen(workflow_id: str) -> bool:
        """Mark unread workflow activity as seen."""

        if workflow_id not in unread:
            return False
        unread.remove(workflow_id)
        return True

    view.workflow_activity_service = SimpleNamespace(mark_seen=mark_seen)
    view.workflow_tabbar.set_workflow_unread_result = lambda workflow_id, state: (
        tab_updates.append((workflow_id, state))
    )

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert tab_updates == [("wf-b", False)]
    assert "refresh" not in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert scheduler.requests == []


def test_project_workflow_restores_workflow_layout_before_projection() -> None:
    """Workflow projection should leave Settings layout before showing workflow panes."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    mod.WorkflowWorkspaceCoordinator(view).project_workflow(
        "wf-a",
        force_refresh=True,
    )

    assert view.calls.index("route:workflow") < view.calls.index(
        f"cube:set:{id(view.cube_stacks['wf-a'])}"
    )
    assert view.calls.index("route:workflow") < view.calls.index("canvas:project:wf-a")
