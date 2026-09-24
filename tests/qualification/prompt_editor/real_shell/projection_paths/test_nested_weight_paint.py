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

"""Qualify visible nested-weight paint beneath exact numeric input."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QWidget

from tests.presentation.editor.prompt_editor.interactions.weight.mounting import (
    start_exact_weight_edit,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def _render_projection_without_input(viewport: QWidget) -> QImage:
    """Render only the prepared projection layer, excluding child input widgets."""

    image = QImage(viewport.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("transparent"))
    painter = QPainter(image)
    try:
        viewport.render(
            painter,
            QPoint(),
            QRegion(),
            QWidget.RenderFlag.DrawWindowBackground,
        )
    finally:
        painter.end()
    return image


def _different_pixels(image: QImage, rect: QRectF) -> int:
    """Count foreground pixels inside a controlled weight-glyph region."""

    background = image.pixelColor(0, 0)
    return sum(
        image.pixelColor(x, y) != background
        for x in range(max(0, int(rect.left())), min(image.width(), int(rect.right())))
        for y in range(max(0, int(rect.top())), min(image.height(), int(rect.bottom())))
    )


def test_nested_exact_weight_edit_does_not_paint_a_second_number_beneath_input(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Hide the projected 2.80 while its native editable version owns that glyph area."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="((atmospheric:2.80) perspective:1.15), portrait"
    )
    real_shell_scenario.input.focus_editor(field)
    surface = surface_for(field.editor)
    token = next(
        item
        for item in surface.projection_document().tokens
        if item.value_text == "2.80"
    )
    weight_rect = surface.token_weight_text_rect(token)
    assert weight_rect is not None
    normal = _render_projection_without_input(surface.viewport())
    normal_ink = _different_pixels(normal, weight_rect)
    assert normal_ink > 5
    normal_state = real_shell_scenario.snapshots.capture(field, label="nested-weight")
    next_text = next(
        item
        for item in normal_state.visible_text_fragments
        if item.viewport_rect[0] >= weight_rect.right() - 0.75
        and item.viewport_rect[1]
        <= weight_rect.center().y()
        <= item.viewport_rect[1] + item.viewport_rect[3]
    )
    assert weight_rect.right() <= next_text.viewport_rect[0] + 0.75

    start_exact_weight_edit(field.editor, token)
    QApplication.processEvents()
    editing = _render_projection_without_input(surface.viewport())
    editing_ink = _different_pixels(editing, weight_rect)

    assert editing_ink < normal_ink / 3, (normal_ink, editing_ink)
    native_input = surface.exact_weight_editor
    native_input.setCursorPosition(len(native_input.text()))
    end_cursor = native_input.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
    assert isinstance(end_cursor, QRect)
    edit_text_right = (
        native_input.geometry().left() + end_cursor.left() + end_cursor.width() / 2.0
    )
    assert edit_text_right <= next_text.viewport_rect[0] + 1.0
