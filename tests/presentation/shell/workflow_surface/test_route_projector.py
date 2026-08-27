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

"""Workflow route projection and surface-reuse contracts."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)
from substitute.presentation.shell.main_window_workflow_route_adapter import (
    MainWindowWorkflowRouteAdapter,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces
from tests.presentation.shell.workflow_surface.route_projector_support import (
    _build_projector,
    _build_projector_view,
)


def test_projector_swaps_visible_widgets_and_projects_shared_canvas() -> None:
    """Route projection should switch cached widgets and shared canvas state."""

    view = _build_projector_view()
    invalidation = WorkflowSurfaceInvalidationService()

    result = _build_projector(view, invalidation).project("wf-b")

    assert view.calls.index("route") < view.calls.index(
        f"cube:{id(view.cube_stacks['wf-b'])}"
    )
    assert view.calls.index("route") < view.calls.index("canvas:wf-b")
    assert f"editor:{id(view.editor_panels['wf-b'])}" in view.calls
    assert view.calls.index(
        f"editor:{id(view.editor_panels['wf-b'])}"
    ) < view.calls.index("presentation:cube_stack:True")
    assert view._active_workspace_route == "wf-b"
    assert "actions" in view.calls
    assert "position" in view.calls
    assert "busy" in view.calls
    assert "overrides:wf-a:detach" in view.calls
    assert "overrides:wf-b:sync" in view.calls
    assert "overrides:wf-b:menu" in view.calls
    assert "overrides:wf-b:controls" in view.calls
    assert view.calls.index("overrides:wf-a:detach") < view.calls.index(
        "overrides:wf-b:controls"
    )
    assert result.canvas_projected
    assert result.overrides_projected
    assert not result.created_widgets


def test_route_adapter_materializes_missing_workflow_ui_through_materializer() -> None:
    """Route adapter should delegate missing workflow UI creation to the owner."""

    view = _build_projector_view()
    view.cube_stacks.pop("wf-a")
    view.editor_panels.pop("wf-a")
    view._pending_restored_workflow_snapshots = {}
    created: list[tuple[str, bool]] = []
    cube_stack = object()
    editor_panel = object()

    def create_workflow_ui(
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Record workflow UI creation and install fake widgets."""

        created.append((workflow_id, set_as_current))
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        return WorkflowUiSurfaces(
            cube_stack=cube_stack,
            editor_panel=editor_panel,
            created=True,
        )

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=create_workflow_ui)

    result = MainWindowWorkflowRouteAdapter(view).ensure_workflow_ui(
        "wf-a",
        set_as_current=False,
    )

    assert created == [("wf-a", False)]
    assert result.cube_stack is cube_stack
    assert result.editor_panel is editor_panel
    assert result.created


def test_projector_flushes_pending_editor_commit_after_editor_swap() -> None:
    """Route projection should reveal background editor work after activation."""

    view = _build_projector_view()
    pending_panel = SimpleNamespace(
        finalize_pending_visible_projection=lambda: (
            view.calls.append("editor:pending-finalize") or True
        )
    )
    view.editor_panels["wf-b"] = pending_panel
    invalidation = WorkflowSurfaceInvalidationService()

    _build_projector(view, invalidation).project("wf-b")

    assert view.calls.index(f"editor:{id(pending_panel)}") < view.calls.index(
        "editor:pending-finalize"
    )


def test_editor_surface_adapter_flushes_pending_commit_before_clean_reuse() -> None:
    """Editor refresh should reveal pending work before clean-projection checks."""

    calls: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow = SimpleNamespace(cubes={"Cube": cube}, stack_order=["Cube"])

    def _finalize_pending_visible_projection() -> bool:
        """Record pending commit finalization and report success."""

        calls.append("finalize")
        return True

    def _is_projection_clean(_signature: object) -> bool:
        """Record clean-projection check and report reusable state."""

        calls.append("clean_check")
        return True

    editor_panel = SimpleNamespace(
        finalize_pending_visible_projection=_finalize_pending_visible_projection,
        current_projection_signature=lambda **_kwargs: "signature",
        is_projection_clean=_is_projection_clean,
        refresh_clean_projection=lambda **_kwargs: calls.append("clean_refresh"),
        load_all_cubes=lambda **_kwargs: calls.append("load"),
    )
    shell = SimpleNamespace(
        active_editor_panel=editor_panel,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        editor_panels={"wf-a": editor_panel},
    )
    completed: list[str] = []

    result = MainWindowEditorSurfaceAdapter(shell).refresh_editor_surface(
        "wf-a",
        force=False,
        on_complete=lambda _result: completed.append("complete"),
    )

    assert result.status.name == "SKIPPED_CLEAN"
    assert calls == ["finalize", "clean_check", "clean_refresh"]
    assert completed == ["complete"]


def test_projector_clears_canvas_dirty_state_without_rebuilding_editor() -> None:
    """Canvas-only dirty state should be satisfied by route projection."""

    view = _build_projector_view()
    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-b",
        {WorkflowSurface.CANVAS},
        WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
    )

    _build_projector(view, invalidation).project("wf-b")

    assert invalidation.is_clean("wf-b")


def test_projector_clears_unread_activity() -> None:
    """Route projection should clear selected workflow unread activity."""

    view = _build_projector_view()
    unread: set[str] = {"wf-b"}

    def mark_seen(workflow_id: str) -> bool:
        """Mark the workflow seen and report whether unread state changed."""

        if workflow_id not in unread:
            return False
        unread.remove(workflow_id)
        return True

    view.workflow_activity_service = SimpleNamespace(mark_seen=mark_seen)
    invalidation = WorkflowSurfaceInvalidationService()

    result = _build_projector(view, invalidation).project("wf-b")

    assert result.activity_cleared
    assert view.workflow_tabbar.unread_updates == [("wf-b", False)]


def test_projector_materializes_missing_ui_once() -> None:
    """Route projection should create missing workflow widgets exactly once."""

    view = _build_projector_view()
    view.cube_stacks.pop("wf-b")
    view.editor_panels.pop("wf-b")

    def create_new_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create missing cached widgets for one workflow."""

        cube_stack = object()
        editor_panel = object()
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return WorkflowUiSurfaces(
            cube_stack=cube_stack,
            editor_panel=editor_panel,
            created=True,
        )

    view.workflow_ui_factory = SimpleNamespace(
        create_workflow_ui=create_new_workflow_ui
    )
    invalidation = WorkflowSurfaceInvalidationService()

    result = _build_projector(view, invalidation).project("wf-b")

    assert result.created_widgets
    assert view.calls.count("create:wf-b:False") == 1
    assert f"cube:{id(view.cube_stacks['wf-b'])}" in view.calls
