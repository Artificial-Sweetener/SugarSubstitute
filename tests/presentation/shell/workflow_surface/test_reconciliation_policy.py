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

"""Workflow dirty-surface reconciliation contracts."""

from __future__ import annotations


from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshStatus,
)


from tests.presentation.shell.workflow_surface.reconciler_support import (
    _build_reconciler,
)


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
