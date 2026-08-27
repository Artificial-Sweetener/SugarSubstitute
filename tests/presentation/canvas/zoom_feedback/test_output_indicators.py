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

"""Test output-canvas zoom-indicator lifetime ownership."""

from __future__ import annotations

from PySide6.QtCore import QSize
from cutecanvas import CanvasDocument, CanvasWorkspace

from substitute.presentation.canvas.output.output_canvas_zoom_indicators import (
    OutputCanvasZoomIndicators,
)
from tests.presentation.canvas.zoom_feedback.support import image
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_output_indicator_releases_canvas_after_native_canvas_destruction() -> None:
    """Drop the registry reference without touching an already-deleted canvas."""

    ensure_qt_application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(image(QSize(200, 120)))
    workspace = CanvasWorkspace(document=document, features=())
    indicators = OutputCanvasZoomIndicators(workspace)
    try:
        workspace.setSinglePresentation(composition_id)
        wait_for_qt_condition(lambda: workspace.currentCanvas() is not None)
        canvas = workspace.currentCanvas()
        assert canvas is not None
        assert canvas in indicators._indicators

        canvas.destroyed.disconnect()
        destroy_qt_object(canvas)
        indicators._release_canvas(canvas)

        assert canvas not in indicators._indicators
    finally:
        workspace.close()
        destroy_qt_object(workspace)
        document.close()
