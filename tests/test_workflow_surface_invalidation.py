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

"""Contract tests for workflow surface invalidation state."""

from __future__ import annotations

from PySide6.QtCore import QObject

from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)


def test_mark_dirty_accumulates_surfaces_and_reasons() -> None:
    """Dirty tracking should preserve requested surfaces and reason history."""

    service = WorkflowSurfaceInvalidationService()

    service.mark_dirty(
        "wf-a",
        {WorkflowSurface.EDITOR},
        WorkflowInvalidationReason.CUBE_ADDED,
    )
    service.mark_dirty(
        "wf-a",
        {WorkflowSurface.CANVAS, WorkflowSurface.EDITOR},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    state = service.dirty_state("wf-a")
    assert state.dirty_surfaces == frozenset(
        {WorkflowSurface.EDITOR, WorkflowSurface.CANVAS}
    )
    assert state.reasons == (
        WorkflowInvalidationReason.CUBE_ADDED,
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )
    assert not service.is_clean("wf-a")


def test_mark_clean_clears_selected_or_all_surfaces() -> None:
    """Clean tracking should support partial and full reconciliation."""

    service = WorkflowSurfaceInvalidationService()
    service.mark_dirty(
        "wf-a",
        {WorkflowSurface.EDITOR, WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CUBE_LOADED,
    )

    service.mark_clean("wf-a", {WorkflowSurface.EDITOR})

    assert service.dirty_state("wf-a").dirty_surfaces == frozenset(
        {WorkflowSurface.CANVAS}
    )

    service.mark_clean("wf-a")

    assert service.is_clean("wf-a")
    assert service.dirty_state("wf-a").reasons == ()


def test_remove_workflow_forgets_dirty_state() -> None:
    """Closing a workflow should drop pending maintenance state."""

    service = WorkflowSurfaceInvalidationService()
    service.mark_dirty(
        "wf-a",
        {WorkflowSurface.OVERRIDES},
        WorkflowInvalidationReason.GLOBAL_OVERRIDES_CHANGED,
    )

    service.remove_workflow("wf-a")

    assert service.is_clean("wf-a")


def test_rename_workflow_preserves_dirty_state() -> None:
    """Renaming a workflow should re-key pending maintenance state."""

    service = WorkflowSurfaceInvalidationService()
    service.mark_dirty(
        "wf-a",
        {WorkflowSurface.GENERATION_AVAILABILITY},
        WorkflowInvalidationReason.GENERATION_RESULT_MATERIALIZED,
    )

    service.rename_workflow("wf-a", "wf-renamed")

    assert service.is_clean("wf-a")
    assert service.dirty_state("wf-renamed").dirty_surfaces == frozenset(
        {WorkflowSurface.GENERATION_AVAILABILITY}
    )


def test_service_does_not_inherit_qt_object() -> None:
    """Invalidation state should stay pure Python without QObject ownership."""

    assert not isinstance(WorkflowSurfaceInvalidationService(), QObject)
