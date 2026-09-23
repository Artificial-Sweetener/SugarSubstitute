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

"""Define stable top-right tile badge geometry shared by paint and hit testing."""

from __future__ import annotations

from PySide6.QtCore import QRect

_BADGE_SIZE = 28
_BADGE_INSET = 8


def media_wall_badge_rect(tile_rect: QRect) -> QRect:
    """Return the unobtrusive top-right badge target inside one tile."""

    return QRect(
        tile_rect.right() - _BADGE_INSET - _BADGE_SIZE + 1,
        tile_rect.top() + _BADGE_INSET,
        _BADGE_SIZE,
        _BADGE_SIZE,
    )


__all__ = ["media_wall_badge_rect"]
