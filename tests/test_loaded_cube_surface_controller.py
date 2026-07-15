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

"""Tests for loaded-cube shell surface refresh helpers."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.domain.workflow import CubeState
from substitute.presentation.shell import loaded_cube_surface_controller as surface_mod
from substitute.presentation.shell.loaded_cube_surface_controller import (
    WorkspaceLoadedCubeSurfaceActions,
    activate_loaded_cube_surface,
    build_cube_load_ui_callbacks_for_view,
    cube_stack_tab_index,
    mark_loaded_cube_surface_stale,
    refresh_active_cube_stack_tab_for_view,
    refresh_incremental_loaded_cube_surface,
    refresh_loaded_cube_surface_for_view,
    refresh_loaded_cube_surface_for_view_async,
    refresh_workflow_after_cube_load_for_view,
    schedule_deferred_incremental_override_presentation_rebuild,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "loaded_cube_surface_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


class _PresentationTab:
    """Expose a route key for stack presentation tests."""

    def __init__(self, route_key: str) -> None:
        """Store the route key."""

        self._route_key = route_key

    def routeKey(self) -> str:
        """Return the cube alias route key."""

        return self._route_key

    def setRouteKey(self, route_key: str) -> None:
        """Replace the cube alias route key."""

        self._route_key = route_key


class _PresentationStack:
    """Collect tab presentation updates for one stack tab."""

    def __init__(self, *route_keys: str) -> None:
        """Create route-keyed tab items."""

        self._items = [_PresentationTab(route_key) for route_key in route_keys]
        self.itemMap: dict[str, _PresentationTab] = {
            item.routeKey(): item for item in self._items
        }
        self.presentations: list[dict[str, object]] = []
        self.icons: list[tuple[int, object]] = []
        self.issue_severities: list[tuple[str, str | None]] = []
        self.bypassed: list[tuple[int, bool]] = []

    def count(self) -> int:
        """Return the number of test tabs."""

        return len(self._items)

    def tabItem(self, index: int) -> _PresentationTab:
        """Return one tab item by index."""

        return self._items[index]

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Record a tab presentation update."""

        self.presentations.append(
            {
                "index": index,
                "primary_text": primary_text,
                "secondary_text": secondary_text,
                "tooltip_text": tooltip_text,
            }
        )

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record a tab icon update."""

        self.icons.append((index, icon))

    def setTabIssueSeverity(self, route_key: str, severity: str | None) -> None:
        """Record a tab issue severity update."""

        self.issue_severities.append((route_key, severity))

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Record cube bypass presentation state."""

        self.bypassed.append((index, bypassed))


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_cube_stack_tab_index_returns_route_key_index() -> None:
    """Tab index lookup should find the current tab by route key."""

    stack = _PresentationStack("CubeA", "CubeB")

    assert cube_stack_tab_index(stack, "CubeB") == 1
    assert cube_stack_tab_index(stack, "Missing") is None


def test_build_cube_load_ui_callbacks_for_view_assembles_shell_collaborators() -> None:
    """Cube-load callback assembly should bind view services and shell callbacks."""

    materialize_calls: list[tuple[str, str]] = []
    refresh_calls: list[tuple[str, str]] = []
    prepare_calls: list[tuple[object, str]] = []
    refresh_surface_calls: list[tuple[str, str]] = []
    activate_calls: list[tuple[str, str]] = []
    refresh_async_calls: list[tuple[str, str]] = []
    refresh_surface_async_calls: list[tuple[str, str]] = []
    route_factory_calls: list[str] = []
    workflow_session_service = SimpleNamespace(
        active_workflow_id="wf-a",
        workflows={"wf-a": object()},
    )
    cube_view = SimpleNamespace(
        workflow_session_service=workflow_session_service,
        cube_stacks={"wf-a": object()},
        editor_panels={"wf-a": object()},
        cube_load_service=object(),
        cube_stack_service=object(),
        cube_icon_factory=object(),
        active_cube_stack=object(),
        active_editor_panel=object(),
    )

    def materialize_loaded_cube_input_canvas(
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Record loaded-cube Input canvas materialization."""

        materialize_calls.append((workflow_id, cube_alias))

    def refresh_workflow_after_cube_load(workflow_id: str, cube_alias: str) -> None:
        """Record loaded-cube workflow refresh."""

        refresh_calls.append((workflow_id, cube_alias))

    def prepare_node_behavior_runtime(loaded_cube: object, alias: str) -> object:
        """Record node-behavior runtime preparation."""

        prepare_calls.append((loaded_cube, alias))
        return object()

    def refresh_loaded_cube_surface(
        workflow_id: str,
        cube_alias: str,
        **_kwargs: object,
    ) -> bool:
        """Record loaded-cube surface refresh."""

        refresh_surface_calls.append((workflow_id, cube_alias))
        return True

    def activate_loaded_cube(workflow_id: str, cube_alias: str) -> None:
        """Record loaded-cube activation."""

        activate_calls.append((workflow_id, cube_alias))

    def refresh_workflow_after_cube_load_async(
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[], None],
    ) -> None:
        """Record async loaded-cube workflow refresh."""

        refresh_async_calls.append((workflow_id, cube_alias))
        on_complete()

    def refresh_loaded_cube_surface_async(
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[bool], None],
        **_kwargs: object,
    ) -> None:
        """Record async loaded-cube surface refresh."""

        refresh_surface_async_calls.append((workflow_id, cube_alias))
        on_complete(True)

    def cube_load_execution_route_factory(*, cube_load_trace_id: str) -> object:
        """Record cube-load execution route requests."""

        route_factory_calls.append(cube_load_trace_id)
        return object()

    callbacks = build_cube_load_ui_callbacks_for_view(
        cube_view=cube_view,
        callbacks_type=SimpleNamespace,
        materialize_loaded_cube_input_canvas=materialize_loaded_cube_input_canvas,
        refresh_workflow_after_cube_load=refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=prepare_node_behavior_runtime,
        refresh_loaded_cube_surface=refresh_loaded_cube_surface,
        activate_loaded_cube=activate_loaded_cube,
        refresh_workflow_after_cube_load_async=refresh_workflow_after_cube_load_async,
        refresh_loaded_cube_surface_async=refresh_loaded_cube_surface_async,
        cube_load_execution_route_factory=cube_load_execution_route_factory,
    )

    callbacks.materialize_loaded_cube_input_canvas("wf-a", "CubeA")
    callbacks.refresh_workflow_after_cube_load("wf-a", "CubeA")
    callbacks.prepare_node_behavior_runtime(object(), "CubeA")
    assert callbacks.refresh_loaded_cube_surface("wf-a", "CubeA") is True
    callbacks.activate_loaded_cube("wf-a", "CubeA")
    callbacks.refresh_workflow_after_cube_load_async("wf-a", "CubeA", lambda: None)
    callbacks.refresh_loaded_cube_surface_async(
        "wf-a",
        "CubeA",
        lambda _refreshed: None,
    )
    callbacks.cube_load_execution_route_factory(cube_load_trace_id="trace-a")

    assert callbacks.workflow_session_service is workflow_session_service
    assert callbacks.cube_stacks is cube_view.cube_stacks
    assert callbacks.editor_panels is cube_view.editor_panels
    assert callbacks.cube_load_service is cube_view.cube_load_service
    assert callbacks.cube_stack_service is cube_view.cube_stack_service
    assert callbacks.cube_icon_factory is cube_view.cube_icon_factory
    assert materialize_calls == [("wf-a", "CubeA")]
    assert refresh_calls == [("wf-a", "CubeA")]
    assert len(prepare_calls) == 1
    assert refresh_surface_calls == [("wf-a", "CubeA")]
    assert activate_calls == [("wf-a", "CubeA")]
    assert refresh_async_calls == [("wf-a", "CubeA")]
    assert refresh_surface_async_calls == [("wf-a", "CubeA")]
    assert route_factory_calls == ["trace-a"]


def test_workspace_loaded_cube_surface_actions_delegate_to_owner_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded-cube surface actions should supply composed collaborators."""

    calls: list[tuple[str, dict[str, object]]] = []
    cube_view = object()
    workflow_workspace_view = object()
    workflow_workspace = object()

    def schedule_deferred(callback: Callable[[], None]) -> None:
        """Accept deferred rebuild callbacks."""

        _ = callback

    def schedule_realign(callback: Callable[[], None]) -> None:
        """Accept indicator realign callbacks."""

        _ = callback

    def refresh_workflow_after_cube_load_for_view(**kwargs: object) -> None:
        """Record synchronous workflow refresh collaborator wiring."""

        calls.append(("refresh_workflow", kwargs))

    def refresh_workflow_after_cube_load_for_view_async(**kwargs: object) -> None:
        """Record async workflow refresh collaborator wiring."""

        calls.append(("refresh_workflow_async", kwargs))

    def refresh_loaded_cube_surface_for_view(**kwargs: object) -> bool:
        """Record synchronous surface refresh collaborator wiring."""

        calls.append(("refresh_surface", kwargs))
        return True

    def refresh_loaded_cube_surface_for_view_async(**kwargs: object) -> None:
        """Record async surface refresh collaborator wiring."""

        calls.append(("refresh_surface_async", kwargs))

    def mark_loaded_cube_surface_stale(
        view: object,
        workflow_id: str,
        cube_alias: str,
        *,
        reason: str,
    ) -> None:
        """Record stale-mark collaborator wiring."""

        calls.append(
            (
                "mark_stale",
                {
                    "view": view,
                    "workflow_id": workflow_id,
                    "cube_alias": cube_alias,
                    "reason": reason,
                },
            )
        )

    def activate_loaded_cube_surface(view: object, **kwargs: object) -> None:
        """Record activation collaborator wiring."""

        kwargs["view"] = view
        calls.append(("activate", kwargs))

    monkeypatch.setattr(
        surface_mod,
        "refresh_workflow_after_cube_load_for_view",
        refresh_workflow_after_cube_load_for_view,
    )
    monkeypatch.setattr(
        surface_mod,
        "refresh_workflow_after_cube_load_for_view_async",
        refresh_workflow_after_cube_load_for_view_async,
    )
    monkeypatch.setattr(
        surface_mod,
        "refresh_loaded_cube_surface_for_view",
        refresh_loaded_cube_surface_for_view,
    )
    monkeypatch.setattr(
        surface_mod,
        "refresh_loaded_cube_surface_for_view_async",
        refresh_loaded_cube_surface_for_view_async,
    )
    monkeypatch.setattr(
        surface_mod,
        "mark_loaded_cube_surface_stale",
        mark_loaded_cube_surface_stale,
    )
    monkeypatch.setattr(
        surface_mod,
        "activate_loaded_cube_surface",
        activate_loaded_cube_surface,
    )
    actions = WorkspaceLoadedCubeSurfaceActions(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_workspace=workflow_workspace,
        schedule_deferred_rebuild=schedule_deferred,
        schedule_indicator_realign=schedule_realign,
    )

    actions.refresh_workflow_after_cube_load("wf-a", "CubeA")
    actions.refresh_workflow_after_cube_load_async("wf-a", "CubeA", lambda: None)
    assert actions.refresh_loaded_cube_surface("wf-a", "CubeA") is True
    actions.refresh_loaded_cube_surface_async("wf-a", "CubeA", lambda _value: None)
    actions.mark_loaded_cube_surface_stale(
        "wf-a",
        "CubeA",
        reason="cube_definition_updated",
    )
    actions.activate_loaded_cube("wf-a", "CubeA")

    refresh_call = calls[0][1]
    assert refresh_call["cube_view"] is cube_view
    assert refresh_call["workflow_workspace_view"] is workflow_workspace_view
    assert refresh_call["workflow_workspace"] is workflow_workspace
    assert refresh_call["workflow_id"] == "wf-a"
    assert refresh_call["cube_alias"] == "CubeA"
    assert refresh_call["schedule_deferred_rebuild"] is schedule_deferred
    assert refresh_call["activate_loaded_cube"] == actions.activate_loaded_cube
    assert calls[2][0] == "refresh_surface"
    assert calls[4] == (
        "mark_stale",
        {
            "view": cube_view,
            "workflow_id": "wf-a",
            "cube_alias": "CubeA",
            "reason": "cube_definition_updated",
        },
    )
    assert calls[5][1]["schedule_indicator_realign"] is schedule_realign


def test_refresh_active_cube_stack_tab_skips_stale_workflow() -> None:
    """Tab refresh should not touch stale workflow stacks."""

    stack = _PresentationStack("CubeA")
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current"),
        active_cube_stack=stack,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )

    refreshed = refresh_active_cube_stack_tab_for_view(
        cube_view,
        "wf-stale",
        "CubeA",
    )

    assert refreshed is False
    assert stack.presentations == []


def test_refresh_active_cube_stack_tab_applies_cube_state_presentation() -> None:
    """Tab refresh should rederive tab presentation from loaded CubeState."""

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
    stack = _PresentationStack("CubeA")
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=stack,
        cube_icon_factory=SimpleNamespace(icon_for_cube=lambda **_kwargs: "icon"),
        cube_tab_fallback_icon="fallback",
        workflow_issue_state=None,
        get_active_workflow=lambda: workflow,
    )

    refreshed = refresh_active_cube_stack_tab_for_view(cube_view, "wf-a", "CubeA")

    assert refreshed is True
    assert stack.presentations == [
        {
            "index": 0,
            "primary_text": "CubeA",
            "secondary_text": "v2.0 · repo",
            "tooltip_text": (
                '<div style="max-width: 420px; width: 420px; white-space: normal; '
                'word-wrap: break-word; overflow-wrap: anywhere;">'
                "<b>Demo</b>, v2.0<br>Repo by Owner</div>"
            ),
        }
    ]
    assert stack.icons == [(0, "icon")]


def test_activate_loaded_cube_surface_selects_stack_and_reveals_editor() -> None:
    """Loaded-cube activation should select by alias and reveal the editor section."""

    selected: list[tuple[str, bool]] = []
    scheduled: list[Callable[[], None]] = []
    realigned: list[bool] = []
    revealed: list[str] = []
    stack = SimpleNamespace(
        select_cube=lambda alias, *, animated: selected.append((alias, animated)),
        realign_indicator=lambda *, animated: realigned.append(animated),
    )
    panel = SimpleNamespace(reveal_loaded_cube=lambda alias: revealed.append(alias))
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=stack,
        active_editor_panel=panel,
        get_active_workflow=lambda: SimpleNamespace(stack_order=["CubeA"]),
    )

    activate_loaded_cube_surface(
        cube_view,
        "wf-a",
        "CubeA",
        schedule_indicator_realign=scheduled.append,
    )
    scheduled[0]()

    assert selected == [("CubeA", True)]
    assert realigned == [False]
    assert revealed == ["CubeA"]


def test_activate_loaded_cube_surface_skips_selection_for_current_tab() -> None:
    """Loaded-cube activation should not reselect the already-current tab."""

    selected: list[tuple[str, bool]] = []
    realigned: list[bool] = []
    revealed: list[str] = []
    current_tab = SimpleNamespace(routeKey=lambda: "CubeA")
    stack = SimpleNamespace(
        currentTab=lambda: current_tab,
        select_cube=lambda alias, *, animated: selected.append((alias, animated)),
        realign_indicator=lambda *, animated: realigned.append(animated),
    )
    panel = SimpleNamespace(reveal_loaded_cube=lambda alias: revealed.append(alias))
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=stack,
        active_editor_panel=panel,
        get_active_workflow=lambda: SimpleNamespace(stack_order=["CubeA"]),
    )

    activate_loaded_cube_surface(
        cube_view,
        "wf-a",
        "CubeA",
        schedule_indicator_realign=lambda callback: callback(),
    )

    assert selected == []
    assert realigned == [False]
    assert revealed == ["CubeA"]


def test_activate_loaded_cube_surface_uses_index_fallback_without_select_cube() -> None:
    """Loaded-cube activation should use stack order when select_cube is absent."""

    selected_indices: list[int] = []
    revealed: list[str] = []
    stack = SimpleNamespace(
        setCurrentIndex=selected_indices.append,
    )
    panel = SimpleNamespace(reveal_new_cube=lambda alias: revealed.append(alias))
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        active_cube_stack=stack,
        active_editor_panel=panel,
        get_active_workflow=lambda: SimpleNamespace(stack_order=["CubeA", "CubeB"]),
    )

    activate_loaded_cube_surface(
        cube_view,
        "wf-a",
        "CubeB",
        schedule_indicator_realign=lambda _callback: None,
    )

    assert selected_indices == [1]
    assert revealed == ["CubeB"]


def test_activate_loaded_cube_surface_skips_stale_workflow() -> None:
    """Loaded-cube activation should ignore stale workflow callbacks."""

    selected: list[str] = []
    revealed: list[str] = []
    cube_view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current"),
        active_cube_stack=SimpleNamespace(
            select_cube=lambda alias, *, animated: selected.append(alias)
        ),
        active_editor_panel=SimpleNamespace(
            reveal_loaded_cube=lambda alias: revealed.append(alias)
        ),
    )

    activate_loaded_cube_surface(
        cube_view,
        "wf-old",
        "CubeA",
        schedule_indicator_realign=lambda _callback: None,
    )

    assert selected == []
    assert revealed == []


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


def test_loaded_cube_surface_controller_imports_no_qt_or_workspace_controller() -> None:
    """Loaded-cube surface helpers should not import Qt or workspace facade."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()
