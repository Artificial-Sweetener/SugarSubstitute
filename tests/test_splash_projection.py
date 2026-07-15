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

"""Tests for splash paper-flip projection math."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPolygonF, QTransform

from substitute.presentation.splash_animation.projection import (
    ProjectionParameters,
    build_projected_quad,
    is_valid_projected_quad,
)


def test_front_facing_projection_is_rectangle_like() -> None:
    """Progress zero should keep the splash pose front-facing."""

    bounds = QRectF(10.0, 20.0, 300.0, 300.0)
    quad = build_projected_quad(
        bounds,
        progress=0.0,
        direction=1,
        parameters=ProjectionParameters(),
    )

    assert quad.count() == 4
    assert quad.at(0) == bounds.topLeft()
    assert quad.at(1) == bounds.topRight()
    assert quad.at(2) == bounds.bottomRight()
    assert quad.at(3) == bounds.bottomLeft()


def test_midpoint_projection_is_skewed_and_non_degenerate() -> None:
    """The edge-on phase should stay narrow, skewed, and transformable."""

    bounds = QRectF(0.0, 0.0, 220.0, 220.0)
    quad = build_projected_quad(
        bounds,
        progress=0.5,
        direction=1,
        parameters=ProjectionParameters(perspective_strength=0.75),
    )

    assert is_valid_projected_quad(quad)
    assert abs(quad.at(1).x() - quad.at(0).x()) < bounds.width() * 0.20
    assert quad.at(0).y() != quad.at(1).y()
    assert QTransform.quadToQuad(_source_quad(), quad) is not None


def test_projection_keeps_horizontal_center_stable_during_flip() -> None:
    """Perspective should not make the splash pose orbit around the center."""

    bounds = QRectF(20.0, 40.0, 220.0, 220.0)

    for step in range(101):
        quad = build_projected_quad(
            bounds,
            progress=step / 100.0,
            direction=1,
            parameters=ProjectionParameters(perspective_strength=1.0),
        )
        average_x = (
            sum(quad.at(index).x() for index in range(quad.count())) / quad.count()
        )
        assert average_x == bounds.center().x()


def test_projection_stays_transformable_across_animation_range() -> None:
    """Configured projection should avoid collapsed quads for all flip phases."""

    bounds = QRectF(0.0, 0.0, 220.0, 220.0)
    source = _source_quad()

    for step in range(101):
        quad = build_projected_quad(
            bounds,
            progress=step / 100.0,
            direction=-1 if step % 2 else 1,
            parameters=ProjectionParameters(),
        )
        assert is_valid_projected_quad(quad)
        assert QTransform.quadToQuad(source, quad) is not None


def _source_quad() -> QPolygonF:
    """Return a simple source quad for transformability checks."""

    return QPolygonF(
        [
            QPointF(0.0, 0.0),
            QPointF(100.0, 0.0),
            QPointF(100.0, 100.0),
            QPointF(0.0, 100.0),
        ]
    )
