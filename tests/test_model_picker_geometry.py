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

"""Contract tests for shared model picker popup placement geometry."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QApplication

from substitute.presentation.widgets.model_picker.model_picker_geometry import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_MARGIN,
    MODEL_PICKER_POPUP_MIN_HEIGHT,
    MODEL_PICKER_POPUP_MIN_WIDTH,
    MODEL_PICKER_POPUP_WIDTH,
    ModelPickerPopupPlacementMode,
    model_picker_screen_available_geometry,
    resolve_model_picker_popup_placement,
)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for screen-geometry tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_popup_placement_uses_below_when_preferred_height_fits() -> None:
    """Popup should attach below the anchor when the preferred height fits."""

    anchor = QRect(120, 100, 208, 32)

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 800, 1000),
        anchor_rect=anchor,
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.mode is ModelPickerPopupPlacementMode.BELOW
    assert placement.geometry.top() == _exclusive_bottom(anchor)
    assert placement.geometry.top() >= _exclusive_bottom(anchor)
    assert _exclusive_bottom(placement.geometry) <= 1000 - MODEL_PICKER_POPUP_MARGIN


def test_popup_placement_uses_above_when_below_is_constrained() -> None:
    """Popup should attach above a low anchor instead of clamping over it."""

    anchor = QRect(100, 680, 208, 32)

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 640, 720),
        anchor_rect=anchor,
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.mode is ModelPickerPopupPlacementMode.ABOVE
    assert _exclusive_bottom(placement.geometry) <= anchor.top()
    assert placement.geometry.top() >= MODEL_PICKER_POPUP_MARGIN
    assert _exclusive_bottom(placement.geometry) == anchor.top()


def test_popup_placement_chooses_larger_attached_side_when_neither_fits_preferred() -> (
    None
):
    """Popup should attach to the larger useful side when preferred size cannot fit."""

    anchor = QRect(100, 410, 208, 32)

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 640, 760),
        anchor_rect=anchor,
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.mode is ModelPickerPopupPlacementMode.ABOVE
    assert placement.geometry.top() == MODEL_PICKER_POPUP_MARGIN
    assert _exclusive_bottom(placement.geometry) == anchor.top()


def test_popup_placement_shrinks_attached_when_neither_side_fits_minimum() -> None:
    """Popup should shrink on an attached side instead of detaching."""

    anchor = QRect(100, 180, 208, 40)

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 640, 400),
        anchor_rect=anchor,
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.mode is ModelPickerPopupPlacementMode.BELOW
    assert placement.geometry.top() == _exclusive_bottom(anchor)
    assert placement.geometry.height() == (
        400 - MODEL_PICKER_POPUP_MARGIN - _exclusive_bottom(anchor)
    )
    assert placement.geometry.top() >= anchor.top()


def test_popup_placement_clamps_horizontally_inside_boundary() -> None:
    """Popup should keep its right edge inside the boundary safe area."""

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 640, 900),
        anchor_rect=QRect(620, 100, 20, 32),
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.geometry.left() >= MODEL_PICKER_POPUP_MARGIN
    assert _exclusive_right(placement.geometry) == 640 - MODEL_PICKER_POPUP_MARGIN


def test_popup_placement_stays_inside_very_narrow_boundary() -> None:
    """Popup should prefer boundary containment over nominal minimum width."""

    placement = resolve_model_picker_popup_placement(
        boundary_rect=QRect(0, 0, 120, 500),
        anchor_rect=QRect(80, 100, 20, 32),
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.geometry.left() == MODEL_PICKER_POPUP_MARGIN
    assert _exclusive_right(placement.geometry) == 120 - MODEL_PICKER_POPUP_MARGIN


def test_popup_placement_uses_screen_boundary_coordinates() -> None:
    """Popup geometry should stay in the same global coordinate space as boundary."""

    boundary = QRect(1920, 40, 1600, 1000)
    anchor = QRect(2040, 120, 208, 32)

    placement = resolve_model_picker_popup_placement(
        boundary_rect=boundary,
        anchor_rect=anchor,
        preferred_width=MODEL_PICKER_POPUP_WIDTH,
        preferred_height=MODEL_PICKER_POPUP_HEIGHT,
        minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
        minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
    )

    assert placement.mode is ModelPickerPopupPlacementMode.BELOW
    assert placement.geometry.left() >= boundary.left() + MODEL_PICKER_POPUP_MARGIN
    assert placement.geometry.top() == _exclusive_bottom(anchor)
    assert _exclusive_right(placement.geometry) <= (
        boundary.left() + boundary.width() - MODEL_PICKER_POPUP_MARGIN
    )


def test_screen_available_geometry_uses_screen_at_anchor() -> None:
    """Screen helper should return available geometry for the anchor's screen."""

    app = ensure_qapp()
    screen = app.primaryScreen()
    if screen is None:
        pytest.skip("Qt did not provide a primary screen")
    available = screen.availableGeometry()
    anchor = QRect(available.center(), QSize(1, 1))

    assert model_picker_screen_available_geometry(anchor) == available


def _exclusive_bottom(rect: QRect) -> int:
    """Return the exclusive bottom edge for placement assertions."""

    return rect.top() + rect.height()


def _exclusive_right(rect: QRect) -> int:
    """Return the exclusive right edge for placement assertions."""

    return rect.left() + rect.width()
