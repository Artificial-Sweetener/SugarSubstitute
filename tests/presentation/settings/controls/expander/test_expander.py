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

"""Test reusable Settings expander state and row contracts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QWidget

from substitute.presentation.settings.settings_expander import (
    SettingsExpander,
    SettingsExpanderRow,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
    SETTINGS_EXPANDER_ITEM_MIN_HEIGHT,
    SETTINGS_EXPANDER_ITEM_PADDING,
)
from tests.presentation.settings.controls.expander.support import (
    application,
    wait_for_motion,
)


def test_settings_expander_starts_collapsed_and_toggles(
    owned_widgets: list[QWidget],
) -> None:
    """Collapsed expanders should hide body content until toggled."""

    app = application()
    expander = SettingsExpander(title="Tracked pack")
    owned_widgets.append(expander)
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

    wait_for_motion(expander)

    assert expander.header_card.expander_header_attached() is True
    assert expander.header_separator_visible() is True
    assert expander.chevron.rotation_value() == 180.0


def test_settings_expander_rows_match_reference_item_metrics(
    owned_widgets: list[QWidget],
) -> None:
    """Expanded item rows should use WinUI SettingsExpander item metrics."""

    application()
    row = SettingsExpanderRow(title="Cubes", description="demo.cube")
    owned_widgets.append(row)
    layout = row.layout()
    assert layout is not None
    margins = layout.contentsMargins()

    assert row.appearance() == "expander_item"
    assert row.minimumHeight() == SETTINGS_EXPANDER_ITEM_MIN_HEIGHT
    assert margins.left() == SETTINGS_EXPANDER_ITEM_PADDING.left()
    assert margins.top() == SETTINGS_EXPANDER_ITEM_PADDING.top()
    assert margins.right() == SETTINGS_EXPANDER_ITEM_PADDING.right()
    assert margins.bottom() == SETTINGS_EXPANDER_ITEM_PADDING.bottom()


def test_settings_expander_inserts_full_width_separators(
    owned_widgets: list[QWidget],
) -> None:
    """Expanded body separators should only divide adjacent child rows."""

    application()
    expander = SettingsExpander(title="Tracked pack", expanded=True)
    owned_widgets.append(expander)
    first = SettingsExpanderRow(title="Cubes", parent=expander.content_widget())
    second = SettingsExpanderRow(title="Actions", parent=expander.content_widget())

    expander.add_widget(first)
    expander.add_widget(second)

    assert expander.separator_count() == 1


def test_settings_expander_body_click_toggles_without_trailing_control(
    owned_widgets: list[QWidget],
) -> None:
    """Header body activation should toggle the expander state."""

    app = application()
    expander = SettingsExpander(title="Add Cube Pack", description="Track a repo.")
    owned_widgets.append(expander)
    expander.show()
    app.processEvents()

    expander.header_card.activated.emit()
    app.processEvents()

    assert expander.is_expanded() is True


def test_settings_expander_without_available_content_behaves_as_header_row(
    owned_widgets: list[QWidget],
) -> None:
    """Header-only expanders should not expose empty accordion behavior."""

    app = application()
    expander = SettingsExpander(
        title="Add Cube Pack",
        description="Track a repo.",
        content_available=False,
    )
    owned_widgets.append(expander)
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

    wait_for_motion(expander)

    assert expander.header_separator_visible() is True
    assert expander.header_card.expander_header_attached() is True


def test_settings_expander_expanded_constructor_shows_body(
    owned_widgets: list[QWidget],
) -> None:
    """Expanded constructor state should show body content immediately."""

    app = application()
    expander = SettingsExpander(title="Readiness", expanded=True)
    owned_widgets.append(expander)
    child = QWidget(expander.content_widget())
    child.setFixedHeight(24)
    expander.add_widget(child)
    expander.show()
    app.processEvents()

    assert expander.is_expanded() is True
    assert expander.content_widget().isHidden() is False
    assert expander.chevron.rotation_value() == 180.0
