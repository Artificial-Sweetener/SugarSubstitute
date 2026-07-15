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

"""Contract tests for workflow-tab unread generation highlighting."""

from __future__ import annotations

import inspect
import os

import pytest
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from substitute.presentation.workflows import workflow_tabs_view
from substitute.presentation.workflows.workflow_tabs_view import TabItem

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "workflow tab Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_unread_tab_starts_one_shot_shimmer_on_first_unread_transition() -> None:
    """Unread tabs should shimmer once when new unseen output first appears."""

    _app()
    tab = _tab()

    assert tab._unread_result_visible is False
    assert tab._unread_shimmer_animation.state() is QAbstractAnimation.State.Stopped

    tab.set_unread_result_visible(True)

    assert tab._unread_result_visible is True
    assert tab._unread_shimmer_animation.state() is QAbstractAnimation.State.Running
    assert tab._unread_shimmer_animation.startValue() == 0.0
    assert tab._unread_shimmer_animation.endValue() == 1.0

    tab._unread_shimmer_animation.setCurrentTime(400)
    tab.set_unread_result_visible(True)

    assert tab._unread_shimmer_animation.currentTime() == 400
    tab._unread_shimmer_animation.stop()


def test_clearing_unread_stops_shimmer() -> None:
    """Clearing unread state should stop shimmer and reset progress."""

    _app()
    tab = _tab()

    tab.set_unread_result_visible(True)
    tab._set_unread_shimmer_progress(0.35)
    tab.set_unread_result_visible(False)

    assert tab._unread_result_visible is False
    assert tab._unread_shimmer_animation.state() is QAbstractAnimation.State.Stopped
    assert tab._unread_shimmer_progress == 1.0


def test_unread_tab_does_not_draw_legacy_dot() -> None:
    """Unread workflow tab painting should not contain the old teal dot marker."""

    source = inspect.getsource(workflow_tabs_view.TabItem)

    assert "drawEllipse(self.width() - 18, 7" not in source
    assert "QColor(0, 159, 170, 230)" not in source


def test_unread_tab_renders_accent_body_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unread inactive tabs should fill their hover-shaped body with accent color."""

    _app()
    monkeypatch.setattr(workflow_tabs_view, "isDarkTheme", lambda: True)
    monkeypatch.setattr(workflow_tabs_view, "themeColor", lambda: QColor("#40C8FF"))
    idle_tab = _tab()
    unread_tab = _tab()
    unread_tab.set_unread_result_visible(True)
    unread_tab._stop_unread_shimmer()

    idle_pixel = _paint_inactive_background(idle_tab).pixelColor(24, 10)
    unread_pixel = _paint_inactive_background(unread_tab).pixelColor(24, 10)

    assert idle_pixel.alpha() == 0
    assert unread_pixel.alpha() > 0
    assert unread_pixel.blue() > unread_pixel.red()


def test_unread_hover_preserves_hover_wash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unread inactive tabs should still show hover wash over the accent fill."""

    _app()
    monkeypatch.setattr(workflow_tabs_view, "isDarkTheme", lambda: True)
    monkeypatch.setattr(workflow_tabs_view, "themeColor", lambda: QColor("#40C8FF"))
    idle_tab = _tab()
    hover_tab = _tab()
    for tab in (idle_tab, hover_tab):
        tab.set_unread_result_visible(True)
        tab._stop_unread_shimmer()
    setattr(hover_tab, "isHover", True)

    idle_pixel = _paint_inactive_background(idle_tab).pixelColor(24, 10)
    hover_pixel = _paint_inactive_background(hover_tab).pixelColor(24, 10)

    assert hover_pixel.alpha() > idle_pixel.alpha()
    assert hover_pixel.red() > idle_pixel.red()
    assert hover_pixel.green() > idle_pixel.green()
    assert hover_pixel.blue() >= idle_pixel.blue()


def test_selected_unread_tab_does_not_paint_unread_highlight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unread highlight helpers should fail closed while the tab is selected."""

    _app()
    monkeypatch.setattr(workflow_tabs_view, "isDarkTheme", lambda: True)
    monkeypatch.setattr(workflow_tabs_view, "themeColor", lambda: QColor("#40C8FF"))
    tab = _tab()
    tab.setSelected(True)
    tab.set_unread_result_visible(True)
    tab._stop_unread_shimmer()

    image = QImage(tab.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        tab._draw_unread_result_background(painter)
        tab._draw_unread_result_shimmer(painter)
    finally:
        painter.end()

    assert image.pixelColor(24, 10).alpha() == 0


def _tab() -> TabItem:
    """Create one inactive workflow tab item sized for paint assertions."""

    tab = TabItem("Workflow")
    tab.resize(140, 30)
    tab.setSelected(False)
    return tab


def _paint_inactive_background(tab: TabItem) -> QImage:
    """Render one tab's inactive background paint into a transparent image."""

    image = QImage(tab.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        tab._drawNotSelectedBackground(painter)
    finally:
        painter.end()
    return image


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
