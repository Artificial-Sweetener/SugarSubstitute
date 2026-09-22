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

"""Verify splash progress and optional diagnostics through the mounted Fluent panel."""

from __future__ import annotations

from collections.abc import Iterator
import pytest
from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.launch_splash.progress import SplashProgress
from substitute.presentation.shell.splash_progress_panel import SplashProgressPanel
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.fixture
def panel() -> Iterator[SplashProgressPanel]:
    """Release all mounted progress animations after each case."""
    value = SplashProgressPanel(details=QWidget())
    value.resize(546, 193)
    value.show()
    try:
        yield value
    finally:
        destroy_qt_object(value)


def test_initial_activity_claims_no_completion(panel: SplashProgressPanel) -> None:
    """Keep unknown work empty and its unfilled track stationary."""
    assert panel.progress.isVisible()
    assert panel.progress.value() == 0
    assert not panel.progress.activity_running
    assert not panel.details.isVisible()


def test_milestones_and_log_activity_have_separate_meanings(
    panel: SplashProgressPanel,
) -> None:
    """Fill from producer units while activity leaves completion untouched."""
    panel.set_progress(SplashProgress(2, 5), status="Preparing workspace")
    assert panel.progress.isVisible()
    assert panel.progress.value() == 2
    assert panel.progress.maximum() == 5
    assert panel.status.text() == "Preparing workspace"
    panel.record_activity()
    assert panel.progress.value() == 2
    panel.set_details_visible(not panel.details_visible)
    assert panel.details.isVisible()
    panel.set_details_visible(not panel.details_visible)
    assert not panel.details.isVisible()
    assert panel.progress.value() == 2


def test_completion_and_hide_stop_activity(panel: SplashProgressPanel) -> None:
    """Release animation work without altering completed units."""
    panel.set_progress(SplashProgress(2, 5), status="Preparing workspace")
    panel.hide()
    assert not panel.progress.activity_running
    panel.show()
    assert not panel.progress.activity_running
    panel.record_activity()
    assert panel.progress.activity_running
    panel.set_progress(SplashProgress(5, 5), status="Ready")
    assert not panel.progress.activity_running
    assert panel.progress.value() == 5
    panel.record_activity()
    assert panel.progress.value() == 5


def test_collapsed_splash_exposes_activity_without_claiming_completion() -> None:
    """Keep long-running work visible outside optional logs and retain milestone units."""
    from PySide6.QtGui import QIcon
    from substitute.presentation.shell.splash_window import SplashWindow
    from sugarsubstitute_shared.launch_splash.activity import SplashActivity

    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        splash.set_progress(SplashProgress(2, 5), status="Preparing workspace")
        splash.start_activity(
            SplashActivity("Waiting for backend", "Still waiting", "Taking longer")
        )
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        assert not panel.details.isVisible()
        assert panel.status.text().startswith("Waiting for backend")
        assert panel.progress.value() == 2
        splash.append_log("Backend diagnostic output")
        assert panel.status.text().startswith("Waiting for backend")
        assert panel.progress.value() == 2
        splash.clear_activity()
        assert panel.status.text() == "Preparing workspace"
        splash.show_failure("Backend failed")
        splash.start_activity(
            SplashActivity("Delayed activity", "Delayed activity", "Delayed activity")
        )
        assert panel.status.text() == "Backend failed"
        assert "Delayed activity" not in splash.log_view.toPlainText()
    finally:
        destroy_qt_object(splash)


def test_activity_before_milestones_returns_to_initial_status(
    panel: SplashProgressPanel,
) -> None:
    """Clear early operation copy even before a producer supplies completion units."""
    initial_status = panel.status.text()
    panel.set_activity_status("Checking installation")
    panel.set_activity_status("")
    assert panel.status.text() == initial_status
    assert not panel.progress.activity_running


@pytest.mark.parametrize("transport", ["shared", "pipe", "in_process"])
def test_client_progress_reaches_the_production_splash(transport: str) -> None:
    """Render all client transports with details collapsed in the real splash."""
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from substitute.app.bootstrap.shared_splash_host import _handle_session_message
    from substitute.presentation.shell.splash_window import SplashWindow
    from sugarsubstitute_shared.launch_splash.protocol import SplashSessionMessage
    from substitute.app.bootstrap.launch_splash_client import (
        InProcessLaunchSplashClient,
    )
    from substitute.app.bootstrap.splash_process import _handle_message
    from typing import cast

    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        assert not panel.details.isVisible()
        application = cast(QApplication, QApplication.instance())
        if transport == "shared":
            _handle_session_message(
                SplashSessionMessage(
                    "status",
                    "token",
                    "Preparing workspace",
                    progress=SplashProgress(2, 5),
                ),
                splash=splash,
                app=application,
            )
        elif transport == "pipe":
            _handle_message(
                {
                    "type": "status",
                    "line": "Preparing workspace",
                    "completed": "2",
                    "total": "5",
                },
                splash=splash,
                app=application,
            )
        else:
            InProcessLaunchSplashClient(splash).set_progress(
                SplashProgress(2, 5), status="Preparing workspace"
            )
        assert panel.progress.value() == 2
        assert panel.status.text() == "Preparing workspace"
        splash.append_log("Loaded backend modules")
        assert panel.progress.value() == 2
        assert panel.status.text() == "Preparing workspace"
        panel.set_details_visible(not panel.details_visible)
        assert "Loaded backend modules" in splash.log_view.toPlainText()
    finally:
        destroy_qt_object(splash)


@pytest.mark.parametrize("transport", ["shared", "pipe"])
def test_fatal_message_exposes_diagnostics_and_stops_progress(transport: str) -> None:
    """Keep terminal failure visible even if delayed progress arrives afterward."""
    from typing import cast
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from substitute.app.bootstrap.shared_splash_host import _handle_session_message
    from substitute.app.bootstrap.splash_process import _handle_message
    from substitute.presentation.shell.splash_window import SplashWindow
    from sugarsubstitute_shared.launch_splash.protocol import SplashSessionMessage

    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        splash.set_progress(SplashProgress(2, 5), status="Preparing workspace")
        application = cast(QApplication, QApplication.instance())
        if transport == "shared":
            _handle_session_message(
                SplashSessionMessage("fatal", "token", "Backend could not start"),
                splash=splash,
                app=application,
            )
        else:
            _handle_message(
                {"type": "fatal", "line": "Backend could not start"},
                splash=splash,
                app=application,
            )
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        assert panel.status.text() == "Backend could not start"
        assert panel.details.isVisible()
        assert not panel.progress.activity_running
        assert "Backend could not start" in splash.log_view.toPlainText()
        splash.set_progress(SplashProgress(3, 5), status="Preparing workspace")
        assert panel.status.text() == "Backend could not start"
        assert panel.progress.value() == 2
    finally:
        destroy_qt_object(splash)


@pytest.mark.parametrize(
    ("message_type", "completed", "total"),
    [
        ("status", "-1", "5"),
        ("status", "6", "5"),
        ("status", "0", "0"),
        ("status", "unknown", "5"),
        ("status", "1", ""),
        ("log", "5", "5"),
    ],
)
def test_pipe_records_cannot_fabricate_completion(
    message_type: str, completed: str, total: str
) -> None:
    """Retain completion when a malformed status or ordinary log includes counts."""
    from typing import cast
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from substitute.app.bootstrap.splash_process import _handle_message
    from substitute.presentation.shell.splash_window import SplashWindow

    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        splash.set_progress(SplashProgress(2, 5), status="Preparing workspace")
        _handle_message(
            {
                "type": message_type,
                "line": "Diagnostic output",
                "completed": completed,
                "total": total,
            },
            splash=splash,
            app=cast(QApplication, QApplication.instance()),
        )
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        assert panel.progress.value() == 2
        assert panel.progress.maximum() == 5
        assert panel.status.text() == "Preparing workspace"
        assert "Diagnostic output" in splash.log_view.toPlainText()
    finally:
        destroy_qt_object(splash)
