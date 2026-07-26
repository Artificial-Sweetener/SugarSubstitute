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

"""Resolve one post-drop visual observation from immutable publications."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
)
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .chip_visuals import PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptReorderDropActualObservation:
    """Describe visible geometry observed after a committed drop is republished."""

    checkpoint: str
    segment_index: int
    actual_visual: PromptChipVisual | None
    actual_geometry: PromptReorderChipGeometry | None
    chip_rect: QRectF | None
    preview_mode_active: bool
    has_preview_snapshot: bool
    has_base_drag_snapshot: bool
    ordered_segment_indices: tuple[int, ...]
    gesture_id: int | None
    event_id: int | None

    @classmethod
    def from_publications(
        cls,
        *,
        checkpoint: str,
        segment_index: int,
        live_visuals: Mapping[int, PromptChipVisual],
        preview_visuals: Mapping[int, PromptChipVisual],
        live_chip_geometry: PromptReorderChipGeometrySnapshot | None,
        chip_rect: QRectF | None,
        preview_mode_active: bool,
        geometry: PromptReorderInteractionGeometryState,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderDropActualObservation:
        """Capture one actual observation from coherent visual publications."""

        preview_visual = (
            preview_visuals.get(segment_index) if preview_mode_active else None
        )
        actual_geometry = (
            None
            if live_chip_geometry is None
            else live_chip_geometry.geometries_by_chip_index.get(segment_index)
        )
        return cls(
            checkpoint=checkpoint,
            segment_index=segment_index,
            actual_visual=preview_visual or live_visuals.get(segment_index),
            actual_geometry=actual_geometry,
            chip_rect=chip_rect,
            preview_mode_active=preview_mode_active,
            has_preview_snapshot=geometry.preview_snapshot is not None,
            has_base_drag_snapshot=geometry.base_drag_snapshot is not None,
            ordered_segment_indices=geometry.ordered_segment_indices,
            gesture_id=gesture_id,
            event_id=event_id,
        )
