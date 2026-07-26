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

"""Draw prepared regional prompt chrome without cache or layout discovery."""

from __future__ import annotations

from PySide6.QtGui import QPainter

from .region_chrome_state import PromptRegionChromeSnapshot


class PromptRegionChromeRenderer:
    """Draw immutable separator and rail geometry in one allocation-free call."""

    def draw(
        self,
        painter: QPainter,
        snapshot: PromptRegionChromeSnapshot | None,
        *,
        scroll_offset: float,
    ) -> None:
        """Draw prepared regional chrome without querying its cache owner."""

        if snapshot is None or not snapshot.paint_lines:
            return
        painter.save()
        try:
            painter.translate(0.0, -scroll_offset)
            painter.setPen(snapshot.pen)
            painter.drawLines(snapshot.paint_lines)
        finally:
            painter.restore()


__all__ = ["PromptRegionChromeRenderer"]
