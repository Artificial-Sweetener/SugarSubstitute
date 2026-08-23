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

"""Verify mounted media wall selection and pointer interaction."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtCore import QPoint, Qt

from substitute.presentation.widgets.media_wall import PickerJustifiedWallProfile
from tests.presentation.widgets.media_wall.support import (
    MediaWallOwner,
    mouse_press_event,
    square_wall_item,
    wall_item,
)


@pytest.fixture
def media_wall_owner() -> Generator[MediaWallOwner, None, None]:
    """Own every mounted interaction surface."""

    owner = MediaWallOwner()
    yield owner
    owner.destroy_all()


def test_selection_api_moves_and_clamps_current_item(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Expose generic bounded current-item navigation."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.set_items(tuple(wall_item(str(index)) for index in range(3)))

    assert view.current_index() == 0
    view.move_current(2)
    assert view.current_index() == 2
    view.move_current(8)
    assert view.current_index() == 2
    view.set_current_index(1)
    assert view.current_index() == 1
    assert view.current_payload() == "1"
    view.set_current_index(12)
    assert view.current_index() == -1
    assert view.current_payload() is None


def test_activation_api_emits_current_payload(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Activate the selected payload without requiring mouse focus."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    activated: list[object] = []
    view.itemActivated.connect(activated.append)
    view.set_items((wall_item("one"), wall_item("two")))
    view.set_current_index(1)

    assert view.activate_current()
    assert activated == ["two"]
    view.set_items(())
    assert not view.activate_current()


def test_right_click_emits_context_menu_payload(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Publish the clicked tile and global position for a context menu."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.show()
    view.set_items((wall_item("one"), wall_item("two")))
    emitted: list[tuple[object, QPoint]] = []
    view.itemContextMenuRequested.connect(
        lambda payload, point: emitted.append((payload, point))
    )
    point = QPoint(10, 10)
    event = mouse_press_event(view, point, button=Qt.MouseButton.RightButton)

    view.mousePressEvent(event)

    assert emitted == [("one", view.mapToGlobal(point))]
    assert view.current_payload() == "one"
    assert event.isAccepted()


def test_right_click_empty_space_does_not_emit_context_menu(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Ignore context-menu input that does not hit a tile."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.show()
    view.set_items(())
    emitted: list[tuple[object, QPoint]] = []
    view.itemContextMenuRequested.connect(
        lambda payload, point: emitted.append((payload, point))
    )

    view.mousePressEvent(
        mouse_press_event(
            view,
            QPoint(10, 10),
            button=Qt.MouseButton.RightButton,
        )
    )

    assert emitted == []


def test_left_click_activation_emits_payload(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Retain direct left-click tile activation."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.show()
    view.set_items((wall_item("one"), wall_item("two")))
    activated: list[object] = []
    view.itemActivated.connect(activated.append)
    event = mouse_press_event(
        view,
        QPoint(10, 10),
        button=Qt.MouseButton.LeftButton,
    )

    view.mousePressEvent(event)

    assert activated == ["one"]
    assert event.isAccepted()


def test_directional_navigation_follows_visual_rows(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Navigate vertical and horizontal intent through visual row geometry."""

    view = media_wall_owner.create(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        )
    )
    view.resize(300, 220)
    view.setUpdatesEnabled(False)
    view.viewport().setUpdatesEnabled(False)
    view._fluent_vertical_scroll_bar.setUpdatesEnabled(False)
    view.show()
    view.set_items(tuple(square_wall_item(str(index)) for index in range(6)))

    view.set_current_index(1)
    view.move_current_down()
    assert view.current_index() == 4
    view.move_current_up()
    assert view.current_index() == 1
    view.move_current_up()
    assert view.current_index() == 4
    view.move_current_down()
    assert view.current_index() == 1
    view.set_current_index(2)
    view.move_current_right()
    assert view.current_index() == 3
    view.move_current_left()
    assert view.current_index() == 2
