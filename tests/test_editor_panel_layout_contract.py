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

"""Behavior contracts for editor-panel workspace layout margins."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.panel.content_gutter_controller import (
    CANVAS_ADJACENT_GUTTER,
    CUBE_STACK_ADJACENT_GUTTER,
    DIRECT_WORKFLOW_LEFT_GUTTER,
    EditorPanelContentGutterController,
)
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
)


def _application() -> QApplication:
    """Return the QApplication required for real content-margin behavior."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_editor_panel_content_gutters_follow_stack_availability_progress() -> None:
    """Direct mode should match the fixed left gutter to the leading section gap."""

    _application()
    content = QWidget()
    controller = EditorPanelContentGutterController(content)

    assert controller.horizontal_gutters() == (
        CUBE_STACK_ADJACENT_GUTTER,
        CANVAS_ADJACENT_GUTTER,
    )
    controller.apply_cube_stack_unavailable_progress(0.5)
    assert controller.horizontal_gutters() == (7, CANVAS_ADJACENT_GUTTER)
    controller.apply_cube_stack_unavailable_progress(1.0)
    assert controller.horizontal_gutters() == (
        DIRECT_WORKFLOW_LEFT_GUTTER,
        CANVAS_ADJACENT_GUTTER,
    )
    assert DIRECT_WORKFLOW_LEFT_GUTTER == EDITOR_SECTION_GAP
