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

"""Contract tests for the pending restart toolbar button."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget
import pytest

from substitute.presentation.shell.pending_restart_toolbar_button import (
    PendingRestartToolbarButton,
)
from substitute.presentation.shell.chrome_style import WORKFLOW_TOOLBAR_CONTROL_HEIGHT

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "toolbar Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by toolbar button tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_pending_restart_toolbar_button_starts_hidden() -> None:
    """Button should start collapsed until restart items are pending."""

    _app()
    button = PendingRestartToolbarButton()

    assert button.count() == 0
    assert button.is_collapsed() is True
    assert button.isHidden() is True
    assert button.width() == 0
    assert button.accessibleName() == "Pending restart requirements"

    button.close()


def test_pending_restart_toolbar_button_shows_count() -> None:
    """Button should become visible with a pending restart count."""

    _app()
    button = PendingRestartToolbarButton()

    button.set_count(2)
    button.set_collapsed(False)

    assert button.count() == 2
    assert button.is_collapsed() is False
    assert button.isHidden() is False
    assert button.minimumWidth() == WORKFLOW_TOOLBAR_CONTROL_HEIGHT
    assert button.maximumWidth() == WORKFLOW_TOOLBAR_CONTROL_HEIGHT
    assert button.minimumWidth() == button.minimumHeight()
    assert button.toolTip() == "2 changes require restart"

    button.close()


def test_pending_restart_toolbar_button_emits_activated_on_click() -> None:
    """Clicking the visible toolbar button should emit activation intent."""

    _app()
    button = PendingRestartToolbarButton()
    calls: list[bool] = []
    button.activated.connect(lambda: calls.append(True))
    button.set_count(1)
    button.set_collapsed(False)

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    assert calls == [True]

    button.close()


def test_pending_restart_toolbar_button_uses_fluent_restart_icon() -> None:
    """Button should use the app icon system instead of hand-drawn arcs."""

    source = (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "shell"
        / "pending_restart_toolbar_button.py"
    ).read_text(encoding="utf-8")

    assert "FIF.SYNC" in source
    assert "drawArc" not in source
    assert "drawLine" not in source


def test_pending_restart_toolbar_button_collapses_balance_when_search_hidden() -> None:
    """Toolbar balance spacer should not reserve width outside Settings search."""

    _app()
    toolbar = QWidget()
    search = QWidget(toolbar)
    spacer = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    search.hide()
    spacer.setFixedWidth(47)

    button.set_balance_spacer(
        spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )

    assert spacer.minimumWidth() == 0
    assert spacer.maximumWidth() == 0
    assert spacer.isHidden() is True

    button.close()
    toolbar.close()


def test_pending_restart_toolbar_button_expands_balance_when_search_has_room() -> None:
    """Toolbar balance spacer may center visible Settings search when affordable."""

    _app()
    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    search = QWidget(toolbar)
    spacer = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    search.setFixedWidth(420)
    toolbar.resize(900, 44)
    search.show()
    spacer.setFixedWidth(0)
    layout.addWidget(search)
    layout.addWidget(spacer)
    layout.addWidget(button)

    button.set_balance_spacer(
        spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )

    assert spacer.minimumWidth() == 47
    assert spacer.maximumWidth() == 47
    assert spacer.isHidden() is False

    button.close()
    toolbar.close()


def test_pending_restart_toolbar_button_collapses_balance_when_visible() -> None:
    """Restart indicator should consume the right edge without adjacent dead space."""

    _app()
    toolbar = QWidget()
    search = QWidget(toolbar)
    spacer = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    search.setFixedWidth(420)
    toolbar.resize(900, 44)
    search.show()

    button.set_balance_spacer(
        spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )
    button.set_count(1)
    button.set_collapsed(False)

    assert spacer.minimumWidth() == 0
    assert spacer.maximumWidth() == 0
    assert spacer.isHidden() is True

    button.close()
    toolbar.close()


def test_pending_restart_toolbar_button_collapses_balance_when_width_starved() -> None:
    """Toolbar balance spacer should be discarded before it creates dead space."""

    _app()
    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    search = QWidget(toolbar)
    spacer = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    search.setFixedWidth(420)
    toolbar.resize(520, 44)
    search.show()
    layout.addWidget(search)
    layout.addWidget(spacer)
    layout.addWidget(button)

    button.set_balance_spacer(
        spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )

    assert spacer.minimumWidth() == 0
    assert spacer.maximumWidth() == 0
    assert spacer.isHidden() is True

    button.close()
    toolbar.close()


def test_pending_restart_toolbar_button_hides_alignment_spacer_when_starved() -> None:
    """Zero-width toolbar spacers must not leave layout spacing when starved."""

    app = _app()
    reference_toolbar = QWidget()
    reference_layout = QHBoxLayout(reference_toolbar)
    reference_layout.setContentsMargins(8, 4, 8, 4)
    reference_layout.setSpacing(4)
    reference_label = QWidget(reference_toolbar)
    reference_control = QWidget(reference_toolbar)
    reference_balance_spacer = QWidget(reference_toolbar)
    reference_alignment_spacer = QWidget(reference_toolbar)
    reference_search = QWidget(reference_toolbar)
    reference_button = PendingRestartToolbarButton(reference_toolbar)
    reference_label.setFixedWidth(26)
    reference_control.setFixedWidth(145)
    reference_button.set_count(1)
    reference_button.set_collapsed(False)
    for widget in (
        reference_label,
        reference_control,
        reference_balance_spacer,
        reference_alignment_spacer,
        reference_button,
    ):
        reference_layout.addWidget(widget)
    reference_layout.removeWidget(reference_balance_spacer)
    reference_layout.removeWidget(reference_alignment_spacer)
    reference_balance_spacer.hide()
    reference_alignment_spacer.hide()
    reference_search.hide()
    reference_button.set_balance_spacer(
        reference_balance_spacer,
        expanded_width=47,
        center_widget=reference_search,
        toolbar=reference_toolbar,
    )
    reference_button.set_alignment_spacer(
        reference_alignment_spacer,
        toolbar=reference_toolbar,
    )
    reference_toolbar.resize(223, 44)
    reference_toolbar.show()
    app.processEvents()
    reference_layout.activate()
    app.processEvents()
    reference_control_right = (
        reference_control.geometry().x() + reference_control.geometry().width()
    )
    natural_gap = reference_button.geometry().x() - reference_control_right

    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(4)
    label = QWidget(toolbar)
    control = QWidget(toolbar)
    balance_spacer = QWidget(toolbar)
    alignment_spacer = QWidget(toolbar)
    search = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    label.setFixedWidth(26)
    control.setFixedWidth(145)
    search.hide()
    for widget in (label, control, balance_spacer, alignment_spacer, button):
        layout.addWidget(widget)
    button.set_balance_spacer(
        balance_spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )
    button.set_alignment_spacer(alignment_spacer, toolbar=toolbar)
    button.set_count(1)
    button.set_collapsed(False)
    toolbar.resize(223, 44)
    toolbar.show()

    app.processEvents()
    layout.activate()
    button.eventFilter(toolbar, QEvent(QEvent.Type.Resize))
    layout.activate()
    app.processEvents()

    control_right = control.geometry().x() + control.geometry().width()
    restart_gap = button.geometry().x() - control_right
    assert balance_spacer.isHidden() is True
    assert alignment_spacer.isHidden() is True
    assert layout.indexOf(balance_spacer) == -1
    assert layout.indexOf(alignment_spacer) == -1
    assert restart_gap == natural_gap

    reference_toolbar.close()
    toolbar.close()


def test_pending_restart_toolbar_button_shows_alignment_spacer_with_room() -> None:
    """Restart indicator should still align right when the toolbar has real surplus."""

    app = _app()
    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(4)
    label = QWidget(toolbar)
    control = QWidget(toolbar)
    balance_spacer = QWidget(toolbar)
    alignment_spacer = QWidget(toolbar)
    search = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    label.setFixedWidth(26)
    control.setFixedWidth(145)
    search.hide()
    for widget in (label, control, balance_spacer, alignment_spacer, button):
        layout.addWidget(widget)
    button.set_balance_spacer(
        balance_spacer,
        expanded_width=47,
        center_widget=search,
        toolbar=toolbar,
    )
    button.set_alignment_spacer(alignment_spacer, toolbar=toolbar)
    button.set_count(1)
    button.set_collapsed(False)
    toolbar.resize(360, 44)
    toolbar.show()

    app.processEvents()
    layout.activate()
    button.eventFilter(toolbar, QEvent(QEvent.Type.Resize))
    layout.activate()
    app.processEvents()

    assert alignment_spacer.isHidden() is False
    assert alignment_spacer.geometry().width() >= 32
    assert button.geometry().right() == toolbar.width() - 9

    toolbar.close()


def test_pending_restart_toolbar_button_ignores_stale_stretched_control_width() -> None:
    """Right-alignment should recover after previous layouts stretched controls."""

    app = _app()
    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(4)
    control = QWidget(toolbar)
    alignment_spacer = QWidget(toolbar)
    button = PendingRestartToolbarButton(toolbar)
    control.setFixedWidth(145)
    control.resize(900, 32)
    layout.addWidget(control)
    layout.addWidget(alignment_spacer)
    layout.addWidget(button)
    button.set_alignment_spacer(alignment_spacer, toolbar=toolbar)
    button.set_count(1)
    button.set_collapsed(False)
    toolbar.resize(360, 44)
    toolbar.show()

    app.processEvents()
    layout.activate()
    button.eventFilter(toolbar, QEvent(QEvent.Type.Resize))
    layout.activate()
    app.processEvents()

    assert alignment_spacer.isHidden() is False
    assert layout.indexOf(alignment_spacer) >= 0
    assert button.geometry().right() == toolbar.width() - 9

    toolbar.close()
