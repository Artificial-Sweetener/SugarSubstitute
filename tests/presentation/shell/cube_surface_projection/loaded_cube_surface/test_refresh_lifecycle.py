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

"""Test loaded-cube surface refresh lifecycle projection."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace


from substitute.domain.workflow import CubeState
from substitute.presentation.shell.loaded_cube_surface_controller import (
    mark_loaded_cube_surface_stale,
    refresh_incremental_loaded_cube_surface,
    refresh_loaded_cube_surface_for_view,
    refresh_loaded_cube_surface_for_view_async,
    refresh_workflow_after_cube_load_for_view,
    schedule_deferred_incremental_override_presentation_rebuild,
)


from .surface_support import _PresentationStack


def test_mark_loaded_cube_surface_stale_delegates_to_projection_coordinator() -> None:
    """Stale marking should target the active editor projection coordinator."""

    marked: list[tuple[list[str], str]] = []
    coordinator = SimpleNamespace(
        mark_cube_sections_stale=lambda aliases, *, reason: marked.append(
            (list(aliases), reason)
        )
    )
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_editor_panel=SimpleNamespace(_projection_coordinator=coordinator),
    )

    mark_loaded_cube_surface_stale(
        cube_view,
        "wf-a",
        "CubeA",
        reason="node_definition_changed",
    )

    assert marked == [(["CubeA"], "node_definition_changed")]


def test_mark_loaded_cube_surface_stale_skips_stale_workflow() -> None:
    """Stale marking should ignore callbacks for inactive workflows."""

    marked: list[tuple[list[str], str]] = []
    coordinator = SimpleNamespace(
        mark_cube_sections_stale=lambda aliases, *, reason: marked.append(
            (list(aliases), reason)
        )
    )
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current"),
        active_editor_panel=SimpleNamespace(_projection_coordinator=coordinator),
    )

    mark_loaded_cube_surface_stale(
        cube_view,
        "wf-old",
        "CubeA",
        reason="node_definition_changed",
    )

    assert marked == []


def test_mark_loaded_cube_surface_stale_skips_missing_coordinator() -> None:
    """Stale marking should tolerate missing active projection coordinator."""

    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_editor_panel=SimpleNamespace(),
    )

    mark_loaded_cube_surface_stale(
        cube_view,
        "wf-a",
        "CubeA",
        reason="node_definition_changed",
    )


def test_deferred_incremental_override_rebuild_schedules_rebuild() -> None:
    """Deferred override rebuild should run manager refreshes for active workflow."""

    scheduled: list[Callable[[], None]] = []
    manager_calls: list[str] = []
    manager = SimpleNamespace(
        _global_override_controls={"a": object(), "b": object()},
        rebuild_override_menu=lambda: manager_calls.append("menu"),
        rebuild_active_override_controls=lambda: manager_calls.append("controls"),
    )

    schedule_deferred_incremental_override_presentation_rebuild(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workflow_id="wf-a",
        active_manager=manager,
        schedule_rebuild=scheduled.append,
    )

    assert manager_calls == []
    scheduled[0]()
    assert manager_calls == ["menu", "controls"]


def test_deferred_incremental_override_rebuild_skips_stale_workflow() -> None:
    """Deferred override rebuild should ignore callbacks for inactive workflows."""

    scheduled: list[Callable[[], None]] = []
    manager_calls: list[str] = []
    manager = SimpleNamespace(
        rebuild_override_menu=lambda: manager_calls.append("menu"),
        rebuild_active_override_controls=lambda: manager_calls.append("controls"),
    )

    schedule_deferred_incremental_override_presentation_rebuild(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current"),
        workflow_id="wf-old",
        active_manager=manager,
        schedule_rebuild=scheduled.append,
    )
    scheduled[0]()

    assert manager_calls == []


def test_refresh_incremental_loaded_cube_surface_uses_editor_insert_path() -> None:
    """Incremental refresh should project one cube and refresh dependent controls."""

    inserted: list[tuple[tuple[object, ...], dict[str, object]]] = []
    manager_calls: list[str] = []
    input_canvas_availability_calls: list[str] = []
    generation_availability_calls: list[str] = []
    workflow = SimpleNamespace(
        cubes={"CubeA": "cube-state"},
        stack_order=["CubeA"],
    )

    def insert_cube_section(*args: object, **kwargs: object) -> None:
        """Record insert call and complete the progressive editor build."""

        inserted.append((args, kwargs))
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    manager = SimpleNamespace(
        sync_state_from_workflow=lambda: manager_calls.append("sync"),
        materialize_default_overrides=lambda: manager_calls.append("defaults"),
        rebuild_override_menu=lambda: manager_calls.append("menu"),
        rebuild_active_override_controls=lambda: manager_calls.append("controls"),
        apply_global_overrides=lambda **_kwargs: manager_calls.append("apply"),
    )
    cube_view = SimpleNamespace(
        active_editor_panel=SimpleNamespace(insert_cube_section=insert_cube_section),
        get_active_workflow=lambda: workflow,
    )
    workflow_workspace_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        override_managers={"wf-a": manager},
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: (
                input_canvas_availability_calls.append("input")
            )
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: (
                generation_availability_calls.append("generation")
            )
        ),
    )

    result = refresh_incremental_loaded_cube_surface(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda callback: callback(),
    )

    assert result is True
    assert inserted == [
        (
            ("CubeA", "cube-state"),
            {
                "cube_states": workflow.cubes,
                "stack_order": workflow.stack_order,
                "on_complete": inserted[0][1]["on_complete"],
                "completion_phase": "first_usable",
            },
        )
    ]
    assert manager_calls == ["sync", "defaults", "apply", "menu", "controls"]
    assert input_canvas_availability_calls == ["input"]
    assert generation_availability_calls == ["generation"]


def test_refresh_incremental_loaded_cube_surface_reports_complete_phase() -> None:
    """Incremental refresh should pass requested completion phase to insertion."""

    inserted: list[dict[str, object]] = []
    completed: list[str] = []
    workflow = SimpleNamespace(cubes={"CubeA": "cube-state"}, stack_order=["CubeA"])

    def insert_cube_section(*_args: object, **kwargs: object) -> None:
        """Record insert options and complete the progressive editor build."""

        inserted.append(kwargs)
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    result = refresh_incremental_loaded_cube_surface(
        cube_view=SimpleNamespace(
            active_editor_panel=SimpleNamespace(
                insert_cube_section=insert_cube_section
            ),
            get_active_workflow=lambda: workflow,
        ),
        workflow_workspace_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            override_managers={},
            canvas_route_controller=SimpleNamespace(
                refresh_input_canvas_availability=lambda: None,
            ),
        ),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
        on_complete=lambda: completed.append("done"),
        completion_phase="complete",
    )

    assert result is True
    assert completed == ["done"]
    assert inserted[0]["completion_phase"] == "complete"


def test_refresh_incremental_loaded_cube_surface_skips_missing_panel() -> None:
    """Incremental refresh should report unavailable editor insertion."""

    result = refresh_incremental_loaded_cube_surface(
        cube_view=SimpleNamespace(
            active_editor_panel=None,
            get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        ),
        workflow_workspace_view=SimpleNamespace(),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
    )

    assert result is False


def test_refresh_loaded_cube_surface_for_view_updates_tab_and_editor() -> None:
    """Loaded-cube refresh should update tab presentation and use editor insertion."""

    inserted: list[dict[str, object]] = []
    fallback_refresh_calls: list[str] = []
    workflow = SimpleNamespace(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/demo.cube",
                version="2.0",
                alias="CubeA",
                original_cube={},
                buffer={},
                display_name="Demo",
                ui={
                    "canonical_cube": {
                        "cube_id": "Owner/Repo/demo.cube",
                        "version": "2.0",
                        "metadata": {"default_alias": "Demo"},
                    }
                },
            )
        },
        stack_order=["CubeA"],
    )
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=_PresentationStack("CubeA"),
        cube_icon_factory=SimpleNamespace(icon_for_cube=lambda **_kwargs: "icon"),
        cube_tab_fallback_icon="fallback",
        workflow_issue_state=None,
        active_editor_panel=SimpleNamespace(
            insert_cube_section=lambda *_args, **kwargs: inserted.append(kwargs)
        ),
        get_active_workflow=lambda: workflow,
    )

    refreshed = refresh_loaded_cube_surface_for_view(
        cube_view=cube_view,
        workflow_workspace_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            override_managers={},
            canvas_route_controller=SimpleNamespace(
                refresh_input_canvas_availability=lambda: None,
            ),
        ),
        workflow_workspace=SimpleNamespace(
            reconcile_active_workflow_after_structural_mutation=lambda: (
                fallback_refresh_calls.append("fallback")
            )
        ),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
    )

    assert refreshed is True
    assert inserted[0]["completion_phase"] == "first_usable"
    assert fallback_refresh_calls == []
    assert cube_view.active_cube_stack.icons == [(0, "icon")]


def test_refresh_loaded_cube_surface_for_view_uses_fallback_without_insert() -> None:
    """Loaded-cube refresh should fall back to full active-workflow reconciliation."""

    fallback_refresh_calls: list[str] = []
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=None,
        active_editor_panel=None,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )

    refreshed = refresh_loaded_cube_surface_for_view(
        cube_view=cube_view,
        workflow_workspace_view=SimpleNamespace(),
        workflow_workspace=SimpleNamespace(
            reconcile_active_workflow_after_structural_mutation=lambda: (
                fallback_refresh_calls.append("fallback")
            )
        ),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
    )

    assert refreshed is True
    assert fallback_refresh_calls == ["fallback"]


def test_refresh_loaded_cube_surface_for_view_skips_stale_workflow() -> None:
    """Loaded-cube refresh should ignore callbacks for inactive workflows."""

    fallback_refresh_calls: list[str] = []

    refreshed = refresh_loaded_cube_surface_for_view(
        cube_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-current"),
            active_editor_panel=None,
        ),
        workflow_workspace_view=SimpleNamespace(),
        workflow_workspace=SimpleNamespace(
            reconcile_active_workflow_after_structural_mutation=lambda: (
                fallback_refresh_calls.append("fallback")
            )
        ),
        workflow_id="wf-old",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
    )

    assert refreshed is False
    assert fallback_refresh_calls == []


def test_refresh_loaded_cube_surface_for_view_async_waits_for_complete_phase() -> None:
    """Async loaded-cube refresh should pass complete phase when requested."""

    inserted: list[dict[str, object]] = []
    completed: list[bool] = []
    workflow = SimpleNamespace(cubes={"CubeA": "cube-state"}, stack_order=["CubeA"])

    def insert_cube_section(*_args: object, **kwargs: object) -> None:
        """Record insert options and complete the progressive editor build."""

        inserted.append(kwargs)
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    refresh_loaded_cube_surface_for_view_async(
        cube_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            active_editor_panel=SimpleNamespace(
                insert_cube_section=insert_cube_section
            ),
            get_active_workflow=lambda: workflow,
        ),
        workflow_workspace_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            override_managers={},
            canvas_route_controller=SimpleNamespace(
                refresh_input_canvas_availability=lambda: None,
            ),
        ),
        workflow_workspace=SimpleNamespace(
            reconcile_active_workflow_after_structural_mutation=lambda: None
        ),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
        on_complete=completed.append,
        wait_for_complete=True,
    )

    assert completed == [True]
    assert inserted[0]["completion_phase"] == "complete"


def test_refresh_workflow_after_cube_load_for_view_activates_after_refresh() -> None:
    """Workflow refresh should activate a loaded cube after successful refresh."""

    activated: list[tuple[str, str]] = []
    workflow = SimpleNamespace(cubes={"CubeA": "cube-state"}, stack_order=["CubeA"])

    refresh_workflow_after_cube_load_for_view(
        cube_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            active_editor_panel=SimpleNamespace(
                insert_cube_section=lambda *_args, **_kwargs: None
            ),
            get_active_workflow=lambda: workflow,
        ),
        workflow_workspace_view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
            override_managers={},
            canvas_route_controller=SimpleNamespace(
                refresh_input_canvas_availability=lambda: None,
            ),
        ),
        workflow_workspace=SimpleNamespace(
            reconcile_active_workflow_after_structural_mutation=lambda: None
        ),
        workflow_id="wf-a",
        cube_alias="CubeA",
        schedule_deferred_rebuild=lambda _callback: None,
        activate_loaded_cube=lambda workflow_id, cube_alias: activated.append(
            (workflow_id, cube_alias)
        ),
    )

    assert activated == [("wf-a", "CubeA")]
