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

"""Define immutable plans for synchronized presentation motion."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QRectF
from PySide6.QtGui import QPixmap


@dataclass(frozen=True, slots=True)
class MotionSpec:
    """Describe timing and visual interpolation for one surface transition."""

    duration_ms: int = 180
    stagger_ms: int = 18
    translation_x: float = 0.0
    translation_y: float = 14.0
    start_opacity: float = 0.0
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic

    def __post_init__(self) -> None:
        """Reject timing and opacity values that cannot produce stable motion."""

        if self.duration_ms < 0:
            raise ValueError("Motion duration cannot be negative.")
        if self.stagger_ms < 0:
            raise ValueError("Motion stagger cannot be negative.")
        if not 0.0 <= self.start_opacity <= 1.0:
            raise ValueError("Motion start opacity must be between zero and one.")


@dataclass(frozen=True, slots=True)
class MotionTarget:
    """Bind one semantic surface identity to a captured final-state image."""

    identity: str
    final_rect: QRectF
    snapshot: QPixmap
    order: int = 0


@dataclass(frozen=True, slots=True)
class MotionPlan:
    """Describe one generation of synchronized surface motion."""

    generation: int
    reason: str
    background: QPixmap
    viewport_rect: QRectF
    targets: tuple[MotionTarget, ...]
    spec: MotionSpec


@dataclass(frozen=True, slots=True)
class MotionFrameTarget:
    """Describe one target's interpolated paint state."""

    identity: str
    rect: QRectF
    opacity: float
    snapshot: QPixmap


def target_progress(
    *,
    elapsed_ms: float,
    target_order: int,
    spec: MotionSpec,
) -> float:
    """Return clamped linear progress for one staggered target."""

    delay_ms = target_order * spec.stagger_ms
    if spec.duration_ms == 0:
        return 1.0
    return max(0.0, min(1.0, (elapsed_ms - delay_ms) / spec.duration_ms))


def motion_duration_ms(plan: MotionPlan) -> int:
    """Return total plan duration including bounded target stagger."""

    if not plan.targets:
        return 0
    last_order = max(target.order for target in plan.targets)
    return plan.spec.duration_ms + (last_order * plan.spec.stagger_ms)


__all__ = [
    "MotionFrameTarget",
    "MotionPlan",
    "MotionSpec",
    "MotionTarget",
    "motion_duration_ms",
    "target_progress",
]
