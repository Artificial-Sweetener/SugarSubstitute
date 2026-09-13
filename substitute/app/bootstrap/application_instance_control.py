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

from collections import deque
from collections.abc import Callable
import logging
from typing import Protocol

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QWidget

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocation,
    ApplicationInvocationOutcome,
    RoutedApplicationInvocation,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from sugarsubstitute_shared.qt_window_presentation import request_window_presentation


_ACTIVE_CLIENT: ApplicationInstanceControlClient | None = None
_LOGGER = logging.getLogger(__name__)


class ApplicationSupervisorControl(Protocol):
    """Expose the supervisor operations consumed by the Qt application bridge."""

    def bind_invocation_handler(
        self,
        handler: Callable[[RoutedApplicationInvocation], None],
    ) -> None:
        """Bind the application invocation receiver."""

    def bind_disconnect_handler(self, handler: Callable[[], None]) -> None:
        """Bind the supervisor-loss receiver."""

    def request_restart(self) -> bool:
        """Request one supervisor-owned child restart."""

    def complete_invocation(
        self,
        request_id: str,
        *,
        outcome: ApplicationInvocationOutcome,
        surface: str,
    ) -> None:
        """Return one presentation receipt to the supervisor."""

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
        self._pending_invocations: deque[RoutedApplicationInvocation] = deque()
        self._presentations: dict[int, tuple[QWidget, list[str]]] = {}
        self._known_windows: list[QWidget] = [
            window for window in QApplication.topLevelWidgets() if window.isVisible()
        ]
        application = QCoreApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        self.invocation_received.connect(
            self._activate_for_invocation,
            Qt.ConnectionType.QueuedConnection,
        )
        if invocation_observer is not None:
            self.invocation_received.connect(
                lambda request: (
                    invocation_observer(request.invocation)
                    if isinstance(request, RoutedApplicationInvocation)
                    else None
                ),
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

        application = QCoreApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self._complete_all_presentations(outcome="unavailable")
        while self._pending_invocations:
            request = self._pending_invocations.popleft()
            self._client.complete_invocation(
                request.request_id,
                outcome="unavailable",
                surface="application-closing",
            )
        self._client.close()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Retry queued activation when a top-level application surface appears."""

        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and watched.isWindow()
        ):
            self._remember_window(watched)
            self._present_pending_invocations(window=watched)
        elif event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            self._complete_window_presentations(watched, outcome="presented")
        elif event.type() == QEvent.Type.Destroy and isinstance(watched, QWidget):
            self._complete_window_presentations(watched, outcome="unavailable")
            self._forget_window(watched)
        return False

    def _activate_for_invocation(self, invocation: object) -> None:
        """Bring the current shell forward for one validated launch request."""

        if not isinstance(invocation, RoutedApplicationInvocation):
            return
        window = _activation_window(self._known_windows)
        if window is None:
            self._pending_invocations.append(invocation)
            _LOGGER.info(
                "Queued invocation until an application surface exists | "
                "request_id=%s | pending_count=%s",
                invocation.request_id,
                len(self._pending_invocations),
            )
            return
        self._present_invocations(window, (invocation,))

    def _present_pending_invocations(self, *, window: QWidget) -> None:
        """Present one newly available surface for every retained invocation."""

        if not self._pending_invocations:
            return
        invocations = tuple(self._pending_invocations)
        self._pending_invocations.clear()
        self._present_invocations(window, invocations)

    def _present_invocations(
        self,
        window: QWidget,
        invocations: tuple[RoutedApplicationInvocation, ...],
    ) -> None:
        """Present one surface and await its next paint before acknowledging."""

        self._present_window(window)
        key = id(window)
        presentation = self._presentations.get(key)
        if presentation is None:
            request_ids: list[str] = []
            self._presentations[key] = (window, request_ids)
        else:
            request_ids = presentation[1]
        request_ids.extend(invocation.request_id for invocation in invocations)
        _LOGGER.info(
            "Requested application surface presentation | surface=%s | request_ids=%s",
            type(window).__name__,
            ",".join(invocation.request_id for invocation in invocations),
        )
        window.update()
        QTimer.singleShot(
            2000,
            lambda: self._complete_window_presentations(
                window,
                outcome="unavailable",
            ),
        )

    def _remember_window(self, window: QWidget) -> None:
        """Retain the most recently shown top-level application surface."""

        self._forget_window(window)
        self._known_windows.append(window)

    def _forget_window(self, window: QWidget) -> None:
        """Remove one closed or replaced surface from activation candidates."""

        self._known_windows = [
            candidate for candidate in self._known_windows if candidate is not window
        ]

    def _complete_window_presentations(
        self,
        window: QWidget,
        *,
        outcome: ApplicationInvocationOutcome,
    ) -> None:
        """Complete every invocation waiting on one exact surface."""

        presentation = self._presentations.pop(id(window), None)
        if presentation is None or presentation[0] is not window:
            return
        surface = type(window).__name__
        for request_id in presentation[1]:
            _LOGGER.info(
                "Completed application surface presentation | request_id=%s | "
                "surface=%s | outcome=%s",
                request_id,
                surface,
                outcome,
            )
            self._client.complete_invocation(
                request_id,
                outcome=outcome,
                surface=surface,
            )

    def _complete_all_presentations(
        self,
        *,
        outcome: ApplicationInvocationOutcome,
    ) -> None:
        """Complete every outstanding presentation during control teardown."""

        for window, _request_ids in tuple(self._presentations.values()):
            self._complete_window_presentations(window, outcome=outcome)

    @staticmethod
    def _present_window(window: QWidget) -> None:
        """Reveal and request activation for one concrete application surface."""

        request_window_presentation(window)

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


def _activation_window(known_windows: list[QWidget]) -> QWidget | None:
    """Return the best existing top-level surface, including hidden shells."""

    active = QApplication.activeWindow()
    if active is not None:
        return active
    visible = [window for window in known_windows if window.isVisible()]
    if visible:
        return visible[-1]
    return known_windows[-1] if known_windows else None


__all__ = [
    "ApplicationInstanceControlClient",
    "request_supervised_application_restart",
    "start_application_instance_control",
    "stop_application_instance_control",
]
