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

"""Test direct dimension aspect-ratio application."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QWidget

from substitute.application.node_behavior import DimensionFieldPair
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    AspectRatioPreset,
    DimensionRowBinding,
    DimensionSide,
    apply_aspect_ratio,
)
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.mark.parametrize(
    ("anchor_side", "preset", "width_value", "height_value", "expected"),
    [
        (DimensionSide.WIDTH, AspectRatioPreset("16:9", 16, 9), 1600, 100, (1600, 900)),
        (DimensionSide.HEIGHT, AspectRatioPreset("16:9", 16, 9), 100, 900, (1600, 900)),
        (DimensionSide.WIDTH, AspectRatioPreset("4:5", 4, 5), 800, 100, (800, 1000)),
        (DimensionSide.HEIGHT, AspectRatioPreset("4:5", 4, 5), 100, 1000, (800, 1000)),
        (DimensionSide.WIDTH, AspectRatioPreset("1:1", 1, 1), 512, 1000, (512, 512)),
        (DimensionSide.HEIGHT, AspectRatioPreset("1:1", 1, 1), 1000, 512, (512, 512)),
    ],
)
def test_preserves_anchor_side(
    qt_application_owner: QApplication,
    anchor_side: DimensionSide,
    preset: AspectRatioPreset,
    width_value: int,
    height_value: int,
    expected: tuple[int, int],
) -> None:
    """Update only the non-anchored side for each representative ratio."""

    _ = qt_application_owner
    parent = QWidget()
    width = _spinbox(parent, value=width_value)
    height = _spinbox(parent, value=height_value)
    try:
        apply_aspect_ratio(
            _binding(parent, width=width, height=height),
            anchor_side=anchor_side,
            preset=preset,
        )

        assert (width.value(), height.value()) == expected
    finally:
        destroy_qt_object(parent)


def test_ignores_non_numeric_values(qt_application_owner: QApplication) -> None:
    """Avoid partial writes when neither dimension contains a numeric value."""

    _ = qt_application_owner
    parent = QWidget()
    width = QLineEdit(parent)
    height = QLineEdit(parent)
    width.setText("wide")
    height.setText("tall")
    try:
        apply_aspect_ratio(
            _binding(parent, width=width, height=height),
            anchor_side=DimensionSide.WIDTH,
            preset=AspectRatioPreset("16:9", 16, 9),
        )

        assert width.text() == "wide"
        assert height.text() == "tall"
    finally:
        destroy_qt_object(parent)


def _spinbox(parent: QWidget, *, value: int) -> QSpinBox:
    """Build one bounded numeric dimension field."""

    spinbox = QSpinBox(parent)
    spinbox.setRange(0, 4096)
    spinbox.setValue(value)
    return spinbox


def _binding(
    parent: QWidget,
    *,
    width: QWidget,
    height: QWidget,
) -> DimensionRowBinding:
    """Build a direct source-dimension binding."""

    return DimensionRowBinding(
        pair=DimensionFieldPair(
            stem="source",
            width_key="source_width",
            height_key="source_height",
        ),
        width_widget=width,
        height_widget=height,
        width_column=QWidget(parent),
        height_column=QWidget(parent),
    )
