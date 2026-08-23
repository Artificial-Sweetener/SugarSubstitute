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

"""Verify the model picker refreshes its QFluent theme style."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import Theme  # type: ignore[import-untyped]

from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.presentation.theme.support import ThemeWidgetOwner, is_qfluent_managed


def test_combo_uses_qfluent_light_and_dark_style(
    theme_owner: ThemeWidgetOwner,
) -> None:
    """Model picker styling refreshes without forcing white text."""

    with theme_owner.using_theme(Theme.DARK):
        combo = theme_owner.own(_ModelPickerComboSurface())
        combo.show()
        theme_owner.wait_until(combo.isVisible)

        assert is_qfluent_managed(combo)
        dark_style = combo.styleSheet()
        theme_owner.switch_theme(
            Theme.LIGHT,
            settled=lambda: combo.styleSheet() != dark_style,
        )

        light_text = combo.palette().color(QPalette.ColorRole.Text)
        assert light_text != QColor("white")
