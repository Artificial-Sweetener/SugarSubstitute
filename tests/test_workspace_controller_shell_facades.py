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

"""Tests for WorkspaceController shell facade behavior."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.workspace_controller_test_support import import_workspace_controller_module


def test_project_workflow_forces_workspace_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore callers should be able to force projection of an active workflow."""

    mod = import_workspace_controller_module(monkeypatch)
    calls: list[dict[str, object]] = []

    def _activate_workflow(workflow_id: str, **kwargs: object) -> None:
        """Record workflow activation request."""

        calls.append({"workflow_id": workflow_id, **kwargs})

    controller = object.__new__(mod.WorkspaceController)
    controller._views = SimpleNamespace(
        workflow_workspace=SimpleNamespace(
            workflow_session_service=SimpleNamespace(
                active_workflow_id="",
                workflows={},
            ),
            _active_workspace_route="",
            cube_stacks={},
            editor_panels={},
        )
    )
    controller._collaborators = SimpleNamespace(
        workflow_workspace=SimpleNamespace(activate_workflow=_activate_workflow)
    )

    controller.project_workflow("wf-a", force_refresh=True)

    assert calls == [
        {
            "workflow_id": "wf-a",
            "source": "workspace_projection",
            "force_refresh": True,
        }
    ]


def test_settings_tab_selection_projects_through_settings_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pinned Settings selection should not require a MainWindow request adapter."""

    mod = import_workspace_controller_module(monkeypatch)
    calls: list[str] = []

    def _project_settings_workspace() -> None:
        """Record Settings workspace projection."""

        calls.append("settings")

    controller = object.__new__(mod.WorkspaceController)
    controller._views = SimpleNamespace(
        generation=SimpleNamespace(
            settings_route_controller=SimpleNamespace(
                project_settings_workspace=_project_settings_workspace
            )
        )
    )

    controller.on_settings_tab_selected()

    assert calls == ["settings"]


def test_cube_load_callbacks_route_through_extracted_collaborators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube loader callbacks should not route through controller facades."""

    mod = import_workspace_controller_module(monkeypatch)
    events: list[tuple[str, tuple[object, ...]]] = []
    canvas_view = SimpleNamespace(name="canvas")

    def materialize_for_view(
        view: object,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Record direct Input canvas adapter routing."""

        events.append(("materialize", (view, workflow_id, cube_alias)))

    def _prepare_node_behavior_runtime(workflow: object, alias: str) -> None:
        """Record node-behavior runtime preparation."""

        events.append(("prepare", (workflow, alias)))

    def _refresh_workflow_after_cube_load(workflow_id: str, cube_alias: str) -> None:
        """Record loaded-cube workflow refresh."""

        events.append(("refresh_workflow", (workflow_id, cube_alias)))

    def _refresh_loaded_cube_surface(
        workflow_id: str,
        cube_alias: str,
        **kwargs: object,
    ) -> bool:
        """Record loaded-cube surface refresh."""

        events.append(("refresh_surface", (workflow_id, cube_alias, kwargs)))
        return True

    def _activate_loaded_cube(workflow_id: str, cube_alias: str) -> None:
        """Record loaded-cube activation."""

        events.append(("activate", (workflow_id, cube_alias)))

    def _refresh_workflow_after_cube_load_async(
        workflow_id: str,
        cube_alias: str,
        done: Callable[[], None],
    ) -> None:
        """Record async workflow refresh and complete it."""

        events.append(("refresh_workflow_async", (workflow_id, cube_alias)))
        done()

    def _refresh_loaded_cube_surface_async(
        workflow_id: str,
        cube_alias: str,
        done: Callable[[bool], None],
        **kwargs: object,
    ) -> None:
        """Record async surface refresh and complete it."""

        events.append(("refresh_surface_async", (workflow_id, cube_alias, kwargs)))
        done(True)

    monkeypatch.setattr(
        mod,
        "materialize_loaded_cube_input_canvas_for_view",
        materialize_for_view,
    )
    controller = object.__new__(mod.WorkspaceController)
    controller._views = SimpleNamespace(
        canvas=canvas_view,
        cube=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            cube_stacks={},
            editor_panels={},
            cube_load_service=SimpleNamespace(),
            cube_stack_service=SimpleNamespace(),
            cube_icon_factory=SimpleNamespace(),
            active_cube_stack=None,
            active_editor_panel=None,
        ),
    )
    controller._collaborators = SimpleNamespace(
        cube_picker_actions=SimpleNamespace(
            prepare_node_behavior_runtime=_prepare_node_behavior_runtime
        ),
        cube_load_execution_route_factory=object(),
        loaded_cube_surface_actions=SimpleNamespace(
            refresh_workflow_after_cube_load=_refresh_workflow_after_cube_load,
            refresh_loaded_cube_surface=_refresh_loaded_cube_surface,
            activate_loaded_cube=_activate_loaded_cube,
            refresh_workflow_after_cube_load_async=(
                _refresh_workflow_after_cube_load_async
            ),
            refresh_loaded_cube_surface_async=_refresh_loaded_cube_surface_async,
        ),
    )

    callbacks = cast(
        Any,
        mod.WorkspaceController._build_cube_load_ui_callbacks(controller),
    )

    callbacks.materialize_loaded_cube_input_canvas("wf-a", "CubeA")
    callbacks.refresh_workflow_after_cube_load("wf-a", "CubeA")
    callbacks.prepare_node_behavior_runtime("workflow", "CubeA")
    assert callbacks.refresh_loaded_cube_surface is not None
    assert callbacks.refresh_loaded_cube_surface("wf-a", "CubeA", phase="complete")
    assert callbacks.activate_loaded_cube is not None
    callbacks.activate_loaded_cube("wf-a", "CubeA")
    assert callbacks.refresh_workflow_after_cube_load_async is not None
    callbacks.refresh_workflow_after_cube_load_async(
        "wf-a",
        "CubeA",
        lambda: events.append(("workflow_async_done", ())),
    )
    assert callbacks.refresh_loaded_cube_surface_async is not None
    callbacks.refresh_loaded_cube_surface_async(
        "wf-a",
        "CubeA",
        lambda refreshed: events.append(("surface_async_done", (refreshed,))),
        wait_for_complete=True,
    )

    assert events == [
        ("materialize", (canvas_view, "wf-a", "CubeA")),
        ("refresh_workflow", ("wf-a", "CubeA")),
        ("prepare", ("workflow", "CubeA")),
        ("refresh_surface", ("wf-a", "CubeA", {"phase": "complete"})),
        ("activate", ("wf-a", "CubeA")),
        ("refresh_workflow_async", ("wf-a", "CubeA")),
        ("workflow_async_done", ()),
        ("refresh_surface_async", ("wf-a", "CubeA", {"wait_for_complete": True})),
        ("surface_async_done", (True,)),
    ]
