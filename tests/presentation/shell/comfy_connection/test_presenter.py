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

"""Prove Comfy connection alerts through the offscreen Qt platform."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    InfoBar,
    InfoBarPosition,
    PushButton,
)

from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.onboarding import ComfyTargetMode
from substitute.domain.onboarding import ComfyEndpoint, ComfyTargetConfiguration
from substitute.application.comfy_connection import ComfyConnectionRecoveryService
from substitute.presentation.shell.comfy_connection_presenter import (
    ComfyConnectionPresenter,
)


def _change(
    previous: ComfyConnectionPhase,
    current: ComfyConnectionPhase,
    *,
    can_restart: bool = True,
    revision: int = 1,
) -> ComfyConnectionStateChange:
    """Build one deterministic state transition for presentation tests."""

    return ComfyConnectionStateChange(
        previous=ComfyConnectionState(
            phase=previous,
            target_mode=ComfyTargetMode.MANAGED_LOCAL,
            can_restart=can_restart,
            revision=max(0, revision - 1),
        ),
        current=ComfyConnectionState(
            phase=current,
            target_mode=ComfyTargetMode.MANAGED_LOCAL,
            can_restart=can_restart,
            revision=revision,
        ),
    )


def _current_phase(
    service: ComfyConnectionRecoveryService,
) -> ComfyConnectionPhase:
    """Read mutable recovery state without retaining mypy's prior narrowing."""

    return service.state.phase


def test_managed_disconnect_offers_restart_without_blocking_window() -> None:
    """A sustained managed outage should show one non-modal restart action."""

    parent = QWidget()
    restart_requests: list[str] = []
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: restart_requests.append("restart"),
        open_connection_settings=lambda: None,
    )

    presenter.present(
        _change(ComfyConnectionPhase.RECONNECTING, ComfyConnectionPhase.DISCONNECTED)
    )
    QApplication.processEvents()

    bars = parent.findChildren(InfoBar, "comfyConnectionInfoBar")
    assert len(bars) == 1
    assert bars[0].isWindow() is False
    assert bars[0].content == ""
    assert bars[0].position is InfoBarPosition.TOP_RIGHT
    restart_button = bars[0].findChild(PushButton, "restartComfyButton")
    assert restart_button is not None
    assert restart_button.text() == "Restart Comfy"
    restart_button.click()
    assert restart_requests == ["restart"]
    parent.close()


def test_remote_disconnect_offers_settings_and_never_restart() -> None:
    """A non-owned target should expose settings instead of local process control."""

    parent = QWidget()
    settings_requests: list[str] = []
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: None,
        open_connection_settings=lambda: settings_requests.append("settings"),
    )

    presenter.present(
        _change(
            ComfyConnectionPhase.RECONNECTING,
            ComfyConnectionPhase.DISCONNECTED,
            can_restart=False,
        )
    )
    QApplication.processEvents()

    bar = parent.findChild(InfoBar, "comfyConnectionInfoBar")
    assert bar is not None
    assert bar.findChild(PushButton, "restartComfyButton") is None
    settings_button = bar.findChild(
        PushButton,
        "openComfyConnectionSettingsButton",
    )
    assert settings_button is not None
    assert settings_button.text() == "Settings"
    settings_button.click()
    assert settings_requests == ["settings"]
    parent.close()


def test_restart_progress_and_success_replace_alert_without_duplicate() -> None:
    """Restart transitions should retain one bar and confirm websocket readiness."""

    parent = QWidget()
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: None,
        open_connection_settings=lambda: None,
    )
    restarting = _change(
        ComfyConnectionPhase.DISCONNECTED,
        ComfyConnectionPhase.RESTARTING,
        revision=2,
    )

    presenter.present(restarting)
    presenter.present(restarting)
    QApplication.processEvents()
    progress_bar = parent.findChild(InfoBar, "comfyConnectionInfoBar")
    assert progress_bar is not None
    assert progress_bar.title == "Restarting Comfy"
    assert progress_bar.content == ""
    presenter.present(
        _change(
            ComfyConnectionPhase.RESTARTING,
            ComfyConnectionPhase.READY,
            revision=3,
        )
    )
    QApplication.processEvents()

    bars = parent.findChildren(InfoBar, "comfyConnectionInfoBar")
    assert len(bars) == 1
    assert bars[0].title == "Comfy restarted"
    assert bars[0].content == ""
    parent.close()


def test_transient_reconnecting_state_does_not_show_alert() -> None:
    """The grace-period state should remain silent when Comfy reconnects quickly."""

    parent = QWidget()
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: None,
        open_connection_settings=lambda: None,
    )

    presenter.present(
        _change(ComfyConnectionPhase.READY, ComfyConnectionPhase.RECONNECTING)
    )
    QApplication.processEvents()

    assert parent.findChild(InfoBar, "comfyConnectionInfoBar") is None
    parent.close()


def test_restart_failure_offers_retry_and_settings_without_duplicate_bar() -> None:
    """A failed managed restart should retain one actionable non-modal alert."""

    parent = QWidget()
    restart_requests: list[str] = []
    settings_requests: list[str] = []
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: restart_requests.append("restart"),
        open_connection_settings=lambda: settings_requests.append("settings"),
    )

    presenter.present(
        _change(
            ComfyConnectionPhase.RESTARTING,
            ComfyConnectionPhase.RESTART_FAILED,
            revision=3,
        )
    )
    QApplication.processEvents()

    bars = parent.findChildren(InfoBar, "comfyConnectionInfoBar")
    assert len(bars) == 1
    retry_button = bars[0].findChild(PushButton, "retryComfyRestartButton")
    settings_button = bars[0].findChild(
        PushButton,
        "openComfyConnectionSettingsButton",
    )
    assert retry_button is not None
    assert settings_button is not None
    assert retry_button.text() == "Retry"
    assert settings_button.text() == "Settings"
    retry_button.click()
    settings_button.click()
    assert restart_requests == ["restart"]
    assert settings_requests == ["settings"]
    parent.close()


def test_alert_is_top_right_below_toolbar_surface() -> None:
    """Connection feedback should occupy the workspace beneath shell chrome."""

    shell = QWidget()
    shell.resize(1000, 600)
    toolbar = QWidget(shell)
    toolbar.setGeometry(0, 0, 1000, 44)
    notification_surface = QWidget(shell)
    notification_surface.setGeometry(0, 44, 1000, 556)
    shell.show()
    presenter = ComfyConnectionPresenter(
        notification_surface=notification_surface,
        request_restart=lambda: None,
        open_connection_settings=lambda: None,
    )

    presenter.present(
        _change(ComfyConnectionPhase.RECONNECTING, ComfyConnectionPhase.DISCONNECTED)
    )
    QApplication.processEvents()

    bar = notification_surface.findChild(InfoBar, "comfyConnectionInfoBar")
    assert bar is not None
    assert bar.parent() is notification_surface
    assert bar.position is InfoBarPosition.TOP_RIGHT
    assert notification_surface.geometry().top() + bar.y() > toolbar.geometry().bottom()
    slide_animation = cast(QPropertyAnimation, bar.property("slideAni"))
    if slide_animation.state() == QAbstractAnimation.State.Running:
        assert QSignalSpy(slide_animation.finished).wait(1000)
    right_margin = notification_surface.rect().right() - bar.geometry().right()
    assert 16 <= right_margin <= 32
    shell.close()


def test_dismissed_alert_is_not_recreated_by_duplicate_transition() -> None:
    """User dismissal should survive repeated delivery of the same revision."""

    parent = QWidget()
    parent.show()
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=lambda: None,
        open_connection_settings=lambda: None,
    )
    disconnected = _change(
        ComfyConnectionPhase.RECONNECTING,
        ComfyConnectionPhase.DISCONNECTED,
    )
    presenter.present(disconnected)
    QApplication.processEvents()
    bar = parent.findChild(InfoBar, "comfyConnectionInfoBar")
    assert bar is not None
    assert bar.isVisible()

    bar.close()
    QApplication.processEvents()
    presenter.present(disconnected)
    QApplication.processEvents()

    assert not any(
        candidate.isVisible()
        for candidate in parent.findChildren(InfoBar, "comfyConnectionInfoBar")
    )
    parent.close()


class _HeadlessWorkspaceWindow(QWidget):
    """Carry editor and session identities through an offscreen recovery cycle."""

    def __init__(self) -> None:
        """Create stable work-state identities without mounting a desktop window."""

        super().__init__()
        self.workflow_document = object()
        self.undo_stack = object()
        self.autosave_state = object()
        self.pending_queue = object()


class _HeadlessRestartRequester:
    """Capture the asynchronous restart callback in the offscreen proof."""

    def __init__(self) -> None:
        """Initialize no captured failures."""

        self.failure_callbacks: list[Callable[[], None]] = []

    def request_restart(self, *, on_failure: Callable[[], None]) -> None:
        """Capture the callback while representing a successful process launch."""

        self.failure_callbacks.append(on_failure)


def test_offscreen_recovery_preserves_work_and_waits_for_readiness() -> None:
    """A full headless recovery should preserve work and confirm monitor readiness."""

    assert QApplication.platformName().casefold() == "offscreen"
    parent = _HeadlessWorkspaceWindow()
    identities = (
        parent.workflow_document,
        parent.undo_stack,
        parent.autosave_state,
        parent.pending_queue,
    )
    scheduled: list[Callable[[], None]] = []
    backend_states: list[str] = []
    dispatch_states: list[bool] = []
    restart_requester = _HeadlessRestartRequester()
    service = ComfyConnectionRecoveryService(
        target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint("127.0.0.1", 8188),
            workspace_path=Path("ComfyUI"),
            install_owned=True,
            launch_owned=True,
        ),
        set_backend_state=backend_states.append,
        set_dispatch_available=dispatch_states.append,
        schedule_delay=lambda _delay_ms, callback: scheduled.append(callback),
        restart_requester=restart_requester,
    )
    presenter = ComfyConnectionPresenter(
        notification_surface=parent,
        request_restart=service.request_restart,
        open_connection_settings=lambda: None,
    )
    service.add_observer(presenter.present)

    service.report_disconnected()
    scheduled.pop(0)()
    assert _current_phase(service) is ComfyConnectionPhase.DISCONNECTED
    assert service.request_restart()
    assert _current_phase(service) is ComfyConnectionPhase.RESTARTING
    QApplication.processEvents()
    restarting_bars = [
        bar
        for bar in parent.findChildren(InfoBar, "comfyConnectionInfoBar")
        if bar.title == "Restarting Comfy"
    ]
    assert len(restarting_bars) == 1

    service.report_connected()
    scheduled.pop(0)()
    QApplication.processEvents()

    assert _current_phase(service) is ComfyConnectionPhase.READY
    ready_bars = parent.findChildren(InfoBar, "comfyConnectionInfoBar")
    assert len(ready_bars) == 1
    assert ready_bars[0].title == "Comfy restarted"
    assert (
        parent.workflow_document,
        parent.undo_stack,
        parent.autosave_state,
        parent.pending_queue,
    ) == identities
    assert backend_states == ["starting", "unavailable", "starting", "ready"]
    assert dispatch_states == [False, False, True]
    assert len(restart_requester.failure_callbacks) == 1
    parent.close()
