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

"""Coordinate reorder overlay displacement animation presentation."""

# mypy: disable-error-code="assignment,attr-defined,has-type,no-any-return,var-annotated"
# This mixin intentionally uses state initialized by SegmentReorderOverlay; the
# suppressions keep animation presentation glue on the shell without duplicating
# state.

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF

from ..projection.reorder_animation import PromptReorderAnimationPlan
from ..projection.reorder_state import PromptReorderAnimationGenerationState
from .reorder_displacement_intent import ReorderDisplacementIntent


class _OverlayShellAccess:
    """Provide dynamic access to state initialized by the concrete overlay shell."""

    def __getattr__(self, name: str) -> Any:
        """Defer shell-owned attribute lookup to the concrete overlay instance."""

        raise AttributeError(name)


class PromptReorderOverlayAnimationMixin(_OverlayShellAccess):
    """Own overlay animation presentation glue for prepared reorder geometry."""

    def animation_generation_state(self) -> PromptReorderAnimationGenerationState:
        """Return display-only animation generation state for focused tests."""

        return PromptReorderAnimationGenerationState(
            generation_id=self._animation_generation_id,
            geometry_generation_id=self._instrumentation_work_unit_id,
            active_target=self._gesture.state.active_drop_target,
            invalidated=False,
        )

    def apply_animation_plan(self, plan: PromptReorderAnimationPlan) -> None:
        """Animate chip widgets using projection-owned target geometry."""

        self._begin_animation_frame_batch()
        try:
            self._apply_held_chip_animation(plan)
            self._animation_presenter.apply_plan(plan, self._chips_by_index)
        finally:
            self._end_animation_frame_batch()

    def _begin_animation_frame_batch(self) -> None:
        """Defer presenter frame publication until all plan presenters are primed."""

        self._animation_frame_batch_depth += 1

    def _end_animation_frame_batch(self) -> None:
        """Publish one coherent animation frame after presenter setup completes."""

        self._animation_frame_batch_depth -= 1
        if self._animation_frame_batch_depth > 0:
            return
        if not self._animation_frame_sync_pending:
            return
        self._animation_frame_sync_pending = False
        self._sync_reorder_animation_frame()

    def _apply_held_chip_animation(self, plan: PromptReorderAnimationPlan) -> None:
        """Animate the keyboard-held chip outside neighbor displacement."""

        session_state = self._displacement_session.state
        if session_state.input_source != "keyboard":
            return
        held_segment_index = session_state.held_segment_index
        if held_segment_index is None:
            return
        start_rect = session_state.previous_visible_rects.get(held_segment_index)
        if start_rect is None or self._preview_chip_geometry_snapshot is None:
            return
        target_geometry = (
            self._preview_chip_geometry_snapshot.geometries_by_chip_index.get(
                held_segment_index
            )
        )
        if target_geometry is None:
            return
        target_rect = QRectF(target_geometry.hotspot_rect)
        if start_rect == target_rect:
            return
        self._held_chip_presenter.apply_target(
            generation=plan.generation,
            segment_index=held_segment_index,
            start_rect=start_rect,
            target_rect=target_rect,
        )

    def _sync_reorder_animation_frame(self) -> None:
        """Publish the presenter's latest paint rects to the passive view."""

        if self._animation_frame_batch_depth > 0:
            self._animation_frame_sync_pending = True
            return
        self._sync_reorder_view_state(reason="animation_frame")

    def _current_visible_chip_rects_for_animation(self) -> dict[int, QRectF]:
        """Return current painted chip rects only when animation is pending."""

        pending_target = self._displacement_session.pending_target
        if pending_target is None:
            return {}
        current_visuals = {
            segment_index: QRectF(rect)
            for (
                segment_index,
                rect,
            ) in self._displacement_session.state.previous_visible_rects.items()
            if segment_index != pending_target.held_segment_index
        }
        if current_visuals:
            return current_visuals
        current_visuals = {}
        animation_overrides = self._animation_presenter.paint_rect_overrides()
        for segment_index in self._chips_by_index:
            if segment_index == pending_target.held_segment_index:
                continue
            animation_rect = animation_overrides.get(segment_index)
            if animation_rect is not None:
                current_visuals[segment_index] = QRectF(animation_rect)
                continue
            visible_visual = self._visible_visual_for_segment(segment_index)
            if visible_visual is not None:
                current_visuals[segment_index] = QRectF(visible_visual.hotspot_rect)
        return current_visuals

    def _capture_displacement_start_rects(
        self,
        *,
        held_segment_index: int,
    ) -> dict[int, QRectF]:
        """Capture visible chip rects before a displacement intent mutates layout."""

        current_visuals: dict[int, QRectF] = {}
        animation_overrides = self._animation_presenter.paint_rect_overrides()
        for segment_index in self._chips_by_index:
            animation_rect = animation_overrides.get(segment_index)
            if animation_rect is not None:
                current_visuals[segment_index] = QRectF(animation_rect)
                continue
            visible_visual = self._visible_visual_for_segment(segment_index)
            if visible_visual is not None:
                current_visuals[segment_index] = QRectF(visible_visual.hotspot_rect)
        return current_visuals

    def _mark_reorder_displacement_target_changed(
        self,
        intent: ReorderDisplacementIntent,
    ) -> None:
        """Advance shared displacement state after an input-selected target changes."""

        self._animation_generation_id += 1
        if intent.target is None:
            self._displacement_session.record_target_change(
                intent,
                generation=self._animation_generation_id,
                previous_visible_rects={},
            )
            self._settle_chip_animations(reason=f"{intent.reason}_cleared")
            return
        self._displacement_session.record_target_change(
            intent,
            generation=self._animation_generation_id,
            previous_visible_rects=self._capture_displacement_start_rects(
                held_segment_index=intent.held_segment_index
            ),
        )

    def _build_reorder_animation_plan_if_ready(
        self,
        *,
        current_visuals: dict[int, QRectF],
    ) -> PromptReorderAnimationPlan | None:
        """Build one pending animation plan from settled preview chip geometry."""

        pending = self._displacement_session.consume_pending_target(
            active_target=self._displacement_session.state.active_target
        )
        if pending is None:
            return None
        generation = pending.generation
        reason = pending.reason
        proposed_layout_view = self._layout_for_painted_preview()
        if proposed_layout_view is None or self._preview_chip_geometry_snapshot is None:
            return None
        proposed_chip_geometry = {
            segment_index: QRectF(geometry.hotspot_rect)
            for (
                segment_index,
                geometry,
            ) in self._preview_chip_geometry_snapshot.geometries_by_chip_index.items()
        }
        self._instrumentation_animation_plan_build_count += 1
        return self._animation_planner.build_plan(
            generation=generation,
            current_visuals=current_visuals,
            proposed_layout_view=proposed_layout_view,
            proposed_chip_geometry=proposed_chip_geometry,
            ordered_segment_indices=tuple(self._ordered_segment_indices),
            dragged_segment_index=pending.held_segment_index,
            reason=reason or "reorder_target_changed",
        )


__all__ = ["PromptReorderOverlayAnimationMixin"]
