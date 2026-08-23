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

"""Regression tests for prompt projection Unicode and input-method behavior."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp

from .support import _set_source


def test_prompt_navigation_and_deletion_do_not_split_grapheme_clusters(
    widgets: list[QWidget],
) -> None:
    """Move and delete across emoji ZWJ and combining sequences atomically."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "A👩‍🚀é日")
    surface.set_cursor_positions(cursor_position=7, anchor_position=7)

    surface.move_cursor_by_operation(
        QTextCursor.MoveOperation.Left,
        keep_anchor=False,
    )
    assert surface.cursor_position == 6
    surface.move_cursor_by_operation(
        QTextCursor.MoveOperation.Left,
        keep_anchor=False,
    )
    assert surface.cursor_position == 4

    QTest.keyClick(surface, Qt.Key.Key_Backspace)

    assert surface.toPlainText() == "Aé日"
    assert surface.cursor_position == 1
