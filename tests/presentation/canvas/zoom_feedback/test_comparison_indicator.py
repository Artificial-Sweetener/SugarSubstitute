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

"""Test mounted comparison-canvas zoom feedback."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize
from PySide6.QtWidgets import QApplication
from cutecanvas import CanvasComparisonOverlayState, CanvasDocument, CanvasWorkspace
import pytest

from substitute.presentation.canvas.shared.canvas_comparison_zoom_indicator import (
    CanvasComparisonZoomIndicator,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import CanvasZoomScale
from tests.presentation.canvas.zoom_feedback.support import (
    RecordingPainter,
    double_click_event,
    image,
    wheel_event,
)
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.mark.parametrize("gesture_kind", ("wheel", "double_click"))
def test_real_comparison_gestures_show_independent_source_scales(
    gesture_kind: str,
) -> None:
    """Exercise mounted comparison interaction and its two-layer geometry."""

    ensure_qt_application()
    document = CanvasDocument()
    primary_id = document.create_composition_from_image(image(QSize(320, 240)))
    secondary_id = document.create_composition_from_image(image(QSize(800, 300)))
    workspace = CanvasWorkspace(document=document, features=())
    indicator = CanvasComparisonZoomIndicator(workspace)
    observed: list[CanvasComparisonOverlayState] = []
    try:
        workspace.resize(800, 600)
        workspace.registerComparisonOverlay(
            "test-comparison-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        workspace.setComparisonPresentation(primary_id, secondary_id)
        workspace.show()
        wait_for_qt_condition(workspace.isVisible)
        activate_widget_layouts(workspace)
        surface = workspace.currentCanvas()
        assert surface is not None
        pointer = QPointF(200.0, 150.0)
        event = (
            wheel_event(surface, pointer)
            if gesture_kind == "wheel"
            else double_click_event(surface, pointer)
        )

        QApplication.sendEvent(surface, event)

        wait_for_qt_condition(lambda: indicator.opacity == 1.0)
        surface.grab()
        assert observed
        state = observed[-1]
        painter = RecordingPainter()
        indicator.draw(painter, state)  # type: ignore[arg-type]
        expected = [
            CanvasZoomScale(
                state.primary_scale.horizontal,
                state.primary_scale.vertical,
            ).label(),
            CanvasZoomScale(
                state.secondary_scale.horizontal,
                state.secondary_scale.vertical,
            ).label(),
        ]
        assert painter.texts == expected
        assert painter.texts[0] != painter.texts[1]
        assert state.divider.visible_segment is not None
        divider_x = state.divider.visible_segment.x1()
        assert painter.rounded_bounds[0].right() < divider_x
        assert painter.rounded_bounds[1].left() > divider_x
    finally:
        indicator.close()
        workspace.close()
        destroy_qt_object(workspace)
        document.close()
