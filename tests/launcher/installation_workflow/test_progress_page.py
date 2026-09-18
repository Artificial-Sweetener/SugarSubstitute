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

"""Verify Fluent installer progress through its production presentation owner."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget
from qfluentwidgets import IndeterminateProgressBar, ProgressBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.application.installation.progress import (
    InstallationProgress,
    InstallationStage,
)
from launcher.sugarsubstitute_launcher.ui.installation_progress_page import (
    InstallationProgressPage,
)
from tests.launcher.support import launcher_test_application
from tests.support.qt.semantic_wait import wait_for_qt_condition, wait_for_qt_signal


@pytest.fixture
def progress_page() -> Iterator[InstallationProgressPage]:
    """Mount the production page and release its animation and timer owners."""
    launcher_test_application()
    host = QWidget()
    page = InstallationProgressPage(host)
    host.resize(1000, 600)
    page.resize(950, 550)
    host.show()
    page.show()
    try:
        yield page
    finally:
        destroyed = QSignalSpy(host.destroyed)
        host.close()
        host.deleteLater()
        wait_for_qt_signal(destroyed)


def test_console_activity_does_not_advance_fill_or_replace_stage(
    progress_page: InstallationProgressPage,
) -> None:
    """Pulse a real Fluent bar while preserving stage-based completion."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME))
    headline = page.activity_label.text()
    page.append_log("Resolved 184 packages; preparing wheel cache")
    assert isinstance(page.progress_bar, ProgressBar)
    assert page.progress_bar.value() == 2
    assert page.progress_bar.maximum() == 4
    assert page.activity_label.text() == headline
    assert "184 packages" in page.progress_log.log_view.toPlainText()
    assert not page.progress_log.isVisible()
    effect = page.progress_bar.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    wait_for_qt_condition(lambda: effect.opacity() < 0.95)
    assert page.progress_bar.value() == 2


def test_failure_preserves_completed_work_and_retry_resumes(
    progress_page: InstallationProgressPage,
) -> None:
    """Stop activity on failure and accept a new authoritative retry boundary."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME))
    page.show_failure("The runtime could not be prepared.")
    assert page.progress_bar.value() == 2
    assert page.activity_label.text() == "The runtime could not be prepared."
    assert page.progress_log.isVisible()
    effect = page.progress_bar.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == 1.0
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME))
    assert "Installing Python runtime" in page.activity_label.text()
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME, True))
    assert page.progress_bar.value() == 3
    page.set_progress(InstallationProgress(InstallationStage.HANDOFF))
    assert page.progress_bar.value() == 3
    page.set_progress(InstallationProgress(InstallationStage.HANDOFF, True))
    assert page.progress_bar.value() == 4
    assert effect.opacity() == 1.0
    assert page.activity_label.text() == "Waiting for the setup window to open."


def test_safe_close_message_survives_remaining_worker_events(
    progress_page: InstallationProgressPage,
) -> None:
    """Retain cancellation acknowledgement while the worker finishes its stage."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME))
    page.show_stopping("Finishing the current setup step before closing.")
    page.append_log("Installed 10 packages")
    page.set_progress(InstallationProgress(InstallationStage.RUNTIME, True))
    assert page.progress_bar.value() == 3
    assert page.activity_label.text().startswith(
        "Finishing the current setup step before closing."
    )


def test_details_toggle_reports_geometry_without_resetting_progress(
    progress_page: InstallationProgressPage,
) -> None:
    """Keep console access reversible without changing the reported work."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.APPLICATION))
    changed = QSignalSpy(page.geometry_changed)
    page.details_button.click()
    assert page.progress_log.isVisible()
    page.details_button.click()
    assert not page.progress_log.isVisible()
    assert changed.count() == 2
    assert page.progress_bar.value() == 1


def test_preparation_shows_activity_before_any_stage_has_completed(
    progress_page: InstallationProgressPage,
) -> None:
    """Show Fluent activity at zero completion and retire it at a real milestone."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.PREPARATION))
    activity = page.findChild(IndeterminateProgressBar)
    assert activity is not None
    assert activity.isVisible()
    assert activity.isStarted()
    assert page.progress_bar.value() == 0
    assert not page.progress_bar.isVisible()
    page.hide()
    assert not activity.isStarted()
    page.show()
    assert activity.isStarted()
    page.set_progress(InstallationProgress(InstallationStage.PREPARATION, True))
    assert not activity.isVisible()
    assert not activity.isStarted()
    assert page.progress_bar.isVisible()
    assert page.progress_bar.value() == 1


def test_preparation_failure_stops_activity_without_claiming_progress(
    progress_page: InstallationProgressPage,
) -> None:
    """Keep failed preparation stationary and resume activity on retry."""
    page = progress_page
    page.set_progress(InstallationProgress(InstallationStage.PREPARATION))
    activity = page.findChild(IndeterminateProgressBar)
    assert activity is not None
    page.show_failure("Preparation failed")
    assert not activity.isStarted()
    assert not activity.isVisible()
    assert page.progress_bar.isVisible()
    assert page.progress_bar.value() == 0
    page.set_progress(InstallationProgress(InstallationStage.PREPARATION))
    assert activity.isVisible()
    assert activity.isStarted()
