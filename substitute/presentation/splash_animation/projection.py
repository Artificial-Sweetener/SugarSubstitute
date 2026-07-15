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

"""Project a flat splash pose into the paper-flip quadrilateral."""

from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPolygonF


@dataclass(frozen=True)
class ProjectionParameters:
    """Tune the perspective constraints used by the splash paper flip."""

    perspective_strength: float = 0.25
    minimum_edge_fraction: float = 0.055
    bob_fraction: float = 0.035
    settle_fraction: float = 0.018

    def normalized(self) -> "ProjectionParameters":
        """Return parameters clamped to ranges that keep quads transformable."""

        return ProjectionParameters(
            perspective_strength=_clamp(self.perspective_strength, 0.0, 1.25),
            minimum_edge_fraction=_clamp(self.minimum_edge_fraction, 0.015, 0.35),
            bob_fraction=_clamp(self.bob_fraction, 0.0, 0.16),
            settle_fraction=_clamp(self.settle_fraction, 0.0, 0.12),
        )


def build_projected_quad(
    bounds: QRectF,
    *,
    progress: float,
    direction: int,
    parameters: ProjectionParameters,
) -> QPolygonF:
    """Return destination points for a front-edge-front splash pose flip."""

    params = parameters.normalized()
    clamped_progress = _clamp(progress, 0.0, 1.0)
    turn = math.sin(clamped_progress * math.pi)
    width_fraction = max(
        params.minimum_edge_fraction,
        abs(math.cos(clamped_progress * math.pi)),
    )

    signed_direction = 1 if direction >= 0 else -1
    width = max(2.0, bounds.width() * width_fraction)
    half_width = width / 2.0
    half_height = bounds.height() / 2.0
    depth = turn * params.perspective_strength

    center = bounds.center()
    center_y = center.y() - (bounds.height() * params.bob_fraction * turn)
    center_y += _settle_offset(
        bounds=bounds,
        progress=clamped_progress,
        settle_fraction=params.settle_fraction,
    )

    left_x = center.x() - half_width
    right_x = center.x() + half_width
    slant = half_height * depth * 0.18 * signed_direction

    return QPolygonF(
        [
            QPointF(left_x, center_y - half_height + slant),
            QPointF(right_x, center_y - half_height - slant),
            QPointF(right_x, center_y + half_height - slant),
            QPointF(left_x, center_y + half_height + slant),
        ]
    )


def is_valid_projected_quad(quad: QPolygonF) -> bool:
    """Return whether one projected quad has enough area to render safely."""

    if quad.count() != 4:
        return False
    return abs(_polygon_area(quad)) > 1.0


def _settle_offset(
    *,
    bounds: QRectF,
    progress: float,
    settle_fraction: float,
) -> float:
    """Return a small damped landing bounce near the end of a flip."""

    if progress < 0.82 or settle_fraction <= 0:
        return 0.0
    local = (progress - 0.82) / 0.18
    damped_wave = math.sin(local * math.pi * 2.0) * (1.0 - local)
    return bounds.height() * settle_fraction * damped_wave


def _polygon_area(quad: QPolygonF) -> float:
    """Return the signed area for one four-point polygon."""

    area = 0.0
    for index in range(quad.count()):
        point = _quad_point(quad, index)
        next_point = _quad_point(quad, (index + 1) % quad.count())
        area += point.x() * next_point.y()
        area -= next_point.x() * point.y()
    return area / 2.0


def _quad_point(quad: QPolygonF, index: int) -> QPointF:
    """Return one quad point through the typed Qt API."""

    return quad.at(index)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Limit a numeric value to an inclusive range."""

    return max(minimum, min(maximum, value))


__all__ = [
    "ProjectionParameters",
    "build_projected_quad",
    "is_valid_projected_quad",
]
