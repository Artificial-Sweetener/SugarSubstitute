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

"""Workflow activation and profiling contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _DeferredSurfaceRefreshScheduler,
    _build_view,
)


def test_same_workflow_activation_is_idempotent() -> None:
    """Activating current workflow should not clear or project active surfaces."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    mod.WorkflowWorkspaceCoordinator(view).activate_workflow("wf-a")

    assert view.calls == []


def test_same_workflow_activation_reprojects_after_settings_route() -> None:
    """Returning from Settings should sync shared canvas without editor refresh."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view._active_workspace_route = "settings"
    scheduler = _DeferredSurfaceRefreshScheduler()

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-a")

    assert view._active_workspace_route == "wf-a"
    assert view.workflow_tabbar.selected == [("wf-a", False)]
    assert "canvas:project:wf-a" in view.calls
    assert "refresh" not in view.calls
    assert scheduler.requests == []


def test_clean_workflow_tab_activation_swaps_route_without_surface_refresh() -> None:
    """Clean workflow tab activation should swap widgets and sync shared canvas."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert view.workflow_session_service.active_workflow_id == "wf-b"
    assert view.workflow_tabbar.selected == [("wf-b", False)]
    assert f"cube:set:{id(view.cube_stacks['wf-b'])}" in view.calls
    assert f"editor:set:{id(view.editor_panels['wf-b'])}" in view.calls
    assert "position" in view.calls
    assert "refresh" not in view.calls
    assert "canvas:project:wf-b" in view.calls
    assert "progress:project" in view.calls
    assert scheduler.requests == []


def test_clean_workflow_tab_activation_projects_per_workflow_override_toolbar() -> None:
    """Clean tab selection should rebuild shared override toolbar for the selected tab."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert view.calls.index("wf-a:detach") < view.calls.index("wf-b:sync")
    assert "wf-a:clear" not in view.calls
    assert view.calls.index("editor:set:" + str(id(view.editor_panels["wf-b"]))) < (
        view.calls.index("wf-b:sync")
    )
    assert "wf-b:menu" in view.calls
    assert "wf-b:controls" in view.calls
    assert scheduler.requests == []


def test_clean_workflow_tab_activation_records_profile_diagnostic() -> None:
    """Clean workflow tab activation should expose non-fragile profile fields."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    coordinator = mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    )

    coordinator.activate_workflow("wf-b")

    diagnostic = coordinator.last_tab_switch_diagnostic
    assert diagnostic is not None
    assert diagnostic.workflow_id == "wf-b"
    assert diagnostic.source == "workflow_tab"
    assert diagnostic.active_workflow_update_elapsed_ms >= 0.0
    assert diagnostic.route_projection_elapsed_ms >= 0.0
    assert diagnostic.canvas_projection_elapsed_ms >= 0.0
    assert diagnostic.ensure_workflow_ui_elapsed_ms >= 0.0
    assert diagnostic.show_route_elapsed_ms >= 0.0
    assert diagnostic.tab_select_elapsed_ms >= 0.0
    assert diagnostic.cube_stack_swap_elapsed_ms >= 0.0
    assert diagnostic.editor_panel_swap_elapsed_ms >= 0.0
    assert diagnostic.override_projection_elapsed_ms >= 0.0
    assert diagnostic.input_canvas_availability_elapsed_ms >= 0.0
    assert diagnostic.overlay_refresh_elapsed_ms >= 0.0
    assert diagnostic.activity_badge_elapsed_ms >= 0.0
    assert not diagnostic.widgets_created
    assert not diagnostic.editor_rebuilt
    assert diagnostic.deferred_requests == 0


def test_env_gated_workflow_tab_perf_writes_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Enabled live tab-switch diagnostics should append JSONL performance rows."""

    mod = _import_module()
    output_path = tmp_path / "tab-switches.jsonl"
    monkeypatch.setenv("SUGARSUBSTITUTE_WORKFLOW_TAB_PERF", "1")
    monkeypatch.setenv("SUGARSUBSTITUTE_WORKFLOW_TAB_PERF_PATH", str(output_path))
    view = _build_view(active_workflow_id="wf-a")

    mod.WorkflowWorkspaceCoordinator(view).activate_workflow("wf-b")

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["workflow_id"] == "wf-b"
    assert rows[0]["source"] == "workflow_tab"
    assert rows[0]["route_projection_elapsed_ms"] >= 0.0
    assert rows[0]["canvas_projection_elapsed_ms"] >= 0.0
    assert rows[0]["ensure_workflow_ui_elapsed_ms"] >= 0.0
    assert rows[0]["show_route_elapsed_ms"] >= 0.0
    assert rows[0]["tab_select_elapsed_ms"] >= 0.0
    assert rows[0]["cube_stack_swap_elapsed_ms"] >= 0.0
    assert rows[0]["editor_panel_swap_elapsed_ms"] >= 0.0
    assert rows[0]["override_projection_elapsed_ms"] >= 0.0
    assert rows[0]["input_canvas_availability_elapsed_ms"] >= 0.0
    assert rows[0]["overlay_refresh_elapsed_ms"] >= 0.0
    assert rows[0]["activity_badge_elapsed_ms"] >= 0.0
    assert rows[0]["overrides_projected"] is True
    assert rows[0]["editor_rebuilt"] is False
    assert rows[0]["deferred_requests"] == 0
    assert "captured_at" in rows[0]


def test_clean_workflow_tab_activation_preserves_widget_identity() -> None:
    """Clean tab switches should reuse existing workflow widgets."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    scheduler = _DeferredSurfaceRefreshScheduler()
    cube_stack = view.cube_stacks["wf-b"]
    editor_panel = view.editor_panels["wf-b"]

    mod.WorkflowWorkspaceCoordinator(
        view,
        surface_refresh_scheduler=scheduler,
    ).activate_workflow("wf-b")

    assert view.cube_stacks["wf-b"] is cube_stack
    assert view.editor_panels["wf-b"] is editor_panel
    assert not any(call.startswith("create:wf-b") for call in view.calls)
    assert "canvas:project:wf-b" in view.calls
    assert scheduler.requests == []
