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

"""Calculate cursor-relative zoom-indicator geometry without owning widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRect, QRectF

if TYPE_CHECKING:
    from qpane import ComparisonDividerState

_CURSOR_OFFSET = QPointF(12.0, 12.0)
_CANVAS_MARGIN = 4.0
_DIVIDER_GAP = 6.0


@dataclass(frozen=True, slots=True)
class CanvasZoomBadge:
    """Describe one zoom label and its canvas-space bounds."""

    text: str
    bounds: QRectF


def position_zoom_badges(
    qpane_rect: QRect,
    cursor_position: QPointF,
    divider: ComparisonDividerState | None,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge | None = None,
) -> tuple[CanvasZoomBadge, ...]:
    """Position zoom badges by gesture location and optional comparison boundary."""

    canvas = QRectF(qpane_rect).adjusted(
        _CANVAS_MARGIN,
        _CANVAS_MARGIN,
        -_CANVAS_MARGIN,
        -_CANVAS_MARGIN,
    )
    desired = cursor_position + _CURSOR_OFFSET
    if divider is None or not divider.enabled or comparison_badge is None:
        bounds = _clamped_badge_bounds(base_badge.bounds, desired, canvas)
        return (CanvasZoomBadge(base_badge.text, bounds),) if bounds is not None else ()

    segment = divider.visible_segment or divider.full_segment
    if segment is None:
        return ()
    orientation = getattr(divider.orientation, "value", divider.orientation)
    if orientation == "horizontal":
        return _position_horizontal_compare_badges(
            canvas,
            desired,
            segment.y1(),
            cursor_position.y() <= segment.y1(),
            base_badge,
            comparison_badge,
        )
    return _position_vertical_compare_badges(
        canvas,
        desired,
        segment.x1(),
        cursor_position.x() <= segment.x1(),
        base_badge,
        comparison_badge,
    )


def _position_vertical_compare_badges(
    canvas: QRectF,
    desired: QPointF,
    split: float,
    cursor_over_base: bool,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge,
) -> tuple[CanvasZoomBadge, ...]:
    """Position vertical-compare badges at the cursor and opposite divider edge."""

    base_right = min(canvas.right(), split - _DIVIDER_GAP)
    base_region = QRectF(
        canvas.left(),
        canvas.top(),
        max(0.0, base_right - canvas.left()),
        canvas.height(),
    )
    comparison_left = max(canvas.left(), split + _DIVIDER_GAP)
    comparison_region = QRectF(
        comparison_left,
        canvas.top(),
        max(0.0, canvas.right() - comparison_left),
        canvas.height(),
    )
    shared_y = _clamped_axis_position(
        desired.y(),
        max(base_badge.bounds.height(), comparison_badge.bounds.height()),
        canvas.top(),
        canvas.bottom(),
    )
    if shared_y is None:
        return ()
    if cursor_over_base:
        base_position = QPointF(desired.x(), shared_y)
        comparison_position = QPointF(comparison_region.left(), shared_y)
    else:
        base_position = QPointF(
            base_region.right() - base_badge.bounds.width(),
            shared_y,
        )
        comparison_position = QPointF(desired.x(), shared_y)
    return _positioned_badges(
        base_badge,
        base_position,
        base_region,
        comparison_badge,
        comparison_position,
        comparison_region,
    )


def _position_horizontal_compare_badges(
    canvas: QRectF,
    desired: QPointF,
    split: float,
    cursor_over_base: bool,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge,
) -> tuple[CanvasZoomBadge, ...]:
    """Position horizontal-compare badges at the cursor and opposite divider edge."""

    base_bottom = min(canvas.bottom(), split - _DIVIDER_GAP)
    base_region = QRectF(
        canvas.left(),
        canvas.top(),
        canvas.width(),
        max(0.0, base_bottom - canvas.top()),
    )
    comparison_top = max(canvas.top(), split + _DIVIDER_GAP)
    comparison_region = QRectF(
        canvas.left(),
        comparison_top,
        canvas.width(),
        max(0.0, canvas.bottom() - comparison_top),
    )
    shared_x = _clamped_axis_position(
        desired.x(),
        max(base_badge.bounds.width(), comparison_badge.bounds.width()),
        canvas.left(),
        canvas.right(),
    )
    if shared_x is None:
        return ()
    if cursor_over_base:
        base_position = QPointF(shared_x, desired.y())
        comparison_position = QPointF(shared_x, comparison_region.top())
    else:
        base_position = QPointF(
            shared_x,
            base_region.bottom() - base_badge.bounds.height(),
        )
        comparison_position = QPointF(shared_x, desired.y())
    return _positioned_badges(
        base_badge,
        base_position,
        base_region,
        comparison_badge,
        comparison_position,
        comparison_region,
    )


def _positioned_badges(
    base_badge: CanvasZoomBadge,
    base_position: QPointF,
    base_region: QRectF,
    comparison_badge: CanvasZoomBadge,
    comparison_position: QPointF,
    comparison_region: QRectF,
) -> tuple[CanvasZoomBadge, ...]:
    """Clamp both comparison badges to their authoritative visible regions."""

    base_bounds = _clamped_badge_bounds(base_badge.bounds, base_position, base_region)
    comparison_bounds = _clamped_badge_bounds(
        comparison_badge.bounds,
        comparison_position,
        comparison_region,
    )
    badges: list[CanvasZoomBadge] = []
    if base_bounds is not None:
        badges.append(CanvasZoomBadge(base_badge.text, base_bounds))
    if comparison_bounds is not None:
        badges.append(CanvasZoomBadge(comparison_badge.text, comparison_bounds))
    return tuple(badges)


def _clamped_badge_bounds(
    source_bounds: QRectF,
    desired_position: QPointF,
    region: QRectF,
) -> QRectF | None:
    """Return badge bounds contained by a region, or none when they cannot fit."""

    x = _clamped_axis_position(
        desired_position.x(),
        source_bounds.width(),
        region.left(),
        region.right(),
    )
    y = _clamped_axis_position(
        desired_position.y(),
        source_bounds.height(),
        region.top(),
        region.bottom(),
    )
    if x is None or y is None:
        return None
    bounds = QRectF(source_bounds)
    bounds.moveTopLeft(QPointF(x, y))
    return bounds


def _clamped_axis_position(
    desired: float,
    extent: float,
    minimum: float,
    maximum: float,
) -> float | None:
    """Clamp one leading edge while requiring the full extent to fit."""

    latest = maximum - extent
    if latest < minimum:
        return None
    return max(minimum, min(desired, latest))


__all__ = ["CanvasZoomBadge", "position_zoom_badges"]
