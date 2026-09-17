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

"""Verify standalone splash hosts apply requested Fluent appearance after paint."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, qconfig  # type: ignore[import-untyped]

from substitute.app.bootstrap import shared_splash_host
from substitute.presentation.shell.splash_progress_panel import SplashProgressPanel
from substitute.presentation.shell.splash_window import SplashWindow
from tests.presentation.theme.support import fluent_theme
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.mark.parametrize("requested_theme", ["dark", "light"])
def test_shared_host_applies_requested_fluent_appearance(
    monkeypatch: pytest.MonkeyPatch, requested_theme: str
) -> None:
    """Render requested controls even when QFluent begins in the opposite theme."""
    app = ensure_qt_application()
    windows: list[SplashWindow] = []

    def observe_event_loop() -> int:
        """Drive real queued enrichment without taking over the test event loop."""
        windows.extend(
            window
            for window in app.topLevelWidgets()
            if isinstance(window, SplashWindow)
        )
        assert len(windows) == 1
        splash = windows[0]
        wait_for_qt_condition(
            lambda: bool(splash.findChildren(SplashProgressPanel)),
            description="standalone splash Fluent progress controls",
        )
        panel = splash.findChildren(SplashProgressPanel)[0]
        assert qconfig.theme == (
            Theme.DARK if requested_theme == "dark" else Theme.LIGHT
        )
        assert qconfig.themeColor.value == QColor("#e91e63")
        expected_text = QColor("white" if requested_theme == "dark" else "black")
        panel.status.ensurePolished()
        assert (
            panel.status.palette().color(panel.status.foregroundRole()) == expected_text
        )
        return 0

    monkeypatch.setattr(QApplication, "exec", staticmethod(observe_event_loop))
    with fluent_theme(
        Theme.LIGHT if requested_theme == "dark" else Theme.DARK,
        accent_color=QColor("#009faa"),
    ):
        try:
            assert (
                shared_splash_host.main(
                    [
                        "--theme-mode=" + requested_theme,
                        "--accent-color=#e91e63",
                        "--backdrop-mode=none",
                    ]
                )
                == 0
            )
        finally:
            for window in windows:
                destroy_qt_object(window)
