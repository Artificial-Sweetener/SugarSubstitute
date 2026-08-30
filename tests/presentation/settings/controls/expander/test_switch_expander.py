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

"""Test switch-owned Settings disclosure contracts."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import SwitchButton  # type: ignore[import-untyped]

from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_expander import (
    SwitchSettingsExpander,
)
from substitute.presentation.settings.settings_row_factories import (
    build_settings_icon_widget,
    build_switch_settings_row,
)
from tests.presentation.settings.controls.expander.support import (
    application,
)


def test_switch_settings_expander_owns_feature_disclosure_without_chevron(
    owned_widgets: list[QWidget],
) -> None:
    """Feature enablement should be the sole owner of subordinate disclosure."""

    app = application()
    expander = SwitchSettingsExpander(title="JPEG companions")
    owned_widgets.append(expander)
    expander.add_widget(QLabel("JPEG sizing", expander.content_widget()))
    observed: list[bool] = []
    expander.checkedChanged.connect(observed.append)
    expander.show()
    app.processEvents()

    assert expander.is_checked() is False
    assert expander.is_expanded() is False
    assert expander.chevron.isHidden() is True
    assert expander.header_card.appearance() == "controlled_expander_header"
    assert expander.header_card.trailing_widget is expander.switch

    expander.header_card.activated.emit()
    app.processEvents()

    assert expander.is_checked() is True
    assert expander.is_expanded() is True
    assert expander.chevron.isHidden() is True
    assert observed == [True]

    expander.set_checked(False)
    app.processEvents()

    assert expander.is_checked() is False
    assert expander.is_expanded() is False
    assert observed == [True, False]


def test_switch_settings_expander_aligns_toggle_with_standard_settings_rows(
    owned_widgets: list[QWidget],
) -> None:
    """Controlled expander switches should use the standard trailing-card inset."""

    app = application()
    host = QWidget()
    owned_widgets.append(host)
    layout = QVBoxLayout(host)
    expander = SwitchSettingsExpander(
        title="JPEG companions",
        visual_widget=build_settings_icon_widget(
            AppIcon.SAVE_IMAGE_20_REGULAR,
            host,
        ),
        parent=host,
    )
    standard_row = build_switch_settings_row(
        parent=host,
        icon=AppIcon.SAVE_IMAGE_20_REGULAR,
        title="Look up missing recipe models",
        description="Use CivitAI only after local recipe model matching fails.",
        checked=True,
        on_changed=lambda _checked: None,
    )
    standard_switch = standard_row.findChild(SwitchButton)
    assert isinstance(standard_switch, QWidget)
    assert isinstance(expander.switch, QWidget)
    assert expander.header_card.trailing_widget is expander.switch
    layout.addWidget(expander)
    layout.addWidget(standard_row)
    host.resize(900, 220)
    host.show()
    app.processEvents()

    expander_right = (
        expander.width()
        - expander.switch.mapTo(expander, QPoint()).x()
        - expander.switch.width()
    )
    standard_right = (
        standard_row.width()
        - standard_switch.mapTo(standard_row, QPoint()).x()
        - standard_switch.width()
    )

    assert expander_right == standard_right == 16
