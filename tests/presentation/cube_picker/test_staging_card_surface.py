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

"""Cube staging card geometry and hit-target contracts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from substitute.presentation.cube_picker.cube_drag_ghost import CubeDragGhost
from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack
from substitute.presentation.cubes.cube_card_visual import CubeCardVisual
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_BUTTON_SIZE,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from tests.presentation.cube_picker.support import (
    ensure_application as _app,
    entry as _entry,
)


def test_draft_stack_and_drag_ghost_use_real_cube_stack_card_size() -> None:
    """Draft placement affordances should match real cube-stack card metrics."""

    _app()
    stack = CubeDraftStack()
    entry = _entry("copy-a")
    stack.insert_entry(0, entry, QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    ghost = CubeDragGhost(entry=entry, icon=QIcon(), parent=stack)

    assert card.size().width() == CUBE_ITEM_EXPANDED_WIDTH
    assert card.size().height() == CUBE_ITEM_HEIGHT
    assert ghost.size().width() == CUBE_ITEM_EXPANDED_WIDTH
    assert ghost.size().height() == CUBE_ITEM_HEIGHT


def test_draft_stack_card_exposes_real_stack_sized_close_button() -> None:
    """Draft cards should expose an X button matching real stack card metrics."""

    _app()
    stack = CubeDraftStack()
    entry = _entry("copy-a")
    stack.insert_entry(0, entry, QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")
    close_x = CubeCardVisual.close_button_x(
        CUBE_ITEM_EXPANDED_WIDTH,
        CUBE_ITEM_CLOSE_BUTTON_SIZE,
    )
    reserve_center = close_x + (CUBE_ITEM_CLOSE_BUTTON_SIZE / 2)

    assert close_button.isVisible() is True
    assert close_button.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert close_button.width() == CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert close_button.height() == CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert close_button.x() + (close_button.width() / 2) == reserve_center


def test_draft_stack_card_uses_painted_visual_without_label_hit_targets() -> None:
    """Draft card visuals should not add child labels that split the hit target."""

    _app()
    stack = CubeDraftStack()
    stack.insert_entry(0, _entry("copy-a"), QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    labels = card.findChildren(QLabel)

    assert card.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is False
    assert card.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert labels == []


def test_draft_stack_card_close_button_is_only_mouse_child() -> None:
    """The shared painted card visual should leave only the X button as a child."""

    _app()
    stack = CubeDraftStack()
    stack.insert_entry(0, _entry("copy-a"), QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")
    labels = card.findChildren(QLabel)

    assert labels == []
    assert (
        close_button.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        is False
    )
    assert close_button.isEnabled() is True
    assert close_button.isVisible() is True
