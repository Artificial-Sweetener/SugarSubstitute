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

"""Test loaded-cube shell surface action projection."""

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
    refresh_active_cube_stack_tab_for_view,
)


from .surface_support import _PresentationStack

PROJECT_ROOT = Path(__file__).resolve().parents[5]
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
