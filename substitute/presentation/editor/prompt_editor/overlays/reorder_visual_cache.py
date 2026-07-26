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

"""Describe complete reorder chip visuals used by animated displacement."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from ..projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)
from .chip_visuals import PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptReorderChipVisualSnapshot:
    """Bind chip chrome geometry to projection-owned paint fragments."""

    segment_index: int
    visual: PromptChipVisual
    projection_snapshot: PromptReorderProjectionPaintSnapshot

    @property
    def key(self) -> PromptReorderProjectionSnapshotKey:
        """Return the projection identity proving this snapshot is fresh."""

        return self.projection_snapshot.key

    @property
    def source_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return source ranges represented by this complete visual snapshot."""

        return self.projection_snapshot.source_ranges


def translated_snapshot_offset(
    *,
    painted_rect: QRectF,
    snapshot: PromptReorderChipVisualSnapshot,
) -> tuple[float, float]:
    """Return the translation from snapshot chrome to the current painted rect."""

    source_rect = QRectF(snapshot.visual.hotspot_rect)
    return (
        painted_rect.left() - source_rect.left(),
        painted_rect.top() - source_rect.top(),
    )


__all__ = [
    "PromptReorderChipVisualSnapshot",
    "translated_snapshot_offset",
]
