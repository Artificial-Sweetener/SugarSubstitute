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

"""Verify synthetic canvas resolution dialog interaction and defaults."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import themeColor  # type: ignore[import-untyped]


from substitute.domain.workflow import (
    SyntheticCanvasAnchor,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from substitute.presentation.dialogs.synthetic_canvas_anchor_button import (
    SyntheticCanvasAnchorButton,
)
from tests.presentation.dialogs.synthetic_resolution.support import (
    _activate_hidden_dialog_layout,
    _app,
    _role,
)


def test_center_anchor_renders_a_large_live_accent_dot() -> None:
    """The center anchor should remain legible as an accent-colored spatial mark."""

    app = _app()
    parent = QWidget()
    parent.resize(1200, 900)
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=parent,
    )
    _activate_hidden_dialog_layout(dialog)

    buttons = dialog.findChildren(SyntheticCanvasAnchorButton)
    assert len(buttons) == 9
    center_button = next(button for button in buttons if button.isChecked())
    image = center_button.grab().toImage()
    center = center_button.rect().center()
    accent = QColor(themeColor())
    assert image.pixelColor(center).rgb() == accent.rgb()
    assert image.pixelColor(center + QPoint(4, 0)).rgb() == accent.rgb()

    bottom_left = next(
        button
        for button in buttons
        if button.anchor is SyntheticCanvasAnchor.BOTTOM_LEFT
    )
    bottom_left.click()
    app.processEvents()
    assert bottom_left.isChecked()
    assert not center_button.isChecked()
    selected_image = bottom_left.grab().toImage()
    assert selected_image.pixelColor(bottom_left.rect().center()).rgb() == accent.rgb()
    former_center_image = center_button.grab().toImage()
    white = QColor(255, 255, 255)
    assert former_center_image.pixelColor(center_button.rect().center()).rgb() == (
        white.rgb()
    )
    assert (
        former_center_image.pixelColor(
            center_button.rect().center() + QPoint(4, 0)
        ).alpha()
        < 255
    )


def test_dialog_preserves_the_fluent_modal_backing_surface() -> None:
    """The dialog body should retain the primitive-owned opaque surface styling."""

    app = _app()
    parent = QWidget()
    parent.resize(1200, 900)
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=parent,
    )
    _activate_hidden_dialog_layout(dialog)
    dialog.widget.repaint()
    app.processEvents()

    assert dialog.widget.objectName() == "centerWidget"
    surface_image = dialog.widget.grab().toImage()
    assert surface_image.pixelColor(QPoint(12, 12)).alpha() == 255
