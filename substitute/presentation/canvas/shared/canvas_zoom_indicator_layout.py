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

"""Calculate cursor-relative normal and reveal zoom-badge geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QFontMetricsF

_CURSOR_OFFSET = QPointF(12.0, 12.0)
_CANVAS_MARGIN = 4.0
_DIVIDER_GAP = 6.0


@dataclass(frozen=True, slots=True)
class CanvasZoomBadge:
    """Describe one percentage label and its canvas-local bounds."""

    text: str
    bounds: QRectF


def zoom_badge_for_text(text: str, metrics: QFontMetricsF) -> CanvasZoomBadge:
    """Build one origin-relative badge that comfortably contains ``text``."""

    text_bounds = metrics.tightBoundingRect(text)
    return CanvasZoomBadge(
        text,
        QRectF(0.0, 0.0, text_bounds.width() + 20.0, 28.0),
    )


def position_zoom_badges(
    viewport: QRect,
    cursor_position: QPointF,
    divider: object | None,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge | None = None,
) -> tuple[CanvasZoomBadge, ...]:
    """Place normal feedback or one badge in each visible comparison region."""

    canvas = QRectF(viewport).adjusted(
        _CANVAS_MARGIN,
        _CANVAS_MARGIN,
        -_CANVAS_MARGIN,
        -_CANVAS_MARGIN,
    )
    desired = cursor_position + _CURSOR_OFFSET
    if (
        divider is None
        or not bool(getattr(divider, "enabled", False))
        or comparison_badge is None
    ):
        bounds = _clamped_badge_bounds(base_badge.bounds, desired, canvas)
        return (CanvasZoomBadge(base_badge.text, bounds),) if bounds is not None else ()
    segment = getattr(divider, "visible_segment", None) or getattr(
        divider, "full_segment", None
    )
    if segment is None:
        return ()
    orientation = getattr(
        getattr(divider, "orientation", None),
        "value",
        getattr(divider, "orientation", None),
    )
    if orientation == "horizontal":
        return _position_horizontal(
            canvas,
            desired,
            float(segment.y1()),
            cursor_position.y() <= segment.y1(),
            base_badge,
            comparison_badge,
        )
    return _position_vertical(
        canvas,
        desired,
        float(segment.x1()),
        cursor_position.x() <= segment.x1(),
        base_badge,
        comparison_badge,
    )


def _position_vertical(
    canvas: QRectF,
    desired: QPointF,
    split: float,
    cursor_over_base: bool,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge,
) -> tuple[CanvasZoomBadge, ...]:
    """Place vertical-reveal labels beside the cursor and divider."""

    base = QRectF(
        canvas.left(),
        canvas.top(),
        max(0.0, min(canvas.right(), split - _DIVIDER_GAP) - canvas.left()),
        canvas.height(),
    )
    comparison = QRectF(
        max(canvas.left(), split + _DIVIDER_GAP),
        canvas.top(),
        max(0.0, canvas.right() - max(canvas.left(), split + _DIVIDER_GAP)),
        canvas.height(),
    )
    y = _clamped_axis_position(
        desired.y(),
        max(base_badge.bounds.height(), comparison_badge.bounds.height()),
        canvas.top(),
        canvas.bottom(),
    )
    if y is None:
        return ()
    return _position_pair(
        base_badge,
        QPointF(desired.x(), y)
        if cursor_over_base
        else QPointF(base.right() - base_badge.bounds.width(), y),
        base,
        comparison_badge,
        QPointF(comparison.left(), y) if cursor_over_base else QPointF(desired.x(), y),
        comparison,
    )


def _position_horizontal(
    canvas: QRectF,
    desired: QPointF,
    split: float,
    cursor_over_base: bool,
    base_badge: CanvasZoomBadge,
    comparison_badge: CanvasZoomBadge,
) -> tuple[CanvasZoomBadge, ...]:
    """Place horizontal-reveal labels beside the cursor and divider."""

    base = QRectF(
        canvas.left(),
        canvas.top(),
        canvas.width(),
        max(0.0, min(canvas.bottom(), split - _DIVIDER_GAP) - canvas.top()),
    )
    comparison = QRectF(
        canvas.left(),
        max(canvas.top(), split + _DIVIDER_GAP),
        canvas.width(),
        max(0.0, canvas.bottom() - max(canvas.top(), split + _DIVIDER_GAP)),
    )
    x = _clamped_axis_position(
        desired.x(),
        max(base_badge.bounds.width(), comparison_badge.bounds.width()),
        canvas.left(),
        canvas.right(),
    )
    if x is None:
        return ()
    return _position_pair(
        base_badge,
        QPointF(x, desired.y())
        if cursor_over_base
        else QPointF(x, base.bottom() - base_badge.bounds.height()),
        base,
        comparison_badge,
        QPointF(x, comparison.top()) if cursor_over_base else QPointF(x, desired.y()),
        comparison,
    )


def _position_pair(
    base_badge: CanvasZoomBadge,
    base_position: QPointF,
    base_region: QRectF,
    comparison_badge: CanvasZoomBadge,
    comparison_position: QPointF,
    comparison_region: QRectF,
) -> tuple[CanvasZoomBadge, ...]:
    """Clamp both source labels independently to their visible regions."""

    result: list[CanvasZoomBadge] = []
    for badge, position, region in (
        (base_badge, base_position, base_region),
        (comparison_badge, comparison_position, comparison_region),
    ):
        bounds = _clamped_badge_bounds(badge.bounds, position, region)
        if bounds is not None:
            result.append(CanvasZoomBadge(badge.text, bounds))
    return tuple(result)


def _clamped_badge_bounds(
    source: QRectF, desired: QPointF, region: QRectF
) -> QRectF | None:
    """Return fully contained bounds or no badge when the region is too small."""

    x = _clamped_axis_position(
        desired.x(), source.width(), region.left(), region.right()
    )
    y = _clamped_axis_position(
        desired.y(), source.height(), region.top(), region.bottom()
    )
    if x is None or y is None:
        return None
    bounds = QRectF(source)
    bounds.moveTopLeft(QPointF(x, y))
    return bounds


def _clamped_axis_position(
    desired: float, extent: float, minimum: float, maximum: float
) -> float | None:
    """Clamp one leading edge while preserving the complete badge extent."""

    latest = maximum - extent
    return None if latest < minimum else max(minimum, min(desired, latest))


__all__ = ["CanvasZoomBadge", "position_zoom_badges", "zoom_badge_for_text"]
