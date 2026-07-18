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

"""Contract tests for workflow surface reconciliation policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtCore import QTimer

from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
    WorkflowSurfaceReconciler,
    active_workflow_surface_refresher_for,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)


class _SessionPort:
    """Session-state port double for reconciler tests."""

    def __init__(self, active_workflow_id: str = "wf-a") -> None:
        """Store active workflow id and workflow mapping."""

        self._active_workflow_id = active_workflow_id
        self._workflows: Mapping[str, object] = {
            "wf-a": object(),
            "wf-b": object(),
        }

    @property
    def active_workflow_id(self) -> str:
        """Return active workflow id."""

        return self._active_workflow_id

    @property
    def workflows(self) -> Mapping[str, object]:
        """Return workflow state by id."""

        return self._workflows


class _CanvasPort:
    """Canvas port double recording route projection."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS

    def project_workflow_canvas(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record one canvas projection."""

        self._calls.append(f"canvas:{workflow_id}")
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=self.status,
            operation="project_workflow_canvas",
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )

    def refresh_input_canvas_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record input-canvas availability refresh."""

        self._calls.append(f"canvas-input:{workflow_id}")
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_input_canvas_availability",
            elapsed_ms=1.0,
        )


class _EditorPort:
    """Editor port double controlling projection results."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS
        self.call_complete = True

    def current_projection_state(
        self,
        workflow_id: str,
    ) -> WorkflowSurfaceLifecycleState:
        """Return a clean state for simple tests."""

        del workflow_id
        return WorkflowSurfaceLifecycleState.CLEAN

    def refresh_editor_surface(
        self,
        workflow_id: str,
        *,
        force: bool,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> SurfaceRefreshResult:
        """Record editor refresh and optionally complete synchronously."""

        self._calls.append(f"editor:{workflow_id}:{force}")
        result = surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.EDITOR,
            status=self.status,
            operation="refresh_editor_surface",
            elapsed_ms=1.0,
            cleanable=self.status
            in {SurfaceRefreshStatus.SUCCESS, SurfaceRefreshStatus.SKIPPED_CLEAN},
        )
        if on_complete is not None and self.call_complete:
            on_complete(result)
        return result

    def refresh_clean_editor_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh a clean editor projection."""

        return self.refresh_editor_surface(
            workflow_id,
            force=False,
            on_complete=None,
        )


class _OverridePort:
    """Override port double recording override reconciliation."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS
        self.schedule_status = SurfaceRefreshStatus.SUCCESS

    def last_materialized_defaults(self, workflow_id: str) -> bool:
        """Return no default materialization for tests."""

        del workflow_id
        return False

    def sync_override_state(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record override state sync."""

        return self._result(workflow_id, "override-sync")

    def apply_overrides_before_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record pre-projection override apply."""

        return self._result(workflow_id, "override-pre")

    def materialize_default_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record default override materialization."""

        return self._result(workflow_id, "override-defaults")

    def apply_overrides_after_projection(
        self,
        workflow_id: str,
        *,
        materialized_defaults: bool,
    ) -> SurfaceRefreshResult:
        """Record post-projection override apply."""

        self._calls.append(f"override-post-defaults:{materialized_defaults}")
        return self._result(workflow_id, "override-post")

    def schedule_override_presentation_rebuild(
        self,
        workflow_id: str,
        token: ReconciliationToken,
        on_complete: Callable[[SurfaceRefreshResult], None] | None = None,
    ) -> SurfaceRefreshResult:
        """Record override rebuild scheduling and complete synchronously."""

        self._calls.append(f"override-schedule:{token.generation}")
        result = surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=self.schedule_status,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=1.0,
            cleanable=self.schedule_status is SurfaceRefreshStatus.SUCCESS,
        )
        if on_complete is not None:
            on_complete(result)
        return result

    def _result(self, workflow_id: str, operation: str) -> SurfaceRefreshResult:
        """Return configured override result for one operation."""

        self._calls.append(operation)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=self.status,
            operation=operation,
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )


class _GenerationPort:
    """Generation availability port double recording refreshes."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS

    def refresh_generation_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record generation availability refresh."""

        return self._result(workflow_id, "generation")

    def refresh_input_availability(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record input availability refresh."""

        return self._result(workflow_id, "input")

    def _result(self, workflow_id: str, operation: str) -> SurfaceRefreshResult:
        """Return configured generation result."""

        self._calls.append(operation)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            status=self.status,
            operation=operation,
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )


def _build_reconciler(
    invalidation: WorkflowSurfaceInvalidationService,
    *,
    active_workflow_id: str = "wf-a",
) -> tuple[
    WorkflowSurfaceReconciler,
    list[str],
    _CanvasPort,
    _EditorPort,
    _OverridePort,
    _GenerationPort,
]:
    """Build a reconciler and expose its fake ports."""

    calls: list[str] = []
    canvas = _CanvasPort(calls)
    editor = _EditorPort(calls)
    overrides = _OverridePort(calls)
    generation = _GenerationPort(calls)
    reconciler = WorkflowSurfaceReconciler(
        _SessionPort(active_workflow_id),
        canvas_port=canvas,
        editor_port=editor,
        override_port=overrides,
        generation_port=generation,
        surface_invalidation_service=invalidation,
    )
    return reconciler, calls, canvas, editor, overrides, generation


class _GenerationActionCluster:
    """Record projected generation titlebar presentations."""

    def __init__(self) -> None:
        """Initialize with no projected presentations."""

        self.presentations: list[GenerationActionPresentation] = []

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one generated titlebar presentation."""

        self.presentations.append(presentation)


def _active_surface_shell(
    *,
    workflow_id: str,
    workflow: object,
    editor_panel: object,
    override_manager: object,
) -> SimpleNamespace:
    """Build a shell fake exposing active workflow surface collaborators."""

    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows={workflow_id: workflow},
        ),
        get_active_workflow=lambda: workflow,
        active_editor_panel=editor_panel,
        editor_panels={workflow_id: editor_panel},
        active_override_manager=override_manager,
        override_managers={workflow_id: override_manager},
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, _workflow_id: None
        ),
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: None
        ),
        generationActionCluster=_GenerationActionCluster(),
        generation_titlebar_control_registry=None,
        _current_generate_mode="generate",
        _backend_state="ready",
        _active_workspace_route=workflow_id,
        _detached_for_gui_reload=False,
        workspace_generation_controller=SimpleNamespace(is_continuous_active=False),
        generation_job_queue_service=SimpleNamespace(
            has_active_job=lambda: False,
            has_cancellable_jobs=lambda: False,
            jobs=lambda: (),
        ),
        generation_queue_controller=SimpleNamespace(panel_visible=False),
    )
    shell.generation_action_controller = GenerationActionController(shell)
    return shell


def _record_bool(calls: list[str], label: str, result: bool) -> bool:
    """Record an action label and return a configured boolean result."""

    calls.append(label)
    return result


def test_full_reconciliation_refreshes_then_projects_canvas() -> None:
    """Full reconciliation should refresh editor and project shared canvas."""

    invalidation = WorkflowSurfaceInvalidationService()
    reconciler, calls, *_ports = _build_reconciler(invalidation)

    result = reconciler.reconcile_projected(
        "wf-a",
        force_refresh=True,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert calls[:3] == ["override-sync", "override-pre", "editor:wf-a:True"]
    assert "canvas:wf-a" in calls
    assert result.full_refresh
    assert result.canvas_projected
    assert invalidation.is_clean("wf-a")


def test_canvas_only_dirty_reconciliation_skips_editor_refresh() -> None:
    """Canvas-only dirtiness should not rebuild editor surfaces."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )
    reconciler, calls, *_ports = _build_reconciler(invalidation)

    result = reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert "editor:wf-a:False" not in calls
    assert calls == ["canvas:wf-a"]
    assert result.reconciled_surfaces == frozenset({WorkflowSurface.CANVAS})
    assert invalidation.is_clean("wf-a")


def test_override_only_dirty_reconciliation_waits_for_rebuild_success() -> None:
    """Override dirtiness should clean only after rebuild completion succeeds."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.OVERRIDES},
        WorkflowInvalidationReason.GLOBAL_OVERRIDES_CHANGED,
    )
    reconciler, calls, *_ports = _build_reconciler(invalidation)

    result = reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert "override-schedule:1" in calls
    assert "canvas:wf-a" not in calls
    assert result.reconciled_surfaces == frozenset({WorkflowSurface.OVERRIDES})
    assert invalidation.is_clean("wf-a")


def test_stale_reconciliation_marks_nothing_clean() -> None:
    """Stale scheduled work should not mutate shared UI or clean dirty state."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )
    reconciler, calls, *_ports = _build_reconciler(
        invalidation,
        active_workflow_id="wf-b",
    )

    result = reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert calls == []
    assert result.stale
    assert not invalidation.is_clean("wf-a")


def test_failed_canvas_projection_leaves_canvas_dirty() -> None:
    """Failed canvas projection should not mark canvas clean."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )
    reconciler, _calls, canvas, *_ports = _build_reconciler(invalidation)
    canvas.status = SurfaceRefreshStatus.FAILED

    result = reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert not result.canvas_projected
    assert WorkflowSurface.CANVAS in invalidation.dirty_state("wf-a").dirty_surfaces


def test_failed_editor_projection_leaves_editor_dirty() -> None:
    """Failed editor projection should not mark editor clean."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.EDITOR},
        WorkflowInvalidationReason.CUBE_LOADED,
    )
    reconciler, _calls, _canvas, editor, *_ports = _build_reconciler(invalidation)
    editor.status = SurfaceRefreshStatus.FAILED

    reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert WorkflowSurface.EDITOR in invalidation.dirty_state("wf-a").dirty_surfaces


def test_failed_override_rebuild_leaves_overrides_dirty() -> None:
    """Failed override rebuild should not mark overrides clean."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.OVERRIDES},
        WorkflowInvalidationReason.GLOBAL_OVERRIDES_CHANGED,
    )
    reconciler, _calls, _canvas, _editor, overrides, _generation = _build_reconciler(
        invalidation
    )
    overrides.schedule_status = SurfaceRefreshStatus.FAILED

    reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert WorkflowSurface.OVERRIDES in invalidation.dirty_state("wf-a").dirty_surfaces


def test_failed_generation_refresh_leaves_generation_dirty() -> None:
    """Failed generation availability refresh should not mark generation clean."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.GENERATION_AVAILABILITY},
        WorkflowInvalidationReason.NODE_DEFINITIONS_REFRESHED,
    )
    reconciler, _calls, _canvas, _editor, _overrides, generation = _build_reconciler(
        invalidation
    )
    generation.status = SurfaceRefreshStatus.FAILED

    reconciler.reconcile_projected(
        "wf-a",
        force_refresh=False,
        dirty_state=invalidation.dirty_state("wf-a"),
        on_surface_complete=None,
    )

    assert (
        WorkflowSurface.GENERATION_AVAILABILITY
        in invalidation.dirty_state("wf-a").dirty_surfaces
    )


def test_active_surface_refresher_defers_override_presentation_after_editor_completion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Active workflow refresh should rebuild override presentation after loading."""

    loaded: list[dict[str, object]] = []
    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": "state-a", "CubeB": "state-b"},
        stack_order=["CubeB", "CubeA"],
    )

    def load_all_cubes(**kwargs: object) -> None:
        """Record editor projection without completing it immediately."""

        actions.append("load")
        loaded.append(kwargs)

    override_manager = SimpleNamespace(
        sync_state_from_workflow=lambda: actions.append("sync"),
        apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
            actions,
            "pre_apply",
            True,
        ),
        materialize_default_overrides=lambda: _record_bool(
            actions,
            "defaults",
            False,
        ),
        rebuild_override_menu=lambda: actions.append("rebuild"),
        rebuild_active_override_controls=lambda: actions.append("controls"),
        apply_global_overrides=lambda **kwargs: actions.append(
            f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
        ),
    )
    shell = _active_surface_shell(
        workflow_id="wf-copy",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=override_manager,
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.shell.workflow_surface_reconciler",
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    on_surface_complete = loaded[0].pop("on_complete")
    assert callable(on_surface_complete)
    assert loaded == [
        {
            "cube_entries": [("CubeB", "state-b"), ("CubeA", "state-a")],
            "cube_states": workflow.cubes,
            "stack_order": workflow.stack_order,
        }
    ]
    assert actions == ["sync", "pre_apply", "load"]
    assert scheduled == []

    on_surface_complete()

    assert actions == ["sync", "pre_apply", "load", "defaults", "apply:True"]
    assert len(scheduled) == 1
    assert "Started active workflow surface refresh" in caplog.text
    assert "Loading active editor cube surface" in caplog.text
    assert "Queued active editor cube surface refresh" in caplog.text
    assert "Completed active workflow surface refresh" in caplog.text
    assert "Scheduled deferred active override presentation rebuild" in caplog.text
    assert "workflow_id=wf-copy" in caplog.text
    assert "cube_section_count=2" in caplog.text
    assert "stack_order_count=2" in caplog.text

    scheduled[0]()

    assert actions == [
        "sync",
        "pre_apply",
        "load",
        "defaults",
        "apply:True",
        "rebuild",
        "controls",
    ]
    assert "Rebuilt active override presentation" in caplog.text


def test_active_surface_refresher_projects_buffers_after_pre_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restored override values should settle before editor cards are loaded."""

    loaded_sampler_values: list[object] = []
    workflow = SimpleNamespace(
        cubes={
            "CubeA": SimpleNamespace(
                buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": ""}}}}
            )
        },
        stack_order=["CubeA"],
    )

    def pre_apply() -> bool:
        """Mutate the workflow buffer the way restored overrides do."""

        workflow.cubes["CubeA"].buffer["nodes"]["ksampler"]["inputs"][
            "sampler_name"
        ] = "euler_ancestral"
        return True

    def load_all_cubes(**kwargs: object) -> None:
        """Record the sampler value observed by editor projection."""

        cube_states = cast(Mapping[str, Any], kwargs["cube_states"])
        loaded_sampler_values.append(
            cube_states["CubeA"].buffer["nodes"]["ksampler"]["inputs"]["sampler_name"]
        )

    shell = _active_surface_shell(
        workflow_id="wf-restore",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: None,
            apply_global_overrides_without_snapshot_fallback=pre_apply,
            materialize_default_overrides=lambda: False,
            apply_global_overrides=lambda **_kwargs: None,
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    assert loaded_sampler_values == ["euler_ancestral"]


def test_active_surface_refresher_skips_clean_editor_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean workflow switches should reuse the existing editor surface."""

    actions: list[str] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": SimpleNamespace(buffer={"nodes": {}})},
        stack_order=["CubeA"],
    )
    signature = object()
    editor_panel = SimpleNamespace(
        current_projection_signature=lambda **_kwargs: signature,
        is_projection_clean=lambda value: value is signature,
        refresh_clean_projection=lambda **_kwargs: actions.append("clean_refresh"),
        load_all_cubes=lambda **_kwargs: actions.append("load"),
    )
    shell = _active_surface_shell(
        workflow_id="wf-clean",
        workflow=workflow,
        editor_panel=editor_panel,
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    assert actions == [
        "sync",
        "pre_apply",
        "clean_refresh",
        "defaults",
        "apply:True",
    ]
    assert "load" not in actions


def test_active_surface_refresher_force_refresh_bypasses_clean_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced workflow refresh should rebuild even when the editor surface is clean."""

    actions: list[str] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": SimpleNamespace(buffer={"nodes": {}})},
        stack_order=["CubeA"],
    )
    signature = object()

    def load_all_cubes(**kwargs: object) -> None:
        """Record forced load and complete the projection."""

        actions.append("load")
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    editor_panel = SimpleNamespace(
        current_projection_signature=lambda **_kwargs: signature,
        is_projection_clean=lambda value: value is signature,
        refresh_clean_projection=lambda **_kwargs: actions.append("clean_refresh"),
        load_all_cubes=load_all_cubes,
    )
    shell = _active_surface_shell(
        workflow_id="wf-clean",
        workflow=workflow,
        editor_panel=editor_panel,
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda *_args: None),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface(
        force_refresh=True
    )

    assert actions == [
        "sync",
        "pre_apply",
        "load",
        "defaults",
        "apply:True",
    ]
    assert "clean_refresh" not in actions


def test_active_surface_refresher_disables_generation_without_cubes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active workflow refresh should disable Generate when no cubes are loaded."""

    loaded: list[dict[str, object]] = []
    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    def load_all_cubes(**kwargs: object) -> None:
        """Record editor projection without completing it immediately."""

        actions.append("load")
        loaded.append(kwargs)

    shell = _active_surface_shell(
        workflow_id="wf-empty",
        workflow=workflow,
        editor_panel=SimpleNamespace(load_all_cubes=load_all_cubes),
        override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: actions.append("sync"),
            apply_global_overrides_without_snapshot_fallback=lambda: _record_bool(
                actions,
                "pre_apply",
                False,
            ),
            materialize_default_overrides=lambda: _record_bool(
                actions,
                "defaults",
                False,
            ),
            rebuild_override_menu=lambda: actions.append("rebuild"),
            rebuild_active_override_controls=lambda: actions.append("controls"),
            apply_global_overrides=lambda **kwargs: actions.append(
                f"apply:{kwargs.get('use_cached_behavior_snapshot')}"
            ),
        ),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()

    on_surface_complete = loaded[0].pop("on_complete")
    assert callable(on_surface_complete)
    assert loaded == [
        {
            "cube_entries": [],
            "cube_states": workflow.cubes,
            "stack_order": workflow.stack_order,
        }
    ]
    assert actions == ["sync", "pre_apply", "load"]
    assert scheduled == []

    on_surface_complete()

    presentation = shell.generationActionCluster.presentations[-1]
    assert actions == ["sync", "pre_apply", "load", "defaults", "apply:True"]
    assert len(scheduled) == 1
    assert presentation.play_enabled is False
    assert presentation.skip_enabled is False
    assert presentation.stop_enabled is False
    assert presentation.queue_primary_enabled is False


def test_deferred_override_presentation_rebuild_skips_stale_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deferred override rebuild callbacks should ignore stale workflow ids."""

    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current")
    )
    manager = SimpleNamespace(
        rebuild_override_menu=lambda: actions.append("rebuild"),
        rebuild_active_override_controls=lambda: actions.append("controls"),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )

    ActiveWorkflowSurfaceRefresher(shell).schedule_active_override_presentation_rebuild(
        manager, workflow_id="wf-old"
    )
    scheduled[0]()

    assert actions == []


def test_active_surface_refresh_success_emits_no_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Successful active surface maintenance should not spam INFO logs."""

    calls: list[str] = []

    class _EditorPanel:
        """Editor-panel double that reports a clean projection."""

        def current_projection_signature(self, **kwargs: object) -> object:
            """Return a stable projection signature."""

            del kwargs
            return "signature"

        def is_projection_clean(self, signature: object) -> bool:
            """Report whether the requested signature is clean."""

            return signature == "signature"

        def refresh_clean_projection(self, **kwargs: object) -> None:
            """Record lightweight projection refresh."""

            del kwargs
            calls.append("editor:clean")

    class _OverrideManager:
        """Override-manager double for active surface refresh."""

        def sync_state_from_workflow(self) -> None:
            """Record state synchronization."""

            calls.append("override:sync")

        def apply_global_overrides_without_snapshot_fallback(self) -> bool:
            """Record pre-projection override application."""

            calls.append("override:pre")
            return False

        def materialize_default_overrides(self) -> bool:
            """Record default override materialization."""

            calls.append("override:defaults")
            return False

        def apply_global_overrides(
            self,
            *,
            use_cached_behavior_snapshot: bool,
        ) -> None:
            """Record post-projection override application."""

            calls.append(f"override:post:{use_cached_behavior_snapshot}")

    workflow = SimpleNamespace(cubes={}, stack_order=[])
    invalidation = WorkflowSurfaceInvalidationService()
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        get_active_workflow=lambda: workflow,
        active_editor_panel=_EditorPanel(),
        active_override_manager=_OverrideManager(),
        editor_panels={"wf-a": _EditorPanel()},
        override_managers={"wf-a": _OverrideManager()},
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: calls.append(
                f"canvas:{workflow_id}"
            )
        ),
        workflow_surface_invalidation_service=invalidation,
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: calls.append("input")
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: calls.append("generation")
        ),
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_surface_reconciler",
    )

    ActiveWorkflowSurfaceRefresher(view).refresh_active_workflow_surface()

    assert "editor:clean" in calls
    assert invalidation.is_clean("wf-a")
    assert caplog.records == []


def test_active_workflow_surface_refresher_for_reuses_composed_refresher() -> None:
    """Surface refresher composition should attach one owner to the shell."""

    view = SimpleNamespace()

    first = active_workflow_surface_refresher_for(view)
    second = active_workflow_surface_refresher_for(view)

    assert first is second
    assert view.active_workflow_surface_refresher is first


def test_detached_shell_ignores_stale_surface_refresh_callbacks() -> None:
    """Async cube callbacks should not refresh a shell detached for GUI reload."""

    shell = SimpleNamespace(
        _detached_for_gui_reload=True,
        get_active_workflow=lambda: (_ for _ in ()).throw(
            AssertionError("stale shell should not inspect workflow state")
        ),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()
