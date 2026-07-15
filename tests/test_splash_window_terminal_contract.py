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

"""Contract tests for splash-window integration with the shared terminal view."""

from __future__ import annotations

import os
from typing import cast

import pytest

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "splash window Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QLabel, QWidget

import substitute.presentation.shell.splash_window as splash_window
from substitute.presentation.splash_animation import (
    SplashPaperFlipWidget,
    SplashPoseLibraryError,
)
from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
)
from substitute.presentation.shell.splash_window import SplashWindow

_MAX_BOTTOM_CHROME_GAP_PX = 8
_EXPECTED_SPLASH_SIZE = (558, 558)
_EXPECTED_MASCOT_GEOMETRY = (83, 7, 387, 386)
_EXPECTED_CONSOLE_GEOMETRY = (6, 358, 546, 193)


def _app() -> QApplication:
    """Return the shared QApplication used by splash contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _end_of_document_bottom_gap(splash: SplashWindow) -> int:
    """Measure the rendered gap between the final caret row and viewport bottom."""

    cursor = splash.log_view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor_rect = splash.log_view.cursorRect(cursor)
    viewport_rect = splash.log_view.viewport().rect()
    return int(viewport_rect.bottom() - cursor_rect.bottom())


def test_splash_window_routes_append_log_through_shared_terminal_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash append calls should update the shared terminal output surface."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()

    splash.append_log("Starting\n")

    QApplication.processEvents()
    terminal_section = splash.findChild(QWidget, "SplashTerminalSection")
    assert terminal_section is not None
    assert terminal_section.minimumHeight() == terminal_section.maximumHeight()
    assert terminal_section.minimumHeight() >= 150
    assert splash.log_view.minimumHeight() == 0
    assert splash.log_view.maximumHeight() == 16777215
    assert splash.log_view.toPlainText() == "Starting"
    splash.close()


def test_splash_window_acrylic_uses_caption_fix_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash acrylic path should route through the shared caption-style fix."""

    _app()
    acrylic_calls: list[object] = []
    monkeypatch.setattr(
        splash_window,
        "apply_acrylic_effect",
        lambda window: acrylic_calls.append(window),
    )
    splash = SplashWindow(backdrop_mode=ShellBackdropMode.ACRYLIC)

    assert acrylic_calls == [splash]

    splash.close()


def test_splash_window_uses_animation_visual_when_assets_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash should replace the legacy icon with the packaged animation visual."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()

    visual = splash.findChild(SplashPaperFlipWidget, "SplashPaperFlipWidget")

    assert visual is not None
    assert visual in splash._drag_widgets
    splash.close()


def test_splash_window_sets_application_window_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash should use the shared application icon as its window icon."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)

    splash = SplashWindow()

    assert not splash.windowIcon().isNull()
    splash.close()


def test_splash_window_titlebar_close_button_requests_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash titlebar should expose qframeless close as the cancel button."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()
    cancel_calls: list[bool] = []
    splash.cancelRequested.connect(lambda: cancel_calls.append(True))

    titlebar = getattr(splash, "titleBar")
    assert titlebar.minBtn.isHidden()
    assert titlebar.maxBtn.isHidden()
    assert not titlebar.closeBtn.isHidden()
    assert titlebar.closeBtn.toolTip() == "Cancel loading"
    assert "CloseButton" in titlebar.closeBtn.styleSheet()

    titlebar.closeBtn.click()
    QApplication.processEvents()

    assert cancel_calls == [True]


def test_splash_window_uses_psd_fixed_layout_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash window should match the fixed PSD layer geometry."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()
    splash.show()

    for _ in range(5):
        QApplication.processEvents()

    visual = splash.findChild(SplashPaperFlipWidget, "SplashPaperFlipWidget")
    terminal_section = splash.findChild(QWidget, "SplashTerminalSection")
    assert visual is not None
    assert terminal_section is not None
    assert (splash.width(), splash.height()) == _EXPECTED_SPLASH_SIZE
    assert (
        visual.x(),
        visual.y(),
        visual.width(),
        visual.height(),
    ) == _EXPECTED_MASCOT_GEOMETRY
    assert (
        terminal_section.x(),
        terminal_section.y(),
        terminal_section.width(),
        terminal_section.height(),
    ) == _EXPECTED_CONSOLE_GEOMETRY

    splash.close()


def test_splash_window_falls_back_to_static_icon_when_animation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Animation setup failures should not prevent splash construction."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    monkeypatch.setattr(
        splash_window,
        "load_splash_pose_library",
        lambda: (_ for _ in ()).throw(SplashPoseLibraryError("missing poses")),
    )

    splash = SplashWindow()

    assert splash.findChild(QLabel, "SplashStaticIcon") is not None
    assert splash.findChild(SplashPaperFlipWidget, "SplashPaperFlipWidget") is None
    splash.close()


def test_splash_window_redraws_progress_records_in_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash output should replace the active line for carriage-return progress bars."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()

    splash.append_log("  0%|          | 0/28 [00:00<?, ?it/s]\r")
    splash.append_log("100%|##########| 28/28 [00:05<00:00,  5.47it/s]\n")

    QApplication.processEvents()
    assert splash.log_view.toPlainText().splitlines() == [
        "100%|##########| 28/28 [00:05<00:00,  5.47it/s]"
    ]
    splash.close()


def test_splash_window_keeps_wrapped_output_scrolled_to_newest_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash should inherit follow-tail behavior without a false blank row."""

    _app()
    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = SplashWindow()
    splash.show()

    wrapped_line = "wrapped splash output " + ("0123456789 " * 20)
    for index in range(25):
        splash.append_log(f"{index:02d}: {wrapped_line}\n")

    for _ in range(5):
        QApplication.processEvents()

    scrollbar = splash.log_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()
    assert splash.log_view.toPlainText().splitlines()[-1] == f"24: {wrapped_line}"
    assert splash.log_view.toPlainText().endswith("\n") is False
    assert _end_of_document_bottom_gap(splash) <= _MAX_BOTTOM_CHROME_GAP_PX

    splash.close()
