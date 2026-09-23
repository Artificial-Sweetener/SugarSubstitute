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

"""Test anchor-aligned row flyout placement rules."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from substitute.presentation.widgets.anchored_row_flyout_placement import (
    anchored_row_flyout_placement,
    anchored_row_flyout_viewport,
)


def test_anchored_row_flyout_viewport_preserves_anchor_slot_on_roomy_screen() -> None:
    """The scroll window should expose whole rows above and below the anchor."""

    viewport = anchored_row_flyout_viewport(
        anchor_global_rect=QRect(100, 300, 170, 28),
        screen_available_geometry=QRect(0, 0, 800, 600),
        row_height=28,
        row_spacing=2,
        view_margin=7,
    )

    assert viewport.active_row_slot_from_top == 9
    assert viewport.maximum_view_height == 552


def test_anchored_row_flyout_viewport_opens_upward_near_screen_bottom() -> None:
    """A bottom anchor should keep the active row in the last visible slot."""

    viewport = anchored_row_flyout_viewport(
        anchor_global_rect=QRect(100, 560, 170, 28),
        screen_available_geometry=QRect(0, 0, 800, 600),
        row_height=28,
        row_spacing=2,
        view_margin=7,
    )

    assert viewport.active_row_slot_from_top == 18
    assert viewport.maximum_view_height == 582


def test_anchored_row_flyout_viewport_opens_downward_near_screen_top() -> None:
    """A top anchor should retain room below while keeping its row first."""

    viewport = anchored_row_flyout_viewport(
        anchor_global_rect=QRect(100, 20, 170, 28),
        screen_available_geometry=QRect(0, 0, 800, 600),
        row_height=28,
        row_spacing=2,
        view_margin=7,
    )

    assert viewport.active_row_slot_from_top == 0
    assert viewport.maximum_view_height == 582


def test_scroll_viewport_keeps_selected_row_over_anchor() -> None:
    """Scrollable placement should preserve the picker's defining overlap contract."""

    anchor = QRect(100, 300, 170, 28)
    screen = QRect(0, 0, 800, 600)
    viewport = anchored_row_flyout_viewport(
        anchor_global_rect=anchor,
        screen_available_geometry=screen,
        row_height=28,
        row_spacing=2,
        view_margin=7,
    )
    visible_row_count = 18
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(230, viewport.maximum_view_height + 28),
        row_width=170,
        row_height=28,
        row_count=visible_row_count,
        active_row_index_from_top=viewport.active_row_slot_from_top,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        screen_available_geometry=screen.adjusted(0, -8, 0, 20),
    )

    assert placement.align_selected_row_to_anchor is True
    assert (
        _row_rect_with_width(
            placement.position,
            active_row_index_from_top=viewport.active_row_slot_from_top,
            row_width=170,
        )
        == anchor
    )


def test_anchored_row_flyout_placement_overlaps_active_row_when_room_allows() -> None:
    """Normal placement should put the active row slot over the anchor slot."""

    anchor = QRect(100, 300, 34, 28)
    active_row_index_from_top = 2
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=active_row_index_from_top,
        screen_available_geometry=QRect(0, 0, 800, 700),
    )

    assert placement.placement_mode == "active_row"
    assert placement.align_selected_row_to_anchor is True
    assert (
        _row_rect(
            placement.position,
            active_row_index_from_top=active_row_index_from_top,
        )
        == anchor
    )


def test_anchored_row_flyout_placement_overlaps_late_active_row() -> None:
    """Normal placement should work for active rows near the bottom."""

    anchor = QRect(100, 300, 34, 28)
    active_row_index_from_top = 3
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=active_row_index_from_top,
        screen_available_geometry=QRect(0, 0, 800, 700),
    )

    assert placement.placement_mode == "active_row"
    assert (
        _row_rect(
            placement.position,
            active_row_index_from_top=active_row_index_from_top,
        )
        == anchor
    )


def test_anchored_row_flyout_placement_overlaps_bottom_row_when_starved() -> None:
    """Starved placement should put the bottom row slot over the anchor slot."""

    anchor = QRect(100, 560, 34, 28)
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=2,
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.placement_mode == "bottom_row"
    assert placement.align_selected_row_to_anchor is False
    assert _row_rect(placement.position, active_row_index_from_top=3) == anchor


def test_anchored_row_flyout_placement_prefers_active_row_until_it_clips() -> None:
    """Starved mode should activate only when active-row overlap would not fit."""

    anchor = QRect(100, 450, 34, 28)
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=2,
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.placement_mode == "active_row"
    assert _row_rect(placement.position, active_row_index_from_top=2) == anchor


def test_anchored_row_flyout_placement_preserves_overlap_near_horizontal_edges() -> (
    None
):
    """Horizontal overflow should not prevent row-slot overlap."""

    anchor = QRect(790, 200, 34, 28)
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=2,
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert _row_rect(placement.position, active_row_index_from_top=2) == anchor


def test_anchored_row_flyout_placement_handles_empty_rows() -> None:
    """Invalid row counts should return a deterministic fallback placement."""

    placement = anchored_row_flyout_placement(
        anchor_global_rect=QRect(100, 100, 34, 28),
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_count=0,
        active_row_index_from_top=0,
        screen_available_geometry=QRect(0, 0, 800, 600),
    )

    assert placement.opens_down is True
    assert placement.align_selected_row_to_anchor is False


def test_anchored_row_flyout_placement_clamps_invalid_active_row_index() -> None:
    """Invalid active row indexes should clamp to the nearest visible row."""

    anchor = QRect(100, 300, 34, 28)
    placement = anchored_row_flyout_placement(
        anchor_global_rect=anchor,
        popup_size=QSize(64, 146),
        row_width=34,
        row_height=28,
        row_left_offset=22,
        row_top_offset=15,
        row_spacing=2,
        row_count=4,
        active_row_index_from_top=99,
        screen_available_geometry=QRect(0, 0, 800, 700),
    )

    assert placement.placement_mode == "active_row"
    assert _row_rect(placement.position, active_row_index_from_top=3) == anchor


def _row_rect(
    position: QPoint,
    *,
    active_row_index_from_top: int,
) -> QRect:
    """Return a row slot rect for the standard picker geometry."""

    return _row_rect_with_width(
        position,
        active_row_index_from_top=active_row_index_from_top,
        row_width=34,
    )


def _row_rect_with_width(
    position: QPoint,
    *,
    active_row_index_from_top: int,
    row_width: int,
) -> QRect:
    """Return a row slot rect for one explicit picker width."""

    row_height = 28
    row_spacing = 2
    row_left_offset = 22
    row_top_offset = 15
    active_row_top_offset = row_top_offset + active_row_index_from_top * (
        row_height + row_spacing
    )
    return QRect(
        position.x() + row_left_offset,
        position.y() + active_row_top_offset,
        row_width,
        row_height,
    )
