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

"""Verify QFluent theme ownership for custom numeric controls."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox, QSpinBox
from qfluentwidgets import Theme  # type: ignore[import-untyped]

from substitute.presentation.widgets import DoubleSpinBox, SpinBox
from tests.presentation.theme.support import ThemeWidgetOwner, is_qfluent_managed


def test_substitute_spin_boxes_register_with_qfluent_style(
    theme_owner: ThemeWidgetOwner,
) -> None:
    """Custom spin boxes retain behavior while QFluent owns their styling."""

    with theme_owner.using_theme(Theme.DARK):
        raw_spin_box = theme_owner.own(QSpinBox())
        raw_double_spin_box = theme_owner.own(QDoubleSpinBox())
        raw_hidden_spin_box = theme_owner.own(QSpinBox())
        raw_hidden_double_spin_box = theme_owner.own(QDoubleSpinBox())
        raw_hidden_spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        raw_hidden_double_spin_box.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        spin_box = theme_owner.own(SpinBox())
        double_spin_box = theme_owner.own(DoubleSpinBox())
        widgets = (
            raw_spin_box,
            raw_double_spin_box,
            raw_hidden_spin_box,
            raw_hidden_double_spin_box,
            spin_box,
            double_spin_box,
        )
        for widget in widgets:
            widget.setFixedSize(48, 33)
            widget.show()
        theme_owner.wait_until(lambda: all(widget.isVisible() for widget in widgets))

        assert is_qfluent_managed(spin_box)
        assert is_qfluent_managed(double_spin_box)
        assert spin_box.property("transparent") is True
        assert double_spin_box.property("transparent") is True
        assert spin_box.property("symbolVisible") is True
        assert double_spin_box.property("symbolVisible") is True
        assert spin_box.sizeHint() == raw_spin_box.sizeHint()
        assert spin_box.minimumSizeHint() == raw_spin_box.minimumSizeHint()
        assert double_spin_box.sizeHint() == raw_double_spin_box.sizeHint()
        assert (
            double_spin_box.minimumSizeHint() == raw_double_spin_box.minimumSizeHint()
        )
        assert spin_box.lineEdit().geometry() == raw_spin_box.lineEdit().geometry()
        assert (
            double_spin_box.lineEdit().geometry()
            == raw_double_spin_box.lineEdit().geometry()
        )

        dark_spin_style = spin_box.styleSheet()
        dark_double_style = double_spin_box.styleSheet()
        theme_owner.switch_theme(
            Theme.LIGHT,
            settled=lambda: (
                spin_box.styleSheet() != dark_spin_style
                and double_spin_box.styleSheet() != dark_double_style
            ),
        )

        spin_box.setSymbolVisible(False)
        double_spin_box.setSymbolVisible(False)
        assert spin_box.property("symbolVisible") is False
        assert double_spin_box.property("symbolVisible") is False
        assert spin_box.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        assert (
            double_spin_box.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        assert spin_box.sizeHint() == raw_hidden_spin_box.sizeHint()
        assert spin_box.minimumSizeHint() == raw_hidden_spin_box.minimumSizeHint()
        assert double_spin_box.sizeHint() == raw_hidden_double_spin_box.sizeHint()
        assert (
            double_spin_box.minimumSizeHint()
            == raw_hidden_double_spin_box.minimumSizeHint()
        )
        assert (
            spin_box.lineEdit().geometry() == raw_hidden_spin_box.lineEdit().geometry()
        )
        assert (
            double_spin_box.lineEdit().geometry()
            == raw_hidden_double_spin_box.lineEdit().geometry()
        )
        assert double_spin_box.textFromValue(1.2500000000) == "1.25"
