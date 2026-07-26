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

"""Define immutable inputs and results for reorder landing presentation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, QSizeF

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import PromptReorderDropTarget

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from ..projection.reorder_drop_targets import PromptReorderDropTargetVisual
from ..projection.reorder_placement_geometry import PromptReorderPlacementGeometry
from ..projection.reorder_state import PromptReorderPreviewTargetIdentity
from .chip_visuals import PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptReorderHeldShadowGeometry:
    """Describe immutable visible chip chrome captured for one drag."""

    chip_index: int
    normalized_bubble_rects: tuple[QRectF, ...]
    chrome_bounds: QRectF
    hotspot_bounds: QRectF
    source: str
    low_confidence: bool = False

    @property
    def hotspot_size(self) -> QSizeF:
        """Return diagnostic hotspot size retained for instrumentation."""

        return QSizeF(self.hotspot_bounds.size())

    @property
    def outline_size(self) -> QSizeF:
        """Return diagnostic visible chrome size retained for instrumentation."""

        return QSizeF(self.chrome_bounds.size())


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowCounters:
    """Expose landing-shadow instrumentation owned by focused collaborators."""

    initial_shadow_sync_count: int = 0
    initial_shadow_ready_count: int = 0
    stale_shadow_rejected_count: int = 0
    held_shadow_capture_count: int = 0
    held_shadow_missing_count: int = 0
    pending_shadow_fallback_count: int = 0
    pending_shadow_replaced_marker_count: int = 0
    anomaly_count: int = 0
    expected_diagnostic_count: int = 0
    paint_cache_hit_count: int = 0
    paint_cache_miss_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderHeldShadowCaptureInput:
    """Carry prepared held-chip geometry candidates for drag-start capture."""

    chip_index: int
    live_geometry: PromptReorderChipGeometry | None
    base_drag_geometry: PromptReorderChipGeometry | None
    live_visual: PromptChipVisual | None
    chip_size: QSize
    proxy_size: QSize
    proxy_size_hint: QSize
    gesture_id: int | None
    event_id: int | None


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowRequest:
    """Carry current visual reorder state needed to prepare landing feedback."""

    gesture_id: int | None
    event_id: int | None
    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    active_placement: PromptReorderPlacementGeometry | None
    dragged_segment: PromptReorderChipView | None
    content_rect: QRectF
    overlay_rect: QRectF
    preview_layout_active: bool
    preview_snapshot_available: bool
    preview_visual_count: int
    landing_geometry: PromptReorderChipGeometry | None
    target_visual: PromptReorderDropTargetVisual | None
    preview_geometry_target_identity: PromptReorderPreviewTargetIdentity | None
    expected_preview_target_identity: PromptReorderPreviewTargetIdentity | None
    preview_target_identity_matches: bool


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowGeometryResult:
    """Return landing geometry together with any placement state update."""

    geometry: PromptReorderChipGeometry | None
    active_placement: PromptReorderPlacementGeometry | None


@dataclass(frozen=True, slots=True)
class PromptReorderInitialShadowSyncResult:
    """Return the first-shadow sync decision and any placement state update."""

    should_flush: bool
    active_placement: PromptReorderPlacementGeometry | None
