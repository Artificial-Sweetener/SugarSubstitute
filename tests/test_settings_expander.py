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

"""Widget contract tests for reusable SettingsExpander."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.settings.settings_expander import (
    SettingsExpander,
    SettingsExpanderRow,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_EXPAND_DURATION_MS,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
    SETTINGS_EXPANDER_ITEM_MIN_HEIGHT,
    SETTINGS_EXPANDER_ITEM_PADDING,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_settings_expander_starts_collapsed_and_toggles() -> None:
    """Collapsed expanders should hide body content until toggled."""

    app = _app()
    expander = SettingsExpander(title="Tracked pack")
    expander.add_widget(QLabel("Details", expander.content_widget()))
    expander.show()
    app.processEvents()

    assert expander.is_expanded() is False
    assert expander.content_widget().isHidden() is True
    assert expander.chevron.rotation_value() == 0.0
    assert expander.header_card.appearance() == "expander_header"
    assert expander.header_card.expander_header_attached() is False
    assert expander.body_spacing() == 0
    assert expander.separator_count() == 0
    assert expander.header_separator_height() == 1
    assert expander.header_separator_visible() is False
    assert expander.chevron.width() == SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE
    assert expander.chevron.height() == SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE

    QTest.mouseClick(expander.chevron, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert expander.is_expanded() is True
    assert expander.content_widget().isHidden() is False

    QTest.qWait(ACCORDION_EXPAND_DURATION_MS + 80)
    app.processEvents()

    assert expander.header_card.expander_header_attached() is True
    assert expander.header_separator_visible() is True
    assert expander.chevron.rotation_value() == 180.0
    expander.close()


def test_settings_expander_rows_match_reference_item_metrics() -> None:
    """Expanded item rows should use WinUI SettingsExpander item metrics."""

    _app()
    row = SettingsExpanderRow(title="Cubes", description="demo.cube")
    layout = row.layout()
    assert layout is not None
    margins = layout.contentsMargins()

    assert row.appearance() == "expander_item"
    assert row.minimumHeight() == SETTINGS_EXPANDER_ITEM_MIN_HEIGHT
    assert margins.left() == SETTINGS_EXPANDER_ITEM_PADDING.left()
    assert margins.top() == SETTINGS_EXPANDER_ITEM_PADDING.top()
    assert margins.right() == SETTINGS_EXPANDER_ITEM_PADDING.right()
    assert margins.bottom() == SETTINGS_EXPANDER_ITEM_PADDING.bottom()
    row.close()


def test_settings_expander_inserts_full_width_separators() -> None:
    """Expanded body separators should only divide adjacent child rows."""

    _app()
    expander = SettingsExpander(title="Tracked pack", expanded=True)
    first = SettingsExpanderRow(title="Cubes", parent=expander.content_widget())
    second = SettingsExpanderRow(title="Actions", parent=expander.content_widget())

    expander.add_widget(first)
    expander.add_widget(second)

    assert expander.separator_count() == 1
    expander.close()


def test_settings_expander_body_click_toggles_without_trailing_control() -> None:
    """Header body activation should toggle the expander state."""

    app = _app()
    expander = SettingsExpander(title="Add Cube Pack", description="Track a repo.")
    expander.show()
    app.processEvents()

    expander.header_card.activated.emit()
    app.processEvents()

    assert expander.is_expanded() is True
    expander.close()


def test_settings_expander_without_available_content_behaves_as_header_row() -> None:
    """Header-only expanders should not expose empty accordion behavior."""

    app = _app()
    expander = SettingsExpander(
        title="Add Cube Pack",
        description="Track a repo.",
        content_available=False,
    )
    expander.show()
    app.processEvents()

    assert expander.has_content_available() is False
    assert expander.chevron.isHidden() is True

    expander.header_card.activated.emit()
    expander.set_expanded(True)
    app.processEvents()

    assert expander.is_expanded() is False
    assert expander.content_widget().isHidden() is True
    assert expander.header_separator_visible() is False
    assert expander.header_card.expander_header_attached() is False

    expander.set_content_available(True)
    expander.set_expanded(True)
    app.processEvents()

    assert expander.has_content_available() is True
    assert expander.is_expanded() is True
    assert expander.chevron.isHidden() is False

    QTest.qWait(ACCORDION_EXPAND_DURATION_MS + 80)
    app.processEvents()

    assert expander.header_separator_visible() is True
    assert expander.header_card.expander_header_attached() is True
    expander.close()


def test_settings_expander_expanded_constructor_shows_body() -> None:
    """Expanded constructor state should show body content immediately."""

    app = _app()
    expander = SettingsExpander(title="Readiness", expanded=True)
    child = QWidget(expander.content_widget())
    child.setFixedHeight(24)
    expander.add_widget(child)
    expander.show()
    app.processEvents()

    assert expander.is_expanded() is True
    assert expander.content_widget().isHidden() is False
    assert expander.chevron.rotation_value() == 180.0
    expander.close()


def test_settings_expander_uses_node_card_style_motion() -> None:
    """Expansion and collapse should slide clipped body content like node cards."""

    app = _app()
    expander = SettingsExpander(title="Tracked pack", expanded=True)
    child = QWidget(expander.content_widget())
    child.setFixedHeight(140)
    expander.add_widget(child)
    expander.show()
    app.processEvents()

    expanded_height = expander.content_widget().sizeHint().height()

    expander.set_expanded(False)
    QTest.qWait(40)
    app.processEvents()

    assert expander.content_clip_visible() is True
    assert -expanded_height < expander.content_offset_y() < 0
    assert expander.header_separator_visible() is False

    QTest.qWait(ACCORDION_COLLAPSE_DURATION_MS + 80)
    app.processEvents()

    assert expander.content_clip_visible() is False
    assert expander.content_offset_y() == -expanded_height
    assert expander.chevron.rotation_value() == 0.0

    expander.set_expanded(True)
    QTest.qWait(ACCORDION_EXPAND_DURATION_MS + 80)
    app.processEvents()

    assert expander.content_clip_visible() is True
    assert expander.content_offset_y() == 0
    assert expander.header_separator_visible() is True
    assert expander.chevron.rotation_value() == 180.0
    expander.close()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
