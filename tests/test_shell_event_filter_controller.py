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

"""Tests for shell-level event-filter routing."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QEvent

from substitute.presentation.shell.shell_event_filter_controller import (
    ShellEventFilterController,
)


class _Event:
    """Provide a Qt-like event type method."""

    def __init__(self, event_type: QEvent.Type | object) -> None:
        """Store the event type returned to the controller."""

        self._event_type = event_type

    def type(self) -> QEvent.Type | object:
        """Return the configured event type."""

        return self._event_type


def test_activation_event_presents_pending_cube_library_updates() -> None:
    """Window activation should surface pending Cube Library updates."""

    calls: list[str] = []
    shell = SimpleNamespace(
        cube_library_update_controller=SimpleNamespace(
            present_pending_updates=lambda: calls.append("present")
        ),
        search_overlay_controller=SimpleNamespace(
            handle_event_filter_event=lambda _event: (_ for _ in ()).throw(
                AssertionError("activation should not reach search overlay")
            )
        ),
    )
    controller = ShellEventFilterController(shell)

    result = controller.handle_event_filter_event(_Event(QEvent.Type.WindowActivate))

    assert result is False
    assert calls == ["present"]


def test_search_overlay_result_is_returned() -> None:
    """Search overlay should be able to consume global events."""

    event = _Event(object())
    shell = SimpleNamespace(
        cube_library_update_controller=SimpleNamespace(
            present_pending_updates=lambda: None
        ),
        search_overlay_controller=SimpleNamespace(
            handle_event_filter_event=lambda received: received is event
        ),
    )
    controller = ShellEventFilterController(shell)

    assert controller.handle_event_filter_event(event) is True


def test_unhandled_event_returns_none_for_qt_fallback() -> None:
    """Unhandled events should fall through to MainWindow's Qt fallback."""

    shell = SimpleNamespace(
        cube_library_update_controller=SimpleNamespace(
            present_pending_updates=lambda: None
        ),
        search_overlay_controller=SimpleNamespace(
            handle_event_filter_event=lambda _event: None
        ),
    )
    controller = ShellEventFilterController(shell)

    assert controller.handle_event_filter_event(_Event(object())) is None
