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

"""Build workspace cube-action test doubles."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from substitute.domain.links import NodeLinkEndpointIndex, PromptEndpointIndex


def _import_module() -> Any:
    """Import the workspace cube actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_cube_picker_actions"
    )


def _import_stack_module() -> Any:
    """Import the focused workspace cube-card actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_cube_stack_actions"
    )


def _stack_actions(module: Any, view: object) -> Any:
    """Build focused cube-card actions with unused feature dependencies."""

    return module.WorkspaceCubeStackActions(
        view,
        duplication_service=SimpleNamespace(),
        stack_presenter=SimpleNamespace(),
        surface_projector=SimpleNamespace(),
    )


def _surface_refresher(
    refresh: Callable[..., None],
) -> SimpleNamespace:
    """Build a composed active workflow surface refresher double."""

    return SimpleNamespace(refresh_active_workflow_surface=refresh)


class _CubeStack:
    """Cube-stack double tracking inserted placeholders and selection."""

    def __init__(self) -> None:
        self.items: list[Any] = []
        self.current_indices: list[int] = []
        self.bypassed_updates: list[tuple[int, bool]] = []

    def count(self) -> int:
        """Return item count."""

        return len(self.items)

    def insertTab(self, index: int, **kwargs: object) -> Any:
        """Insert one placeholder cube tab."""

        item = SimpleNamespace(
            index=index,
            kwargs=kwargs,
            _route_key=kwargs.get("routeKey", ""),
        )
        item.routeKey = lambda item=item: item._route_key
        item.setRouteKey = lambda key, item=item: setattr(item, "_route_key", key)
        self.items.insert(index, item)
        return item

    def tabItem(self, index: int) -> Any:
        """Return one stack item."""

        return self.items[index]

    def removeTab(self, index: int) -> None:
        """Remove one stack item."""

        self.items.pop(index)

    def reorder_by_route_keys(self, route_keys: list[str]) -> None:
        """Project item order by route key."""

        if len(route_keys) != len(self.items):
            return
        by_route = {item.routeKey(): item for item in self.items}
        if any(route_key not in by_route for route_key in route_keys):
            return
        self.items = [by_route[route_key] for route_key in route_keys]

    def setCurrentIndex(self, index: int) -> None:
        """Record current-index changes."""

        self.current_indices.append(index)

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Record bypass presentation updates."""

        self.bypassed_updates.append((index, bypassed))


class _EmptyNodeBehaviorService:
    """Endpoint provider double that exposes no linkable nodes."""

    def build_prompt_endpoint_index(
        self,
        cube_states: object,
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return an empty prompt endpoint index."""

        return PromptEndpointIndex()

    def build_node_link_endpoint_index(
        self,
        cube_states: object,
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return an empty whole-node endpoint index."""

        return NodeLinkEndpointIndex()


class _EditorBusyRecorder:
    """Record editor busy controller calls for cube action tests."""

    def __init__(self, calls: list[tuple[str, object]]) -> None:
        """Store the shared call list."""

        self._calls = calls

    def begin(self, workflow_id: str, *, message: str = "Loading") -> object:
        """Record a begin request and return a stable token."""

        self._calls.append(("begin", (workflow_id, message)))
        return "busy-token"

    def end(self, token: object) -> None:
        """Record an end request."""

        self._calls.append(("end", token))


def _finish_queued_load(
    queued: list[dict[str, object]],
    stack: _CubeStack,
    index: int,
    resolved_alias: str | None,
) -> None:
    """Resolve a queued loader callback the way the real cube loader does."""

    queued_call = queued[index]
    if resolved_alias is not None:
        placeholder_index = queued_call["placeholder_index"]
        assert isinstance(placeholder_index, int)
        stack.tabItem(placeholder_index).setRouteKey(resolved_alias)
    finish = queued_call["on_load_finished"]
    assert callable(finish)
    finish(resolved_alias)
