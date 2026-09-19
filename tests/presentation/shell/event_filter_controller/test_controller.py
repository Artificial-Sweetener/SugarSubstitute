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

from PySide6.QtCore import QCoreApplication, QEvent, QObject

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
        model_update_notification_controller=SimpleNamespace(
            check_on_focus=lambda: calls.append("check-models")
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
    assert calls == ["present", "check-models"]


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


def test_keyboard_capture_preserves_event_for_the_active_control() -> None:
    """Keyboard capture should prevent global routing from stealing input."""

    calls: list[str] = []
    shell = SimpleNamespace(
        controls_keyboard_capture_active=True,
        cube_library_update_controller=SimpleNamespace(
            present_pending_updates=lambda: calls.append("update")
        ),
        search_overlay_controller=SimpleNamespace(
            handle_event_filter_event=lambda _event: calls.append("search")
        ),
    )
    controller = ShellEventFilterController(shell)

    assert controller.handle_event_filter_event(_Event(object())) is None
    assert calls == []


def test_application_filter_installs_only_when_explicitly_requested() -> None:
    """Avoid routing Qt events through a shell until its composition is complete."""

    application = QCoreApplication.instance() or QCoreApplication([])

    class _Shell(QObject):
        """Expose the minimum shell surface for filter installation."""

        def __init__(self) -> None:
            """Initialize shell state before filtering begins."""

            super().__init__()
            self.installed = False

        def eventFilter(self, _source: QObject, _event: QEvent) -> bool:
            """Record installation-driven event delivery."""

            self.installed = True
            return False

    shell = _Shell()
    controller = ShellEventFilterController(shell)

    assert shell.installed is False

    controller.install_on_application()
    application.sendEvent(application, QEvent(QEvent.Type.ApplicationActivate))

    assert shell.installed is True
    application.removeEventFilter(shell)
