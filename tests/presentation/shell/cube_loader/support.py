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

"""Provide typed doubles and builders for cube-loader contracts."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from tests.support.execution import ImmediateTaskSubmitter

from .execution_support import _route_factory


def _import_cube_loader_module(_monkeypatch: object) -> Any:
    """Import the cube-load orchestration owner without Qt-global replacement."""

    module = importlib.import_module("substitute.presentation.shell.cube_loader")
    return module


class _FakeQTimer:
    """Queueing timer shim to control callback ordering in tests."""

    queue: list[Callable[[], None]] = []

    @staticmethod
    def clear() -> None:
        _FakeQTimer.queue.clear()

    @staticmethod
    def singleShot(_msec: int, callback: Callable[[], None]) -> None:
        _FakeQTimer.queue.append(callback)

    @staticmethod
    def run_all() -> None:
        while _FakeQTimer.queue:
            callback = _FakeQTimer.queue.pop(0)
            callback()

    @staticmethod
    def run_next() -> None:
        """Run one queued timer callback."""

        callback = _FakeQTimer.queue.pop(0)
        callback()


class _FakeTabItem:
    """Simple cube tab item carrying only route key state."""

    def __init__(self, key: str) -> None:
        self._key = key

    def routeKey(self) -> str:
        return self._key

    def setRouteKey(self, key: str) -> None:
        self._key = key


class _FakeCubeStack:
    """Small stack double that mimics the subset used by load_cube_async."""

    def __init__(self, initial_key: str) -> None:
        self.items = [_FakeTabItem(initial_key)]
        self.itemMap = {initial_key: self.items[0]}
        self.tab_text_calls: list[tuple[int, str]] = []
        self.tab_presentation_calls: list[tuple[int, str, str, str]] = []
        self.tab_icon_calls: list[tuple[int, object]] = []
        self.current_index_calls: list[int] = []
        self.alive = True

    def __bool__(self) -> bool:
        return self.alive

    def setTabText(self, index: int, text: str) -> None:
        self.tab_text_calls.append((index, text))

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Record complete cube tab presentation updates."""

        self.tab_presentation_calls.append(
            (index, primary_text, secondary_text, tooltip_text)
        )
        self.setTabText(index, primary_text)

    def setTabIcon(self, index: int, icon: object) -> None:
        self.tab_icon_calls.append((index, icon))

    def tabItem(self, index: int) -> _FakeTabItem:
        return self.items[index]

    def setCurrentIndex(self, index: int) -> None:
        self.current_index_calls.append(index)

    def count(self) -> int:
        return len(self.items)


class _FakeEditorPanel:
    """Simple editor panel double for scroll calls and lifecycle simulation."""

    def __init__(self) -> None:
        self.scroll_calls: list[tuple[str, bool]] = []
        self.reveal_calls: list[str] = []
        self.alive = True

    def __bool__(self) -> bool:
        return self.alive

    def scroll_to_cube(self, alias: str, animated: bool = True) -> None:
        self.scroll_calls.append((alias, animated))

    def reveal_new_cube(self, route_key: str) -> None:
        self.reveal_calls.append(route_key)


class _FakeCubeIconFactory:
    """Record cube icon resolution requests and return a deterministic token."""

    def __init__(self) -> None:
        """Initialize empty icon resolution call history."""

        self.calls: list[tuple[str, str, object | None]] = []

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Record the requested cube and return a stable icon token."""

        _ = catalog_revision, cube_content_hash, render_size
        self.calls.append((cube_id, display_name, icon))
        return "resolved-icon-token"


class _FailingCubeIconFactory:
    """Record cube icon resolution requests and raise an expected failure."""

    def __init__(self) -> None:
        """Initialize empty icon resolution call history."""

        self.calls: list[tuple[str, str, object | None]] = []

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Record the requested cube and raise a resolution failure."""

        _ = catalog_revision, cube_content_hash, render_size
        self.calls.append((cube_id, display_name, icon))
        raise RuntimeError("icon unavailable")


def _build_loader_state(
    module: Any, alias_name: str
) -> tuple[Any, Any, list[tuple[str, str]], list[tuple[str, str]]]:
    """Build focused callback state for cube-loader orchestration tests."""
    from substitute.domain.workflow import WorkflowState
    from substitute.application.node_behavior import NodeBehaviorRuntimeState

    materialized: list[tuple[str, str]] = []
    refresh_calls: list[tuple[str, str]] = []

    cube_stack_service = SimpleNamespace(loaded_cubes={}, added=[])

    def _apply_cube_addition(
        workflow: Any, cube_id: str, alias: str, cube_state: Any
    ) -> None:
        cube_stack_service.added.append((workflow, cube_id, alias, cube_state))
        workflow.cubes[alias] = cube_state
        workflow.stack_order.append(alias)

    def _resolve_unique_alias(workflow: Any, requested_alias: str) -> str:
        if requested_alias not in workflow.cubes:
            return requested_alias
        suffix = 2
        while f"{requested_alias} {suffix}" in workflow.cubes:
            suffix += 1
        return f"{requested_alias} {suffix}"

    cube_stack_service.resolve_unique_alias = _resolve_unique_alias
    cube_stack_service.apply_cube_addition = _apply_cube_addition
    cube_stack_service.apply_reordered_aliases = lambda workflow, new_order: setattr(
        workflow, "stack_order", list(new_order)
    )

    state = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wfA",
            workflows={"wfA": WorkflowState(), "wfB": WorkflowState()},
        ),
        cube_stacks={
            "wfA": _FakeCubeStack(f"loading:{alias_name}"),
            "wfB": _FakeCubeStack("loading:Other"),
        },
        editor_panels={"wfA": _FakeEditorPanel(), "wfB": _FakeEditorPanel()},
        cube_stack_service=cube_stack_service,
        cube_icon_factory=_FakeCubeIconFactory(),
        materialize_loaded_cube_input_canvas=lambda workflow_id, alias: (
            materialized.append((workflow_id, alias))
        ),
        refresh_workflow_after_cube_load=lambda workflow_id, alias: (
            refresh_calls.append((workflow_id, alias))
        ),
    )

    def build_callbacks(cube_load_service: object) -> Any:
        return module.CubeLoadUiCallbacks(
            workflow_session_service=state.workflow_session_service,
            cube_stacks=state.cube_stacks,
            editor_panels=state.editor_panels,
            cube_load_service=cube_load_service,
            cube_stack_service=state.cube_stack_service,
            materialize_loaded_cube_input_canvas=(
                state.materialize_loaded_cube_input_canvas
            ),
            refresh_workflow_after_cube_load=state.refresh_workflow_after_cube_load,
            prepare_node_behavior_runtime=lambda _loaded_cube, _alias: (
                NodeBehaviorRuntimeState()
            ),
            cube_icon_factory=state.cube_icon_factory,
            cube_load_execution_route_factory=_route_factory(
                module,
                ImmediateTaskSubmitter(),
            ),
            schedule_next_gui_turn=_FakeQTimer.queue.append,
        )

    return state, build_callbacks, materialized, refresh_calls


def _stub_cube_service(
    *,
    graph: dict[str, Any] | None = None,
    error: Exception | None = None,
    icon: object | None = None,
    ui_payload: dict[str, object] | None = None,
) -> Any:
    """Build a simple cube-load service stub for loader orchestration tests."""
    from substitute.domain.workflow import CubeState

    class _Service:
        def load_cube_definition(self, _cube_id: str) -> Any:
            if error is not None:
                raise error
            return SimpleNamespace(
                cube_id=_cube_id,
                version="1.0.0",
                display_name=f"{_cube_id} Display",
                graph=graph or {"nodes": {}},
                ui_payload=ui_payload,
                icon=icon,
            )

        def load_cube_definition_version(self, _cube_id: str, version: str) -> Any:
            if error is not None:
                raise error
            return SimpleNamespace(
                cube_id=_cube_id,
                version=version,
                display_name=f"{_cube_id} Display",
                graph=graph or {"nodes": {}},
                ui_payload=ui_payload,
                icon=icon,
            )

        def merge_cube_buffer_patch(
            self,
            *,
            cube_buffer: dict[str, Any],
            buffer_patch: dict[str, Any],
            cube_definition: dict[str, Any],
        ) -> None:
            del cube_definition
            cube_buffer.update(buffer_patch)

        def build_loaded_cube_runtime(
            self,
            cube_id: str,
            alias_name: str,
            *,
            buffer_patch: dict[str, Any] | None,
            runtime_state: object | None,
            loaded_cube_definition: Any | None = None,
        ) -> SimpleNamespace:
            loaded: Any = loaded_cube_definition or self.load_cube_definition(cube_id)
            cube_definition = loaded.graph
            cube_buffer = dict(cube_definition)
            if buffer_patch is not None:
                self.merge_cube_buffer_patch(
                    cube_buffer=cube_buffer,
                    buffer_patch=buffer_patch,
                    cube_definition=cube_definition,
                )
            ui_payload = (
                dict(loaded.ui_payload) if loaded.ui_payload is not None else None
            )
            if loaded.icon is not None:
                if ui_payload is None:
                    ui_payload = {}
                ui_payload["cube_icon"] = loaded.icon
            if ui_payload is not None:
                ui_payload["node_behavior_runtime"] = runtime_state
            cube_state = CubeState(
                cube_id=cube_id,
                version=loaded.version,
                alias=alias_name,
                original_cube=cube_definition,
                buffer=cube_buffer,
                display_name=loaded.display_name,
            )
            if ui_payload is not None:
                cube_state.ui = ui_payload
            return SimpleNamespace(
                cube_id=cube_id,
                version=loaded.version,
                display_name=loaded.display_name,
                cube_definition=cube_definition,
                cube_buffer=cube_buffer,
                cube_state=cube_state,
                ui_payload=ui_payload,
                icon=loaded.icon,
            )

    return _Service()
