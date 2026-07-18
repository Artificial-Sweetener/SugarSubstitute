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

"""Cover blank initial workspace creation outside MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from substitute.presentation.shell.initial_workspace_controller import (
    InitialWorkspaceController,
)
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces


def test_initialize_initial_workspace_bootstraps_first_editor_pair() -> None:
    """Initial workspace bootstrap should create the first UI pair and hydrate it."""

    cube_stack = object()
    load_calls: list[dict[str, object]] = []
    tab_calls: list[tuple[str, object, object]] = []
    workflow = SimpleNamespace(cubes={"CubeA": "state-a"}, stack_order=["CubeA"])
    manager_calls: list[str] = []
    metadata_refresh_calls: list[str] = []
    input_canvas_calls: list[str] = []

    def load_all_cubes(**kwargs: object) -> None:
        """Record the initial editor hydration request."""

        load_calls.append(kwargs)

    editor_panel = SimpleNamespace(load_all_cubes=load_all_cubes)
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workflow_tabbar=SimpleNamespace(
            itemMap={},
            addTab=lambda workflow_id, label: tab_calls.append(
                ("add", workflow_id, label)
            ),
            select_workflow_tab=lambda workflow_id, *, emit=False: tab_calls.append(
                ("select", workflow_id, emit)
            ),
        ),
        workflow_ui_factory=SimpleNamespace(
            create_workflow_ui=lambda workflow_id, set_as_current=True: (
                WorkflowUiSurfaces(
                    cube_stack=cube_stack,
                    editor_panel=editor_panel,
                    created=True,
                )
            )
        ),
        active_override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: manager_calls.append("sync")
        ),
        active_workflow_surface_refresher=SimpleNamespace(
            refresh_active_workflow_surface=lambda: manager_calls.append("refresh")
        ),
        get_active_workflow=lambda: workflow,
        _startup_timer=None,
        model_metadata_surface_refresh_controller=SimpleNamespace(
            request_initial_lora_model_catalog_refresh=lambda reason: (
                metadata_refresh_calls.append(reason)
            )
        ),
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: input_canvas_calls.append(
                "refresh"
            )
        ),
    )

    InitialWorkspaceController(shell).initialize_initial_workspace()
    on_complete = cast("Callable[[], None]", load_calls[0]["on_complete"])
    on_complete()

    assert tab_calls == [
        ("add", "wf-a", "Untitled Workflow"),
        ("select", "wf-a", False),
    ]
    assert shell.cube_stack is cube_stack
    assert shell.editor_panel is editor_panel
    assert manager_calls == ["sync", "refresh"]
    assert load_calls[0]["cube_entries"] == []
    assert load_calls[0]["cube_states"] == workflow.cubes
    assert load_calls[0]["stack_order"] == workflow.stack_order
    assert metadata_refresh_calls == ["initial_editor_cubes"]
    assert input_canvas_calls == ["refresh"]


def test_initialize_initial_workspace_does_not_duplicate_existing_tab() -> None:
    """Initial workspace fallback should not add a second default tab."""

    tab_calls: list[tuple[str, object, object]] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workflow_tabbar=SimpleNamespace(
            itemMap={"wf-a": object()},
            addTab=lambda workflow_id, label: tab_calls.append(
                ("add", workflow_id, label)
            ),
            select_workflow_tab=lambda workflow_id, *, emit=False: tab_calls.append(
                ("select", workflow_id, emit)
            ),
        ),
        workflow_ui_factory=SimpleNamespace(
            create_workflow_ui=lambda _workflow_id, set_as_current=True: (
                WorkflowUiSurfaces(
                    cube_stack=object(),
                    editor_panel=SimpleNamespace(load_all_cubes=lambda **_kwargs: None),
                    created=True,
                )
            )
        ),
        active_override_manager=None,
        _startup_timer=None,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        model_metadata_surface_refresh_controller=SimpleNamespace(
            request_initial_lora_model_catalog_refresh=lambda _reason: None
        ),
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: None
        ),
    )

    InitialWorkspaceController(shell).initialize_initial_workspace()

    assert tab_calls == [("select", "wf-a", False)]


def test_ensure_initial_workflow_tab_falls_back_to_index_selection() -> None:
    """Tab selection should support older tab bars without workflow-id selection."""

    tab_calls: list[tuple[str, object, object]] = []
    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            itemMap={},
            addTab=lambda workflow_id, label: tab_calls.append(
                ("add", workflow_id, label)
            ),
            setCurrentIndex=lambda index: tab_calls.append(("index", index, None)),
        )
    )

    InitialWorkspaceController(shell).ensure_initial_workflow_tab("wf-a")

    assert tab_calls == [
        ("add", "wf-a", "Untitled Workflow"),
        ("index", 0, None),
    ]
