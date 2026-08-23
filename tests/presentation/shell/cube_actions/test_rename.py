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

"""Cube rename expansion, resolution, and presentation contracts."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any


from tests.presentation.shell.cube_actions.support import (
    _import_stack_module,
    _stack_actions,
    _surface_refresher,
)


def test_cube_rename_edit_request_expands_compact_stack_before_editing() -> None:
    """Compact rename editing should wait for temporary expansion completion."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []
    completion_callbacks: list[Callable[[], None]] = []

    class _Stack:
        def __init__(self) -> None:
            self.edit_requests: list[str] = []

        def begin_alias_editing(self, route_key: str) -> bool:
            self.edit_requests.append(route_key)
            events.append(("begin_edit", route_key))
            return True

        def isCompact(self) -> bool:
            return True

    stack = _Stack()

    lease = SimpleNamespace(release=lambda: events.append(("release", "Old")))

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        events.append(("acquire", "Old"))
        if on_expanded is not None:
            completion_callbacks.append(on_expanded)
        return lease

    view = SimpleNamespace(
        active_cube_stack=stack,
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("Old")

    assert events == [("acquire", "Old")]
    assert stack.edit_requests == []

    completion_callbacks[0]()

    assert stack.edit_requests == ["Old"]
    assert events == [
        ("acquire", "Old"),
        ("begin_edit", "Old"),
    ]


def test_cube_rename_edit_finish_releases_temporary_expansion_lease() -> None:
    """Alias editing should release its presentation lease on every finish path."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []

    class _Stack:
        def begin_alias_editing(self, route_key: str) -> bool:
            events.append(("begin_edit", route_key))
            return True

        def isCompact(self) -> bool:
            return False

    lease_counter = {"value": 0}

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        lease_counter["value"] += 1
        lease_id = lease_counter["value"]
        events.append(("acquire", lease_id))
        if on_expanded is not None:
            on_expanded()
        return SimpleNamespace(
            release=lambda: events.append(("release", lease_id)),
        )

    view = SimpleNamespace(
        active_cube_stack=_Stack(),
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("CompactAlias")
    actions.on_cube_rename_edit_finished("CompactAlias")

    actions.on_cube_rename_edit_requested("ExpandedAlias")
    actions.on_cube_rename_edit_finished("ExpandedAlias")

    assert events == [
        ("acquire", 1),
        ("begin_edit", "CompactAlias"),
        ("release", 1),
        ("acquire", 2),
        ("begin_edit", "ExpandedAlias"),
        ("release", 2),
    ]


def test_cube_rename_edit_abort_restores_compact_when_item_disappears() -> None:
    """Failed post-expansion editor start should undo temporary expansion."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []

    class _Stack:
        def begin_alias_editing(self, route_key: str) -> bool:
            events.append(("begin_edit", route_key))
            return False

        def isCompact(self) -> bool:
            return True

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        events.append(("acquire", "Gone"))
        if on_expanded is not None:
            on_expanded()
        return SimpleNamespace(
            release=lambda: events.append(("release", "Gone")),
        )

    view = SimpleNamespace(
        active_cube_stack=_Stack(),
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("Gone")

    assert events == [
        ("acquire", "Gone"),
        ("begin_edit", "Gone"),
        ("release", "Gone"),
    ]


def test_cube_rename_request_uses_service_resolution_to_update_ui_and_editor() -> None:
    """Rename requests should apply the service-resolved alias back into the shell state."""

    mod = _import_stack_module()
    service_calls: list[tuple[str, object]] = []
    workflow = SimpleNamespace(cubes={"Old": object()}, stack_order=["Old"])
    tab_item: Any
    tab_item = SimpleNamespace(
        _route_key="Old",
        text="Old",
        tooltip="Old",
        secondary_text="v1.0.0 · base-cubes",
        routeKey=lambda: tab_item._route_key,
        setRouteKey=lambda key: setattr(tab_item, "_route_key", key),
        setText=lambda text: setattr(tab_item, "text", text),
        setToolTip=lambda text: setattr(tab_item, "tooltip", text),
    )
    active_panel = SimpleNamespace(
        rename_cube=lambda old_key, new_key: service_calls.append(
            (
                "panel_rename",
                (old_key, new_key),
            )
        ),
        scroll_to_cube=lambda alias, animated=False: service_calls.append(
            (
                "panel_scroll",
                (alias, animated),
            )
        ),
    )
    active_stack = SimpleNamespace(
        itemMap={"Old": tab_item},
        count=lambda: 1,
        tabItem=lambda _index: tab_item,
        removeTab=lambda index: service_calls.append(("remove_tab", index)),
    )

    def apply_cube_rename(
        workflow_state: object,
        old_alias: str,
        new_alias: str,
    ) -> SimpleNamespace:
        """Record rename service input and return its resolved alias."""
        service_calls.append(("rename", (old_alias, new_alias, workflow_state)))
        return SimpleNamespace(resolved_alias="New 2")

    view = SimpleNamespace(
        active_editor_panel=active_panel,
        active_cube_stack=active_stack,
        cube_stack_service=SimpleNamespace(
            apply_cube_rename=apply_cube_rename,
            apply_reordered_aliases=lambda workflow_state, new_order: (
                service_calls.append(("reorder", (new_order, workflow_state)))
            ),
            apply_cube_removal=lambda workflow_state, alias_name: service_calls.append(
                (
                    "remove",
                    (alias_name, workflow_state),
                )
            ),
        ),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: service_calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_requested(
        "Old", "New", timer=SimpleNamespace(singleShot=lambda _ms, fn: fn())
    )

    assert ("rename", ("Old", "New", workflow)) in service_calls
    assert ("panel_rename", ("Old", "New 2")) in service_calls
    assert ("panel_scroll", ("New 2", True)) in service_calls
    assert active_stack.itemMap == {"New 2": tab_item}
    assert tab_item.routeKey() == "New 2"
    assert tab_item.text == "New 2"
    assert tab_item.tooltip == "New 2"
    assert tab_item.secondary_text == "v1.0.0 · base-cubes"
