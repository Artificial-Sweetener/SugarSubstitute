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

"""Own projection paint snapshots for animated reorder preview chips."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
)
from .chip_visuals import PromptChipVisual
from .reorder_visual_cache import PromptReorderChipVisualSnapshot

_EMPTY_SNAPSHOTS: Mapping[int, PromptReorderChipVisualSnapshot] = MappingProxyType({})


type PromptReorderPreviewProjectionSnapshotBuilder = Callable[
    ..., dict[int, PromptReorderProjectionPaintSnapshot]
]


class PromptReorderPreviewPaintSnapshotOwner:
    """Publish complete preview visual snapshots for the requested moving chips."""

    def __init__(
        self,
        *,
        build_projection_snapshots: PromptReorderPreviewProjectionSnapshotBuilder,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        preview_visuals: Callable[[], Mapping[int, PromptChipVisual]],
    ) -> None:
        """Store stable collaborators and initialize an empty publication."""

        self._build_projection_snapshots = build_projection_snapshots
        self._geometry_state = geometry_state
        self._preview_visuals = preview_visuals
        self._snapshots_by_index = _EMPTY_SNAPSHOTS

    @property
    def snapshots_by_index(self) -> Mapping[int, PromptReorderChipVisualSnapshot]:
        """Return the current immutable preview paint-snapshot publication."""

        return self._snapshots_by_index

    def clear(self) -> None:
        """Discard every preview paint snapshot at a visual lifecycle boundary."""

        self._snapshots_by_index = _EMPTY_SNAPSHOTS

    def prepare(self, chip_indices: frozenset[int]) -> None:
        """Build snapshots only for preview chips that can move or be held."""

        geometry_state = self._geometry_state()
        chip_snapshot: PromptReorderChipGeometrySnapshot | None = (
            geometry_state.preview_chip_geometry_snapshot
        )
        preview_snapshot = geometry_state.preview_snapshot
        if chip_snapshot is None or preview_snapshot is None or not chip_indices:
            self.clear()
            return
        projection_snapshots = self._build_projection_snapshots(
            chip_geometry_snapshot=chip_snapshot,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            chip_indices=chip_indices,
        )
        visuals = self._preview_visuals()
        self._snapshots_by_index = MappingProxyType(
            {
                segment_index: PromptReorderChipVisualSnapshot(
                    segment_index=segment_index,
                    visual=visuals[segment_index],
                    projection_snapshot=projection_snapshot,
                )
                for segment_index, projection_snapshot in projection_snapshots.items()
                if segment_index in visuals
            }
        )


__all__ = [
    "PromptReorderPreviewPaintSnapshotOwner",
    "PromptReorderPreviewProjectionSnapshotBuilder",
]
