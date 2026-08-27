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

"""Verify cube-stack signal routing and wheel fallback behavior."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QTimer

from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)

from .support import _Signal


def test_cube_stack_signals_route_stack_events_and_optional_signals() -> None:
    """Cube-stack wiring should defer picker dependencies to the picker action."""

    events: list[tuple[str, object]] = []
    wheel_events: list[object] = []
    cube_stack = SimpleNamespace(
        cubeRenameEditRequested=_Signal(),
        cubeRenameRequested=_Signal(),
        aliasEditingFinished=_Signal(),
        cubeMoveFinished=_Signal(),
        tabMouseReleased=_Signal(),
        cubeAddRequested=_Signal(),
        cubeCloseRequested=_Signal(),
        cubeDuplicateRequested=_Signal(),
        cubeBypassToggleRequested=_Signal(),
        cubeOutputPersistenceToggleRequested=_Signal(),
        cubeStackWheelRerouteRequested=_Signal(),
    )
    active_panel = SimpleNamespace(
        handle_external_wheel=lambda event: wheel_events.append(event)
    )
    shell = SimpleNamespace(
        active_editor_panel=active_panel,
        workspace_cube_picker_actions=SimpleNamespace(
            show_cube_picker=lambda: events.append(("picker", None)),
        ),
        workspace_cube_stack_actions=SimpleNamespace(
            on_cube_rename_edit_requested=lambda route_key: events.append(
                ("rename_edit", route_key)
            ),
            on_cube_rename_requested=lambda old_key, new_key, *, timer: events.append(
                ("renamed", (old_key, new_key, timer))
            ),
            on_cube_rename_edit_finished=lambda route_key: events.append(
                ("rename_edit_finished", route_key)
            ),
            on_cube_move_finished=lambda: events.append(("move_finished", None)),
            on_tab_mouse_released=lambda index: events.append(
                ("mouse_released", index)
            ),
            on_cube_close_requested=lambda index: events.append(("closed", index)),
            on_cube_duplicate_requested=lambda route_key: events.append(
                ("duplicate", route_key)
            ),
            on_cube_bypass_toggle_requested=lambda route_key: events.append(
                ("bypass", route_key)
            ),
            on_cube_output_persistence_toggle_requested=lambda route_key: events.append(
                ("output_persistence", route_key)
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_cube_stack_signals(cube_stack)
    wheel_event = object()
    cube_stack.cubeRenameEditRequested.fire("OldAlias")
    cube_stack.cubeRenameRequested.fire("OldAlias", "NewAlias")
    cube_stack.aliasEditingFinished.fire("OldAlias")
    cube_stack.cubeMoveFinished.fire()
    cube_stack.tabMouseReleased.fire(4)
    cube_stack.cubeAddRequested.fire()
    cube_stack.cubeCloseRequested.fire(3)
    cube_stack.cubeDuplicateRequested.fire("OldAlias")
    cube_stack.cubeBypassToggleRequested.fire("OldAlias")
    cube_stack.cubeOutputPersistenceToggleRequested.fire("OldAlias")
    cube_stack.cubeStackWheelRerouteRequested.fire(wheel_event)

    assert events == [
        ("rename_edit", "OldAlias"),
        ("renamed", ("OldAlias", "NewAlias", QTimer)),
        ("rename_edit_finished", "OldAlias"),
        ("move_finished", None),
        ("mouse_released", 4),
        ("picker", None),
        ("closed", 3),
        ("duplicate", "OldAlias"),
        ("bypass", "OldAlias"),
        ("output_persistence", "OldAlias"),
    ]
    assert wheel_events == [wheel_event]


def test_cube_stack_wheel_reroute_ignores_without_active_editor_panel() -> None:
    """Wheel rerouting should leave the event unhandled when no editor is active."""

    calls: list[str] = []
    shell = SimpleNamespace(active_editor_panel=None)
    event = SimpleNamespace(ignore=lambda: calls.append("ignored"))

    MainWindowSignalBinder(shell).route_cube_stack_wheel_to_editor_panel(event)

    assert calls == ["ignored"]
