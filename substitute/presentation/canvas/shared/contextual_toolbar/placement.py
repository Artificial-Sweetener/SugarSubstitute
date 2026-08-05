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

"""Own stable viewport-relative placement for one Contextual Toolbar."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPoint, QPointF, QRect, QSize

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CONTEXTUAL_TOOLBAR_EDGE_HYSTERESIS_PHYSICAL_PX,
    CONTEXTUAL_TOOLBAR_REANCHOR_PHYSICAL_PX,
)

_SELECTION_GAP = 12


class ContextualToolbarPlacementUpdate(str, Enum):
    """Describe why panel-space context geometry changed."""

    RESET = "reset"
    COMMAND = "command"
    VIEW = "view"


class _PlacementSide(str, Enum):
    """Identify the retained automatic side used for hysteresis."""

    BELOW = "below"
    ABOVE = "above"
    VIEWPORT_BOTTOM = "viewport-bottom"


class ContextualToolbarPlacement:
    """Retain manual or hysteretic automatic placement across frame changes."""

    def __init__(self) -> None:
        """Start without context, a chosen side, or user placement."""

        self._normalized_center: QPointF | None = None
        self._context_rect: QRect | None = None
        self._anchor_context_rect: QRect | None = None
        self._automatic_position: QPoint | None = None
        self._automatic_size: QSize | None = None
        self._pending_update = ContextualToolbarPlacementUpdate.RESET
        self._side: _PlacementSide | None = None

    def set_context_rect(
        self,
        bounds: QRect | None,
        *,
        update: ContextualToolbarPlacementUpdate,
    ) -> None:
        """Replace context geometry while retaining update intent."""

        self._context_rect = None if bounds is None else QRect(bounds)
        self._pending_update = ContextualToolbarPlacementUpdate(update)
        if bounds is None:
            self._anchor_context_rect = None
            self._automatic_position = None
            self._automatic_size = None
            self._side = None
        elif update is ContextualToolbarPlacementUpdate.RESET:
            self._normalized_center = None
            self._anchor_context_rect = QRect(bounds)
            self._automatic_position = None
            self._automatic_size = None

    def position(
        self,
        size: QSize,
        safe_rect: QRect,
        *,
        device_pixel_ratio: float,
    ) -> QPoint:
        """Project retained state into one clamped viewport top-left point."""

        if self._normalized_center is not None:
            return self._manual_position(size, safe_rect)
        context = self._context_rect
        if context is None:
            return _clamped_top_left(
                QPoint(
                    safe_rect.center().x() - size.width() // 2,
                    safe_rect.center().y() - size.height() // 2,
                ),
                size,
                safe_rect,
            )
        if (
            self._pending_update is ContextualToolbarPlacementUpdate.COMMAND
            and self._automatic_position is not None
            and not self._command_requires_reanchor(device_pixel_ratio)
        ):
            return self._retained_automatic_position(size, safe_rect)

        side = self._resolve_side(context, safe_rect, device_pixel_ratio)
        position = self._position_for_side(side, context, size, safe_rect)
        self._side = side
        self._automatic_position = position
        self._automatic_size = QSize(size)
        self._anchor_context_rect = QRect(context)
        self._pending_update = ContextualToolbarPlacementUpdate.COMMAND
        return position

    def move_by(
        self,
        delta: QPoint,
        size: QSize,
        safe_rect: QRect,
        *,
        device_pixel_ratio: float,
    ) -> QPoint:
        """Move from the projected point and retain its normalized center."""

        moved = _clamped_top_left(
            self.position(
                size,
                safe_rect,
                device_pixel_ratio=device_pixel_ratio,
            )
            + delta,
            size,
            safe_rect,
        )
        center = QPointF(
            moved.x() + size.width() / 2.0,
            moved.y() + size.height() / 2.0,
        )
        self._normalized_center = QPointF(
            (center.x() - safe_rect.left()) / max(1, safe_rect.width()),
            (center.y() - safe_rect.top()) / max(1, safe_rect.height()),
        )
        return moved

    def _retained_automatic_position(
        self,
        size: QSize,
        safe_rect: QRect,
    ) -> QPoint:
        """Preserve the rendered automatic center while page width morphs."""

        position = self._automatic_position
        previous_size = self._automatic_size
        if position is None or previous_size is None:
            return QPoint()
        center = QPointF(
            position.x() + previous_size.width() / 2.0,
            position.y() + previous_size.height() / 2.0,
        )
        retained = _clamped_top_left(
            QPoint(
                round(center.x() - size.width() / 2.0),
                round(center.y() - size.height() / 2.0),
            ),
            size,
            safe_rect,
        )
        self._automatic_position = retained
        self._automatic_size = QSize(size)
        return retained

    def _manual_position(self, size: QSize, safe_rect: QRect) -> QPoint:
        """Project one retained normalized manual center into the viewport."""

        center = self._normalized_center
        if center is None:
            return QPoint()
        return _clamped_top_left(
            QPoint(
                round(
                    safe_rect.left()
                    + center.x() * max(1, safe_rect.width())
                    - size.width() / 2.0
                ),
                round(
                    safe_rect.top()
                    + center.y() * max(1, safe_rect.height())
                    - size.height() / 2.0
                ),
            ),
            size,
            safe_rect,
        )

    def _command_requires_reanchor(self, device_pixel_ratio: float) -> bool:
        """Return whether command geometry crossed the physical threshold."""

        current = self._context_rect
        anchor = self._anchor_context_rect
        if current is None or anchor is None:
            return True
        maximum_delta = max(
            abs(current.left() - anchor.left()),
            abs(current.top() - anchor.top()),
            abs(current.right() - anchor.right()),
            abs(current.bottom() - anchor.bottom()),
        )
        return (
            maximum_delta * max(1.0, float(device_pixel_ratio))
            >= CONTEXTUAL_TOOLBAR_REANCHOR_PHYSICAL_PX
        )

    def _resolve_side(
        self,
        context: QRect,
        safe_rect: QRect,
        device_pixel_ratio: float,
    ) -> _PlacementSide:
        """Choose a stable side using physical overflow hysteresis."""

        if context.top() < safe_rect.top() and context.bottom() > safe_rect.bottom():
            return _PlacementSide.VIEWPORT_BOTTOM
        ratio = max(1.0, float(device_pixel_ratio))
        bottom_overflow = (context.bottom() - safe_rect.bottom()) * ratio
        if self._side is _PlacementSide.ABOVE:
            return (
                _PlacementSide.BELOW
                if bottom_overflow <= -CONTEXTUAL_TOOLBAR_EDGE_HYSTERESIS_PHYSICAL_PX
                else _PlacementSide.ABOVE
            )
        return (
            _PlacementSide.ABOVE
            if bottom_overflow > CONTEXTUAL_TOOLBAR_EDGE_HYSTERESIS_PHYSICAL_PX
            else _PlacementSide.BELOW
        )

    @staticmethod
    def _position_for_side(
        side: _PlacementSide,
        context: QRect,
        size: QSize,
        safe_rect: QRect,
    ) -> QPoint:
        """Build and clamp one side-specific top-left point."""

        center_x = (
            safe_rect.center().x()
            if side is _PlacementSide.VIEWPORT_BOTTOM
            else context.center().x()
        )
        if side is _PlacementSide.ABOVE:
            top = context.top() - _SELECTION_GAP - size.height()
        elif side is _PlacementSide.VIEWPORT_BOTTOM:
            top = safe_rect.bottom() - size.height() + 1
        else:
            top = context.bottom() + 1 + _SELECTION_GAP
        return _clamped_top_left(
            QPoint(round(center_x - size.width() / 2.0), top),
            size,
            safe_rect,
        )


def _clamped_top_left(candidate: QPoint, size: QSize, safe_rect: QRect) -> QPoint:
    """Clamp a toolbar rectangle completely inside the available viewport."""

    maximum_x = max(safe_rect.left(), safe_rect.right() - size.width() + 1)
    maximum_y = max(safe_rect.top(), safe_rect.bottom() - size.height() + 1)
    return QPoint(
        min(max(candidate.x(), safe_rect.left()), maximum_x),
        min(max(candidate.y(), safe_rect.top()), maximum_y),
    )


__all__ = ["ContextualToolbarPlacement", "ContextualToolbarPlacementUpdate"]
