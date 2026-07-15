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

"""Compute filtering and placement data for searchable combo popups."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QSize


@dataclass(frozen=True, slots=True)
class ComboPopupPlacement:
    """Describe the final popup origin and opening direction."""

    position: QPoint
    opens_down: bool
    maximum_width: int


@dataclass(frozen=True, slots=True)
class AttachedPopupPlacement:
    """Describe final geometry for a popup attached to an anchor control."""

    geometry: QRect
    opens_down: bool
    visible_row_count: int
    requires_scroll: bool


def filtered_combo_indexes(items: Sequence[str], query: str) -> list[int]:
    """Return item indexes matching a query with prefix matches first."""

    normalized_query = query.casefold().strip()
    if not normalized_query:
        return list(range(len(items)))

    prefix_matches: list[int] = []
    substring_matches: list[int] = []
    for index, item in enumerate(items):
        normalized_item = item.casefold()
        if normalized_item.startswith(normalized_query):
            prefix_matches.append(index)
        elif normalized_query in normalized_item:
            substring_matches.append(index)
    return [*prefix_matches, *substring_matches]


def attached_combo_popup_placement(
    *,
    field_global_rect: QRect,
    screen_available_geometry: QRect,
    preferred_popup_width: int,
    row_count: int,
    row_height: int,
    max_visible_rows: int,
    vertical_chrome_height: int,
    horizontal_chrome_width: int,
    minimum_visible_rows: int = 1,
) -> AttachedPopupPlacement:
    """Return final popup geometry that remains attached to one combo field."""

    safe_left = screen_available_geometry.left()
    safe_top = screen_available_geometry.top()
    safe_right = safe_left + max(1, screen_available_geometry.width())
    safe_bottom = safe_top + max(1, screen_available_geometry.height())
    safe_width = max(1, safe_right - safe_left)

    normalized_row_count = max(0, row_count)
    normalized_row_height = max(1, row_height)
    normalized_max_rows = max(1, max_visible_rows)
    normalized_minimum_rows = _clamp(
        max(1, minimum_visible_rows),
        1,
        normalized_max_rows,
    )
    preferred_visible_rows = min(normalized_row_count, normalized_max_rows)
    if preferred_visible_rows <= 0:
        preferred_visible_rows = normalized_minimum_rows

    chrome_height = max(0, vertical_chrome_height)
    chrome_width = max(0, horizontal_chrome_width)
    preferred_height = preferred_visible_rows * normalized_row_height + chrome_height

    field_left = field_global_rect.left()
    field_top = field_global_rect.top()
    field_bottom = field_top + max(0, field_global_rect.height())
    available_below = max(0, safe_bottom - field_bottom)
    available_above = max(0, field_top - safe_top)

    opens_down = _opens_down_for_available_height(
        available_below=available_below,
        available_above=available_above,
        preferred_height=preferred_height,
    )
    available_height = available_below if opens_down else available_above
    visible_rows = _visible_rows_for_available_height(
        available_height=available_height,
        preferred_visible_rows=preferred_visible_rows,
        row_height=normalized_row_height,
        chrome_height=chrome_height,
        minimum_visible_rows=normalized_minimum_rows,
    )
    target_height = visible_rows * normalized_row_height + chrome_height
    height = min(max(1, target_height), max(1, available_height))

    target_width = max(
        1,
        field_global_rect.width(),
        preferred_popup_width + chrome_width,
    )
    width = min(target_width, safe_width)
    left = _clamp(field_left, safe_left, safe_right - width)
    top = field_bottom if opens_down else field_top - height
    top = _clamp(top, safe_top, safe_bottom - height)

    return AttachedPopupPlacement(
        geometry=QRect(left, top, width, height),
        opens_down=opens_down,
        visible_row_count=visible_rows,
        requires_scroll=normalized_row_count > visible_rows,
    )


def left_anchored_combo_popup_placement(
    *,
    field_global_top_left: QPoint,
    field_size: QSize,
    popup_size: QSize,
    screen_available_geometry: QRect,
) -> ComboPopupPlacement:
    """Return a left-anchored popup position clamped inside one screen."""

    maximum_width = max(field_size.width(), screen_available_geometry.width())
    target_width = max(field_size.width(), popup_size.width())
    target_width = min(target_width, screen_available_geometry.width())

    x = field_global_top_left.x()
    right_overflow = x + target_width - screen_available_geometry.right()
    if right_overflow > 0:
        x -= right_overflow
    x = max(screen_available_geometry.left(), x)

    below_y = field_global_top_left.y() + field_size.height()
    above_y = field_global_top_left.y() - popup_size.height()
    space_below = screen_available_geometry.bottom() - below_y
    space_above = field_global_top_left.y() - screen_available_geometry.top()
    opens_down = space_below >= popup_size.height() or space_below >= space_above
    y = below_y if opens_down else max(screen_available_geometry.top(), above_y)

    return ComboPopupPlacement(
        position=QPoint(x, y),
        opens_down=opens_down,
        maximum_width=maximum_width,
    )


def _opens_down_for_available_height(
    *,
    available_below: int,
    available_above: int,
    preferred_height: int,
) -> bool:
    """Return whether a popup should open below its anchor."""

    if available_below >= preferred_height:
        return True
    if available_above >= preferred_height:
        return False
    return available_below >= available_above


def _visible_rows_for_available_height(
    *,
    available_height: int,
    preferred_visible_rows: int,
    row_height: int,
    chrome_height: int,
    minimum_visible_rows: int,
) -> int:
    """Return the row budget that fits in one attached side."""

    if available_height <= chrome_height:
        return minimum_visible_rows
    usable_height = max(0, available_height - chrome_height)
    fitting_rows = max(1, usable_height // row_height)
    return _clamp(
        fitting_rows,
        minimum_visible_rows,
        max(minimum_visible_rows, preferred_visible_rows),
    )


def _clamp(value: int, lower: int, upper: int) -> int:
    """Clamp a value into an inclusive integer range."""

    if upper < lower:
        return lower
    return max(lower, min(value, upper))


__all__ = [
    "AttachedPopupPlacement",
    "ComboPopupPlacement",
    "attached_combo_popup_placement",
    "filtered_combo_indexes",
    "left_anchored_combo_popup_placement",
]
