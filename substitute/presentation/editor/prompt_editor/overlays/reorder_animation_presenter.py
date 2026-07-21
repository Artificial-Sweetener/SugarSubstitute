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

"""Execute prompt reorder chip animations from projection-owned plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QObject,
    QRectF,
    QVariantAnimation,
)

from substitute.presentation.motion import resolve_motion_duration

from ..projection.reorder_animation import (
    PromptReorderAnimationPlan,
    PromptReorderAnimationTarget,
)


_REORDER_DISPLACEMENT_DURATION_MS = 180
_REORDER_DISPLACEMENT_EASING = QEasingCurve.Type.OutQuad


@dataclass(frozen=True, slots=True)
class _AnimatedChipTarget:
    """Bind one semantic chip to planner-provided displacement rects."""

    segment_index: int
    start_rect: QRectF
    target_rect: QRectF


class PromptReorderAnimationPresenter(QObject):
    """Present visible chip displacement according to prepared animation plans."""

    def __init__(
        self,
        *,
        parent: QObject,
        duration_ms: int = _REORDER_DISPLACEMENT_DURATION_MS,
        frame_callback: Callable[[], None] | None = None,
    ) -> None:
        """Initialize animation state without owning geometry planning.

        The overlay paints chip chrome through a passive view while transparent
        logical pointer regions receive input independently. The presenter owns
        only transient paint-rect overrides for visible chrome.
        """

        super().__init__(parent)
        self._duration_ms = duration_ms
        self._frame_callback = frame_callback
        self._latest_generation = -1
        self._active_generation: int | None = None
        self._active_animation: QVariantAnimation | None = None
        self._active_targets: tuple[_AnimatedChipTarget, ...] = ()
        self._settle_targets_by_segment: dict[int, QRectF] = {}
        self._paint_rects_by_segment: dict[int, QRectF] = {}
        self._counters: dict[str, int] = {
            "animation_plan_applied_count": 0,
            "animation_started_count": 0,
            "animation_finished_count": 0,
            "animation_cancelled_count": 0,
            "animation_settled_count": 0,
            "animation_immediate_target_count": 0,
            "animation_skipped_target_count": 0,
            "animation_stale_generation_ignored_count": 0,
            "animation_retargeted_count": 0,
        }

    def apply_plan(self, plan: PromptReorderAnimationPlan) -> None:
        """Run or immediately apply one prepared reorder animation plan."""

        if plan.stale or plan.generation < self._latest_generation:
            self._counters["animation_stale_generation_ignored_count"] += 1
            return

        self._replace_active_plan(reason="generation_replaced")
        self._latest_generation = plan.generation
        self._active_generation = plan.generation
        self._settle_targets_by_segment = {}
        self._paint_rects_by_segment = {}
        self._counters["animation_plan_applied_count"] += 1

        self._apply_immediate_targets(
            plan.immediate_targets,
            dragged_segment_index=plan.dragged_segment_index,
        )
        animated_targets = self._animated_targets(
            plan.changed_targets,
            dragged_segment_index=plan.dragged_segment_index,
        )
        if not animated_targets:
            self._active_generation = None
            self._notify_frame_changed()
            return

        duration_ms = resolve_motion_duration(self._duration_ms)
        if duration_ms == 0:
            self.settle(reason="reduced_motion")
            return

        active_targets: list[_AnimatedChipTarget] = []
        for target, start_rect, target_rect in animated_targets:
            start_paint_rect = QRectF(target.start_rect)
            target_paint_rect = QRectF(target.target_rect)
            animated_target = _AnimatedChipTarget(
                segment_index=target.segment_index,
                start_rect=start_paint_rect,
                target_rect=target_paint_rect,
            )
            active_targets.append(animated_target)
            self._paint_rects_by_segment[target.segment_index] = QRectF(
                start_paint_rect
            )
            self._settle_targets_by_segment[target.segment_index] = QRectF(target_rect)

        self._active_targets = tuple(active_targets)
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(duration_ms)
        animation.setEasingCurve(_REORDER_DISPLACEMENT_EASING)
        animation.valueChanged.connect(self._handle_animation_progress_changed)
        animation.finished.connect(
            lambda generation=plan.generation, finished_animation=animation: (
                self._handle_animation_finished(generation, finished_animation)
            )
        )
        self._active_animation = animation
        animation.start()
        self._counters["animation_started_count"] += 1
        self._notify_frame_changed()

    def _replace_active_plan(self, *, reason: str) -> None:
        """Stop active timing state while preserving uninterrupted retarget paint."""

        animation = self._active_animation
        had_active_visuals = (
            animation is not None
            or bool(self._active_targets)
            or bool(self._settle_targets_by_segment)
            or bool(self._paint_rects_by_segment)
        )
        if animation is not None:
            self._active_animation = None
            self._active_generation = None
            if animation.state() != QAbstractAnimation.State.Stopped:
                animation.stop()
            animation.deleteLater()
        if had_active_visuals:
            self._counters["animation_retargeted_count"] += 1
        self._active_targets = ()
        self._settle_targets_by_segment = {}
        self._paint_rects_by_segment = {}

    def cancel(self, *, reason: str) -> None:
        """Stop active chip animation without applying final target geometry."""

        _ = reason
        animation = self._active_animation
        if animation is None:
            if self._settle_targets_by_segment or self._paint_rects_by_segment:
                self._settle_targets_by_segment = {}
                self._paint_rects_by_segment = {}
                self._active_targets = ()
                self._counters["animation_cancelled_count"] += 1
                self._notify_frame_changed()
            return
        self._active_animation = None
        self._active_generation = None
        if animation.state() != QAbstractAnimation.State.Stopped:
            animation.stop()
        animation.deleteLater()
        self._active_targets = ()
        self._settle_targets_by_segment = {}
        self._paint_rects_by_segment = {}
        self._counters["animation_cancelled_count"] += 1
        self._notify_frame_changed()

    def settle(self, *, reason: str) -> None:
        """Stop active chip animation and place widgets at final target rects."""

        _ = reason
        animation = self._active_animation
        if animation is None and not self._settle_targets_by_segment:
            return
        self._active_animation = None
        self._active_generation = None
        if animation is not None:
            if animation.state() != QAbstractAnimation.State.Stopped:
                animation.stop()
            animation.deleteLater()
        self._active_targets = ()
        self._settle_targets_by_segment = {}
        self._paint_rects_by_segment = {}
        self._counters["animation_settled_count"] += 1
        self._notify_frame_changed()

    def is_animating(self) -> bool:
        """Return whether a reorder chip animation group is currently running."""

        animation = self._active_animation
        return (
            animation is not None
            and animation.state() == QAbstractAnimation.State.Running
        )

    def counters(self) -> dict[str, int]:
        """Return deterministic counters for focused presenter and hot-path tests."""

        return dict(self._counters)

    def paint_rect_overrides(self) -> dict[int, QRectF]:
        """Return current visible-chip paint rects for active animation frames."""

        return {
            segment_index: QRectF(rect)
            for segment_index, rect in self._paint_rects_by_segment.items()
        }

    def _apply_immediate_targets(
        self,
        targets: tuple[PromptReorderAnimationTarget, ...],
        *,
        dragged_segment_index: int | None,
    ) -> None:
        """Record immediate semantic targets without transient paint overrides."""

        for target in targets:
            if target.segment_index == dragged_segment_index:
                self._counters["animation_skipped_target_count"] += 1
                continue
            if not target.target_visible:
                self._counters["animation_skipped_target_count"] += 1
                continue
            self._counters["animation_immediate_target_count"] += 1

    def _animated_targets(
        self,
        targets: tuple[PromptReorderAnimationTarget, ...],
        *,
        dragged_segment_index: int | None,
    ) -> tuple[tuple[PromptReorderAnimationTarget, QRectF, QRectF], ...]:
        """Return visible semantic targets that can be animated safely."""

        animated_targets: list[tuple[PromptReorderAnimationTarget, QRectF, QRectF]] = []
        for target in targets:
            if target.segment_index == dragged_segment_index:
                self._counters["animation_skipped_target_count"] += 1
                continue
            if not target.target_visible:
                self._counters["animation_skipped_target_count"] += 1
                continue
            animated_targets.append(
                (
                    target,
                    QRectF(target.start_rect),
                    QRectF(target.target_rect),
                )
            )
        return tuple(animated_targets)

    def _handle_animation_finished(
        self,
        generation: int,
        animation: QVariantAnimation,
    ) -> None:
        """Finalize state after the current generation reaches its target."""

        if (
            animation is not self._active_animation
            or generation != self._active_generation
        ):
            return
        self._apply_animation_progress(1.0)
        self._active_animation = None
        self._active_generation = None
        self._active_targets = ()
        self._settle_targets_by_segment = {}
        self._paint_rects_by_segment = {}
        animation.deleteLater()
        self._counters["animation_finished_count"] += 1
        self._notify_frame_changed()

    def _handle_animation_progress_changed(self, value: object) -> None:
        """Publish one coherent chip-rect snapshot for an animation progress tick."""

        progress = _progress_value(value)
        if progress is None:
            return
        self._apply_animation_progress(progress)
        self._notify_frame_changed()

    def _apply_animation_progress(self, progress: float) -> None:
        """Move all active chips to the same eased animation progress."""

        next_paint_rects: dict[int, QRectF] = {}
        for target in self._active_targets:
            rect = _interpolated_rect(target.start_rect, target.target_rect, progress)
            next_paint_rects[target.segment_index] = rect
        self._paint_rects_by_segment = next_paint_rects

    def _notify_frame_changed(self) -> None:
        """Notify the overlay that passive paint state needs republishing."""

        if self._frame_callback is not None:
            self._frame_callback()


def _progress_value(value: object) -> float | None:
    """Return a clamped animation progress value from Qt's variant payload."""

    if not isinstance(value, (int, float)):
        return None
    return min(1.0, max(0.0, float(value)))


def _interpolated_rect(
    start_rect: QRectF, target_rect: QRectF, progress: float
) -> QRectF:
    """Return one rect interpolated between planner-provided endpoints."""

    return QRectF(
        _interpolate(start_rect.left(), target_rect.left(), progress),
        _interpolate(start_rect.top(), target_rect.top(), progress),
        _interpolate(start_rect.width(), target_rect.width(), progress),
        _interpolate(start_rect.height(), target_rect.height(), progress),
    )


def _interpolate(start: float, target: float, progress: float) -> float:
    """Return one scalar value at the supplied animation progress."""

    return start + ((target - start) * progress)


__all__ = ["PromptReorderAnimationPresenter"]
