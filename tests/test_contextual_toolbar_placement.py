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

"""Verify stable DPR-aware Contextual Toolbar placement policy."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from substitute.presentation.canvas.shared.contextual_toolbar.placement import (
    ContextualToolbarPlacement,
    ContextualToolbarPlacementUpdate,
)

_SAFE_RECT = QRect(0, 0, 500, 400)
_TOOLBAR_SIZE = QSize(100, 36)


def _position(
    placement: ContextualToolbarPlacement,
    *,
    device_pixel_ratio: float = 1.0,
) -> QPoint:
    """Project the standard toolbar fixture at one display scale."""

    return placement.position(
        _TOOLBAR_SIZE,
        _SAFE_RECT,
        device_pixel_ratio=device_pixel_ratio,
    )


def test_command_changes_reanchor_only_after_physical_threshold() -> None:
    """Small logical changes remain stable until DPR-scaled motion is substantial."""

    placement = ContextualToolbarPlacement()
    placement.set_context_rect(
        QRect(100, 100, 100, 40),
        update=ContextualToolbarPlacementUpdate.RESET,
    )
    original = _position(placement)
    placement.set_context_rect(
        QRect(100, 100, 100, 90),
        update=ContextualToolbarPlacementUpdate.COMMAND,
    )

    assert _position(placement) == original
    assert _position(placement, device_pixel_ratio=2.0) != original


def test_view_projection_tracks_selection_without_command_threshold() -> None:
    """Pan and zoom updates intentionally track viewport-space selection bounds."""

    placement = ContextualToolbarPlacement()
    placement.set_context_rect(
        QRect(100, 100, 100, 40),
        update=ContextualToolbarPlacementUpdate.RESET,
    )
    original = _position(placement)
    placement.set_context_rect(
        QRect(112, 108, 100, 40),
        update=ContextualToolbarPlacementUpdate.VIEW,
    )

    projected = _position(placement)
    assert projected.x() == original.x() + 12
    assert projected.y() == original.y() + 8


def test_bottom_side_uses_overflow_hysteresis_without_oscillation() -> None:
    """Bottom crossing must exceed physical thresholds before either side flips."""

    placement = ContextualToolbarPlacement()
    placement.set_context_rect(
        QRect(100, 360, 100, 50),
        update=ContextualToolbarPlacementUpdate.RESET,
    )
    near_bottom = _position(placement)
    assert near_bottom.y() == _SAFE_RECT.bottom() - _TOOLBAR_SIZE.height() + 1

    placement.set_context_rect(
        QRect(100, 380, 100, 50),
        update=ContextualToolbarPlacementUpdate.VIEW,
    )
    above = _position(placement)
    assert above.y() < 380

    placement.set_context_rect(
        QRect(100, 350, 100, 40),
        update=ContextualToolbarPlacementUpdate.VIEW,
    )
    assert _position(placement).y() < 350

    placement.set_context_rect(
        QRect(100, 320, 100, 40),
        update=ContextualToolbarPlacementUpdate.VIEW,
    )
    assert _position(placement).y() > 320


def test_selection_spanning_viewport_uses_bottom_center_fallback() -> None:
    """Oversized vertical context must use canonical bottom-center placement."""

    placement = ContextualToolbarPlacement()
    placement.set_context_rect(
        QRect(80, -20, 120, 450),
        update=ContextualToolbarPlacementUpdate.RESET,
    )

    position = _position(placement)
    assert position.x() == _SAFE_RECT.center().x() - _TOOLBAR_SIZE.width() // 2
    assert position.y() == _SAFE_RECT.bottom() - _TOOLBAR_SIZE.height() + 1
