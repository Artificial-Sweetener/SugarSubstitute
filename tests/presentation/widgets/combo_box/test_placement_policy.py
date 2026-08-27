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

"""Verify searchable-combo popup placement policy."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from substitute.presentation.widgets.searchable_combo_helpers import (
    attached_combo_popup_placement,
    left_anchored_combo_popup_placement,
)


def test_left_anchor_is_preserved_when_screen_space_allows() -> None:
    """Keep the popup aligned to the field's left edge on a roomy screen."""

    placement = left_anchored_combo_popup_placement(
        field_global_top_left=QPoint(100, 50),
        field_size=QSize(200, 32),
        popup_size=QSize(320, 180),
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.position == QPoint(100, 82)
    assert placement.opens_down is True


def test_left_anchor_clamps_right_overflow() -> None:
    """Keep a wide popup inside the screen's right edge."""

    placement = left_anchored_combo_popup_placement(
        field_global_top_left=QPoint(700, 50),
        field_size=QSize(80, 32),
        popup_size=QSize(240, 180),
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.position.x() < 700
    assert placement.position.x() + 240 <= 800


def test_left_anchor_clamps_left_overflow() -> None:
    """Keep overflow correction inside the screen's left edge."""

    placement = left_anchored_combo_popup_placement(
        field_global_top_left=QPoint(-30, 50),
        field_size=QSize(80, 32),
        popup_size=QSize(240, 180),
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.position.x() == 0


def test_left_anchor_opens_above_when_above_has_more_room() -> None:
    """Open upward when the anchor is near the screen's bottom edge."""

    placement = left_anchored_combo_popup_placement(
        field_global_top_left=QPoint(100, 550),
        field_size=QSize(180, 32),
        popup_size=QSize(240, 180),
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.opens_down is False
    assert placement.position.y() == 370


def test_attached_placement_limits_visible_rows() -> None:
    """Limit a roomy attached popup to its configured visible-row budget."""

    placement = attached_combo_popup_placement(
        field_global_rect=QRect(100, 50, 200, 32),
        screen_available_geometry=QRect(0, 0, 800, 700),
        preferred_popup_width=320,
        row_count=30,
        row_height=33,
        max_visible_rows=10,
        vertical_chrome_height=40,
        horizontal_chrome_width=24,
    )

    assert placement.opens_down is True
    assert placement.visible_row_count == 10
    assert placement.requires_scroll is True
    assert placement.geometry.top() == 82
    assert placement.geometry.height() == 10 * 33 + 40


def test_attached_placement_uses_actual_short_row_count() -> None:
    """Size a short attached popup to its actual item count."""

    placement = attached_combo_popup_placement(
        field_global_rect=QRect(100, 50, 200, 32),
        screen_available_geometry=QRect(0, 0, 800, 700),
        preferred_popup_width=320,
        row_count=3,
        row_height=33,
        max_visible_rows=10,
        vertical_chrome_height=40,
        horizontal_chrome_width=24,
    )

    assert placement.visible_row_count == 3
    assert placement.requires_scroll is False
    assert placement.geometry.height() == 3 * 33 + 40


def test_attached_placement_opens_above_and_touches_anchor() -> None:
    """Attach an upward-opening popup's bottom edge to its field."""

    anchor = QRect(100, 550, 180, 32)

    placement = attached_combo_popup_placement(
        field_global_rect=anchor,
        screen_available_geometry=QRect(0, 0, 800, 600),
        preferred_popup_width=320,
        row_count=8,
        row_height=33,
        max_visible_rows=10,
        vertical_chrome_height=40,
        horizontal_chrome_width=24,
    )

    assert placement.opens_down is False
    assert placement.geometry.top() + placement.geometry.height() == anchor.top()


def test_attached_placement_shrinks_on_the_larger_available_side() -> None:
    """Shrink a starved popup on the larger side without detaching it."""

    anchor = QRect(100, 250, 180, 32)

    placement = attached_combo_popup_placement(
        field_global_rect=anchor,
        screen_available_geometry=QRect(0, 0, 800, 420),
        preferred_popup_width=320,
        row_count=30,
        row_height=33,
        max_visible_rows=10,
        vertical_chrome_height=40,
        horizontal_chrome_width=24,
    )

    assert placement.opens_down is False
    assert placement.visible_row_count < 10
    assert placement.requires_scroll is True
    assert placement.geometry.top() + placement.geometry.height() == anchor.top()
    assert placement.geometry.top() >= 0


def test_attached_placement_clamps_width_without_detaching() -> None:
    """Clamp horizontal overflow without changing vertical attachment."""

    anchor = QRect(740, 80, 80, 32)

    placement = attached_combo_popup_placement(
        field_global_rect=anchor,
        screen_available_geometry=QRect(0, 0, 800, 600),
        preferred_popup_width=320,
        row_count=12,
        row_height=33,
        max_visible_rows=10,
        vertical_chrome_height=40,
        horizontal_chrome_width=24,
    )

    assert placement.geometry.left() < anchor.left()
    assert placement.geometry.left() + placement.geometry.width() <= 800
    assert placement.geometry.top() == anchor.top() + anchor.height()
