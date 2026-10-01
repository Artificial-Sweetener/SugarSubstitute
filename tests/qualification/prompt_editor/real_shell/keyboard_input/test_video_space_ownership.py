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

"""Protect production prompt typing across visible and retained video pages."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtGui import QColor, QCursor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


@pytest.mark.parametrize("rich", [False, True])
@pytest.mark.parametrize("video_visible", [False, True])
def test_prompt_spaces_survive_video_hover(
    real_shell_scenario: PromptEditorRealShellScenario,
    tmp_path: Path,
    rich: bool,
    video_visible: bool,
) -> None:
    """Route Space to the mounted prompt while the mouse overlaps video geometry."""
    scenario = real_shell_scenario
    source = "bad anatomy, blurry"
    field = scenario.workflows.add_prompt_workflow(initial_text=source)
    scenario.input.set_rich_rendering(field, enabled=rich)
    scenario.input.set_source_cursor_position(field, len(source))
    canvas = scenario.shell.output_canvas
    assert canvas is not None
    image = QImage(320, 180, QImage.Format.Format_ARGB32)
    image.fill(QColor("coral"))
    path = tmp_path / "image.png"
    assert image.save(str(path))
    image_id = uuid4()
    assert canvas.document.admit_image(image_id, QImage(str(path)), path=path)
    assert canvas.document.present_single(image_id)
    scenario.shell.canvas_host.activate_canvas("Output", keyboard_focus=False)
    page = canvas.video_presentation.video_page
    canvas.video_presentation.widget.setCurrentWidget(page)
    scenario.wait_for_queued_delivery()
    if not video_visible:
        canvas.video_presentation.deactivate()
        scenario.wait_for_queued_delivery()
        assert canvas.workspace.isVisible()
        assert not page.isVisible()
    target = scenario.input.focus_editor(field)
    pointer_before = QCursor.pos()
    try:
        surface = page.render_surface
        QCursor.setPos(surface.mapToGlobal(surface.rect().center()))
        assert QApplication.focusWidget() is target
        QTest.keyClicks(target, " x y ")
        scenario.wait_for_queued_delivery()
        assert field.editor.toPlainText() == source + " x y "
        assert QApplication.focusWidget() is target
        assert not page.pan_zoom_active
    finally:
        QCursor.setPos(pointer_before)
