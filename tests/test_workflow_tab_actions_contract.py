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

"""Contract tests for workflow workspace lifecycle coordination."""

from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowRecord,
    ClosedWorkflowSnapshotService,
    WorkflowDuplicateService,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    WorkflowSnapshot,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)

_WINDOWS_XDIST_QT_SKIP = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="Qt icon fallback identity is not stable under Windows xdist workers",
)


def _import_module() -> Any:
    """Import the workflow workspace coordinator module."""

    return importlib.import_module(
        "substitute.presentation.shell.workflow_workspace_coordinator"
    )


class _TabItem:
    """Workflow-tab item double with mutable text and route key."""

    def __init__(self, route_key: str, text: str | None = None) -> None:
        """Store route key and label text."""

        self._route_key = route_key
        self._text = text or route_key

    def routeKey(self) -> str:
        """Return the current route key."""

        return self._route_key

    def text(self) -> str:
        """Return the current label text."""

        return self._text

    def setText(self, text: str) -> None:
        """Record text updates."""

        self._text = text

    def setRouteKey(self, key: str) -> None:
        """Record route-key updates."""

        self._route_key = key


class _TabBar:
    """Workflow tabbar double with workflow-id silent operations."""

    def __init__(self, workflow_ids: list[str]) -> None:
        """Create tab items for ids."""

        self.items = [_TabItem(workflow_id) for workflow_id in workflow_ids]
        self.itemMap = {item.routeKey(): item for item in self.items}
        self.selected: list[tuple[str, bool]] = []
        self.removed: list[tuple[str, bool]] = []

    def addTab(self, routeKey: str, text: str) -> _TabItem:
        """Add and return a workflow tab item."""

        item = _TabItem(routeKey, text)
        self.items.append(item)
        self.itemMap[routeKey] = item
        return item

    def insertTab(self, index: int, routeKey: str, text: str) -> _TabItem:
        """Insert and return a workflow tab item."""

        item = _TabItem(routeKey, text)
        self.items.insert(index, item)
        self.itemMap[routeKey] = item
        return item

    def count(self) -> int:
        """Return current tab count."""

        return len(self.items)

    def currentIndex(self) -> int:
        """Return the first selected tab index for legacy fallback."""

        if not self.items:
            return -1
        if not self.selected:
            return 0
        selected_id = self.selected[-1][0]
        return self.items.index(self.itemMap[selected_id])

    def tabItem(self, index: int) -> _TabItem:
        """Return tab item at index."""

        return self.items[index]

    def workflow_ids_in_order(self) -> list[str]:
        """Return current tab ids in order."""

        return [item.routeKey() for item in self.items]

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record tab selection."""

        self.selected.append((workflow_id, emit))

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record and apply tab removal."""

        self.removed.append((workflow_id, emit))
        tab_item = self.itemMap.pop(workflow_id)
        self.items.remove(tab_item)


class _Manager:
    """Override-manager double recording lifecycle calls."""

    def __init__(self, workflow_id: str, calls: list[str]) -> None:
        """Store workflow id and shared call log."""

        self._workflow_id = workflow_id
        self._calls = calls

    def _clear_all_override_widgets(self) -> None:
        """Record toolbar clearing."""

        self._calls.append(f"{self._workflow_id}:clear")

    def detach_override_widgets(self) -> None:
        """Record toolbar detachment."""

        self._calls.append(f"{self._workflow_id}:detach")

    def sync_state_from_workflow(self) -> None:
        """Record per-workflow override state projection."""

        self._calls.append(f"{self._workflow_id}:sync")

    def rebuild_override_menu(self) -> None:
        """Record per-workflow override menu projection."""

        self._calls.append(f"{self._workflow_id}:menu")

    def rebuild_active_override_controls(self) -> None:
        """Record per-workflow override toolbar projection."""

        self._calls.append(f"{self._workflow_id}:controls")

    def dispose(self) -> None:
        """Record manager disposal."""

        self._calls.append(f"{self._workflow_id}:dispose")


class _CubeStack:
    """Cube-stack double recording tab materialization."""

    def __init__(self, label: str, calls: list[str]) -> None:
        """Store label and mutable tab collection."""

        self._label = label
        self._calls = calls
        self.tabs: list[dict[str, object]] = []
        self.current_index: int | None = None

    def clear(self) -> None:
        """Clear recorded tabs."""

        self.tabs.clear()
        self._calls.append(f"{self._label}:clear")

    def count(self) -> int:
        """Return recorded tab count."""

        return len(self.tabs)

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert and record one tab."""

        tab = {"routeKey": routeKey, "text": text, "icon": icon}
        self.tabs.insert(index, tab)
        self._calls.append(f"{self._label}:insert:{routeKey}:{text}")
        return tab

    def setCurrentIndex(self, index: int) -> None:
        """Record selected tab index."""

        self.current_index = index
        self._calls.append(f"{self._label}:current:{index}")

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record one tab icon update."""

        self.tabs[index]["icon"] = icon
        self._calls.append(f"{self._label}:icon:{index}:{icon}")

    def deleteLater(self) -> None:
        """Record deletion."""

        self._calls.append(f"{self._label}:delete")


class _ProjectionAwareEditorPanel:
    """Editor-panel double exposing projection-cleanliness APIs."""

    def __init__(self, *, clean: bool) -> None:
        """Store whether the panel should report a clean projection."""

        self.clean = clean
        self.signature_requests: list[dict[str, object]] = []

    def current_projection_signature(self, **kwargs: object) -> object:
        """Return a signature token for requested projection inputs."""

        self.signature_requests.append(kwargs)
        return "signature"

    def is_projection_clean(self, signature: object) -> bool:
        """Return configured cleanliness for the supplied signature."""

        return signature == "signature" and self.clean

    def clear_model_field_load_progress(self) -> None:
        """Accept generation-feedback progress cleanup."""

    def deleteLater(self) -> None:
        """Provide lifecycle compatibility for coordinator disposal."""


def _deletable(label: str, calls: list[str]) -> SimpleNamespace:
    """Return a widget double with delete recording."""

    return SimpleNamespace(
        clear_model_field_load_progress=lambda: calls.append(f"{label}:model:clear"),
        deleteLater=lambda: calls.append(f"{label}:delete"),
    )


class _SnapshotCapture:
    """Capture close-time workflow snapshot calls for coordinator tests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared call log."""

        self._calls = calls

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return an adapter-provided workflow label."""

        self._calls.append(f"snapshot:label:{workflow_id}")
        return f"Snapshot {workflow_id}"

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return an adapter-provided active cube alias."""

        self._calls.append(f"snapshot:active-cube:{workflow_id}")
        return "SnapshotCube"

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return no viewport while recording the adapter call."""

        self._calls.append(f"snapshot:viewport:{workflow_id}")
        return None

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return no input images while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:input-images:{workflow_id}")
        return ()

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return no input masks while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:input-masks:{workflow_id}")
        return ()

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return no output images while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:output-images:{workflow_id}")
        return ()


def _build_view(
    *,
    active_workflow_id: str = "wf-a",
    closed_workflow_buffer: ClosedWorkflowBuffer | None = None,
    closed_workflow_snapshot_service: object | None = None,
) -> SimpleNamespace:
    """Build coordinator view double with two workflow states."""

    calls: list[str] = []
    session = WorkflowSessionService(WorkflowState, default_workflow_id="wf-a")
    session.add_workflow("wf-b")
    if active_workflow_id != "wf-a":
        session.activate_workflow(active_workflow_id)

    tabbar = _TabBar(["wf-a", "wf-b"])
    reopen_enabled_states: list[bool] = []

    def refresh_active_workflow_surface(**kwargs: object) -> None:
        """Record refresh and run optional completion callback."""

        calls.append("refresh")
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    def create_new_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create workflow UI doubles and record the request."""

        calls.append(f"create:{workflow_id}:{set_as_current}")
        return (
            _deletable(f"{workflow_id}:cube", calls),
            _deletable(f"{workflow_id}:editor", calls),
        )

    view = SimpleNamespace(
        calls=calls,
        closed_workflow_buffer=closed_workflow_buffer or ClosedWorkflowBuffer(),
        closed_workflow_snapshot_service=(
            closed_workflow_snapshot_service or ClosedWorkflowSnapshotService()
        ),
        workflow_tab_service=WorkflowTabService(),
        workflow_session_service=session,
        workflow_tabbar=tabbar,
        cube_stacks={
            "wf-a": _deletable("wf-a:cube", calls),
            "wf-b": _deletable("wf-b:cube", calls),
        },
        editor_panels={
            "wf-a": _deletable("wf-a:editor", calls),
            "wf-b": _deletable("wf-b:editor", calls),
        },
        override_managers={
            "wf-a": _Manager("wf-a", calls),
            "wf-b": _Manager("wf-b", calls),
        },
        cube_stack_container=SimpleNamespace(
            setCurrentWidget=lambda widget: calls.append(f"cube:set:{id(widget)}"),
            removeWidget=lambda widget: calls.append(f"cube:remove:{id(widget)}"),
        ),
        editor_panel_container=SimpleNamespace(
            setCurrentWidget=lambda widget: calls.append(f"editor:set:{id(widget)}"),
            removeWidget=lambda widget: calls.append(f"editor:remove:{id(widget)}"),
        ),
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: calls.append(
                f"canvas:project:{workflow_id}"
            ),
        ),
        output_canvas_projection_coordinator=SimpleNamespace(
            prune_closed_workflow_images=(
                lambda _workflow_id, _closed, _remaining: calls.append("canvas:prune")
            ),
        ),
        input_canvas_state_service=SimpleNamespace(
            prune_closed_workflow_images=(
                lambda _closed, _remaining: calls.append("input:prune")
            ),
        ),
        workflow_ui_factory=SimpleNamespace(create_workflow_ui=create_new_workflow_ui),
        _pending_restored_workflow_snapshots={},
        _clear_all_model_field_load_progress=lambda: calls.append("model:clear"),
        generation_action_controller=SimpleNamespace(
            project_active_workflow_progress=lambda: calls.append("progress:project")
        ),
        workflow_progress_service=SimpleNamespace(
            remove_workflow=lambda workflow_id: calls.append(
                f"progress:remove:{workflow_id}"
            ),
            rename_workflow=lambda old, new: calls.append(
                f"progress:rename:{old}:{new}"
            ),
        ),
        refresh_active_workflow_surface=refresh_active_workflow_surface,
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        reopen_enabled_states=reopen_enabled_states,
        shell_frame_integration_controller=SimpleNamespace(
            set_reopen_closed_workflow_enabled=reopen_enabled_states.append,
        ),
        settings_route_controller=SimpleNamespace(
            show_workflow_workspace=lambda: calls.append("route:workflow"),
        ),
    )
    return view


class _DeferredSurfaceRefreshScheduler:
    """Surface-refresh scheduler double that records deferred requests."""

    def __init__(self) -> None:
        """Initialize an empty request log."""

        self.requests: list[dict[str, object]] = []

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: object = None,
    ) -> None:
        """Record one deferred surface refresh request."""

        self.requests.append(
            {
                "workflow_id": workflow_id,
                "force_refresh": force_refresh,
                "reason": reason,
                "on_complete": on_complete,
            }
        )

    def cancel(self, workflow_id: str | None = None) -> None:
        """Remove pending requests for one workflow or all workflows."""

        if workflow_id is None:
            self.requests.clear()
            return
        self.requests = [
            request
            for request in self.requests
            if request["workflow_id"] != workflow_id
        ]


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


def test_duplicate_workflow_registers_cloned_state_and_projects_unique_tab(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating should register cloned workflow state and project the new tab."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view.workflow_tabbar.itemMap["wf-a"].setText("Recipe")
    cloned_workflow = WorkflowState(metadata={"title": "Cloned"})

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create workflow-scoped doubles for the duplicated workflow."""

        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = _deletable(f"{workflow_id}:editor", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return cube_stack, editor_panel

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_workspace_coordinator",
    )

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    assert duplicated_id not in {"wf-a", "wf-b"}
    assert view.workflow_session_service.workflows[duplicated_id] is cloned_workflow
    assert view.workflow_session_service.active_workflow_id == duplicated_id
    assert view.workflow_tabbar.itemMap[duplicated_id].text() == "Recipe (2)"
    assert view.workflow_tabbar.selected[-1] == (duplicated_id, False)
    assert f"create:{duplicated_id}:True" in view.calls
    assert f"canvas:project:{duplicated_id}" in view.calls
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs == []
    assert view.workflow_session_service.workflows["wf-a"] is not cloned_workflow
    assert "Workflow duplicate coordinator started" in caplog.text
    assert "Workflow duplicate tab planned" in caplog.text
    assert "Workflow duplicate existing workflow registered" in caplog.text
    assert "Workflow duplicate UI created" in caplog.text
    assert "Workflow duplicate cube-stack materialization started" in caplog.text
    assert "Workflow duplicate projection started" in caplog.text
    assert "Workflow duplicate projection completed" in caplog.text
    assert "Workflow duplicate coordinator completed" in caplog.text


def test_duplicate_workflow_missing_source_is_noop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating should not create UI state when the source workflow is missing."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_workspace_coordinator",
    )

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "missing",
        WorkflowState(),
        base_label="Recipe",
    )

    assert duplicated_id is None
    assert set(view.workflow_session_service.workflows) == {"wf-a", "wf-b"}
    assert view.workflow_tabbar.workflow_ids_in_order() == ["wf-a", "wf-b"]
    assert (
        "Skipped workflow duplication because source workflow was missing"
        in caplog.text
    )
    assert "source_workflow_id=missing" in caplog.text


@_WINDOWS_XDIST_QT_SKIP
def test_duplicate_workflow_preserves_asset_metadata_and_resets_live_canvas() -> None:
    """Duplication should preserve durable state without copying live canvas UUIDs."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    source_workflow = view.workflow_session_service.workflows["wf-a"]
    source_workflow.cubes["CubeA"] = CubeState(
        cube_id="Owner/Repo/CubeA.cube",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {"Load": {"inputs": {"image": "old.png"}}}},
        buffer={
            "nodes": {
                "Load": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "assets/input.png"},
                },
            }
        },
    )
    source_workflow.stack_order.append("CubeA")
    source_workflow.metadata["asset_refs"] = {
        "input_images": {
            "CubeA:Load": {
                "kind": "project_asset",
                "relative_path": "assets/input.png",
            },
        },
        "input_masks": {
            "CubeA:Mask": {
                "kind": "project_mask",
                "relative_path": "mask.png",
            },
        },
    }
    image_id = uuid4()
    source_workflow.canvas.input_key_map["CubeA:Load"] = image_id
    source_workflow.canvas.input_image_uuid = image_id

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create workflow-scoped doubles for the duplicated workflow."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = _deletable(f"{workflow_id}:editor", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return cube_stack, editor_panel

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    cloned_workflow = WorkflowDuplicateService().duplicate_workflow(source_workflow)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate = view.workflow_session_service.workflows[duplicated_id]
    assert duplicate.metadata == source_workflow.metadata
    assert duplicate.cubes["CubeA"].buffer == source_workflow.cubes["CubeA"].buffer
    assert duplicate.cubes["CubeA"].buffer is not source_workflow.cubes["CubeA"].buffer
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs[0]["routeKey"] == "CubeA"
    assert duplicate_stack.tabs[0]["text"] == "CubeA"
    duplicate_icon = cast(AppIcon, duplicate_stack.tabs[0]["icon"])
    assert duplicate_icon.value == AppIcon.CUBE_20_FILLED.value
    assert duplicate_stack.current_index == 0
    duplicate_buffer = cast(dict[str, Any], duplicate.cubes["CubeA"].buffer)
    duplicate_nodes = cast(dict[str, Any], duplicate_buffer["nodes"])
    duplicate_load = cast(dict[str, Any], duplicate_nodes["Load"])
    duplicate_inputs = cast(dict[str, Any], duplicate_load["inputs"])
    duplicate_inputs["image"] = "assets/changed.png"
    source_buffer = cast(dict[str, Any], source_workflow.cubes["CubeA"].buffer)
    source_nodes = cast(dict[str, Any], source_buffer["nodes"])
    source_load = cast(dict[str, Any], source_nodes["Load"])
    source_inputs = cast(dict[str, Any], source_load["inputs"])
    assert source_inputs["image"] == "assets/input.png"
    assert duplicate.canvas.input_key_map == {}
    assert duplicate.canvas.input_image_uuid is None


def test_duplicate_workflow_materializes_cube_stack_icons() -> None:
    """Duplicated cube-stack tabs should receive resolved cube icons."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    icon_calls: list[dict[str, object]] = []

    def icon_for_cube(**kwargs: object) -> str:
        """Record icon resolution context and return a fake icon."""

        icon_calls.append(kwargs)
        return "cube-icon"

    view.cube_icon_factory = SimpleNamespace(icon_for_cube=icon_for_cube)
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
                display_name="Cube A",
                ui={"cube_icon": "icon-descriptor"},
            )
        },
        stack_order=["CubeA"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create duplicate UI with cube stack that records icons."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = _deletable(
            f"{workflow_id}:editor", view.calls
        )
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return cube_stack, view.editor_panels[workflow_id]

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs == [
        {"routeKey": "CubeA", "text": "CubeA", "icon": "cube-icon"}
    ]
    assert icon_calls == [
        {
            "cube_id": "Owner/Repo/CubeA.cube",
            "display_name": "Cube A",
            "icon": "icon-descriptor",
            "catalog_revision": "",
            "cube_content_hash": "",
        }
    ]


@_WINDOWS_XDIST_QT_SKIP
def test_duplicate_workflow_applies_fallback_icon_when_resolution_fails() -> None:
    """Duplicated cube-stack tabs should never finish without an icon."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    def _raise_icon_error(**_kwargs: object) -> object:
        """Raise an expected icon resolution failure."""

        raise ValueError("bad descriptor")

    view.cube_icon_factory = SimpleNamespace(icon_for_cube=_raise_icon_error)
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
                display_name="Cube A",
                ui={"cube_icon": "icon-descriptor"},
            )
        },
        stack_order=["CubeA"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create duplicate UI with cube stack that records icons."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = _deletable(
            f"{workflow_id}:editor", view.calls
        )
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return cube_stack, view.editor_panels[workflow_id]

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs[0]["routeKey"] == "CubeA"
    assert duplicate_stack.tabs[0]["text"] == "CubeA"
    duplicate_icon = cast(AppIcon, duplicate_stack.tabs[0]["icon"])
    assert duplicate_icon.value == AppIcon.CUBE_20_FILLED.value


def test_duplicate_workflow_projects_cloned_cube_metadata_tooltip() -> None:
    """Duplicated workflow cube stacks should keep rich metadata tooltips."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    class _PresentingCubeStack(_CubeStack):
        def setTabPresentation(
            self,
            index: int,
            *,
            primary_text: str,
            secondary_text: str,
            tooltip_text: str,
        ) -> None:
            """Record complete cube tab presentation metadata."""

            self.tabs[index]["text"] = primary_text
            self.tabs[index]["secondary_text"] = secondary_text
            self.tabs[index]["tooltip_text"] = tooltip_text

    cloned_workflow = WorkflowState(
        cubes={
            "Workflow Alias": CubeState(
                cube_id="ArtificialSweetener/Base-Cubes/Upscale.cube",
                version="2.0.0",
                alias="Workflow Alias",
                original_cube={},
                buffer={},
                display_name="Diffusion Upscale",
                ui={
                    "canonical_cube": {
                        "cube_id": "ArtificialSweetener/Base-Cubes/Upscale.cube",
                        "version": "2.0.0",
                        "description": "Upscales images with stable defaults.",
                        "metadata": {
                            "default_alias": "Diffusion Upscale",
                            "supported_models": ["SDXL 1.0"],
                            "tags": ["upscale"],
                        },
                    },
                    "source": {"repo_ref": "ArtificialSweetener/Base-Cubes"},
                },
            )
        },
        stack_order=["Workflow Alias"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create duplicate UI with presentation-recording cube stack."""

        del set_as_current
        cube_stack = _PresentingCubeStack(f"{workflow_id}:cube", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = _deletable(
            f"{workflow_id}:editor", view.calls
        )
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return cube_stack, view.editor_panels[workflow_id]

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _PresentingCubeStack)
    tooltip = str(duplicate_stack.tabs[0]["tooltip_text"])
    assert "<b>Diffusion Upscale</b>, v2.0.0" in tooltip
    assert "Base-Cubes by ArtificialSweetener" in tooltip
    assert "<b>Supported models:</b> SDXL 1.0" in tooltip
    assert "<b>Description:</b> Upscales images" in tooltip
    assert "<b>Tags:</b> upscale" in tooltip


def test_duplicate_workflow_projects_cloned_cubes_into_active_editor() -> None:
    """Duplicating should refresh the new editor with cloned cube state."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
            ),
            "CubeB": CubeState(
                cube_id="Owner/Repo/CubeB.cube",
                version="1.0.0",
                alias="CubeB",
                original_cube={},
                buffer={},
            ),
        },
        stack_order=["CubeA", "CubeB"],
    )
    loaded: list[dict[str, object]] = []

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create duplicated workflow UI doubles with editor-load capture."""

        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = SimpleNamespace(
            load_all_cubes=lambda **kwargs: loaded.append(kwargs)
        )
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return cube_stack, editor_panel

    def _refresh_active_workflow_surface(**_kwargs: object) -> None:
        """Refresh active editor double from the active workflow session."""

        workflow_id = view.workflow_session_service.active_workflow_id
        workflow = view.workflow_session_service.workflows[workflow_id]
        editor_panel = view.editor_panels[workflow_id]
        editor_panel.load_all_cubes(
            cube_entries=[
                (alias, workflow.cubes[alias]) for alias in workflow.stack_order
            ],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
        )
        view.calls.append(f"refresh:{workflow_id}")

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    view.refresh_active_workflow_surface = _refresh_active_workflow_surface

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    assert len(loaded) == 1
    assert loaded[0]["cube_entries"] == [
        ("CubeA", cloned_workflow.cubes["CubeA"]),
        ("CubeB", cloned_workflow.cubes["CubeB"]),
    ]
    assert loaded[0]["cube_states"] is cloned_workflow.cubes
    assert loaded[0]["stack_order"] == cloned_workflow.stack_order
    assert view.calls.index(f"create:{duplicated_id}:True") < view.calls.index(
        f"canvas:project:{duplicated_id}"
    )


def test_active_workflow_close_projects_successor_without_final_toolbar_clear() -> None:
    """Closing active workflow should project successor once without clearing it after."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-b")

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "wf-a:clear" not in view.calls
    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert view.workflow_tabbar.removed == [("wf-b", False)]
    assert view.workflow_tabbar.selected == [("wf-a", False)]
    assert view.calls.count("refresh") == 1
    assert view.calls.count("canvas:project:wf-a") == 1
    assert "progress:remove:wf-b" in view.calls
    assert "progress:project" in view.calls
    assert "input:prune" not in view.calls
    assert "canvas:prune" not in view.calls
    assert "wf-b:dispose" in view.calls
    assert view.closed_workflow_buffer.summaries()[0].workflow_id == "wf-b"
    assert view.reopen_enabled_states[-1] is True


def test_inactive_workflow_close_leaves_active_surfaces_alone() -> None:
    """Closing inactive workflow should not refresh or reproject active workflow."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert "wf-a:clear" not in view.calls
    assert "refresh" not in view.calls
    assert "canvas:project:wf-a" not in view.calls
    assert view.workflow_tabbar.removed == [("wf-b", False)]
    assert view.closed_workflow_buffer.summaries()[0].workflow_id == "wf-b"
    assert view.reopen_enabled_states[-1] is True


def test_close_workflow_captures_snapshot_through_snapshot_adapter() -> None:
    """Closing a workflow should capture reopen state through the snapshot port."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view.session_snapshot_capture_adapter = _SnapshotCapture(view.calls)

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    record = view.closed_workflow_buffer.pop_latest()
    assert record is not None
    snapshot = view.closed_workflow_snapshot_service.decode(record.snapshot_payload)
    assert record.tab_label == "Snapshot wf-b"
    assert snapshot.tab_label == "Snapshot wf-b"
    assert snapshot.active_cube_alias == "SnapshotCube"
    assert "snapshot:label:wf-b" in view.calls
    assert "snapshot:active-cube:wf-b" in view.calls
    assert "snapshot:input-images:wf-b" in view.calls
    assert "snapshot:input-masks:wf-b" in view.calls
    assert "snapshot:output-images:wf-b" in view.calls
    assert "snapshot:viewport:wf-b" in view.calls


def test_close_workflow_cleans_evicted_buffer_records() -> None:
    """Closing workflows should prune older records evicted from the reopen buffer."""

    mod = _import_module()
    view = _build_view(
        active_workflow_id="wf-b",
        closed_workflow_buffer=ClosedWorkflowBuffer(budget_bytes=1400),
    )

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")
    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-a")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert [
        summary.workflow_id for summary in view.closed_workflow_buffer.summaries()
    ] == ["wf-a"]


def test_close_workflow_prunes_immediately_when_record_rejected() -> None:
    """Oversized close snapshots should fall back to immediate cleanup."""

    mod = _import_module()
    view = _build_view(closed_workflow_buffer=ClosedWorkflowBuffer(budget_bytes=1))

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert view.closed_workflow_buffer.summaries() == ()


class _FailingClosedWorkflowSnapshotService:
    """Snapshot service double that forces close-time capture failure."""

    def encode(self, _snapshot: object) -> bytes:
        """Raise during encoding to exercise close fallback cleanup."""

        raise ValueError("capture failed")


def test_close_workflow_prunes_immediately_when_snapshot_capture_fails() -> None:
    """Snapshot capture failures should not block normal workflow close cleanup."""

    mod = _import_module()
    view = _build_view(
        closed_workflow_snapshot_service=_FailingClosedWorkflowSnapshotService()
    )

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert view.closed_workflow_buffer.summaries() == ()


def _closed_record(
    *,
    workflow_id: str = "wf-closed",
    tab_label: str = "Closed Workflow",
    tab_index: int = 1,
    payload: bytes | None = None,
    workflow: WorkflowState | None = None,
) -> ClosedWorkflowRecord:
    """Build a closed workflow record for coordinator reopen tests."""

    if payload is None:
        snapshot = WorkflowSnapshot(
            workflow_id=workflow_id,
            tab_label=tab_label,
            workflow=workflow
            or WorkflowState(
                cubes={
                    "Demo": CubeState(
                        cube_id="demo",
                        version="1",
                        alias="Demo",
                        original_cube={},
                        buffer={"value": 1},
                    )
                },
                stack_order=["Demo"],
            ),
            active_cube_alias="Demo",
        )
        payload = ClosedWorkflowSnapshotService().encode(snapshot)
    return ClosedWorkflowRecord(
        close_id=f"close-{workflow_id}",
        workflow_id=workflow_id,
        tab_label=tab_label,
        tab_index=tab_index,
        snapshot_payload=payload,
        payload_size_bytes=len(payload),
        closed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_reopen_latest_closed_workflow_restores_session_workflow() -> None:
    """Reopening should register and activate the buffered workflow state."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record())
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is True
    assert "wf-closed" in view.workflow_session_service.workflows
    assert view.workflow_session_service.active_workflow_id == "wf-closed"
    assert view.workflow_tabbar.itemMap["wf-closed"].text() == "Closed Workflow"
    assert view.reopen_enabled_states[-1] is False


def test_reopen_latest_closed_workflow_uses_preferred_tab_index() -> None:
    """Reopening should insert the tab near its stored close-time index."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(workflow_id="wf-closed", tab_index=1))
    view = _build_view(closed_workflow_buffer=buffer)

    mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert view.workflow_tabbar.workflow_ids_in_order() == [
        "wf-a",
        "wf-closed",
        "wf-b",
    ]


def test_reopen_latest_closed_workflow_returns_false_when_empty() -> None:
    """Empty closed workflow buffers should make reopen a no-op."""

    mod = _import_module()
    view = _build_view()

    assert (
        mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow() is False
    )
    assert view.workflow_session_service.active_workflow_id == "wf-a"


def test_reopen_latest_closed_workflow_rekeys_on_id_collision() -> None:
    """Reopening should not overwrite an already-open workflow id."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(workflow_id="wf-b", tab_label="Old B"))
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is True
    assert "wf-b" in view.workflow_session_service.workflows
    assert "wf-b_reopened" in view.workflow_session_service.workflows
    assert view.workflow_session_service.active_workflow_id == "wf-b_reopened"
    assert view.workflow_tabbar.itemMap["wf-b_reopened"].text() == "Old B"


def test_reopen_latest_closed_workflow_drops_corrupt_payload_without_crash() -> None:
    """Corrupt buffered payloads should fail gracefully and leave session unchanged."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(payload=b"not json"))
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is False
    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert buffer.summaries() == ()
    assert view.reopen_enabled_states[-1] is False


def test_reopen_latest_closed_workflow_projects_once() -> None:
    """Reopening should project the restored active workflow once."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record())
    view = _build_view(closed_workflow_buffer=buffer)

    mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert view.calls.count("canvas:project:wf-closed") == 1


def test_rejected_inline_rename_restores_old_label() -> None:
    """Rejected inline renames should restore the existing workflow label."""

    mod = _import_module()
    view = _build_view()

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow("wf-a", "bad/name")

    assert view.workflow_tabbar.itemMap["wf-a"].text() == "wf-a"


def test_accepted_inline_rename_rekeys_workflow_progress() -> None:
    """Accepted workflow renames should move runtime progress ownership."""

    mod = _import_module()
    view = _build_view()

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow(
        "wf-a",
        "Renamed Workflow",
    )

    assert "progress:rename:wf-a:Renamed Workflow" in view.calls
