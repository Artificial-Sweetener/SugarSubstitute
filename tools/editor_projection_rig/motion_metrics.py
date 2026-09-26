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

"""Measure editor motion independently from functional projection completion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from substitute.presentation.editor.panel.surface_motion import (
    EditorSurfaceMotionController,
)


@dataclass(frozen=True, slots=True)
class MotionMetricCursor:
    """Identify cumulative telemetry positions before one rig operation."""

    plans_started: int
    plans_finished: int
    plans_cancelled: int
    plans_settled_immediately: int
    preparation_count: int
    paint_count: int


class MotionOperationMetrics(TypedDict):
    """Describe motion work attributable to one functional operation."""

    plans_started: int
    plans_finished: int
    plans_cancelled: int
    plans_settled_immediately: int
    preparation_ms: list[float]
    paint_ms: list[float]
    last_capture_target_count: int
    last_capture_target_pixels: int


def motion_metric_cursor(panel: object) -> MotionMetricCursor:
    """Capture current cumulative telemetry indices for one editor panel."""

    controller = _motion_controller(panel)
    if controller is None:
        return MotionMetricCursor(0, 0, 0, 0, 0, 0)
    telemetry = controller.telemetry
    return MotionMetricCursor(
        plans_started=telemetry.plans_started,
        plans_finished=telemetry.plans_finished,
        plans_cancelled=telemetry.plans_cancelled,
        plans_settled_immediately=telemetry.plans_settled_immediately,
        preparation_count=len(telemetry.preparation_ms),
        paint_count=len(telemetry.paint_ms),
    )


def motion_metrics_since(
    panel: object,
    cursor: MotionMetricCursor,
) -> MotionOperationMetrics:
    """Return telemetry recorded since the supplied operation cursor."""

    controller = _motion_controller(panel)
    if controller is None:
        return _empty_metrics()
    telemetry = controller.telemetry
    return MotionOperationMetrics(
        plans_started=telemetry.plans_started - cursor.plans_started,
        plans_finished=telemetry.plans_finished - cursor.plans_finished,
        plans_cancelled=telemetry.plans_cancelled - cursor.plans_cancelled,
        plans_settled_immediately=(
            telemetry.plans_settled_immediately - cursor.plans_settled_immediately
        ),
        preparation_ms=telemetry.preparation_ms[cursor.preparation_count :],
        paint_ms=telemetry.paint_ms[cursor.paint_count :],
        last_capture_target_count=telemetry.last_capture_target_count,
        last_capture_target_pixels=telemetry.last_capture_target_pixels,
    )


def editor_motion_is_active(panel: object) -> bool:
    """Return whether the panel currently owns a cosmetic transition."""

    controller = _motion_controller(panel)
    return controller is not None and controller.is_animating()


def _motion_controller(panel: object) -> EditorSurfaceMotionController | None:
    """Return the installed controller without creating qualification state."""

    controller = getattr(panel, "_surface_motion", None)
    return controller if isinstance(controller, EditorSurfaceMotionController) else None


def _empty_metrics() -> MotionOperationMetrics:
    """Return an empty motion sample for panels without a controller."""

    return MotionOperationMetrics(
        plans_started=0,
        plans_finished=0,
        plans_cancelled=0,
        plans_settled_immediately=0,
        preparation_ms=[],
        paint_ms=[],
        last_capture_target_count=0,
        last_capture_target_pixels=0,
    )


__all__ = [
    "MotionMetricCursor",
    "MotionOperationMetrics",
    "editor_motion_is_active",
    "motion_metric_cursor",
    "motion_metrics_since",
]
