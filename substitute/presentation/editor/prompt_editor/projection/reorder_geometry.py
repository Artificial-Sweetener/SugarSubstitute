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

"""Own projection-derived reorder chip and placement geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import PromptReorderLayoutView

from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_placement_geometry import PromptReorderPlacementSnapshot

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


@dataclass(frozen=True, slots=True)
class PromptProjectionReorderGeometry:
    """Route reorder geometry requests through prepared projection layout state."""

    layout: PromptProjectionLayout

    def reorder_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return one projection-owned geometry object per semantic reorder chip."""

        return self.layout._reorder_chip_geometry_snapshot_from_geometry(  # noqa: SLF001
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def reorder_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderPlacementSnapshot:
        """Return placement geometry derived from projection-owned chip geometry."""

        return self.layout._reorder_placement_snapshot_from_geometry(  # noqa: SLF001
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def source_range_row_rects(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return full-width visible row rects intersecting one source range."""

        return self.layout._source_range_row_rects_from_reorder_geometry(  # noqa: SLF001
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )


__all__ = ["PromptProjectionReorderGeometry"]
