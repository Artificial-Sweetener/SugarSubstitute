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

"""Verify vertical layout construction through real Qt ownership."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.utils.create_vbox import create_vbox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_create_vbox_applies_parent_margins_and_spacing() -> None:
    """The layout should retain its Qt parent and requested geometry settings."""

    ensure_qt_application()
    parent = QWidget()

    layout = create_vbox(parent=parent, margins=(1, 2, 3, 4), spacing=9)

    margins = layout.contentsMargins()
    assert layout.parent() is parent
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        1,
        2,
        3,
        4,
    )
    assert layout.spacing() == 9
    destroy_qt_object(parent)
