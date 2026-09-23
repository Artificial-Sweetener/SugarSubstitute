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

"""Own live and preview reorder projection-paint snapshot caches."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from .frame_state import PromptProjectionEditorState
from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_paint_snapshot_builder import PromptReorderPaintSnapshotBuilder
from .reorder_paint_snapshot_reuse import reuse_reorder_paint_snapshots
from .reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)


class PromptReorderPaintSnapshotCacheOwner:
    """Build, reuse, invalidate, and instrument reorder paint snapshots."""

    def __init__(
        self,
        *,
        surface: QWidget,
        viewport: QWidget,
        editor_state: PromptProjectionEditorState,
        scroll_offset: Callable[[], float],
    ) -> None:
        """Retain the exact viewport and source identities that key snapshots."""
        self._surface = surface
        self._viewport = viewport
        self._editor_state = editor_state
        self._scroll_offset = scroll_offset
        self._preview_snapshots_by_index: dict[
            int, PromptReorderProjectionPaintSnapshot
        ] = {}
        self._live_snapshots_by_index: dict[
            int, PromptReorderProjectionPaintSnapshot
        ] = {}
        self._exact_reuse_count = 0
        self._scroll_reuse_count = 0
        self._rebuild_count = 0

    def clear_preview(self) -> None:
        """Discard preview snapshots when no preview publication remains active."""
        self._preview_snapshots_by_index = {}

    def reset_counters(self) -> None:
        """Reset cache instrumentation for one measured reorder gesture."""
        self._exact_reuse_count = 0
        self._scroll_reuse_count = 0
        self._rebuild_count = 0

    def counters(self) -> dict[str, int]:
        """Return current snapshot cache instrumentation counters."""
        return {
            "paint_snapshot_exact_reuse_count": self._exact_reuse_count,
            "paint_snapshot_scroll_reuse_count": self._scroll_reuse_count,
            "paint_snapshot_rebuild_count": self._rebuild_count,
        }

    def live_snapshots(
        self,
        *,
        projection_frame: PromptProjectionPreparedFrame,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return and retain live snapshots for the current viewport identity."""
        snapshots = self._build_snapshots(
            projection_frame=projection_frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            preview_generation=None,
            mode="live",
            previous_snapshots_by_chip_index=self._live_snapshots_by_index,
            chip_indices=None,
        )
        self._live_snapshots_by_index = snapshots
        return snapshots

    def preview_snapshots(
        self,
        *,
        projection_frame: PromptProjectionPreparedFrame,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        preview_generation: int | None,
        chip_indices: frozenset[int] | None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return and retain preview snapshots for the current preview identity."""
        snapshots = self._build_snapshots(
            projection_frame=projection_frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            preview_generation=preview_generation,
            mode="preview",
            previous_snapshots_by_chip_index=self._preview_snapshots_by_index,
            chip_indices=chip_indices,
        )
        self._preview_snapshots_by_index = snapshots
        return snapshots

    def _build_snapshots(
        self,
        *,
        projection_frame: PromptProjectionPreparedFrame,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        preview_generation: int | None,
        mode: str,
        previous_snapshots_by_chip_index: dict[
            int,
            PromptReorderProjectionPaintSnapshot,
        ],
        chip_indices: frozenset[int] | None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Build or reuse projection snapshots under one complete cache identity."""
        viewport_rect = QRectF(self._viewport.rect())
        scroll_offset = self._scroll_offset()
        keys_by_chip_index: dict[int, PromptReorderProjectionSnapshotKey] = {}
        source_ranges_by_chip_index: dict[int, tuple[tuple[int, int], ...]] = {}
        for (
            segment_index,
            geometry,
        ) in chip_geometry_snapshot.geometries_by_chip_index.items():
            if chip_indices is not None and segment_index not in chip_indices:
                continue
            source_ranges = chip_owned_ranges_by_index.get(segment_index, ())
            if not source_ranges:
                continue
            keys_by_chip_index[segment_index] = PromptReorderProjectionSnapshotKey(
                source_revision=self._editor_state.source.source_revision,
                viewport_rect=self._viewport.rect(),
                scroll_offset=int(round(scroll_offset)),
                font_key=self._surface.font().toString(),
                palette_key=int(self._surface.palette().cacheKey()),
                preview_generation=preview_generation,
                geometry_generation=geometry.geometry_id.visual_revision,
                segment_index=segment_index,
                mode=mode,
            )
            source_ranges_by_chip_index[segment_index] = source_ranges
        reuse = reuse_reorder_paint_snapshots(
            keys_by_chip_index,
            previous_snapshots_by_chip_index=previous_snapshots_by_chip_index,
        )
        rebuilt_snapshots = PromptReorderPaintSnapshotBuilder(
            projection_frame.paint_input
        ).build_many(
            keys_by_chip_index=reuse.rebuild_keys_by_chip_index,
            source_ranges_by_chip_index=source_ranges_by_chip_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        snapshots = dict(reuse.snapshots_by_chip_index)
        snapshots.update(rebuilt_snapshots)
        self._exact_reuse_count += reuse.exact_reuse_count
        self._scroll_reuse_count += reuse.scroll_reuse_count
        self._rebuild_count += len(rebuilt_snapshots)
        return snapshots


__all__ = ["PromptReorderPaintSnapshotCacheOwner"]
