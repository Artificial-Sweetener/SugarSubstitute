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

"""Own prepared reorder animation planning and presentation state."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import QRect, QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
)

from ..projection.reorder_animation import (
    PromptReorderAnimationPlan,
    PromptReorderAnimationPlanner,
)
from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_state import PromptReorderAnimationGenerationState
from .chip_visuals import PromptChipVisual
from .reorder_animation_visual_owner import (
    PromptReorderAnimationVisualOwner,
    PromptReorderAnimationVisualPublication,
    PromptReorderHeldChipAnimationTarget,
)
from .reorder_displacement_intent import ReorderDisplacementIntent
from .reorder_displacement_session import ReorderDisplacementSession
from .reorder_pointer_regions import PromptReorderPointerRegion


class PromptReorderAnimationPresentationOwner:
    """Coordinate animation planning, retained intent, and painted geometry."""

    def __init__(
        self,
        *,
        parent: QWidget,
        frame_callback: Callable[[], None],
    ) -> None:
        """Create the visual timer owner and retained displacement session."""

        self._visual = PromptReorderAnimationVisualOwner(
            parent=parent,
            frame_callback=frame_callback,
        )
        self._planner = PromptReorderAnimationPlanner()
        self._displacement = ReorderDisplacementSession()
        self._generation_id = 0
        self._animated_pointer_region_indices: set[int] = set()
        self._plan_build_count = 0

    @property
    def publication(self) -> PromptReorderAnimationVisualPublication:
        """Return the current coherent animation visual publication."""

        return self._visual.publication

    def generation_state(
        self,
        *,
        geometry_generation_id: int,
        active_target: PromptReorderDropTarget | None,
    ) -> PromptReorderAnimationGenerationState:
        """Return display-only generation state for diagnostics and tests."""

        return PromptReorderAnimationGenerationState(
            generation_id=self._generation_id,
            geometry_generation_id=geometry_generation_id,
            active_target=active_target,
            invalidated=False,
        )

    def reset_counters(self) -> None:
        """Reset per-gesture animation planning counters."""

        self._plan_build_count = 0

    def counters(self) -> dict[str, int]:
        """Return authoritative animation planning and presenter counters."""

        return {
            **self._visual.counters(),
            "animation_plan_build_count": self._plan_build_count,
        }

    def bump_raster_generation(self) -> None:
        """Invalidate displacement intent after raster-dependent state clears."""

        self._displacement.bump_raster_generation()

    def clear_pointer_region_state(self) -> None:
        """Forget pointer regions previously moved by animation."""

        self._animated_pointer_region_indices.clear()

    def cancel(self, *, reason: str) -> None:
        """Cancel active animation while retaining reusable presenters."""

        self._visual.cancel(reason=reason)

    def settle(self, *, reason: str) -> None:
        """Settle active animation and clear paint overrides."""

        self._visual.settle(reason=reason)

    def set_duration_ms(self, duration_ms: int) -> None:
        """Set the visual animation duration for deterministic presentation."""

        self._visual.set_duration_ms(duration_ms)

    def apply_plan(
        self,
        plan: PromptReorderAnimationPlan,
        *,
        preview_geometry: PromptReorderChipGeometrySnapshot | None,
    ) -> None:
        """Apply one prepared plan with an optional keyboard-held target."""

        self._visual.apply_plan(
            plan,
            held_target=self._held_chip_target(
                plan,
                preview_geometry=preview_geometry,
            ),
        )

    def sync_pointer_regions(
        self,
        *,
        regions_by_index: Mapping[int, PromptReorderPointerRegion],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
    ) -> None:
        """Align pointer regions with the exact currently painted rectangles."""

        paint_rects = self.publication.paint_rects_by_index
        current_indices = set(paint_rects)
        for segment_index in self._animated_pointer_region_indices | current_indices:
            region = regions_by_index.get(segment_index)
            if region is None:
                continue
            painted_rect = paint_rects.get(segment_index)
            if painted_rect is None:
                visual = _visible_visual(
                    segment_index,
                    preview_active=preview_active,
                    live_visuals_by_index=live_visuals_by_index,
                    preview_visuals_by_index=preview_visuals_by_index,
                )
                if visual is None:
                    continue
                painted_rect = QRectF(visual.hotspot_rect)
            region.set_geometry(_pointer_region_rect(painted_rect))
        self._animated_pointer_region_indices = current_indices

    def current_visible_chip_rects(
        self,
        *,
        segment_indices: Sequence[int],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
    ) -> dict[int, QRectF]:
        """Return painted chip rectangles only while a target is pending."""

        pending_target = self._displacement.pending_target
        if pending_target is None:
            return {}
        current_visuals = {
            segment_index: QRectF(rect)
            for (
                segment_index,
                rect,
            ) in self._displacement.state.previous_visible_rects.items()
            if segment_index != pending_target.held_segment_index
        }
        if current_visuals:
            return current_visuals
        return self._visible_rects(
            segment_indices=segment_indices,
            preview_active=preview_active,
            live_visuals_by_index=live_visuals_by_index,
            preview_visuals_by_index=preview_visuals_by_index,
            held_segment_index=pending_target.held_segment_index,
        )

    def record_target_change(
        self,
        intent: ReorderDisplacementIntent,
        *,
        segment_indices: Sequence[int],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
    ) -> None:
        """Advance displacement state after an input-selected target changes."""

        self._generation_id += 1
        if intent.target is None:
            self._displacement.record_target_change(
                intent,
                generation=self._generation_id,
                previous_visible_rects={},
            )
            self.settle(reason=f"{intent.reason}_cleared")
            return
        self._displacement.record_target_change(
            intent,
            generation=self._generation_id,
            previous_visible_rects=self._visible_rects(
                segment_indices=segment_indices,
                preview_active=preview_active,
                live_visuals_by_index=live_visuals_by_index,
                preview_visuals_by_index=preview_visuals_by_index,
                held_segment_index=None,
            ),
        )

    def build_plan_if_ready(
        self,
        *,
        current_visuals: Mapping[int, QRectF],
        proposed_layout_view: PromptReorderLayoutView | None,
        preview_geometry: PromptReorderChipGeometrySnapshot | None,
        ordered_segment_indices: Sequence[int],
    ) -> PromptReorderAnimationPlan | None:
        """Build one pending plan from settled prepared preview geometry."""

        pending = self._displacement.consume_pending_target(
            active_target=self._displacement.state.active_target
        )
        if pending is None or proposed_layout_view is None or preview_geometry is None:
            return None
        proposed_chip_geometry = {
            segment_index: QRectF(geometry.hotspot_rect)
            for (
                segment_index,
                geometry,
            ) in preview_geometry.geometries_by_chip_index.items()
        }
        self._plan_build_count += 1
        return self._planner.build_plan(
            generation=pending.generation,
            current_visuals=current_visuals,
            proposed_layout_view=proposed_layout_view,
            proposed_chip_geometry=proposed_chip_geometry,
            ordered_segment_indices=tuple(ordered_segment_indices),
            dragged_segment_index=pending.held_segment_index,
            reason=pending.reason or "reorder_target_changed",
        )

    def _held_chip_target(
        self,
        plan: PromptReorderAnimationPlan,
        *,
        preview_geometry: PromptReorderChipGeometrySnapshot | None,
    ) -> PromptReorderHeldChipAnimationTarget | None:
        """Prepare keyboard-held motion independently from displacement targets."""

        session_state = self._displacement.state
        if session_state.input_source != "keyboard":
            return None
        held_segment_index = session_state.held_segment_index
        if held_segment_index is None:
            return None
        start_rect = session_state.previous_visible_rects.get(held_segment_index)
        if start_rect is None or preview_geometry is None:
            return None
        target_geometry = preview_geometry.geometries_by_chip_index.get(
            held_segment_index
        )
        if target_geometry is None:
            return None
        target_rect = QRectF(target_geometry.hotspot_rect)
        if start_rect == target_rect:
            return None
        return PromptReorderHeldChipAnimationTarget(
            generation=plan.generation,
            segment_index=held_segment_index,
            start_rect=start_rect,
            target_rect=target_rect,
        )

    def _visible_rects(
        self,
        *,
        segment_indices: Sequence[int],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
        held_segment_index: int | None,
    ) -> dict[int, QRectF]:
        """Capture current animation overrides or prepared visual rectangles."""

        current_visuals: dict[int, QRectF] = {}
        overrides = self.publication.displacement_rects_by_index
        for segment_index in segment_indices:
            if segment_index == held_segment_index:
                continue
            animation_rect = overrides.get(segment_index)
            if animation_rect is not None:
                current_visuals[segment_index] = QRectF(animation_rect)
                continue
            visible_visual = _visible_visual(
                segment_index,
                preview_active=preview_active,
                live_visuals_by_index=live_visuals_by_index,
                preview_visuals_by_index=preview_visuals_by_index,
            )
            if visible_visual is not None:
                current_visuals[segment_index] = QRectF(visible_visual.hotspot_rect)
        return current_visuals


def _pointer_region_rect(rect: QRectF) -> QRect:
    """Return integer hit bounds matching a painted animation rectangle."""

    return QRect(
        round(rect.left()),
        round(rect.top()),
        round(rect.width()),
        round(rect.height()),
    )


def _visible_visual(
    segment_index: int,
    *,
    preview_active: bool,
    live_visuals_by_index: Mapping[int, PromptChipVisual],
    preview_visuals_by_index: Mapping[int, PromptChipVisual],
) -> PromptChipVisual | None:
    """Return preview geometry when present, otherwise stable live geometry."""

    if preview_active:
        preview_visual = preview_visuals_by_index.get(segment_index)
        if preview_visual is not None:
            return preview_visual
    return live_visuals_by_index.get(segment_index)


__all__ = ["PromptReorderAnimationPresentationOwner"]
