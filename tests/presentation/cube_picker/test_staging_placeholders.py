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

"""Cube staging placeholder and insertion contracts."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from tests.presentation.cube_picker.support import (
    ensure_application as _app,
    entry as _entry,
)


def test_staging_stack_empty_placeholder_and_insertion_placeholder_are_exclusive() -> (
    None
):
    """Empty drop target and insertion placeholder should not both be visible."""

    _app()
    stack = CubeDraftStack()
    stack.show()
    QApplication.processEvents()

    empty_widgets = stack.findChildren(
        CubePlaceholderCard,
        "cubeStagingEmptyPlaceholder",
    )
    assert len(empty_widgets) == 1
    assert empty_widgets[0].isVisible() is True
    assert empty_widgets[0].isPlusVisible() is False
    assert empty_widgets[0].width() == CUBE_ITEM_EXPANDED_WIDTH
    assert empty_widgets[0].height() == CUBE_ITEM_HEIGHT

    stack.set_placeholder_index(0)
    QApplication.processEvents()

    placeholder_widgets = stack.findChildren(
        CubePlaceholderCard,
        "cubeStagingPlaceholder",
    )
    assert len(empty_widgets) == 1
    assert len(placeholder_widgets) == 1
    assert empty_widgets[0].isVisible() is False
    assert placeholder_widgets[0].isVisible() is True
    assert placeholder_widgets[0].width() == CUBE_ITEM_EXPANDED_WIDTH
    assert placeholder_widgets[0].height() <= CUBE_ITEM_HEIGHT


def test_staging_stack_placeholder_uses_shared_cube_placeholder_card() -> None:
    """Insertion feedback should use the shared cube placeholder visual."""

    _app()
    stack = CubeDraftStack()
    stack.show()
    QApplication.processEvents()

    stack.set_placeholder_index(0)
    QApplication.processEvents()

    placeholder = stack.findChildren(CubePlaceholderCard, "cubeStagingPlaceholder")[0]

    assert placeholder.isPlusVisible() is False
    assert placeholder.width() == CUBE_ITEM_EXPANDED_WIDTH
    assert placeholder.maximumHeight() <= CUBE_ITEM_HEIGHT
    assert placeholder.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_staging_stack_insertion_index_uses_pointer_y_position() -> None:
    """Drag insertion should track the stack card midpoint."""

    _app()
    stack = CubeDraftStack()
    stack.resize(280, 240)
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.show()
    QApplication.processEvents()

    assert stack.insertion_index_at_global_pos(stack.mapToGlobal(QPoint(20, 16))) == 0
    assert stack.insertion_index_at_global_pos(stack.mapToGlobal(QPoint(20, 230))) == 2
