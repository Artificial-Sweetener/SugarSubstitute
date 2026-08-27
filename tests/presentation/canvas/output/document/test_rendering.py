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

"""Verify Output image and percentage-overlay rendering."""

from __future__ import annotations

from uuid import uuid4
from pytest import approx
from PySide6.QtCore import QLineF, QPointF, QRect, QSize
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import QApplication
from cutecanvas import (
    CanvasComparison,
    CanvasComparisonDivider,
    CanvasComparisonOverlayState,
    CanvasComparisonScale,
    CanvasComparisonZoomGesture,
    ComparisonOrientation,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CANVAS_ZOOM_INDICATOR_OVERLAY_NAME,
)
from cutecanvas import ExecutionRuntime
from tests.support.qt.lifecycle import destroy_qt_object

from .rendering_support import _ZoomOverlayPainter, _wait_for_rendered_color
from .support import (
    _sized_image,
    _app,
    _wheel_event,
    _projection,
    _linked_projection,
    _session,
)


def test_output_canvas_renders_an_admitted_final_image_offscreen(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Render received final pixels after single-to-grid presentation reflow."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    expected = QColor("red")
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(960, 1344)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(960, 1344)),
        )
        canvas.bind_projection_session(
            _session(boundary, _linked_projection(first_id, second_id))
        )

        composition_id = canvas.document.composition_id_for(first_id)
        second_composition_id = canvas.document.composition_id_for(second_id)
        assert composition_id is not None
        assert second_composition_id is not None
        target = canvas.workspace.canvasFor(composition_id)
        assert target is not None
        assert _wait_for_rendered_color(app, target, expected)
        groups = canvas.workspace.session.inspection.groups()
        assert len(groups) == 1
        assert groups[0].members == (composition_id, second_composition_id)
        target.applyZoom(target.currentZoom() * 1.5)
        canvas.document.present_single(second_id)
        app.processEvents()
        linked_detail = canvas.workspace.canvasFor(second_composition_id)
        assert linked_detail is not None
        assert linked_detail.currentZoom() == approx(target.currentZoom(), rel=1e-12)

        assert canvas.document.present_grid((first_id, second_id))
        assert canvas.document.present_single(first_id)
        assert _wait_for_rendered_color(app, target, expected)
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_output_attaches_a_percentage_overlay_to_every_active_detail_image(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Show the established cursor-relative percentage for each active Output image."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(960, 1344)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(960, 1344)),
        )
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None
        first_target = canvas.workspace.canvasFor(first_composition)
        assert first_target is not None
        indicators = canvas._zoom_indicators._indicators
        first_indicator = indicators.get(first_target)
        assert first_indicator is not None
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in first_target.contentOverlays()

        position = QPointF(first_target.rect().center())
        first_zoom = first_target.currentZoom()
        QApplication.sendEvent(first_target, _wheel_event(first_target, position))
        first_target.applyZoom(first_zoom * 1.25)
        app.processEvents()
        assert first_target.currentZoom() > first_zoom
        assert first_indicator.opacity == 1.0

        assert canvas.document.present_single(second_id)
        app.processEvents()
        second_target = canvas.workspace.canvasFor(second_composition)
        assert second_target is not None
        second_indicator = indicators.get(second_target)
        assert second_indicator is not None
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in second_target.contentOverlays()
        second_position = QPointF(second_target.rect().center())
        second_zoom = second_target.currentZoom()
        QApplication.sendEvent(
            second_target,
            _wheel_event(second_target, second_position),
        )
        second_target.applyZoom(second_zoom * 1.25)
        app.processEvents()
        assert second_target.currentZoom() > second_zoom
        assert second_indicator.opacity == 1.0
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_output_comparison_paints_one_percentage_on_each_side_of_the_divider(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Paint independent source-scale badges on their matching comparison sides."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    try:
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(32, 24)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(64, 24)),
        )
        canvas.resize(800, 600)
        canvas.show()
        assert canvas.document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None
        indicator = canvas._zoom_indicators._comparison_indicator
        divider = CanvasComparisonDivider(
            enabled=True,
            split_position=0.5,
            orientation=ComparisonOrientation.VERTICAL,
            visible_segment=QLineF(400.0, 0.0, 400.0, 600.0),
            full_segment=QLineF(400.0, 0.0, 400.0, 600.0),
        )
        canvas.workspace.comparisonZoomGesture.emit(
            CanvasComparisonZoomGesture(QPointF(200.0, 150.0), 1.25)
        )
        painter = _ZoomOverlayPainter()
        indicator.draw(
            painter,
            CanvasComparisonOverlayState(
                comparison=CanvasComparison(
                    first_composition,
                    second_composition,
                    0.5,
                    ComparisonOrientation.VERTICAL,
                ),
                divider=divider,
                viewport=QRect(0, 0, 800, 600),
                primary_scale=CanvasComparisonScale(2.0, 2.0),
                secondary_scale=CanvasComparisonScale(1.0, 2.0),
            ),
        )

        assert len(painter.texts) == 2
        assert len(painter.bounds) == 2
        assert painter.texts[0] != painter.texts[1]
        assert painter.bounds[0].right() < 400.0
        assert painter.bounds[1].left() > 400.0
    finally:
        canvas.close()
        destroy_qt_object(canvas)
