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

"""Tests for MainWindow-specific signal wiring and event delegation."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
import substitute.presentation.shell.session_autosave_controller as session_autosave_controller_module
from substitute.presentation.shell.session_autosave_controller import (
    SessionAutosaveController,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)


class _Signal:
    """Capture Qt-like signal connections and allow deterministic emission."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record a connected callback."""

        self._callbacks.append(callback)

    def fire(self, *args: object) -> None:
        """Emit one signal payload to all connected callbacks."""

        for callback in self._callbacks:
            callback(*args)


def test_menu_action_signals_route_toolbar_controls() -> None:
    """Toolbar menu wiring should target composed shell controllers."""

    override_calls: list[object] = []
    compact_calls: list[bool] = []
    shell = SimpleNamespace(
        cubeStackModeButton=SimpleNamespace(toggled=_Signal()),
        _global_override_menu=SimpleNamespace(triggered=_Signal()),
        cube_stack_presentation_controller=SimpleNamespace(
            request_preference=compact_calls.append
        ),
        workspace_search_actions=SimpleNamespace(
            proxy_override_menu_toggled=override_calls.append,
        ),
    )

    MainWindowSignalBinder(shell).connect_menu_action_signals()
    shell._global_override_menu.triggered.fire("pin-action")
    shell.cubeStackModeButton.toggled.fire(True)

    assert override_calls == ["pin-action"]
    assert compact_calls == [True]


def test_mainwindow_drag_drop_events_delegate_to_workspace_drop_controller() -> None:
    """MainWindow drag/drop overrides should delegate to the workspace drop owner."""

    events: list[tuple[str, object]] = []
    enter_event = object()
    move_event = object()
    drop_event = object()

    def handle_drag_enter(event: object) -> bool:
        """Record accepted drag-enter handling."""

        events.append(("enter", event))
        return True

    def handle_drag_move(event: object) -> bool:
        """Record accepted drag-move handling."""

        events.append(("move", event))
        return True

    def handle_drop(event: object) -> bool:
        """Record accepted drop handling."""

        events.append(("drop", event))
        return True

    shell = SimpleNamespace(
        workspace_drop_controller=SimpleNamespace(
            handle_drag_enter=handle_drag_enter,
            handle_drag_move=handle_drag_move,
            handle_drop=handle_drop,
        )
    )

    main_window_type = cast(Any, MainWindow)
    main_window_type.dragEnterEvent(cast(Any, shell), cast(Any, enter_event))
    main_window_type.dragMoveEvent(cast(Any, shell), cast(Any, move_event))
    main_window_type.dropEvent(cast(Any, shell), cast(Any, drop_event))

    assert events == [
        ("enter", enter_event),
        ("move", move_event),
        ("drop", drop_event),
    ]


def test_tab_selection_autosave_uses_debounce_timer_without_coordinator() -> None:
    """Workflow tab selection should restart the legacy timer before autosaving."""

    calls: list[tuple[str, object]] = []
    timer = SimpleNamespace(
        start=lambda interval: calls.append(("start", interval)),
    )
    shell = SimpleNamespace(
        _tab_selection_autosave_timer=timer,
        _initial_workspace_hydrated=True,
        _shell_restore_lifecycle="running",
        _startup_autosave_unmuted_marked=True,
        session_autosave_service=SimpleNamespace(
            request_save=lambda _port: calls.append(("autosave", None))
        ),
    )
    controller = SessionAutosaveController(shell)

    controller.request_tab_selection_autosave()
    controller.request_tab_selection_autosave()
    controller.run_tab_selection_autosave()

    assert calls == [
        (
            "start",
            session_autosave_controller_module._TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS,
        ),
        (
            "start",
            session_autosave_controller_module._TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS,
        ),
        ("autosave", None),
    ]


def test_categorized_session_autosave_uses_composed_coordinator() -> None:
    """Categorized autosave requests should route through the autosave coordinator."""

    categories: list[SessionAutosaveRequestCategory] = []
    shell = SimpleNamespace(
        _session_autosave_coordinator=SimpleNamespace(request=categories.append),
        request_session_autosave=lambda: categories.append(
            cast(SessionAutosaveRequestCategory, "fallback")
        ),
    )
    controller = SessionAutosaveController(shell)

    controller.request_categorized_session_autosave(
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
    )

    assert categories == [SessionAutosaveRequestCategory.CANVAS_SELECTION]
