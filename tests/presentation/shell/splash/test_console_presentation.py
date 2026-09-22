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

"""Exercise splash console chrome, layout and output-derived status together."""

import pytest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from substitute.presentation.shell.splash_window import SplashWindow
from substitute.presentation.shell.splash_progress_panel import SplashProgressPanel
from substitute.presentation.shell.titlebar_buttons import ComfyOutputToggleButton
from sugarsubstitute_shared.launch_splash.activity import SplashActivity
from sugarsubstitute_shared.launch_splash.progress import SplashProgress
from tests.support.qt.lifecycle import destroy_qt_object


def test_console_titlebar_toggle_reflows_and_retains_output() -> None:
    """Use shell chrome to reveal one joined progress/console surface and restore centering."""
    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        QApplication.processEvents()
        button = splash.findChild(ComfyOutputToggleButton)
        panel = splash.findChild(SplashProgressPanel)
        assert button is not None
        assert panel is not None
        assert button.accessibleName() == "Show Comfy output"
        assert not panel.findChildren(QPushButton)
        assert not panel.details.isVisible()
        centered = splash._visual.geometry()
        assert abs(centered.center().x() - splash.rect().center().x()) <= 1
        assert abs(centered.center().y() - splash.rect().center().y()) <= 1
        close = splash.titleBar.closeBtn
        assert button.parent() is close.parent()
        assert button.geometry().right() + 1 == close.geometry().left()
        assert button.height() == close.height()
        splash.append_log("Retained startup output")
        splash.set_progress(SplashProgress(2, 5), status="Preparing workspace")
        button.click()
        QApplication.processEvents()
        assert panel.details.isVisible()
        assert not panel.status.isVisible()
        assert button.accessibleName() == "Hide Comfy output"
        assert splash._visual.y() == 7
        assert panel.progress.parentWidget() is panel.details
        bar_top = panel.progress.mapTo(panel.details, QPoint(0, 0))
        assert bar_top == QPoint(0, 0)
        assert panel.progress.width() == panel.details.width()
        assert (
            splash.log_view.mapTo(panel.details, QPoint()).y()
            >= panel.progress.height() + 8
        )
        assert panel.status.alignment() & Qt.AlignmentFlag.AlignLeft
        assert panel.details.mapTo(splash, QPoint()).x() == 24
        assert (
            panel.details.mapTo(splash, QPoint(0, panel.details.height())).y()
            <= splash.height() - 24
        )
        assert "Retained startup output" in splash.log_view.toPlainText()
        assert panel.progress.value() == 2
        button.click()
        QApplication.processEvents()
        assert not panel.details.isVisible()
        assert splash._visual.geometry() == centered
        assert panel.status.isVisible()
        splash.show_failure("Backend could not start")
        QApplication.processEvents()
        assert button.isChecked()
        assert panel.details.isVisible()
    finally:
        destroy_qt_object(splash)


def test_comfy_output_status_survives_generic_wait_updates() -> None:
    """Keep the last recognized Comfy operation until lifecycle feedback supersedes it."""
    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        splash.start_activity(
            SplashActivity("Waiting", "Still waiting", "Taking longer")
        )
        splash.append_log("[INFO] Total VRAM 32768 MB, total RAM 65536 MB")
        assert panel.status.text().startswith("Preparing ComfyUI's compute device.")
        splash.append_log("[INFO] Set vram state to: NORMAL_VRAM")
        splash.append_log("Unrecognized extension output")
        assert panel.status.text().startswith("Preparing ComfyUI's compute device.")
        splash.append_log("[INFO] Starting server")
        assert panel.status.text().startswith("Starting the ComfyUI server.")
        splash.append_log("To see the GUI go to: http://127.0.0.1:8188")
        assert panel.status.text().startswith("Connecting to ComfyUI.")
        assert panel.progress.value() < panel.progress.maximum()
        splash.clear_activity()
        splash.set_progress(SplashProgress(3, 5), status="Preparing workspace")
        assert panel.status.text() == "Preparing workspace"
        splash.show_failure("Backend failed")
        splash.append_log("[INFO] Starting server")
        assert panel.status.text() == "Backend failed"
    finally:
        destroy_qt_object(splash)


@pytest.mark.parametrize("console_visible", [False, True])
def test_sweep_changes_only_completed_fill_and_stops_on_completion(
    console_visible: bool,
) -> None:
    """Render controlled animation frames and keep the unfilled Fluent track identical."""
    from PySide6.QtCore import QAbstractAnimation, QVariantAnimation
    from PySide6.QtWidgets import QWidget

    panel = SplashProgressPanel(details=QWidget())
    try:
        panel.resize(400, 120)
        panel.set_details_visible(console_visible)
        panel.show()
        panel.set_progress(SplashProgress(2, 5), status="Preparing workspace")
        panel.record_activity()
        QApplication.processEvents()
        animation = panel.progress.findChild(QVariantAnimation, "ProgressActivitySweep")
        assert animation is not None
        assert animation.loopCount() == 1
        animation.setCurrentTime(0)
        before = panel.progress.grab().toImage()
        animation.setCurrentTime(900)
        after = panel.progress.grab().toImage()
        boundary = panel.progress.width() * 2 // 5
        assert before.copy(0, 0, boundary, before.height()) != after.copy(
            0, 0, boundary, after.height()
        )
        assert before.copy(
            boundary, 0, before.width() - boundary, before.height()
        ) == after.copy(boundary, 0, after.width() - boundary, after.height())
        assert panel.progress.value() == 2
        animation.setCurrentTime(animation.duration())
        assert animation.state() == QAbstractAnimation.State.Stopped
        panel.record_activity()
        assert animation.state() == QAbstractAnimation.State.Running
        panel.set_progress(SplashProgress(5, 5), status="Ready")
        assert animation.state() == QAbstractAnimation.State.Stopped
    finally:
        destroy_qt_object(panel)


def test_console_disclosure_retains_animated_wait_stage() -> None:
    """Hide the explanation while logs are visible and restore the current timed frame."""
    from substitute.presentation.shell.splash_activity_presenter import (
        SplashActivityPresenter,
    )

    clock = [0.0]
    splash = SplashWindow(
        icon=QIcon(), backdrop_mode=None, activity_clock=lambda: clock[0]
    )
    try:
        splash.show()
        panel = splash.findChild(SplashProgressPanel)
        presenter = splash.findChild(SplashActivityPresenter)
        button = splash.findChild(ComfyOutputToggleButton)
        assert panel is not None and presenter is not None and button is not None
        splash.start_activity(SplashActivity("Waiting", "Long wait", "Extended wait"))
        splash.append_log("### Loading: SugarCubes")
        clock[0] = 1
        presenter.refresh()
        assert panel.status.text().startswith("Loading custom node: SugarCubes..")
        button.click()
        assert not panel.status.isVisible()
        assert splash.log_view.toPlainText().splitlines()[-1] == "Waiting.."
        assert "Loading custom node:" not in splash.log_view.toPlainText()
        clock[0] = 120
        presenter.refresh()
        assert splash.log_view.toPlainText().splitlines()[-1] == "Long wait."
        button.click()
        assert panel.status.isVisible()
        assert "SugarCubes" in panel.status.text()
        assert "taking longer than usual" in panel.status.text()
        assert not any(character.isdigit() for character in panel.status.text())
    finally:
        destroy_qt_object(splash)


def test_collapsed_status_updates_do_not_move_text_or_progress() -> None:
    """Keep the caption attached to the fixed bar across short and wrapped copy."""
    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        QApplication.processEvents()
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        assert panel.status.alignment() & Qt.AlignmentFlag.AlignBottom
        text_position = panel.status.pos()
        bar_geometry = panel.progress.geometry()
        for text in (
            "Preparing the application interface.",
            "Loading custom node: ComfyUI Advanced Image Processing... This is taking much longer than expected...",
            "Loading..",
        ):
            panel.set_activity_status(text)
            QApplication.processEvents()
            assert panel.status.pos() == text_position
            assert panel.progress.geometry() == bar_geometry
            caption_bottom = panel.status.mapTo(
                panel, panel.status.contentsRect().bottomLeft()
            ).y()
            assert panel.progress.y() - caption_bottom - 1 == 8
        panel.set_details_visible(True)
        QApplication.processEvents()
        panel.set_details_visible(False)
        QApplication.processEvents()
        assert panel.progress.geometry() == bar_geometry
    finally:
        destroy_qt_object(splash)


def test_wait_explanation_breaks_at_its_boundary_only_when_needed() -> None:
    """Keep appended reassurance together and reflow it when available width changes."""
    panel = SplashProgressPanel(details=QWidget())
    message = "Loading custom node: Advanced Image Processing…\nThis is taking much longer than expected..."
    inline = message.replace("\n", " ")
    try:
        panel.resize(510, 60)
        panel.show()
        QApplication.processEvents()
        panel.set_activity_status(message)
        assert panel.status.text() == message
        assert panel.progress.accessibleName() == inline
        panel.resize(panel.status.fontMetrics().horizontalAdvance(inline) + 40, 60)
        QApplication.processEvents()
        assert panel.status.text() == inline
        panel.resize(510, 60)
        QApplication.processEvents()
        assert panel.status.text() == message
        panel.set_activity_status("Loading custom node: SugarCubes.")
        assert "\n" not in panel.status.text()
    finally:
        destroy_qt_object(panel)


def test_output_activity_is_visible_before_any_completion() -> None:
    """Show unseen console output on the empty track without advancing its value."""

    from PySide6.QtCore import QVariantAnimation
    from PySide6.QtWidgets import QWidget

    panel = SplashProgressPanel(details=QWidget())
    try:
        panel.resize(400, 120)
        panel.show()
        panel.set_progress(SplashProgress(0, 5), status="Preparing workspace")
        panel.record_activity()
        animation = panel.progress.findChild(QVariantAnimation, "ProgressActivitySweep")
        assert animation is not None
        animation.setCurrentTime(0)
        before = panel.progress.grab().toImage()
        animation.setCurrentTime(900)
        after = panel.progress.grab().toImage()
        assert before != after
        assert panel.progress.value() == 0
    finally:
        destroy_qt_object(panel)


def test_console_bar_has_flat_fill_end_and_rounded_surface_corners() -> None:
    """Render joined chrome with square fill termination and a full-width rounded cap."""
    panel = SplashProgressPanel(details=QWidget())
    try:
        panel.resize(400, 120)
        panel.set_details_visible(True)
        panel.show()
        panel.set_progress(SplashProgress(1, 2), status="Starting")
        panel.progress.set_activity_enabled(False)
        QApplication.processEvents()
        bar = panel.progress
        partial = bar.grab().toImage()
        edge = partial.width() // 2 - 1
        assert partial.pixelColor(edge, 0) == partial.pixelColor(
            edge, partial.height() - 1
        )
        assert partial.pixelColor(0, 0) != partial.pixelColor(0, partial.height() - 1)
        panel.set_progress(SplashProgress(2, 2), status="Ready")
        complete = bar.grab().toImage()
        assert complete.pixelColor(complete.width() - 1, 0) != complete.pixelColor(
            complete.width() - 1, complete.height() - 1
        )
        panel.resize(520, 120)
        QApplication.processEvents()
        assert bar.width() == panel.details.width()
    finally:
        destroy_qt_object(panel)


def test_empty_console_track_is_subordinate_to_output_surface() -> None:
    """Keep zero-progress chrome close to the console background instead of a bright cap."""
    from qfluentwidgets import Theme, qconfig, setTheme  # type: ignore[import-untyped]

    previous_theme = qconfig.theme
    setTheme(Theme.DARK)
    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)
    try:
        splash.show()
        panel = splash.findChild(SplashProgressPanel)
        assert panel is not None
        panel.set_details_visible(True)
        QApplication.processEvents()
        rendered = panel.details.grab().toImage()
        center = rendered.width() // 2
        track = rendered.pixelColor(center, panel.progress.height() // 2)
        surface = rendered.pixelColor(center, panel.progress.height() + 12)
        assert (
            max(
                abs(track.red() - surface.red()),
                abs(track.green() - surface.green()),
                abs(track.blue() - surface.blue()),
            )
            <= 32
        )
    finally:
        destroy_qt_object(splash)
        setTheme(previous_theme)
