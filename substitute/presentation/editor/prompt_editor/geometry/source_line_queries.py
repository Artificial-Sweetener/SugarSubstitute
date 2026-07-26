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

"""Own cached logical source-line queries for immutable prompt geometry."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF

from .models import PromptProjectionSourceLineRect
from .source_lines import PromptSourceLineGeometry
from .state import PromptProjectionGeometryInput


@dataclass(slots=True)
class PromptSourceLineQueries:
    """Cache visible logical rows for one immutable layout input."""

    input: PromptProjectionGeometryInput
    _cache: PromptSourceLineGeometry = field(
        init=False,
        default_factory=PromptSourceLineGeometry,
    )

    def visible_rects(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return exact-cached visible newline-delimited source rows."""

        return self._cache.visible_rects(
            self.input.projection_document.source_text,
            self.input.layout_snapshot.lines,
            layout_identity=self.input.layout_identity,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=self.input.text_width,
        )


__all__ = ["PromptSourceLineQueries"]
