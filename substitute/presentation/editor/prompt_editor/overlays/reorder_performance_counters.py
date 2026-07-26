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

"""Aggregate reorder work counters from their authoritative owners."""

from __future__ import annotations

from dataclasses import dataclass
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_landing_paint import PromptReorderLandingPaintOwner
from .reorder_overlay_ports import PromptReorderEditor
from .reorder_raster_publication import PromptReorderRasterPublicationOwner


@dataclass(frozen=True, slots=True)
class PromptReorderPerformanceCountersOwner:
    """Publish one merged diagnostic counter snapshot without duplicating state."""

    geometry: PromptReorderEditor
    interaction: PromptReorderInteractionMetricsOwner
    drag_proxy: PromptReorderDragProxyVisualOwner
    autoscroll: PromptReorderAutoscrollOwner
    animation: PromptReorderAnimationPresentationOwner
    raster: PromptReorderRasterPublicationOwner
    landing_preview: PromptReorderLandingPaintOwner

    def reset_for_gesture(self) -> None:
        """Reset lower structural counters at one gesture boundary."""

        self.geometry.reset_reorder_geometry_cache_counters()
        self.autoscroll.reset_counters()

    def owner_counters(self) -> dict[str, object]:
        """Return counters from visual, geometry, and scroll owners."""

        landing = self.landing_preview.counters
        return {
            **self.geometry.reorder_geometry_cache_counters(),
            **self.drag_proxy.counters(),
            **self.autoscroll.counters(),
            **self.animation.counters(),
            **self.raster.counters().as_dict(),
            "landing_paint_cache_hit_count": landing.paint_cache_hit_count,
            "landing_paint_cache_miss_count": landing.paint_cache_miss_count,
        }

    def snapshot(self) -> dict[str, object]:
        """Return all deterministic reorder performance counters."""

        return {
            **self.interaction.performance_counters(),
            **self.owner_counters(),
        }
