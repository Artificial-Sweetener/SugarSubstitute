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

"""Own reorder pointer-region positioning and visual interaction state."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    reorder_drag_color_context,
    reorder_drag_started_at,
)
from ..projection.reorder_state import (
    ReorderPointerRegionGeometryKey,
    reorder_pointer_region_geometry_key,
)
from .chip_visuals import PromptChipVisual
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_interaction_visual import (
    prompt_reorder_chip_interaction_states,
)
from .reorder_pointer_regions import PromptReorderPointerRegions
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_style import PromptReorderVisualStyle


class PromptReorderPointerRegionVisualOwner:
    """Position logical hotspots and publish their interaction chrome state."""

    def __init__(
        self,
        *,
        regions: PromptReorderPointerRegions,
        gesture: PromptReorderGestureController,
        visual_mode: PromptReorderVisualModeOwner,
        live_visuals: Callable[[], Mapping[int, PromptChipVisual]],
        preview_visuals: Callable[[], Mapping[int, PromptChipVisual]],
        raise_drag_proxy: Callable[[], None],
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        visual_style: PromptReorderVisualStyle,
    ) -> None:
        """Store focused visual publications and the stable logical region owner."""

        self._regions = regions
        self._gesture = gesture
        self._visual_mode = visual_mode
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._raise_drag_proxy = raise_drag_proxy
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._visual_style = visual_style
        self._last_geometry_key: ReorderPointerRegionGeometryKey | None = None

    def set_visual_style(self, visual_style: PromptReorderVisualStyle) -> None:
        """Replace the theme-derived style used by the next state sync."""

        self._visual_style = visual_style

    def invalidate_geometry(self) -> None:
        """Force the next geometry request to rematerialize logical regions."""

        self._last_geometry_key = None

    def sync_geometry_if_needed(self, *, reason: str) -> bool:
        """Sync regions only when their complete prepared identity changed."""

        next_key = self._geometry_key()
        if next_key == self._last_geometry_key:
            self._diagnostics.log_event(
                "pointer_region_geometry.update_skipped_unchanged",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                reason=reason,
                chip_count=len(self._regions.regions_by_index),
            )
            return False
        self.sync_geometry()
        return True

    def sync_geometry(self) -> None:
        """Position exactly the regions represented by prepared visible visuals."""

        started_at = reorder_drag_started_at()
        live_visuals = self._live_visuals()
        preview_visuals = self._preview_visuals()
        gesture_state = self._gesture.state
        dragged_segment_index = gesture_state.dragged_segment_index
        interactive_indices = set(live_visuals) | set(preview_visuals)
        if dragged_segment_index is not None:
            interactive_indices.add(dragged_segment_index)
        self._regions.sync(interactive_indices)
        preview_active = self._visual_mode.preview_active()
        preview_positioned_count = 0
        live_positioned_count = 0
        hidden_count = 0
        for segment_index, region in self._regions.regions_by_index.items():
            preview_visual = preview_visuals.get(segment_index)
            if (
                preview_active
                and preview_visual is not None
                and segment_index != dragged_segment_index
            ):
                preview_rect = preview_visual.hotspot_rect
                if region.rect != preview_rect:
                    region.set_geometry(preview_rect)
                region.set_visible(True)
                preview_positioned_count += 1
                continue
            if segment_index == dragged_segment_index:
                continue

            live_visual = live_visuals.get(segment_index)
            if live_visual is None:
                region.set_visible(False)
                hidden_count += 1
                continue
            live_rect = live_visual.hotspot_rect
            if region.rect != live_rect:
                region.set_geometry(live_rect)
            region.set_visible(True)
            live_positioned_count += 1
        self._raise_drag_proxy()
        self.sync_interaction_state()
        self._last_geometry_key = self._geometry_key()
        self._diagnostics.log_timing(
            "pointer_region_geometry.update",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            chip_count=len(self._regions.regions_by_index),
            preview_positioned_count=preview_positioned_count,
            live_positioned_count=live_positioned_count,
            hidden_count=hidden_count,
            dragged_segment_index=dragged_segment_index,
        )

    def sync_interaction_state(self) -> None:
        """Apply active, pressed, hovered, and drag state to every hotspot."""

        gesture_state = self._gesture.state
        detailed_states: list[str] = []
        for chip_state in prompt_reorder_chip_interaction_states(
            tuple(self._regions.regions_by_index),
            visual_style=self._visual_style,
            dragged_segment_index=gesture_state.dragged_segment_index,
            hovered_segment_index=gesture_state.hovered_segment_index,
            active_segment_index=gesture_state.active_segment_index,
            pressed_segment_index=gesture_state.pressed_segment_index,
        ):
            region = self._regions.regions_by_index[chip_state.segment_index]
            region.set_visual_state(
                active=chip_state.active,
                dragging=chip_state.dragging,
                hovered=chip_state.hovered,
            )
            region.set_cursor_shape(chip_state.cursor_shape)
            if not (
                chip_state.active
                or chip_state.dragging
                or chip_state.hovered
                or chip_state.pressed
            ):
                continue
            fill_color = chip_state.style.fill_color
            border_color = chip_state.style.border_color
            detailed_states.append(
                (
                    f"{chip_state.segment_index}:active={chip_state.active}:"
                    f"dragging={chip_state.dragging}:"
                    f"hovered={chip_state.hovered}:"
                    f"pressed={chip_state.pressed}:"
                    f"fill_a={fill_color.alpha()}:border_a={border_color.alpha()}"
                )
            )
            if border_color.alpha() == 0:
                self._diagnostics.log_anomaly(
                    "anomaly.paint_style_transparent_border",
                    segment_index=chip_state.segment_index,
                    active=chip_state.active,
                    dragging=chip_state.dragging,
                    hovered=chip_state.hovered,
                    pressed=chip_state.pressed,
                    **reorder_drag_color_context(
                        border_color,
                        prefix="border",
                    ),
                )
        self._diagnostics.log_event(
            "chip_state.update",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            active_segment_index=gesture_state.active_segment_index,
            hovered_segment_index=gesture_state.hovered_segment_index,
            pressed_segment_index=gesture_state.pressed_segment_index,
            dragged_segment_index=gesture_state.dragged_segment_index,
            detailed_states=";".join(detailed_states),
        )

    def _geometry_key(self) -> ReorderPointerRegionGeometryKey:
        """Return the complete identity for current logical-region placement."""

        return reorder_pointer_region_geometry_key(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            preview_mode_active=self._visual_mode.preview_active(),
            preview_rects=tuple(
                (
                    segment_index,
                    visual.hotspot_rect.left(),
                    visual.hotspot_rect.top(),
                    visual.hotspot_rect.width(),
                    visual.hotspot_rect.height(),
                )
                for segment_index, visual in self._preview_visuals().items()
            ),
            live_rects=tuple(
                (
                    segment_index,
                    visual.hotspot_rect.left(),
                    visual.hotspot_rect.top(),
                    visual.hotspot_rect.width(),
                    visual.hotspot_rect.height(),
                )
                for segment_index, visual in self._live_visuals().items()
            ),
        )


__all__ = [
    "PromptReorderPointerRegionVisualOwner",
]
