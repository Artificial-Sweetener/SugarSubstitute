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

"""Verify the supervised application's Qt-facing control bridge."""

from collections.abc import Callable

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from substitute.app.bootstrap.application_instance_control import (
    ApplicationInstanceControlClient,
)
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from tests.support.qt.lifecycle import ensure_qt_application


class _RecordingSupervisorClient:
    """Expose the child-client contract without opening another endpoint."""

    def __init__(self) -> None:
        """Start without a bound invocation handler."""

        self.handler: Callable[[ApplicationInvocation], None] | None = None
        self.restart_requests = 0
        self.closed = False

    def bind_invocation_handler(
        self,
        handler: Callable[[ApplicationInvocation], None],
    ) -> None:
        """Capture the Qt bridge callback."""

        self.handler = handler

    def request_restart(self) -> bool:
        """Record one supervisor-owned restart request."""

        self.restart_requests += 1
        return True

    def bind_disconnect_handler(self, handler: Callable[[], None]) -> None:
        """Accept the bridge's supervisor-loss callback."""

        _ = handler

    def close(self) -> None:
        """Record child-channel shutdown."""

        self.closed = True


def test_control_bridge_activates_the_existing_window(tmp_path: Path) -> None:
    """A forwarded invocation should reveal and activate the current Qt shell."""

    application = ensure_qt_application()
    window = QWidget()
    window.showMinimized()
    client = _RecordingSupervisorClient()
    observed: list[ApplicationInvocation] = []
    control = ApplicationInstanceControlClient(
        client,
        invocation_observer=observed.append,
    )
    assert callable(client.handler)

    client.handler(
        ApplicationInvocation.capture(
            ["Substitute", "example.sugar"],
            working_directory=tmp_path,
        )
    )
    QCoreApplication.processEvents()

    assert window.isVisible()
    assert not window.isMinimized()
    assert len(observed) == 1
    control.close()
    assert client.closed
    window.close()
    application.processEvents()


def test_control_bridge_routes_restart_to_the_existing_supervisor() -> None:
    """Application restart must not create another launcher process."""

    _ = ensure_qt_application()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)

    assert control.request_restart()
    assert client.restart_requests == 1
    control.close()
