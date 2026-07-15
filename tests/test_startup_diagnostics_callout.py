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

"""Tests for the startup diagnostics speech-bubble callout."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget
import pytest

from substitute.presentation.semantic_colors import semantic_error_color
from substitute.presentation.shell.startup_diagnostics_callout import (
    StartupDiagnosticsCallout,
    _diagnostics_bubble_color,
    _legible_text_color,
    startup_diagnostics_callout_message,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "callout Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by callout tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_startup_diagnostics_callout_positions_below_anchor() -> None:
    """Callout should position itself below and aimed at its anchor widget."""

    app = _app()
    host = QWidget()
    host.move(100, 100)
    host.resize(400, 120)
    anchor = QWidget(host)
    anchor.setGeometry(180, 0, 54, 32)
    host.show()
    app.processEvents()
    callout = StartupDiagnosticsCallout(auto_dismiss_ms=0)

    try:
        callout.show_for(
            anchor,
            "ComfyUI reported errors during startup",
            has_errors=True,
        )
        app.processEvents()

        anchor_center = anchor.mapToGlobal(QPoint(anchor.width() // 2, anchor.height()))
        assert callout.is_visible() is True
        assert callout.y() + 8 >= anchor_center.y()
        assert callout.x() + callout.pointer_x() == anchor_center.x()
        assert callout.message() == "ComfyUI reported errors during startup"
    finally:
        callout.dismiss()
        callout.deleteLater()
        host.close()
        host.deleteLater()
        app.processEvents()


def test_startup_diagnostics_callout_dismiss_hides_widget() -> None:
    """Dismiss should hide the callout immediately."""

    app = _app()
    anchor = QWidget()
    anchor.resize(54, 32)
    anchor.show()
    app.processEvents()
    callout = StartupDiagnosticsCallout(auto_dismiss_ms=0)

    try:
        callout.show_for(
            anchor,
            "ComfyUI reported warnings during startup",
            has_errors=False,
        )
        assert callout.is_visible() is True

        callout.dismiss()

        assert callout.is_visible() is False
    finally:
        callout.deleteLater()
        anchor.close()
        anchor.deleteLater()
        app.processEvents()


def test_startup_diagnostics_callout_message_uses_error_or_warning_copy() -> None:
    """Callout copy should match the visible startup diagnostics severity."""

    assert (
        startup_diagnostics_callout_message(has_errors=True)
        == "ComfyUI reported errors during startup"
    )
    assert (
        startup_diagnostics_callout_message(has_errors=False)
        == "ComfyUI reported warnings during startup"
    )


def test_startup_diagnostics_callout_text_color_contrasts_accent() -> None:
    """Callout text should choose black or white based on accent luminance."""

    assert _legible_text_color(QColor("#101010")) == QColor("#ffffff")
    assert _legible_text_color(QColor("#f0f0f0")) == QColor("#000000")


def test_startup_diagnostics_callout_uses_semantic_error_color_for_errors() -> None:
    """Error callout bubble should use the accent-derived semantic error color."""

    expected = semantic_error_color(alpha=235)

    assert _diagnostics_bubble_color(has_errors=True) == expected
