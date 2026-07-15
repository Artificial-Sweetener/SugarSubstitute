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

"""Contract tests for focused cube-card command orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.application.cubes import CubeStackService
from substitute.application.workflows import CubeDuplicationService
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.cube_stack_presenter import CubeStackPresenter
from substitute.presentation.shell.cube_surface_projection_coordinator import (
    CubeSurfaceProjectionCoordinator,
)
from substitute.presentation.shell.workspace_cube_stack_actions import (
    WorkspaceCubeStackActionView,
    WorkspaceCubeStackActions,
)


class _LinkReconciler:
    """Accept link reconciliation for shell-orchestration testing."""

    def reconcile_transition(self, **_kwargs: object) -> None:
        """Accept transition reconciliation."""

    def sanitize_current_state(self, **_kwargs: object) -> None:
        """Accept current-state sanitation."""


def _cube(alias: str) -> CubeState:
    """Build a mutable cube for card-action testing."""

    return CubeState(
        cube_id="Owner/Cube.cube",
        version="1.0.0",
        alias=alias,
        original_cube={"nodes": {}},
        buffer={"nodes": {"Prompt": {"inputs": {"text": "hello"}}}},
    )


def test_duplicate_command_mutates_then_presents_and_projects_appended_cube() -> None:
    """The card command should delegate durable state and presentation ownership."""

    workflow = WorkflowState(cubes={"Cube": _cube("Cube")}, stack_order=["Cube"])
    invalidation = WorkflowSurfaceInvalidationService()
    presentation_calls: list[dict[str, object]] = []
    projection_calls: list[tuple[str, str]] = []
    stack = SimpleNamespace()
    view = cast(
        WorkspaceCubeStackActionView,
        SimpleNamespace(
            active_cube_stack=stack,
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            workflow_surface_invalidation_service=invalidation,
            get_active_workflow=lambda: workflow,
        ),
    )
    actions = WorkspaceCubeStackActions(
        view,
        duplication_service=CubeDuplicationService(
            cube_stack_service=CubeStackService(),
            link_reconciler=_LinkReconciler(),
        ),
        stack_presenter=cast(
            CubeStackPresenter,
            SimpleNamespace(
                append_cube=lambda cube_stack, **kwargs: presentation_calls.append(
                    {"stack": cube_stack, **kwargs}
                )
            ),
        ),
        surface_projector=cast(
            CubeSurfaceProjectionCoordinator,
            SimpleNamespace(
                project_added_cube=lambda workflow_id, alias: projection_calls.append(
                    (workflow_id, alias)
                )
            ),
        ),
    )

    actions.on_cube_duplicate_requested("Cube")

    assert workflow.stack_order == ["Cube", "Cube 2"]
    assert workflow.cubes["Cube 2"].buffer == workflow.cubes["Cube"].buffer
    assert workflow.cubes["Cube 2"] is not workflow.cubes["Cube"]
    assert presentation_calls[0]["stack"] is stack
    assert presentation_calls[0]["workflow_id"] == "wf-a"
    assert presentation_calls[0]["cube_alias"] == "Cube 2"
    assert presentation_calls[0]["cube_state"] is workflow.cubes["Cube 2"]
    assert presentation_calls[0]["select"] is True
    assert projection_calls == [("wf-a", "Cube 2")]
    dirty = invalidation.dirty_state("wf-a")
    assert dirty.reasons == (WorkflowInvalidationReason.CUBE_DUPLICATED,)


def test_duplicate_command_ignores_stale_source_without_projection() -> None:
    """A stale card signal should not create presentation side effects."""

    workflow = WorkflowState()
    calls: list[str] = []
    view = cast(
        WorkspaceCubeStackActionView,
        SimpleNamespace(
            active_cube_stack=object(),
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            get_active_workflow=lambda: workflow,
        ),
    )
    actions = WorkspaceCubeStackActions(
        view,
        duplication_service=CubeDuplicationService(
            cube_stack_service=CubeStackService(),
            link_reconciler=_LinkReconciler(),
        ),
        stack_presenter=cast(
            CubeStackPresenter,
            SimpleNamespace(append_cube=lambda *_args, **_kwargs: calls.append("card")),
        ),
        surface_projector=cast(
            CubeSurfaceProjectionCoordinator,
            SimpleNamespace(
                project_added_cube=lambda *_args, **_kwargs: calls.append("surface")
            ),
        ),
    )

    actions.on_cube_duplicate_requested("Missing")

    assert calls == []
    assert workflow.cubes == {}
