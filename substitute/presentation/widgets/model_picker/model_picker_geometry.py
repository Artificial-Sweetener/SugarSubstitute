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

"""Define shared model picker popup geometry constraints."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

MODEL_PICKER_POPUP_WIDTH: Final[int] = 560
MODEL_PICKER_POPUP_HEIGHT: Final[int] = 630
MODEL_PICKER_POPUP_MIN_HEIGHT: Final[int] = 270
MODEL_PICKER_POPUP_MIN_WIDTH: Final[int] = 260
MODEL_PICKER_POPUP_MARGIN: Final[int] = 8


class ModelPickerPopupPlacementMode(Enum):
    """Describe how the picker popup is positioned relative to its anchor."""

    BELOW = "below"
    ABOVE = "above"
    DETACHED = "detached"


@dataclass(frozen=True, slots=True)
class ModelPickerPopupPlacement:
    """Describe resolved popup geometry and vertical attachment mode."""

    geometry: QRect
    mode: ModelPickerPopupPlacementMode


def resolve_model_picker_popup_placement(
    *,
    boundary_rect: QRect,
    anchor_rect: QRect,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    margin: int = MODEL_PICKER_POPUP_MARGIN,
) -> ModelPickerPopupPlacement:
    """Return popup geometry and placement mode for one boundary-local anchor."""

    safe_left, safe_right = _safe_exclusive_axis(
        origin=boundary_rect.left(),
        length=boundary_rect.width(),
        margin=margin,
    )
    safe_top, safe_bottom = _safe_exclusive_axis(
        origin=boundary_rect.top(),
        length=boundary_rect.height(),
        margin=margin,
    )
    safe_width = max(1, safe_right - safe_left)
    target_width = max(max(1, minimum_width), preferred_width)
    width = min(target_width, safe_width)
    left = _clamp(anchor_rect.left(), safe_left, safe_right - width)

    anchor_top = anchor_rect.top()
    anchor_bottom = anchor_rect.top() + anchor_rect.height()
    available_below = max(0, safe_bottom - anchor_bottom)
    available_above = max(0, anchor_top - safe_top)
    mode = _placement_mode_for_available_height(
        available_below=available_below,
        available_above=available_above,
        preferred_height=preferred_height,
    )
    top, height = _vertical_geometry_for_mode(
        mode=mode,
        anchor_top=anchor_top,
        anchor_bottom=anchor_bottom,
        available_below=available_below,
        available_above=available_above,
        preferred_height=preferred_height,
        safe_top=safe_top,
        safe_bottom=safe_bottom,
    )
    _ = minimum_height
    return ModelPickerPopupPlacement(
        geometry=QRect(left, top, width, height),
        mode=mode,
    )


def model_picker_screen_available_geometry(anchor_rect: QRect) -> QRect:
    """Return available screen geometry for the screen containing the anchor."""

    screen = QApplication.screenAt(anchor_rect.center())
    if screen is None:
        screen = QApplication.screenAt(anchor_rect.topLeft())
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1080)
    return screen.availableGeometry()


def _safe_exclusive_axis(*, origin: int, length: int, margin: int) -> tuple[int, int]:
    """Return an exclusive safe range, dropping margins when space is too small."""

    bounded_length = max(0, length)
    start = origin
    end = origin + bounded_length
    safe_margin = max(0, margin)
    if bounded_length > safe_margin * 2:
        return start + safe_margin, end - safe_margin
    return start, end


def _placement_mode_for_available_height(
    *,
    available_below: int,
    available_above: int,
    preferred_height: int,
) -> ModelPickerPopupPlacementMode:
    """Choose an attached side from available heights."""

    target_height = max(1, preferred_height)
    if available_below >= target_height:
        return ModelPickerPopupPlacementMode.BELOW
    if available_above >= target_height:
        return ModelPickerPopupPlacementMode.ABOVE
    if available_above > available_below:
        return ModelPickerPopupPlacementMode.ABOVE
    return ModelPickerPopupPlacementMode.BELOW


def _vertical_geometry_for_mode(
    *,
    mode: ModelPickerPopupPlacementMode,
    anchor_top: int,
    anchor_bottom: int,
    available_below: int,
    available_above: int,
    preferred_height: int,
    safe_top: int,
    safe_bottom: int,
) -> tuple[int, int]:
    """Return top and height for one resolved placement mode."""

    target_height = max(1, preferred_height)
    if mode is ModelPickerPopupPlacementMode.BELOW:
        height = min(target_height, max(1, available_below))
        return anchor_bottom, height
    if mode is ModelPickerPopupPlacementMode.ABOVE:
        height = min(target_height, max(1, available_above))
        return anchor_top - height, height

    height = min(target_height, max(1, safe_bottom - anchor_bottom))
    return anchor_bottom, height


def _clamp(value: int, lower: int, upper: int) -> int:
    """Clamp a value into an inclusive range, tolerating reversed bounds."""

    if upper < lower:
        return lower
    return max(lower, min(value, upper))


__all__ = [
    "MODEL_PICKER_POPUP_HEIGHT",
    "MODEL_PICKER_POPUP_MARGIN",
    "MODEL_PICKER_POPUP_MIN_HEIGHT",
    "MODEL_PICKER_POPUP_MIN_WIDTH",
    "MODEL_PICKER_POPUP_WIDTH",
    "ModelPickerPopupPlacement",
    "ModelPickerPopupPlacementMode",
    "model_picker_screen_available_geometry",
    "resolve_model_picker_popup_placement",
]
