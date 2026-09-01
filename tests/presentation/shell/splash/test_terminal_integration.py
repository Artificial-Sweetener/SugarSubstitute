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

from collections.abc import Callable, Iterator
from typing import Protocol

import pytest

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from sugarsubstitute_shared.launch_splash import SplashActivity

import substitute.presentation.shell.splash_window as splash_window
from substitute.presentation.splash_animation import (
    SplashPaperFlipWidget,
    SplashPoseLibraryError,
)
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.splash_window import SplashWindow
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition

_MAX_BOTTOM_CHROME_GAP_PX = 8
_EXPECTED_SPLASH_SIZE = (558, 558)
_EXPECTED_MASCOT_GEOMETRY = (83, 7, 387, 386)
_EXPECTED_CONSOLE_GEOMETRY = (6, 358, 546, 193)


class SplashWindowFactory(Protocol):
    """Construct splash windows owned by the current test."""

    def __call__(
        self,
        *,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
        activity_clock: Callable[[], float] | None = None,
    ) -> SplashWindow:
        """Return one tracked production splash window."""


@pytest.fixture
def splash_window_factory() -> Iterator[SplashWindowFactory]:
    """Destroy every production splash and its native timers after each test."""

    windows: list[SplashWindow] = []

    def create(
        *,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
        activity_clock: Callable[[], float] | None = None,
    ) -> SplashWindow:
        window = (
            SplashWindow(backdrop_mode=backdrop_mode)
            if activity_clock is None
            else SplashWindow(
                backdrop_mode=backdrop_mode,
                activity_clock=activity_clock,
            )
        )
        windows.append(window)
        return window

    yield create

    for window in reversed(windows):
        destroy_qt_object(window)


def _end_of_document_bottom_gap(splash: SplashWindow) -> int:
    """Measure the rendered gap between the final caret row and viewport bottom."""

    cursor = splash.log_view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor_rect = splash.log_view.cursorRect(cursor)
    viewport_rect = splash.log_view.viewport().rect()
    return int(viewport_rect.bottom() - cursor_rect.bottom())


@pytest.mark.parametrize(
    ("cursor_screen_present", "expected_geometry"),
    (
        (True, QRect(1600, 100, 1920, 1080)),
        (False, QRect(-1280, 0, 1280, 1024)),
    ),
)
def test_splash_centers_on_cursor_screen_with_primary_screen_fallback(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
    cursor_screen_present: bool,
    expected_geometry: QRect,
) -> None:
    """Splash placement should prefer the cursor display before using primary."""

    class _Screen:
        """Expose the available geometry required by splash placement."""

        def __init__(self, geometry: QRect) -> None:
            """Store one deterministic available desktop region."""

            self._geometry = geometry

        def availableGeometry(self) -> QRect:
            """Return the region used for centering."""

            return self._geometry

    cursor_screen = _Screen(QRect(1600, 100, 1920, 1080))
    primary_screen = _Screen(QRect(-1280, 0, 1280, 1024))

    class _Cursor:
        """Return a stable cursor position for monitor selection."""

        @staticmethod
        def pos() -> QPoint:
            """Return the global cursor position passed to Qt screen lookup."""

            return QPoint(2100, 400)

    class _GuiApplication:
        """Expose deterministic screen selection without native display state."""

        @staticmethod
        def screenAt(position: QPoint) -> _Screen | None:
            """Return the cursor screen when this scenario exposes one."""

            assert position == QPoint(2100, 400)
            return cursor_screen if cursor_screen_present else None

        @staticmethod
        def primaryScreen() -> _Screen:
            """Return the fallback screen when cursor lookup has no result."""

            return primary_screen

    monkeypatch.setattr(splash_window, "QCursor", _Cursor)
    monkeypatch.setattr(splash_window, "QGuiApplication", _GuiApplication)
    splash = splash_window_factory(backdrop_mode=None)

    splash.center_on_screen()

    assert splash.pos() == QPoint(
        expected_geometry.left() + (expected_geometry.width() - splash.width()) // 2,
        expected_geometry.top() + (expected_geometry.height() - splash.height()) // 2,
    )


def test_splash_window_routes_append_log_through_shared_terminal_view(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash append calls should update the shared terminal output surface."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()

    splash.append_log("Starting\n")

    terminal_section = splash.findChild(QWidget, "SplashTerminalSection")
    assert terminal_section is not None
    assert terminal_section.minimumHeight() == terminal_section.maximumHeight()
    assert terminal_section.minimumHeight() >= 150
    assert splash.log_view.minimumHeight() == 0
    assert splash.log_view.maximumHeight() == 16777215
    assert splash.log_view.toPlainText() == "Starting"


def test_splash_window_keeps_activity_visible_around_durable_logs(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """The production splash should retain one animated tail around durable output."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory(activity_clock=lambda: 0.0)
    activity = SplashActivity(
        initial_text="Updating SugarCubes",
        long_wait_text="Updating SugarCubes is taking longer than usual",
        extended_wait_text="Still updating SugarCubes—network may be slow",
    )

    splash.start_activity(activity)
    QApplication.processEvents()
    assert splash.log_view.toPlainText() == "Updating SugarCubes."

    splash.append_log("Downloaded package metadata.\n")
    QApplication.processEvents()
    assert splash.log_view.toPlainText().splitlines() == [
        "Downloaded package metadata.",
        "Updating SugarCubes.",
    ]

    splash.clear_activity()
    QApplication.processEvents()
    assert splash.log_view.toPlainText() == "Downloaded package metadata."


def test_splash_window_acrylic_uses_caption_fix_helper(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash acrylic path should route through the shared caption-style fix."""

    acrylic_calls: list[object] = []
    monkeypatch.setattr(
        splash_window,
        "apply_acrylic_effect",
        lambda window: acrylic_calls.append(window),
    )
    splash = splash_window_factory(backdrop_mode=ShellBackdropMode.ACRYLIC)

    assert acrylic_calls == [splash]


def test_splash_window_uses_animation_visual_when_assets_load(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash should replace the legacy icon with the packaged animation visual."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()

    visual = splash.findChild(SplashPaperFlipWidget, "SplashPaperFlipWidget")

    assert visual is not None
    assert visual in splash._drag_widgets


def test_splash_window_sets_application_window_icon(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash should use the shared application icon as its window icon."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)

    splash = splash_window_factory()

    assert not splash.windowIcon().isNull()


def test_splash_window_titlebar_close_button_requests_cancel(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash titlebar should expose qframeless close as the cancel button."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()
    cancel_calls: list[bool] = []
    splash.cancelRequested.connect(lambda: cancel_calls.append(True))

    titlebar = getattr(splash, "titleBar")
    assert titlebar.minBtn.isHidden()
    assert titlebar.maxBtn.isHidden()
    assert not titlebar.closeBtn.isHidden()
    assert titlebar.closeBtn.toolTip() == "Cancel loading"
    assert "CloseButton" in titlebar.closeBtn.styleSheet()

    titlebar.closeBtn.click()

    assert cancel_calls == [True]


def test_splash_window_uses_psd_fixed_layout_geometry(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash window should match the fixed PSD layer geometry."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()

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


def test_splash_window_falls_back_to_static_icon_when_animation_fails(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Animation setup failures should not prevent splash construction."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    monkeypatch.setattr(
        splash_window,
        "load_splash_pose_library",
        lambda: (_ for _ in ()).throw(SplashPoseLibraryError("missing poses")),
    )

    splash = splash_window_factory()

    assert splash.findChild(QLabel, "SplashStaticIcon") is not None
    assert splash.findChild(SplashPaperFlipWidget, "SplashPaperFlipWidget") is None


def test_splash_window_redraws_progress_records_in_place(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash output should replace the active line for carriage-return progress bars."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()

    splash.append_log("  0%|          | 0/28 [00:00<?, ?it/s]\r")
    splash.append_log("100%|##########| 28/28 [00:05<00:00,  5.47it/s]\n")

    assert splash.log_view.toPlainText().splitlines() == [
        "100%|##########| 28/28 [00:05<00:00,  5.47it/s]"
    ]


def test_splash_window_keeps_wrapped_output_scrolled_to_newest_line(
    monkeypatch: pytest.MonkeyPatch,
    splash_window_factory: SplashWindowFactory,
) -> None:
    """Splash should inherit follow-tail behavior without a false blank row."""

    monkeypatch.setattr(SplashWindow, "center_on_screen", lambda self: None)
    splash = splash_window_factory()
    splash.show()

    wrapped_line = "wrapped splash output " + ("0123456789 " * 20)
    for index in range(25):
        splash.append_log(f"{index:02d}: {wrapped_line}\n")

    scrollbar = splash.log_view.verticalScrollBar()
    wait_for_qt_condition(
        lambda: (
            scrollbar.value() == scrollbar.maximum()
            and _end_of_document_bottom_gap(splash) <= _MAX_BOTTOM_CHROME_GAP_PX
        )
    )
    assert scrollbar.value() == scrollbar.maximum()
    assert splash.log_view.toPlainText().splitlines()[-1] == f"24: {wrapped_line}"
    assert splash.log_view.toPlainText().endswith("\n") is False
    assert _end_of_document_bottom_gap(splash) <= _MAX_BOTTOM_CHROME_GAP_PX
