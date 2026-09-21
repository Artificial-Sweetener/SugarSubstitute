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

"""Expose the prompt editor's public reorder projection API."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView

from .projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .projection.reorder_geometry_cache_keys import ReorderGeometrySnapshot
from .projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)
from .projection.reorder_preview import PromptReorderPreviewState
from .projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)
from .projection.reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from .projection.surface import PromptProjectionSurface


class PromptEditorReorderFacade:
    """Adapt the stable editor host contract to focused reorder owners."""

    _surface: PromptProjectionSurface

    def set_reorder_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> None:
        """Replace the active reorder preview through projection ownership."""

        self._surface.reorder.set_preview_state(preview_state)

    def clear_reorder_preview_state(self) -> None:
        """Clear the active reorder preview through projection ownership."""

        self._surface.reorder.clear_preview_state()

    def reorder_preview_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments for one active preview source range."""

        return self._surface.reorder.preview_fragments(start=start, end=end)

    def reorder_live_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned live reorder chip geometry."""

        return self._surface.reorder.live_chip_geometry_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def reorder_live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Return provisional placements from the current live projection."""

        return self._surface.reorder.live_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
        )

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned preview reorder chip geometry."""

        return self._surface.reorder.preview_chip_geometry_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible chips."""

        return self._surface.reorder.live_chip_paint_snapshots(
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        chip_indices: frozenset[int] | None = None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned preview paint snapshots for visible chips."""

        return self._surface.reorder.preview_chip_paint_snapshots(
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            chip_indices=chip_indices,
        )

    def set_reorder_surface_visual_publication(
        self,
        publication: PromptReorderSurfaceVisualPublication,
    ) -> None:
        """Publish reorder chrome and suppression as one prepared frame."""

        self._surface.reorder.presentation.publish(publication)

    def reorder_preview_cursor_rect(self, position: int) -> QRectF:
        """Return the active preview caret rectangle for one source position."""

        return self._surface.reorder.preview_cursor_rect(position)

    def reorder_base_drag_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments for one stable drag-base source range."""

        return self._surface.reorder.base_drag_fragments(start=start, end=end)

    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned stable drag-base chip geometry."""

        return self._surface.reorder.base_drag_chip_geometry_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_base_drag_cursor_rect(self, position: int) -> QRectF:
        """Return the stable drag-base caret rectangle for one source position."""

        return self._surface.reorder.base_drag_cursor_rect(position)

    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Return projection-owned stable drag-base placement geometry."""

        return self._surface.reorder.base_drag_placement_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reset_reorder_geometry_cache_counters(self) -> None:
        """Reset reorder cache counters for a new drag gesture."""

        self._surface.reorder.reset_cache_counters()

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return reorder cache counters for gesture diagnostics."""

        return self._surface.reorder.cache_counters()

    def reorder_placement_at_rect(
        self,
        drag_rect: QRectF,
        *,
        snapshot: PromptReorderPlacementSnapshot,
        active_placement_id: PromptReorderPlacementId | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Return the projection-owned placement selected by one drag rectangle."""

        return self._surface.reorder.placement_at_rect(
            drag_rect,
            snapshot=snapshot,
            active_placement_id=active_placement_id,
        )


__all__ = ["PromptEditorReorderFacade"]
