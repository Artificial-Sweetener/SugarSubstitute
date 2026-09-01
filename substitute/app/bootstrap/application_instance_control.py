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

"""Receive supervisor-owned activation and restart control in the Qt process."""

from __future__ import annotations

from collections.abc import Callable
import sys
from typing import Protocol

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QWidget

from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


_ACTIVE_CLIENT: ApplicationInstanceControlClient | None = None


class ApplicationSupervisorControl(Protocol):
    """Expose the supervisor operations consumed by the Qt application bridge."""

    def bind_invocation_handler(
        self,
        handler: Callable[[ApplicationInvocation], None],
    ) -> None:
        """Bind the application invocation receiver."""

    def bind_disconnect_handler(self, handler: Callable[[], None]) -> None:
        """Bind the supervisor-loss receiver."""

    def request_restart(self) -> bool:
        """Request one supervisor-owned child restart."""

    def close(self) -> None:
        """Release the child control channel."""


class ApplicationInstanceControlClient(QObject):
    """Bridge the private supervisor channel into the Qt application thread."""

    invocation_received = Signal(object)
    supervisor_disconnected = Signal()

    def __init__(
        self,
        client: ApplicationSupervisorControl,
        *,
        invocation_observer: Callable[[ApplicationInvocation], None] | None = None,
    ) -> None:
        """Bind one authenticated client before application startup continues."""

        super().__init__()
        self._client = client
        self.invocation_received.connect(
            self._activate_for_invocation,
            Qt.ConnectionType.QueuedConnection,
        )
        if invocation_observer is not None:
            self.invocation_received.connect(
                invocation_observer,
                Qt.ConnectionType.QueuedConnection,
            )
        self.supervisor_disconnected.connect(
            self._quit_after_supervisor_disconnect,
            Qt.ConnectionType.QueuedConnection,
        )
        client.bind_invocation_handler(self.invocation_received.emit)
        client.bind_disconnect_handler(self.supervisor_disconnected.emit)

    def request_restart(self) -> bool:
        """Ask the existing launcher supervisor to own the next application run."""

        return self._client.request_restart()

    def close(self) -> None:
        """Disconnect the private child channel."""

        self._client.close()

    def _activate_for_invocation(self, invocation: object) -> None:
        """Bring the current shell forward for one validated launch request."""

        if not isinstance(invocation, ApplicationInvocation):
            return
        window = _activation_window()
        if window is None:
            return
        if window.isMinimized():
            window.showNormal()
        elif not window.isVisible():
            window.show()
        window.raise_()
        window.activateWindow()
        if sys.platform == "darwin":
            from sugarsubstitute_shared.application_instance_macos import (
                activate_current_macos_application,
            )

            activate_current_macos_application()
        if not window.isActiveWindow():
            QApplication.alert(window, 0)

    def _quit_after_supervisor_disconnect(self) -> None:
        """Exit before another supervisor can launch a competing child."""

        application = QCoreApplication.instance()
        if application is not None:
            application.quit()


def start_application_instance_control(
    *,
    invocation_observer: Callable[[ApplicationInvocation], None] | None = None,
) -> ApplicationInstanceControlClient | None:
    """Connect this supervised child to its launcher-owned instance broker."""

    global _ACTIVE_CLIENT
    stop_application_instance_control()
    client = ApplicationSupervisorClient.connect_from_environment()
    if client is None:
        return None
    control = ApplicationInstanceControlClient(
        client,
        invocation_observer=invocation_observer,
    )
    _ACTIVE_CLIENT = control
    return control


def request_supervised_application_restart() -> bool:
    """Request restart from the long-lived supervisor when one is connected."""

    client = _ACTIVE_CLIENT
    return client is not None and client.request_restart()


def stop_application_instance_control() -> None:
    """Stop and release the supervised child channel idempotently."""

    global _ACTIVE_CLIENT
    client = _ACTIVE_CLIENT
    _ACTIVE_CLIENT = None
    if client is not None:
        client.close()


def _activation_window() -> QWidget | None:
    """Return the best visible top-level application window."""

    active = QApplication.activeWindow()
    if active is not None:
        return active
    visible = [
        window for window in QApplication.topLevelWidgets() if window.isVisible()
    ]
    return visible[-1] if visible else None


__all__ = [
    "ApplicationInstanceControlClient",
    "request_supervised_application_restart",
    "start_application_instance_control",
    "stop_application_instance_control",
]
