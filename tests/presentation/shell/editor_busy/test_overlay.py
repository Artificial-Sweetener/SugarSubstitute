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

"""Qt contract tests for the editor busy wash overlay."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.shell.editor_busy_overlay import EditorBusyOverlay
from substitute.presentation.shell.editor_busy_coordinator import EditorBusyCoordinator


def _ensure_qapp() -> QApplication:
    """Return an application instance for widget contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _clear_override_cursor() -> None:
    """Remove any cursor override left by an interrupted Qt assertion."""

    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


def test_editor_busy_overlay_starts_hidden_and_blocks_pointer_events() -> None:
    """The busy wash should start hidden and remain mouse-interactive when shown."""

    _ensure_qapp()
    parent = QWidget()
    parent.resize(320, 180)
    overlay = EditorBusyOverlay(parent)

    assert overlay.is_loading() is False
    assert (
        overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False
    )
    assert overlay.geometry() == parent.rect()


def test_editor_busy_overlay_sets_application_wait_cursor_idempotently() -> None:
    """The busy wash should show an OS wait cursor without stacking overrides."""

    _ensure_qapp()
    _clear_override_cursor()
    parent = QWidget()
    overlay = EditorBusyOverlay(parent)

    try:
        overlay.show_loading("Loading")
        cursor = QApplication.overrideCursor()
        assert cursor is not None
        assert cursor.shape() == Qt.CursorShape.WaitCursor

        overlay.show_loading("Loading")
        overlay.hide_loading()
        assert QApplication.overrideCursor() is None
    finally:
        _clear_override_cursor()


def test_settings_route_clears_wait_cursor_while_work_remains_pending() -> None:
    """Route projection should release the global cursor without losing busy work."""

    _ensure_qapp()
    _clear_override_cursor()
    editor_surface_active = True
    parent = QWidget()
    overlay = EditorBusyOverlay(parent)
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: "wf-a",
        is_editor_surface_active=lambda: editor_surface_active,
        overlay=overlay,
    )

    try:
        coordinator.begin("wf-a", message="Loading")
        assert QApplication.overrideCursor() is not None

        editor_surface_active = False
        coordinator.refresh_active_surface()

        assert QApplication.overrideCursor() is None
        assert coordinator.has_pending_workflow("wf-a") is True
    finally:
        coordinator.shutdown()
        _clear_override_cursor()


def test_editor_busy_overlay_animates_loading_ellipses() -> None:
    """The overlay should cycle ellipses without changing the centered word."""

    _ensure_qapp()
    parent = QWidget()
    parent.resize(320, 180)
    overlay = EditorBusyOverlay(parent)
    message_label = overlay.findChild(QLabel, "EditorBusyOverlayMessageLabel")
    ellipsis_label = overlay.findChild(QLabel, "EditorBusyOverlayEllipsisLabel")
    assert message_label is not None
    assert ellipsis_label is not None

    overlay.show_loading("Loading")
    assert message_label.text() == "Loading"
    assert ellipsis_label.text() == ""
    centered_word_x = message_label.geometry().center().x()
    assert abs(centered_word_x - overlay.rect().center().x()) <= 1
    ellipsis_x = ellipsis_label.geometry().x()

    overlay._advance_ellipsis()
    assert message_label.text() == "Loading"
    assert message_label.geometry().center().x() == centered_word_x
    assert ellipsis_label.geometry().x() == ellipsis_x
    assert ellipsis_label.text() == "."
    overlay._advance_ellipsis()
    assert message_label.text() == "Loading"
    assert message_label.geometry().center().x() == centered_word_x
    assert ellipsis_label.geometry().x() == ellipsis_x
    assert ellipsis_label.text() == ".."
    overlay._advance_ellipsis()
    assert message_label.text() == "Loading"
    assert message_label.geometry().center().x() == centered_word_x
    assert ellipsis_label.geometry().x() == ellipsis_x
    assert ellipsis_label.text() == "..."
    overlay._advance_ellipsis()
    assert message_label.text() == "Loading"
    assert message_label.geometry().center().x() == centered_word_x
    assert ellipsis_label.geometry().x() == ellipsis_x
    assert ellipsis_label.text() == ""

    overlay.hide_loading()
    assert overlay.is_loading() is False


def test_editor_busy_overlay_timer_updates_visible_label() -> None:
    """The ellipsis label should change from the active Qt timer."""

    _ensure_qapp()
    parent = QWidget()
    overlay = EditorBusyOverlay(parent)
    message_label = overlay.findChild(QLabel, "EditorBusyOverlayMessageLabel")
    ellipsis_label = overlay.findChild(QLabel, "EditorBusyOverlayEllipsisLabel")
    assert message_label is not None
    assert ellipsis_label is not None
    timeout_spy = QSignalSpy(overlay._timer.timeout)

    try:
        overlay.show_loading("Loading")
        assert message_label.text() == "Loading"
        assert ellipsis_label.text() == ""

        assert timeout_spy.wait(2_000)
        assert message_label.text() == "Loading"
        assert ellipsis_label.text() == "."

        assert timeout_spy.wait(2_000)
        assert message_label.text() == "Loading"
        assert ellipsis_label.text() == ".."
    finally:
        overlay.hide_loading()
