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

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap.application_instance_control import (
    ApplicationInstanceControlClient,
)
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocationOutcome,
    RoutedApplicationInvocation,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _RecordingSupervisorClient:
    """Expose the child-client contract without opening another endpoint."""

    def __init__(self) -> None:
        """Start without a bound invocation handler."""

        self.handler: Callable[[RoutedApplicationInvocation], None] | None = None
        self.restart_requests = 0
        self.closed = False
        self.receipts: list[tuple[str, ApplicationInvocationOutcome, str]] = []

    def bind_invocation_handler(
        self,
        handler: Callable[[RoutedApplicationInvocation], None],
    ) -> None:
        """Capture the Qt bridge callback."""

        self.handler = handler

    def request_restart(self) -> bool:
        """Record one supervisor-owned restart request."""

        self.restart_requests += 1
        return True

    def complete_invocation(
        self,
        request_id: str,
        *,
        outcome: ApplicationInvocationOutcome,
        surface: str,
    ) -> None:
        """Record one presentation receipt."""

        self.receipts.append((request_id, outcome, surface))

    def bind_disconnect_handler(self, handler: Callable[[], None]) -> None:
        """Accept the bridge's supervisor-loss callback."""

        _ = handler

    def close(self) -> None:
        """Record child-channel shutdown."""

        self.closed = True


class _ActivationTrackingWindow(QWidget):
    """Record forwarded-launch presentation without relying on window-manager state."""

    def __init__(self) -> None:
        """Initialize presentation counters before the window becomes available."""

        super().__init__()
        self.raise_requests = 0
        self.activation_requests = 0

    def raise_(self) -> None:
        """Record one request to bring this surface above peer windows."""

        self.raise_requests += 1
        super().raise_()

    def activateWindow(self) -> None:  # noqa: N802
        """Record one request to activate this surface."""

        self.activation_requests += 1
        super().activateWindow()


class _CloseRejectingWindow(_ActivationTrackingWindow):
    """Keep the surface alive when application state rejects a close request."""

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Reject closure to model unsaved-work confirmation cancellation."""

        event.ignore()


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
        RoutedApplicationInvocation(
            request_id="request-1",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "example.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    QCoreApplication.processEvents()

    assert window.isVisible()
    assert not window.isMinimized()
    assert len(observed) == 1
    assert client.receipts == [
        ("request-1", "presented", "QWidget"),
    ]
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


def test_control_bridge_retains_invocation_until_a_window_exists(
    tmp_path: Path,
) -> None:
    """A launch received during startup must surface the first available window."""

    application = ensure_qt_application()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    assert callable(client.handler)

    client.handler(
        RoutedApplicationInvocation(
            request_id="request-during-startup",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "during-startup.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    QCoreApplication.processEvents()

    window = _ActivationTrackingWindow()
    window.show()
    QCoreApplication.processEvents()

    assert window.raise_requests == 1
    assert window.activation_requests == 1
    assert client.receipts == [
        ("request-during-startup", "presented", "_ActivationTrackingWindow"),
    ]
    control.close()
    window.close()
    application.processEvents()


def test_control_bridge_reveals_an_existing_hidden_window(tmp_path: Path) -> None:
    """A hidden live shell must never leave a second launch queued forever."""

    application = ensure_qt_application()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    window = _ActivationTrackingWindow()
    window.show()
    application.processEvents()
    window.hide()
    application.processEvents()
    assert callable(client.handler)

    client.handler(
        RoutedApplicationInvocation(
            request_id="request-hidden",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "hidden.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    application.processEvents()

    assert window.isVisible()
    assert window.raise_requests == 1
    assert window.activation_requests == 1
    assert client.receipts == [
        ("request-hidden", "presented", "_ActivationTrackingWindow")
    ]
    control.close()
    window.close()
    application.processEvents()


def test_rejected_close_does_not_make_live_window_undiscoverable(
    tmp_path: Path,
) -> None:
    """A cancelled close must leave the same shell available to later launches."""

    application = ensure_qt_application()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    window = _CloseRejectingWindow()
    window.show()
    application.processEvents()

    assert not window.close()
    application.processEvents()
    assert callable(client.handler)
    client.handler(
        RoutedApplicationInvocation(
            request_id="request-after-rejected-close",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "still-open.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    application.processEvents()
    wait_for_qt_condition(lambda: bool(client.receipts))

    assert client.receipts == [
        (
            "request-after-rejected-close",
            "presented",
            "_CloseRejectingWindow",
        )
    ]
    control.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_control_bridge_recovers_an_entirely_offscreen_window(tmp_path: Path) -> None:
    """Activation must move an inaccessible shell onto an available monitor."""

    application = ensure_qt_application()
    window = _ActivationTrackingWindow()
    window.resize(480, 320)
    window.move(100_000, 100_000)
    window.show()
    application.processEvents()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    assert callable(client.handler)

    client.handler(
        RoutedApplicationInvocation(
            request_id="request-offscreen",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "offscreen.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    application.processEvents()

    assert any(
        window.frameGeometry().intersects(screen.availableGeometry())
        for screen in QGuiApplication.screens()
    )
    assert client.receipts == [
        ("request-offscreen", "presented", "_ActivationTrackingWindow")
    ]
    control.close()
    window.close()
    application.processEvents()


def test_control_bridge_completes_every_request_waiting_for_first_window(
    tmp_path: Path,
) -> None:
    """A burst during startup must retain and present every invocation."""

    application = ensure_qt_application()
    for existing in QApplication.topLevelWidgets():
        existing.close()
        existing.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    assert callable(client.handler)

    for index in range(32):
        client.handler(
            RoutedApplicationInvocation(
                request_id=f"request-{index}",
                invocation=ApplicationInvocation.capture(
                    ["Substitute", f"burst-{index}.sugar"],
                    working_directory=tmp_path,
                ),
            )
        )
    application.processEvents()
    assert client.receipts == []

    window = _ActivationTrackingWindow()
    window.show()
    application.processEvents()

    assert [request_id for request_id, _outcome, _surface in client.receipts] == [
        f"request-{index}" for index in range(32)
    ]
    assert all(
        outcome == "presented" for _request_id, outcome, _surface in client.receipts
    )
    control.close()
    window.close()
    application.processEvents()


def test_control_bridge_close_releases_requests_without_a_window(
    tmp_path: Path,
) -> None:
    """Application shutdown must explicitly release every startup request."""

    application = ensure_qt_application()
    for existing in QApplication.topLevelWidgets():
        existing.close()
        existing.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    client = _RecordingSupervisorClient()
    control = ApplicationInstanceControlClient(client)
    assert callable(client.handler)
    client.handler(
        RoutedApplicationInvocation(
            request_id="request-close",
            invocation=ApplicationInvocation.capture(
                ["Substitute", "closing.sugar"],
                working_directory=tmp_path,
            ),
        )
    )
    application.processEvents()

    control.close()

    assert client.receipts == [("request-close", "unavailable", "application-closing")]
