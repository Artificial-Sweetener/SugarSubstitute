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

"""Verify Output grid, detail, and comparison presentation contracts."""

from __future__ import annotations

from typing import cast
from uuid import uuid4
from pytest import approx
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
)
from PySide6.QtTest import QTest
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapCoordinator,
)
from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    resolved_backdrop_mode,
)
from cutecanvas import ExecutionRuntime
from tests.support.qt.lifecycle import destroy_qt_object

from .comparison_support import (
    _NativeComparisonProbe,
    _wait_for_comparison_colors,
)
from .support import (
    _image,
    _sized_image,
    _app,
)


def test_output_presentations_keep_grid_detail_and_comparison_viewports_independent(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Output presentation changes must never transfer viewport state across roles."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = (uuid4(), uuid4(), uuid4())
    try:
        for image_id, color in zip(image_ids, ("red", "blue", "green"), strict=True):
            assert document.admit_image(image_id, _image(color))
        document.workspace.resize(900, 600)
        document.workspace.show()

        assert document.present_grid(image_ids)
        app.processEvents()
        first_composition = document.composition_id_for(image_ids[0])
        assert first_composition is not None
        grid_canvas = document.workspace.canvasFor(first_composition)
        assert grid_canvas is not None
        grid_zoom = grid_canvas.currentZoom()

        assert document.present_single(image_ids[0])
        app.processEvents()
        detail_canvas = document.workspace.canvasFor(first_composition)
        assert detail_canvas is not None
        assert detail_canvas is not grid_canvas
        detail_canvas.applyZoom(detail_canvas.currentZoom() * 1.5)
        detail_zoom = detail_canvas.currentZoom()

        assert document.present_grid(image_ids)
        app.processEvents()
        assert document.workspace.canvasFor(first_composition) is grid_canvas
        assert grid_canvas.currentZoom() == grid_zoom

        assert document.present_comparison(
            image_ids[0],
            image_ids[1],
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        second_composition = document.composition_id_for(image_ids[1])
        assert second_composition is not None
        comparison_widget = document.workspace.currentCanvas()
        assert comparison_widget is not None
        assert comparison_widget is not grid_canvas
        assert comparison_widget is not detail_canvas
        comparison_pane = cast(_NativeComparisonProbe, comparison_widget)
        assert tuple(entry.entry_id for entry in comparison_pane.catalog().entries) == (
            first_composition,
            second_composition,
        )
        assert comparison_pane.comparisonState().source_id == second_composition
        assert tuple(
            group.members for group in comparison_pane.linkedImageGroups()
        ) == ((first_composition, second_composition),)
        comparison_pane.applyZoom(comparison_pane.currentZoom() * 1.5)
        app.processEvents()
        assert detail_canvas.currentZoom() == detail_zoom
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_comparison_uses_one_native_scene_without_mask_or_geometry_churn(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Drag the native divider while retaining one fitted QPane viewport widget."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()
    try:
        source_size = QSize(320, 240)
        assert document.admit_image(first_id, _sized_image("red", source_size))
        assert document.admit_image(second_id, _sized_image("blue", source_size))
        assert document.admit_image(third_id, _sized_image("green", source_size))
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()

        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        assert pane.viewport.get_zoom_mode().value == "fit"
        assert pane.currentZoom() == approx(pane.viewport.computeFitZoom())
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
        geometry = pane_widget.geometry()
        assert pane_widget.mask().isEmpty()
        divider = pane.comparisonDividerState()
        assert divider.enabled is True
        assert divider.full_segment is not None
        start = divider.full_segment.pointAt(0.5).toPoint()
        destination = QPoint(
            min(pane_widget.width() - 2, start.x() + 80),
            start.y(),
        )

        QTest.mousePress(pane_widget, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(pane_widget, destination)
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.LeftButton,
            pos=destination,
        )
        app.processEvents()

        assert pane_widget.geometry() == geometry
        assert pane_widget.mask().isEmpty()
        state = pane.comparisonState()
        assert state.split_position > 0.5
        presentation = document.workspace.session.presentation
        assert presentation.comparison is not None
        assert presentation.comparison.split_position == state.split_position
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=state.split_position,
            orientation="horizontal",
        )
        app.processEvents()
        assert document.workspace.currentCanvas() is pane_widget
        assert pane.comparisonState().orientation.value == "horizontal"
        pane.applyZoom(pane.currentZoom() * 1.5)
        pan_before = pane.currentPan()
        pan_start = QPoint(pane_widget.width() // 4, pane_widget.height() // 2)
        pan_destination = pan_start + QPoint(47, 19)
        QTest.mousePress(pane_widget, Qt.MouseButton.LeftButton, pos=pan_start)
        app.sendEvent(
            pane_widget,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(pan_destination),
                QPointF(pane_widget.mapToGlobal(pan_destination)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.LeftButton,
            pos=pan_destination,
        )
        app.processEvents()
        comparison_pan = pane.currentPan()
        assert comparison_pan != pan_before
        comparison_zoom = pane.currentZoom()
        assert document.present_comparison(
            second_id,
            third_id,
            split_position=0.4,
            orientation="vertical",
        )
        app.processEvents()
        assert document.workspace.currentCanvas() is pane_widget
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("blue"),
            secondary=QColor("green"),
        )
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=state.split_position,
            orientation="vertical",
        )
        app.processEvents()
        restored_widget = document.workspace.currentCanvas()
        assert restored_widget is pane_widget
        assert restored_widget is not None
        restored = cast(_NativeComparisonProbe, restored_widget)
        current_entry = restored.catalog().current
        assert current_entry is not None
        assert current_entry.entry_id == document.composition_id_for(first_id)
        assert restored.comparisonState().source_id == document.composition_id_for(
            second_id
        )
        assert restored.currentZoom() == approx(comparison_zoom)
        restored_pan = restored.currentPan()
        assert restored_pan.x() == approx(comparison_pan.x())
        assert restored_pan.y() == approx(comparison_pan.y())
        restored.setZoomFit()
        assert _wait_for_comparison_colors(
            app,
            restored_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_comparison_zoom_stops_when_slower_side_reaches_1000_percent(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Preserve QPane's source-relative comparison ceiling through CuteCanvas."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    primary_id = uuid4()
    secondary_id = uuid4()
    try:
        assert document.admit_image(
            primary_id,
            _sized_image("red", QSize(320, 240)),
        )
        assert document.admit_image(
            secondary_id,
            _sized_image("blue", QSize(640, 480)),
        )
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            primary_id,
            secondary_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()

        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        pane.applyZoom(1000.0)
        app.processEvents()

        assert pane.currentZoom() == approx(20.0)
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_comparison_preserves_the_original_two_pixel_material_seam(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep the two-pixel Output divider on the transformed comparison seam."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    first_id = uuid4()
    second_id = uuid4()
    overlay: OutputCompareMaterialGapCoordinator | None = None
    try:
        assert document.admit_image(first_id, _sized_image("red", QSize(640, 480)))
        assert document.admit_image(second_id, _sized_image("blue", QSize(1280, 960)))
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=0.35,
            orientation="vertical",
        )
        app.processEvents()

        overlay = OutputCompareMaterialGapCoordinator(document.workspace)
        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        fit_divider = pane.comparisonDividerState()
        assert fit_divider.visible_segment is not None
        fit_divider_x = fit_divider.visible_segment.x1()
        pane.viewport.setZoomAndPan(1.5, QPointF(70.0, -35.0))
        app.processEvents()
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
        image = pane_widget.grab().toImage()
        divider = pane.comparisonDividerState()
        assert divider.visible_segment is not None
        assert divider.visible_segment.x1() != approx(fit_divider_x)
        point = divider.visible_segment.pointAt(0.5).toPoint()
        material = QColor(
            *body_material_wash_color(resolved_backdrop_mode(document.workspace))
        )
        seam_colors = [
            image.pixelColor(x, point.y()) for x in range(point.x() - 2, point.x() + 3)
        ]
        assert sum(color.name() == material.name() for color in seam_colors) == 2
        assert QColor("red") in seam_colors
        assert QColor("blue") in seam_colors
    finally:
        if overlay is not None:
            overlay.close()
        document.close()
        destroy_qt_object(document)
