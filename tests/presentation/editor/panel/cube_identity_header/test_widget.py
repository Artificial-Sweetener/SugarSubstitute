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

"""Tests for editor cube identity headers."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.panel.widgets.cube_title_label import (
    CubeTitleLabel,
)


def test_custom_alias_retains_target_model_without_adding_an_icon(
    qt_application_owner: QApplication,
) -> None:
    """Changing title text should preserve the model pill without an editor icon."""

    label = CubeTitleLabel("Text to Image")
    _ = qt_application_owner
    label.setTargetModel("SDXL")

    label.setTitleText("Hero Background")

    assert label.text() == "Hero Background"
    assert label.targetModel() == "SDXL"
    label.deleteLater()
