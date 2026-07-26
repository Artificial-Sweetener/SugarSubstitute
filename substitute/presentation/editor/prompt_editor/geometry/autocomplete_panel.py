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

"""Place the autocomplete panel without covering its active text line."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QWidget

_DEFAULT_PANEL_GAP = 6
_DEFAULT_PANEL_MARGIN = 4


def compute_autocomplete_panel_rect(
    host: QWidget,
    anchor_rect: QRect,
    panel_size: QSize,
    *,
    gap: int = _DEFAULT_PANEL_GAP,
    margin: int = _DEFAULT_PANEL_MARGIN,
) -> QRect:
    """Place the autocomplete panel inside its host near the caret."""

    panel_width = min(panel_size.width(), max(1, host.width() - (margin * 2)))
    left = max(
        margin,
        min(
            anchor_rect.left(),
            max(margin, host.width() - panel_width - margin),
        ),
    )
    top, panel_height = _vertical_geometry(
        host_height=host.height(),
        anchor_rect=anchor_rect,
        preferred_height=panel_size.height(),
        gap=gap,
        margin=margin,
    )
    return QRect(left, top, panel_width, panel_height)


def _vertical_geometry(
    *,
    host_height: int,
    anchor_rect: QRect,
    preferred_height: int,
    gap: int,
    margin: int,
) -> tuple[int, int]:
    """Return a side-capped top and height that reserve the active line."""

    usable_bottom = max(margin + 1, host_height - margin)
    anchor_top = anchor_rect.top()
    anchor_bottom = anchor_rect.top() + max(1, anchor_rect.height())
    below_top = anchor_bottom + gap
    above_bottom = anchor_top - gap
    available_below = max(0, usable_bottom - below_top)
    available_above = max(0, above_bottom - margin)
    target_height = max(1, preferred_height)

    if _should_place_below(
        available_below=available_below,
        available_above=available_above,
        target_height=target_height,
    ):
        if available_below > 0:
            return below_top, min(target_height, available_below)
    elif available_above > 0:
        height = min(target_height, available_above)
        return above_bottom - height, height

    height = min(target_height, max(1, usable_bottom - margin))
    top = max(margin, min(below_top, usable_bottom - height))
    return top, height


def _should_place_below(
    *,
    available_below: int,
    available_above: int,
    target_height: int,
) -> bool:
    """Return whether below placement has the best usable space."""

    if available_below >= target_height:
        return True
    if available_above >= target_height:
        return False
    return available_below >= available_above
