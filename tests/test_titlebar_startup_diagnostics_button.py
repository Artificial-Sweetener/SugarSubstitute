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

"""Contract tests for the startup diagnostics titlebar button."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.semantic_colors import (
    semantic_error_color,
    semantic_warning_color,
)
from substitute.presentation.shell.titlebar_buttons import (
    StartupDiagnosticsTitleBarButton,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "titlebar Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by titlebar button tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_startup_diagnostics_button_exposes_accessible_titlebar_state() -> None:
    """Button should expose tooltip, accessibility, and tooltip filter state."""

    _app()
    button = StartupDiagnosticsTitleBarButton()

    assert button.toolTip() == "View ComfyUI startup diagnostics"
    assert button.accessibleName() == "ComfyUI startup diagnostics"
    assert button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert button.visible_width > button.height()
    assert isinstance(button._tooltip_filter, FluentToolTipFilter)
    assert button._tooltip_filter.parent() is button

    button.close()


def test_startup_diagnostics_button_tracks_error_count_and_badge_color() -> None:
    """Error diagnostics should use semantic error badge treatment."""

    _app()
    button = StartupDiagnosticsTitleBarButton()

    button.set_count(3, has_errors=True)

    assert button.count() == 3
    assert button.has_errors() is True
    assert button.badge_color() == semantic_error_color()

    button.close()


def test_startup_diagnostics_button_tracks_warning_only_badge_color() -> None:
    """Warning-only diagnostics should use semantic warning badge treatment."""

    _app()
    button = StartupDiagnosticsTitleBarButton()

    button.set_count(2, has_errors=False)

    assert button.count() == 2
    assert button.has_errors() is False
    assert button.badge_color() == semantic_warning_color()

    button.close()


def test_startup_diagnostics_button_emits_activated_on_click() -> None:
    """Clicking the button should emit the diagnostics activation intent."""

    _app()
    button = StartupDiagnosticsTitleBarButton()
    button.set_collapsed(False, animated=False)
    calls: list[bool] = []
    button.activated.connect(lambda: calls.append(True))

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    assert calls == [True]

    button.close()


def test_startup_diagnostics_button_collapses_and_expands_width_constraints() -> None:
    """Collapsed state should occupy no titlebar width until expanded."""

    _app()
    button = StartupDiagnosticsTitleBarButton()

    assert button.is_collapsed() is True
    assert button.maximumWidth() == 0
    assert button.minimumWidth() == 0
    assert button.isHidden() is True

    button.set_collapsed(False, animated=False)

    assert button.is_collapsed() is False
    assert button.maximumWidth() == button.visible_width
    assert button.minimumWidth() == button.visible_width
    assert button.isHidden() is False

    button.set_collapsed(True, animated=False)

    assert button.is_collapsed() is True
    assert button.maximumWidth() == 0
    assert button.minimumWidth() == 0
    assert button.isHidden() is True

    button.close()


def test_startup_diagnostics_button_emits_expanded_after_width_is_restored() -> None:
    """Expansion signal should fire only after the button has usable geometry."""

    app = _app()
    button = StartupDiagnosticsTitleBarButton()
    widths: list[int] = []
    button.expanded.connect(lambda: widths.append(button.width()))

    button.set_collapsed(False)
    QTest.qWait(200)
    app.processEvents()

    assert widths
    assert widths[-1] == button.visible_width

    button.close()
