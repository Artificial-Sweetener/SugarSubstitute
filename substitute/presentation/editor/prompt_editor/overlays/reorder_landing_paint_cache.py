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

"""Cache one exact reorder landing paint publication by strong input identity."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from ..projection.reorder_placement_geometry import PromptReorderPlacementGeometry
from .reorder_landing_models import (
    PromptReorderHeldShadowGeometry,
    PromptReorderLandingShadowRequest,
)
from .reorder_render_state import PromptReorderLandingPreviewPaintState
from .reorder_visual_style import PromptReorderVisualStyle


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowPaintResult:
    """Return prepared landing paint state and any placement state update."""

    paint_state: PromptReorderLandingPreviewPaintState | None
    active_placement: PromptReorderPlacementGeometry | None


@dataclass(frozen=True, slots=True, eq=False)
class PromptReorderLandingPaintKey:
    """Retain exact object sources plus bounded value geometry identity."""

    visual_style: PromptReorderVisualStyle
    dragged_segment: object | None
    target_visual: object | None
    value_identity: tuple[object, ...]

    def matches(self, other: PromptReorderLandingPaintKey) -> bool:
        """Compare strong sources by identity and bounded values structurally."""

        return (
            self.visual_style is other.visual_style
            and self.dragged_segment is other.dragged_segment
            and self.target_visual is other.target_visual
            and self.value_identity == other.value_identity
        )


@dataclass(frozen=True, slots=True)
class PromptReorderLandingPaintCacheMetrics:
    """Count exact landing paint publication hits and misses."""

    hit_count: int = 0
    miss_count: int = 0


@dataclass(frozen=True, slots=True)
class _PromptReorderLandingPaintPublication:
    """Retain one exact landing paint key and its immutable result."""

    key: PromptReorderLandingPaintKey
    result: PromptReorderLandingShadowPaintResult


class PromptReorderLandingPaintCache:
    """Own exact landing paint reuse without integer object identities."""

    def __init__(self) -> None:
        """Initialize an empty single-frame publication cache."""

        self._publication: _PromptReorderLandingPaintPublication | None = None
        self._hit_count = 0
        self._miss_count = 0

    @property
    def metrics(self) -> PromptReorderLandingPaintCacheMetrics:
        """Return immutable cache diagnostics."""

        return PromptReorderLandingPaintCacheMetrics(
            hit_count=self._hit_count,
            miss_count=self._miss_count,
        )

    def lookup(
        self,
        key: PromptReorderLandingPaintKey,
    ) -> PromptReorderLandingShadowPaintResult | None:
        """Return the exact cached result or record one miss."""

        publication = self._publication
        if publication is not None and publication.key.matches(key):
            self._hit_count += 1
            return publication.result
        self._miss_count += 1
        return None

    def store(
        self,
        key: PromptReorderLandingPaintKey,
        result: PromptReorderLandingShadowPaintResult,
    ) -> None:
        """Replace the cache with one complete landing paint publication."""

        self._publication = _PromptReorderLandingPaintPublication(
            key=key,
            result=result,
        )

    def clear(self) -> None:
        """Discard the cached publication while retaining diagnostics."""

        self._publication = None

    def reset_metrics(self) -> None:
        """Reset cache diagnostics without changing publication state."""

        self._hit_count = 0
        self._miss_count = 0


def prompt_reorder_landing_paint_key(
    request: PromptReorderLandingShadowRequest,
    *,
    visual_style: PromptReorderVisualStyle,
    held_shadow_geometry: PromptReorderHeldShadowGeometry | None,
    initial_landing_shadow_ready: bool,
    initial_landing_shadow_sync_used: bool,
) -> PromptReorderLandingPaintKey:
    """Build an exact reusable landing paint identity from prepared inputs."""

    return PromptReorderLandingPaintKey(
        visual_style=visual_style,
        dragged_segment=request.dragged_segment,
        target_visual=request.target_visual,
        value_identity=(
            request.gesture_id,
            request.event_id,
            request.dragged_segment_index,
            request.active_target,
            _placement_key(request.active_placement),
            _rect_key(request.content_rect),
            _rect_key(request.overlay_rect),
            request.preview_layout_active,
            request.preview_snapshot_available,
            request.preview_visual_count,
            _chip_geometry_key(request.landing_geometry),
            request.preview_geometry_target_identity,
            request.expected_preview_target_identity,
            request.preview_target_identity_matches,
            _held_shadow_key(held_shadow_geometry),
            initial_landing_shadow_ready,
            initial_landing_shadow_sync_used,
        ),
    )


def _chip_geometry_key(
    geometry: PromptReorderChipGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for landing outline geometry."""

    if geometry is None:
        return None
    return (
        geometry.geometry_id,
        geometry.chip_index,
        geometry.source_start,
        geometry.source_end,
        geometry.rendered_start,
        geometry.rendered_end,
        tuple(
            (
                line.visual_line_index,
                _rect_key(line.line_rect),
                _rect_key(line.content_rect),
                _point_key(line.leading_anchor),
                _point_key(line.trailing_anchor),
            )
            for line in geometry.visual_lines
        ),
        _rect_key(geometry.hotspot_rect),
        _rect_key(geometry.outline_bounds),
        _point_key(geometry.slot_before),
        _point_key(geometry.slot_after),
        geometry.marker_height,
    )


def _placement_key(
    placement: PromptReorderPlacementGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for placement geometry used by landing paint."""

    if placement is None:
        return None
    return (
        placement.placement_id,
        placement.target,
        _rect_key(placement.hit_rect),
        _rect_key(placement.insertion_anchor_rect),
        _rect_key(placement.visual_line_rect),
        _optional_rect_key(placement.expected_landing_rect),
        placement.source_before,
        placement.source_after,
        placement.adjacent_chip_indices,
        placement.expected_landing_chip_index,
        _optional_rect_key(placement.expected_landing_bounds),
    )


def _held_shadow_key(
    geometry: PromptReorderHeldShadowGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for held-shadow fallback inputs."""

    if geometry is None:
        return None
    return (
        geometry.chip_index,
        tuple(_rect_key(rect) for rect in geometry.normalized_bubble_rects),
        _rect_key(geometry.chrome_bounds),
        _rect_key(geometry.hotspot_bounds),
        geometry.source,
        geometry.low_confidence,
    )


def _optional_rect_key(rect: QRectF | None) -> tuple[float, float, float, float] | None:
    """Return a value identity for an optional Qt rectangle."""

    if rect is None:
        return None
    return _rect_key(rect)


def _rect_key(rect: QRectF | QRect) -> tuple[float, float, float, float]:
    """Return a value identity for a Qt rectangle."""

    return (rect.x(), rect.y(), rect.width(), rect.height())


def _point_key(point: QPointF) -> tuple[float, float]:
    """Return a value identity for a Qt point."""

    return (point.x(), point.y())


__all__ = [
    "PromptReorderLandingPaintCache",
    "PromptReorderLandingPaintCacheMetrics",
    "PromptReorderLandingPaintKey",
    "PromptReorderLandingShadowPaintResult",
    "prompt_reorder_landing_paint_key",
]
