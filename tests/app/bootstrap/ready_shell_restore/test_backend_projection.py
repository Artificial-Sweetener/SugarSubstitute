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

"""Test ready-shell restore shell backend-state projection contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap.ready_shell_restore_controller import (
    update_shell_backend_state,
)

from .restore_support import (
    _patch_trace,
)


class _BackendMainWindow:
    """Expose generation action state projection collaborators."""

    def __init__(self, *, generation_action_controller: object | None) -> None:
        """Store generation controller double."""

        self.generation_action_controller = generation_action_controller


class _GenerationActionController:
    """Record backend state updates."""

    def __init__(self, states: list[str]) -> None:
        """Store state records."""

        self._states = states

    def set_backend_state(self, state: str) -> None:
        """Record one backend state."""

        self._states.append(state)


def test_update_shell_backend_state_projects_generation_action_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should call the composed generation controller."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    states: list[str] = []
    main_window = _BackendMainWindow(
        generation_action_controller=_GenerationActionController(states)
    )

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is True
    assert states == ["ready"]
    assert events == [
        ("shell_backend_state.update", {"state": "ready", "route": "ready"}),
    ]


def test_update_shell_backend_state_skips_without_shell_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should ignore missing shell frames."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    def main_window_for_shell(_frame: object) -> object:
        """Record unexpected shell access."""

        calls.append("main_window")
        return object()

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=None,
        main_window_for_shell=main_window_for_shell,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert calls == []
    assert events == []


def test_update_shell_backend_state_skips_without_generation_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should tolerate incomplete shell adapters."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _BackendMainWindow(generation_action_controller=None)

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert events == []
