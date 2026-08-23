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

"""Contract tests for mutation-owned workflow surface invalidation."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from substitute.presentation.shell import workspace_canvas_actions
from substitute.presentation.shell import workspace_cube_stack_actions
from substitute.presentation.shell import workspace_cube_update_actions
from substitute.presentation.shell import workspace_file_actions
from substitute.presentation.shell.workflow_surface_invalidation import (
    CANVAS_AND_GENERATION_SURFACES,
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)


def _view_with_invalidation() -> tuple[
    SimpleNamespace, WorkflowSurfaceInvalidationService
]:
    """Build a view double exposing workflow surface invalidation."""

    invalidation = WorkflowSurfaceInvalidationService()
    return (
        SimpleNamespace(workflow_surface_invalidation_service=invalidation),
        invalidation,
    )


def test_cube_mutation_marks_cube_structure_surfaces_dirty() -> None:
    """Cube mutations should request every structural workflow surface."""

    view, invalidation = _view_with_invalidation()

    mark_dirty = cast(
        Callable[..., None],
        getattr(workspace_cube_stack_actions, "_mark_workflow_surfaces_dirty"),
    )

    mark_dirty(
        view,
        "wf-a",
        reason=WorkflowInvalidationReason.CUBE_REMOVED,
    )

    state = invalidation.dirty_state("wf-a")
    assert state.dirty_surfaces == CUBE_STRUCTURE_SURFACES
    assert state.reasons == (WorkflowInvalidationReason.CUBE_REMOVED,)


def test_canvas_mutation_marks_canvas_and_generation_surfaces_dirty() -> None:
    """Canvas mutations should request shared canvas and generation availability."""

    view, invalidation = _view_with_invalidation()

    mark_dirty = cast(
        Callable[..., None],
        getattr(workspace_canvas_actions, "_mark_canvas_surfaces_dirty"),
    )

    mark_dirty(
        view,
        "wf-a",
        reason=WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    state = invalidation.dirty_state("wf-a")
    assert state.dirty_surfaces == CANVAS_AND_GENERATION_SURFACES
    assert state.reasons == (WorkflowInvalidationReason.CANVAS_STATE_CHANGED,)


def test_recipe_load_marks_cube_structure_surfaces_dirty() -> None:
    """Recipe materialization should request all workflow presentation surfaces."""

    view, invalidation = _view_with_invalidation()

    mark_dirty = cast(
        Callable[[object, str], None],
        getattr(workspace_file_actions, "_mark_recipe_surfaces_dirty"),
    )

    mark_dirty(view, "wf-a")

    state = invalidation.dirty_state("wf-a")
    assert state.dirty_surfaces == CUBE_STRUCTURE_SURFACES
    assert state.reasons == (WorkflowInvalidationReason.RECIPE_LOADED,)


def test_cube_update_marks_cube_structure_surfaces_dirty() -> None:
    """Cube definition updates should request structural workflow reconciliation."""

    view, invalidation = _view_with_invalidation()

    workspace_cube_update_actions._mark_cube_update_surfaces_dirty(view, "wf-a")

    state = invalidation.dirty_state("wf-a")
    assert state.dirty_surfaces == CUBE_STRUCTURE_SURFACES
    assert state.reasons == (WorkflowInvalidationReason.NODE_DEFINITIONS_REFRESHED,)


def test_tab_selection_does_not_dirty_workflow_presentation_surfaces() -> None:
    """Tab selection should project shared route state without mutation dirtiness."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    assert invalidation.is_clean("wf-b")
