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

"""Verify MainWindow signal binder menu wiring."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
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
