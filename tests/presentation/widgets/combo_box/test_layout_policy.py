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

"""Verify searchable combo participation in parent layouts."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from substitute.presentation.widgets.combo_box import ComboBox
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)


def test_default_size_policy_caps_title_row_width_to_hint() -> None:
    """A title-row combo should not consume all expandable row width."""

    ensure_qt_application()
    host = QWidget()
    host.resize(520, 80)
    layout = QHBoxLayout(host)
    layout.addWidget(QLabel("Text to Image", host), 1)
    combo = ComboBox(host)
    combo.addItems(["Independent", "Text to Image"])
    layout.addWidget(combo)
    host.show()
    activate_widget_layouts(host)

    assert combo.width() <= combo.sizeHint().width() + 8
    destroy_qt_object(host)
