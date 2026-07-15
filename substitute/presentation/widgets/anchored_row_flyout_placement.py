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

"""Compute anchor-aligned placement for row-based flyout pickers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QPoint, QRect, QSize

AnchoredRowFlyoutPlacementMode = Literal["active_row", "bottom_row"]


@dataclass(frozen=True, slots=True)
class AnchoredRowFlyoutPlacement:
    """Describe popup placement for a row flyout anchored to a control."""

    position: QPoint
    opens_down: bool
    align_selected_row_to_anchor: bool
    placement_mode: AnchoredRowFlyoutPlacementMode


def anchored_row_flyout_placement(
    *,
    anchor_global_rect: QRect,
    popup_size: QSize,
    row_width: int,
    row_height: int,
    row_count: int,
    active_row_index_from_top: int,
    row_left_offset: int = 0,
    row_top_offset: int = 0,
    row_spacing: int = 0,
    screen_available_geometry: QRect,
) -> AnchoredRowFlyoutPlacement:
    """Return popup top-left that overlaps the active row slot with the anchor."""

    if row_count <= 0 or row_height <= 0:
        return AnchoredRowFlyoutPlacement(
            position=anchor_global_rect.bottomLeft(),
            opens_down=True,
            align_selected_row_to_anchor=False,
            placement_mode="active_row",
        )

    clamped_active_row = _clamp(
        active_row_index_from_top,
        0,
        row_count - 1,
    )
    active_row_top_offset = row_top_offset + clamped_active_row * (
        row_height + row_spacing
    )
    active_position = QPoint(
        anchor_global_rect.left() - row_left_offset,
        anchor_global_rect.top() - active_row_top_offset,
    )
    if _fits_vertically(active_position, popup_size, screen_available_geometry):
        return AnchoredRowFlyoutPlacement(
            position=active_position,
            opens_down=active_position.y() <= anchor_global_rect.top(),
            align_selected_row_to_anchor=True,
            placement_mode="active_row",
        )

    bottom_row_top_offset = row_top_offset + (row_count - 1) * (
        row_height + row_spacing
    )
    bottom_position = QPoint(
        anchor_global_rect.left() - row_left_offset,
        anchor_global_rect.top() - bottom_row_top_offset,
    )

    return AnchoredRowFlyoutPlacement(
        position=bottom_position,
        opens_down=bottom_position.y() <= anchor_global_rect.top(),
        align_selected_row_to_anchor=False,
        placement_mode="bottom_row",
    )


def _fits_vertically(
    position: QPoint,
    popup_size: QSize,
    available_geometry: QRect,
) -> bool:
    """Return whether popup fits vertically at position."""

    popup_bottom = position.y() + popup_size.height() - 1
    return position.y() >= available_geometry.top() and (
        popup_bottom <= available_geometry.bottom()
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    """Return value clamped between inclusive bounds."""

    if maximum < minimum:
        return minimum
    return max(minimum, min(value, maximum))


__all__ = [
    "AnchoredRowFlyoutPlacement",
    "AnchoredRowFlyoutPlacementMode",
    "anchored_row_flyout_placement",
]
