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

"""Coordinate capture, timing, painting, cancellation, and cleanup for motion."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from time import perf_counter

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from .fluent_motion import resolve_motion_duration
from .models import (
    MotionFrameTarget,
    MotionPlan,
    MotionSpec,
    MotionTarget,
    motion_duration_ms,
    target_progress,
)
from .overlay import MotionOverlay
from .timeline import MotionTimeline

_MAX_CAPTURE_PIXELS = 16_000_000
_MAX_TARGETS = 24


@dataclass(slots=True)
class MotionTelemetry:
    """Record bounded preparation and paint evidence for one controller."""

    plans_started: int = 0
    plans_finished: int = 0
    plans_cancelled: int = 0
    plans_settled_immediately: int = 0
    preparation_ms: list[float] = field(default_factory=list)
    paint_ms: list[float] = field(default_factory=list)


class SurfaceMotionController(QObject):
    """Run one synchronized snapshot-overlay transition for a mounted surface."""

    def __init__(
        self,
        *,
        viewport_provider: Callable[[], QWidget | None],
        default_spec: MotionSpec | None = None,
    ) -> None:
        """Store the viewport provider and initialize idle transition state."""

        super().__init__()
        self._viewport_provider = viewport_provider
        self._default_spec = default_spec or MotionSpec()
        self._timeline = MotionTimeline(self)
        self._watched_viewport: QWidget | None = None
        self._overlay: MotionOverlay | None = None
        self._prepared_background: QPixmap | None = None
        self._prepared_generation: int | None = None
        self._prepared_reason: str | None = None
        self._latest_generation = 0
        self.telemetry = MotionTelemetry()

    def prepare(self, *, reason: str) -> int | None:
        """Capture the current viewport before an eligible structural commit."""

        self.cancel(reason="superseded_prepare")
        viewport = self._valid_viewport()
        if viewport is None or not self._capture_is_bounded(viewport):
            return None
        self._latest_generation += 1
        self._prepared_generation = self._latest_generation
        self._prepared_reason = reason
        self._prepared_background = viewport.grab()
        return self._prepared_generation

    def animate_widgets(
        self,
        *,
        generation: int,
        widgets: Sequence[tuple[str, QWidget]],
        spec: MotionSpec | None = None,
    ) -> bool:
        """Animate captured widgets above their already-committed final surface."""

        started_at = perf_counter()
        viewport = self._valid_viewport()
        background = self._prepared_background
        reason = self._prepared_reason
        if (
            viewport is None
            or background is None
            or generation != self._prepared_generation
            or reason is None
        ):
            self.cancel(reason="invalid_or_stale_generation")
            return False
        active_spec = spec or self._default_spec
        resolved_duration = resolve_motion_duration(active_spec.duration_ms)
        if resolved_duration == 0:
            self._clear_prepared()
            self.telemetry.plans_settled_immediately += 1
            return False
        active_spec = MotionSpec(
            duration_ms=resolved_duration,
            stagger_ms=active_spec.stagger_ms,
            translation_x=active_spec.translation_x,
            translation_y=active_spec.translation_y,
            start_opacity=active_spec.start_opacity,
            easing=active_spec.easing,
        )
        targets = self._capture_targets(viewport, widgets)
        if not targets:
            self._clear_prepared()
            return False
        plan = MotionPlan(
            generation=generation,
            reason=reason,
            background=background,
            viewport_rect=QRectF(viewport.rect()),
            targets=targets,
            spec=active_spec,
        )
        overlay = MotionOverlay(
            viewport,
            background=background,
            paint_observer=self._record_paint,
        )
        self._overlay = overlay
        self._clear_prepared()
        self.telemetry.plans_started += 1
        self.telemetry.preparation_ms.append((perf_counter() - started_at) * 1000.0)
        total_duration = motion_duration_ms(plan)
        self._timeline.start(
            generation=generation,
            duration_ms=total_duration,
            easing=active_spec.easing,
            frame=lambda elapsed: self._paint_frame(plan, elapsed),
            finished=self._finish,
        )
        return True

    def cancel(self, *, reason: str) -> None:
        """Stop active or prepared motion and reveal the committed surface."""

        _ = reason
        had_motion = (
            self._overlay is not None
            or self._prepared_background is not None
            or self._timeline.is_running()
        )
        self._timeline.stop()
        self._dispose_overlay()
        self._clear_prepared()
        if had_motion:
            self.telemetry.plans_cancelled += 1

    def is_animating(self) -> bool:
        """Return whether the controller owns a visible transition."""

        return self._overlay is not None and self._timeline.is_running()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Settle motion when its viewport changes or receives direct input."""

        if watched is self._watched_viewport and event.type() in {
            QEvent.Type.Destroy,
            QEvent.Type.Hide,
            QEvent.Type.Resize,
            QEvent.Type.Wheel,
            QEvent.Type.MouseButtonPress,
        }:
            self.cancel(reason=f"viewport_event:{event.type().name}")
        return False

    def _capture_targets(
        self,
        viewport: QWidget,
        widgets: Sequence[tuple[str, QWidget]],
    ) -> tuple[MotionTarget, ...]:
        """Capture bounded visible targets in viewport coordinates."""

        targets: list[MotionTarget] = []
        for identity, widget in widgets[:_MAX_TARGETS]:
            if not isValid(widget) or not widget.isVisible():
                continue
            top_left = widget.mapTo(viewport, QPoint(0, 0))
            final_rect = QRectF(
                top_left.x(), top_left.y(), widget.width(), widget.height()
            )
            if not final_rect.intersects(QRectF(viewport.rect())):
                continue
            snapshot = widget.grab()
            if snapshot.isNull():
                continue
            targets.append(
                MotionTarget(
                    identity=identity,
                    final_rect=final_rect,
                    snapshot=snapshot,
                    order=len(targets),
                )
            )
        return tuple(targets)

    def _paint_frame(self, plan: MotionPlan, elapsed_ms: float) -> None:
        """Interpolate and publish one frame for all plan targets."""

        overlay = self._overlay
        if overlay is None or not isValid(overlay):
            self.cancel(reason="overlay_destroyed")
            return
        frame_targets: list[MotionFrameTarget] = []
        for target in plan.targets:
            progress = target_progress(
                elapsed_ms=elapsed_ms,
                target_order=target.order,
                spec=plan.spec,
            )
            rect = QRectF(target.final_rect)
            rect.translate(
                plan.spec.translation_x * (1.0 - progress),
                plan.spec.translation_y * (1.0 - progress),
            )
            opacity = plan.spec.start_opacity + (
                (1.0 - plan.spec.start_opacity) * progress
            )
            frame_targets.append(
                MotionFrameTarget(
                    identity=target.identity,
                    rect=rect,
                    opacity=opacity,
                    snapshot=target.snapshot,
                )
            )
        overlay.set_frame(frame_targets)

    def _finish(self, generation: int) -> None:
        """Dispose the overlay only when the active generation completes."""

        if generation != self._latest_generation:
            return
        self._dispose_overlay()
        self.telemetry.plans_finished += 1

    def _dispose_overlay(self) -> None:
        """Hide and delete the active overlay without touching committed widgets."""

        overlay = self._overlay
        self._overlay = None
        if overlay is None:
            return
        if isValid(overlay):
            overlay.hide()
            overlay.deleteLater()

    def _clear_prepared(self) -> None:
        """Drop pre-commit capture state after start, cancel, or settlement."""

        self._prepared_background = None
        self._prepared_generation = None
        self._prepared_reason = None

    def _valid_viewport(self) -> QWidget | None:
        """Return the live viewport when it is suitable for capture."""

        viewport = self._viewport_provider()
        if viewport is None or not isValid(viewport) or not viewport.isVisible():
            return None
        if viewport.width() <= 0 or viewport.height() <= 0:
            return None
        if viewport is not self._watched_viewport:
            if self._watched_viewport is not None and isValid(self._watched_viewport):
                self._watched_viewport.removeEventFilter(self)
            self._watched_viewport = viewport
            viewport.installEventFilter(self)
        return viewport

    @staticmethod
    def _capture_is_bounded(viewport: QWidget) -> bool:
        """Return whether one viewport snapshot fits the memory safety bound."""

        return viewport.width() * viewport.height() <= _MAX_CAPTURE_PIXELS

    def _record_paint(self, elapsed_ms: float) -> None:
        """Retain bounded frame-paint timings for qualification."""

        self.telemetry.paint_ms.append(elapsed_ms)
        if len(self.telemetry.paint_ms) > 512:
            del self.telemetry.paint_ms[:-512]


__all__ = ["MotionTelemetry", "SurfaceMotionController"]
