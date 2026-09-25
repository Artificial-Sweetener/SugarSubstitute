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

"""Verify visible repair progress and explicit terminal actions."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
)
import pytest

from launcher.sugarsubstitute_launcher.ui.repair_progress_view import RepairProgressView
from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow
from sugarsubstitute_shared.presentation.activity_progress_bar import (
    ActivityProgressBar,
)
from sugarsubstitute_shared.session_recovery import (
    SessionRecoveryResult,
    SessionRecoveryState,
)


@pytest.fixture
def view(qt_application_owner: QApplication) -> Iterator[RepairProgressView]:
    """Mount and dispose one real repair view with all child animations."""
    widget = RepairProgressView()
    widget.resize(900, 540)
    widget.show()
    qt_application_owner.processEvents()
    try:
        yield widget
    finally:
        widget.close()
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_activity_does_not_manufacture_completed_progress(
    view: RepairProgressView,
) -> None:
    """Activity may pulse the bar but only completed steps change its value."""
    view.set_stage("Preparing the runtime", completed=2, total=5)
    bar = view.findChild(QProgressBar, "RepairProgress")
    assert bar is not None
    assert isinstance(bar, ActivityProgressBar)
    assert bar.visible_fraction == pytest.approx(2 / 5)
    view.pulse_activity()
    assert bar.visible_fraction == pytest.approx(2 / 5)
    assert isinstance(bar, ActivityProgressBar)
    assert bar.activity_running
    assert bar.visible_fraction == pytest.approx(2 / 5)
    view.set_stage("Checking the installation", completed=4, total=5)
    assert bar.visible_fraction == pytest.approx(4 / 5)


def test_diagnostics_open_only_on_request(view: RepairProgressView) -> None:
    """Incoming diagnostics must not expose or resize the details pane on their own."""
    details = view.findChild(QPlainTextEdit)
    toggle = view.findChild(QPushButton, "RepairDetailsToggle")
    assert details is not None and toggle is not None
    view.set_details("Synthetic repair diagnostic")
    assert details.isHidden()
    QTest.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert details.isVisible()
    view.set_details("Updated synthetic diagnostic")
    assert details.isVisible()
    assert details.toPlainText() == "Updated synthetic diagnostic"


@pytest.mark.parametrize("succeeded", [True, False])
def test_terminal_result_exposes_the_next_action(
    view: RepairProgressView, succeeded: bool
) -> None:
    """Offer an explicit open or retry action only after repair finishes."""
    primary = view.findChild(QPushButton, "RepairPrimaryAction")
    assert primary is not None and primary.isHidden()
    view.show_result(succeeded=succeeded, details="Synthetic details")
    assert primary.isVisible()
    assert primary.text() == ("Open SugarSubstitute" if succeeded else "Try again")
    activated = QSignalSpy(view.primary_requested)
    QTest.mouseClick(primary, Qt.MouseButton.LeftButton)
    assert activated.count() == 1


def test_success_warns_when_session_was_preserved_but_not_restored(
    view: RepairProgressView,
) -> None:
    """Repair success must not imply that incompatible mutable session state loaded."""

    recovery_root = Path("C:/SugarSubstitute/.repair/session-recovery/example")
    view.show_result(
        succeeded=True,
        session_recovery=SessionRecoveryResult(
            SessionRecoveryState.PRESERVED_NOT_RESTORED,
            recovery_root=recovery_root,
        ),
    )

    visible_text = "\n".join(label.text() for label in view.findChildren(QLabel))
    assert "previous session could not be restored" in visible_text
    assert str(recovery_root) in visible_text


def test_window_defers_close_until_execution_is_safe(
    qt_application_owner: QApplication,
) -> None:
    """Keep the repair visible when its owner has not yet finished mutations."""
    window = RepairWindow()
    window.show()
    qt_application_owner.processEvents()
    requested = QSignalSpy(window.close_requested)
    try:
        journey = window.findChild(QProgressBar, "InstallerJourneyProgress")
        assert journey is not None and not journey.isVisible()
        window.set_running(True)
        assert not window.close()
        assert window.isVisible()
        assert requested.count() == 1
        window.set_running(False)
        assert window.close()
        assert not window.isVisible()
    finally:
        window.set_running(False)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
