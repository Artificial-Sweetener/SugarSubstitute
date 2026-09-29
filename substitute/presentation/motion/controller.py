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
from time import perf_counter

from PySide6.QtCore import QEvent, QObject, QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from .fluent_motion import resolve_motion_duration
from .capture import (
    CapturedSurface,
    capture_background_without_targets,
    capture_surfaces,
)
from .models import (
    MotionFrameTarget,
    MotionPlan,
    MotionSpec,
    MotionTarget,
    interpolate_target,
    motion_duration_ms,
    target_progress,
)
from .overlay import MotionOverlay
from .plans import plan_entrances, plan_layout_transition
from .timeline import MotionClockFactory, MotionTimeline
from .telemetry import MotionTelemetry

_MAX_BACKGROUND_CAPTURE_PIXELS = 16_000_000


class SurfaceMotionController(QObject):
    """Run one synchronized snapshot-overlay transition for a mounted surface."""

    def __init__(
        self,
        *,
        viewport_provider: Callable[[], QWidget | None],
        default_spec: MotionSpec | None = None,
        clock_factory: MotionClockFactory | None = None,
    ) -> None:
        """Store the viewport provider and initialize idle transition state."""

        super().__init__()
        self._viewport_provider = viewport_provider
        self._default_spec = default_spec or MotionSpec()
        self._timeline = MotionTimeline(self, clock_factory=clock_factory)
        self._watched_viewport: QWidget | None = None
        self._watched_inputs: list[QWidget] = []
        self._overlay: MotionOverlay | None = None
        self._prepared_background: QPixmap | None = None
        self._prepared_surfaces: tuple[CapturedSurface, ...] = ()
        self._prepared_capture_ms = 0.0
        self._prepared_generation: int | None = None
        self._prepared_reason: str | None = None
        self._latest_generation = 0
        self.telemetry = MotionTelemetry()

    def prepare(
        self,
        *,
        reason: str,
        widgets: Sequence[tuple[str, QWidget]] = (),
    ) -> int | None:
        """Capture the current viewport before an eligible structural commit."""

        self.cancel(reason="superseded_prepare")
        started_at = perf_counter()
        viewport = self._valid_viewport()
        if viewport is None or not self._capture_is_bounded(viewport):
            return None
        self._latest_generation += 1
        self._prepared_generation = self._latest_generation
        self._prepared_reason = reason
        self._prepared_background = viewport.grab() if not widgets else None
        capture = capture_surfaces(viewport, widgets)
        self._prepared_surfaces = capture.surfaces
        self._record_target_capture(capture.surfaces, capture.pixels)
        self._prepared_capture_ms = (perf_counter() - started_at) * 1000.0
        self._watch_direct_inputs(viewport)
        return self._prepared_generation

    def animate_layout(
        self,
        *,
        generation: int,
        widgets: Sequence[tuple[str, QWidget]],
        spec: MotionSpec | None = None,
        exit_translation_y: float = -8.0,
    ) -> bool:
        """Animate entering, moved, and exiting surfaces across one layout commit."""

        started_at = perf_counter()
        prepared = self._prepared_state(generation)
        if prepared is None:
            self.cancel(reason="invalid_or_stale_generation")
            return False
        viewport, reason = prepared
        active_spec = self._resolved_spec(spec)
        if active_spec is None:
            return False
        final_capture = capture_surfaces(viewport, widgets)
        self._record_target_capture(
            final_capture.surfaces,
            final_capture.pixels,
        )
        targets = plan_layout_transition(
            self._prepared_surfaces,
            final_capture.surfaces,
            active_spec,
            exit_translation_y=exit_translation_y,
        )
        if not targets:
            self._clear_prepared()
            self._unwatch_direct_inputs()
            return False
        background = capture_background_without_targets(viewport, widgets)
        return self._start_plan(
            generation=generation,
            reason=reason,
            background=background,
            viewport=viewport,
            targets=targets,
            spec=active_spec,
            started_at=started_at,
        )

    def animate_widgets(
        self,
        *,
        generation: int,
        widgets: Sequence[tuple[str, QWidget]],
        spec: MotionSpec | None = None,
    ) -> bool:
        """Animate captured widgets above their already-committed final surface."""

        started_at = perf_counter()
        prepared = self._prepared_state(generation)
        background = self._prepared_background
        if prepared is None or background is None:
            self.cancel(reason="invalid_or_stale_generation")
            return False
        viewport, reason = prepared
        active_spec = self._resolved_spec(spec)
        if active_spec is None:
            return False
        capture = capture_surfaces(viewport, widgets)
        self._record_target_capture(capture.surfaces, capture.pixels)
        targets = plan_entrances(capture.surfaces, active_spec)
        if not targets:
            self._clear_prepared()
            self._unwatch_direct_inputs()
            return False
        return self._start_plan(
            generation=generation,
            reason=reason,
            background=background,
            viewport=viewport,
            targets=targets,
            spec=active_spec,
            started_at=started_at,
        )

    def _start_plan(
        self,
        *,
        generation: int,
        reason: str,
        background: QPixmap,
        viewport: QWidget,
        targets: tuple[MotionTarget, ...],
        spec: MotionSpec,
        started_at: float,
    ) -> bool:
        """Mount one overlay and start its single synchronized timeline."""

        plan = MotionPlan(
            generation=generation,
            reason=reason,
            background=background,
            viewport_rect=QRectF(viewport.rect()),
            targets=targets,
            spec=spec,
        )
        overlay = MotionOverlay(
            viewport,
            background=background,
            paint_observer=self._record_paint,
        )
        self._overlay = overlay
        self._watch_direct_inputs(viewport)
        preparation_ms = self._prepared_capture_ms + (
            (perf_counter() - started_at) * 1000.0
        )
        self._clear_prepared()
        self.telemetry.plans_started += 1
        self.telemetry.preparation_ms.append(preparation_ms)
        self._paint_frame(plan, 0.0)
        self._timeline.start(
            generation=generation,
            duration_ms=motion_duration_ms(plan),
            easing=spec.easing,
            frame=lambda elapsed: self._paint_frame(plan, elapsed),
            finished=self._finish,
        )
        return True

    def _prepared_state(
        self,
        generation: int,
    ) -> tuple[QWidget, str] | None:
        """Return the valid viewport and reason for one prepared generation."""

        viewport = self._valid_viewport()
        reason = self._prepared_reason
        if (
            viewport is None
            or generation != self._prepared_generation
            or reason is None
        ):
            return None
        return viewport, reason

    def _resolved_spec(self, spec: MotionSpec | None) -> MotionSpec | None:
        """Resolve one policy through reduced motion and settle when disabled."""

        active_spec = spec or self._default_spec
        resolved_duration = resolve_motion_duration(active_spec.duration_ms)
        if resolved_duration == 0:
            self._clear_prepared()
            self._unwatch_direct_inputs()
            self.telemetry.plans_settled_immediately += 1
            return None
        return MotionSpec(
            duration_ms=resolved_duration,
            stagger_ms=active_spec.stagger_ms,
            translation_x=active_spec.translation_x,
            translation_y=active_spec.translation_y,
            start_opacity=active_spec.start_opacity,
            easing=active_spec.easing,
        )

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

        event_type = event.type()
        if watched is self._watched_viewport and event_type in {
            QEvent.Type.Destroy,
            QEvent.Type.Hide,
            QEvent.Type.Resize,
        }:
            self.cancel(reason=f"viewport_event:{event_type.name}")
        elif event_type in {
            QEvent.Type.Wheel,
            QEvent.Type.MouseButtonPress,
        } and self._is_viewport_target(watched):
            self.cancel(reason=f"direct_input:{event_type.name}")
        return False

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
            frame_targets.append(interpolate_target(target, progress=progress))
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
            self._unwatch_direct_inputs()
            return
        if isValid(overlay):
            overlay.hide()
            overlay.deleteLater()
        self._unwatch_direct_inputs()

    def _clear_prepared(self) -> None:
        """Drop pre-commit capture state after start, cancel, or settlement."""

        self._prepared_background = None
        self._prepared_surfaces = ()
        self._prepared_capture_ms = 0.0
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
            self._watched_viewport = viewport
        return viewport

    @staticmethod
    def _capture_is_bounded(viewport: QWidget) -> bool:
        """Return whether one viewport snapshot fits the memory safety bound."""

        return viewport.width() * viewport.height() <= _MAX_BACKGROUND_CAPTURE_PIXELS

    def _is_viewport_target(self, watched: QObject) -> bool:
        """Return whether an input receiver belongs to the active viewport."""

        viewport = self._watched_viewport
        return (
            viewport is not None
            and isValid(viewport)
            and isinstance(watched, QWidget)
            and (watched is viewport or viewport.isAncestorOf(watched))
        )

    def _watch_direct_inputs(self, viewport: QWidget) -> None:
        """Observe direct input on the committed viewport subtree during motion."""

        self._unwatch_direct_inputs()
        self._watched_inputs = [viewport, *viewport.findChildren(QWidget)]
        for widget in self._watched_inputs:
            if isValid(widget):
                widget.installEventFilter(self)

    def _unwatch_direct_inputs(self) -> None:
        """Release transient child filters when motion settles."""

        watched_inputs = self._watched_inputs
        self._watched_inputs = []
        for widget in watched_inputs:
            if isValid(widget):
                widget.removeEventFilter(self)

    def _record_paint(self, elapsed_ms: float) -> None:
        """Retain bounded frame-paint timings for qualification."""

        self.telemetry.paint_ms.append(elapsed_ms)
        if len(self.telemetry.paint_ms) > 512:
            del self.telemetry.paint_ms[:-512]

    def _record_target_capture(
        self,
        surfaces: tuple[CapturedSurface, ...],
        pixels: int,
    ) -> None:
        """Publish bounded capture evidence for the most recent snapshot set."""

        self.telemetry.last_capture_target_count = len(surfaces)
        self.telemetry.last_capture_target_pixels = pixels


__all__ = ["MotionTelemetry", "SurfaceMotionController"]
