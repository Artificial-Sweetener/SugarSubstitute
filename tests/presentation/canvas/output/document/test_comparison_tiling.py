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

"""Abuse tiled Output comparisons through the public document owner."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from cutecanvas import ExecutionRuntime

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from tests.presentation.canvas.output.document.tiling_support import (
    ComparisonPaneProbe,
    abuse_comparison_pan,
    normalized_pattern_image,
    wait_for_dense_pixels,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_output_comparison_tiling_survives_pair_navigation_and_resize(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Reject stale or cross-source tiles throughout mounted Output comparison churn."""

    application = _application()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    fixtures = (
        (
            QSize(2048, 1536),
            (QColor("#f5222d"), QColor("#13c2c2"), QColor("#faad14")),
        ),
        (
            QSize(4096, 3072),
            (QColor("#2f54eb"), QColor("#fadb14"), QColor("#eb2f96")),
        ),
        (
            QSize(3072, 2304),
            (QColor("#52c41a"), QColor("#722ed1"), QColor("#fa8c16")),
        ),
    )
    images = tuple(
        normalized_pattern_image(size, palette) for size, palette in fixtures
    )
    image_ids = tuple(uuid4() for _image in images)
    try:
        for image_id, image in zip(image_ids, images, strict=True):
            assert document.admit_image(image_id, image)
        composition_ids = tuple(
            document.composition_id_for(image_id) for image_id in image_ids
        )
        assert all(composition_id is not None for composition_id in composition_ids)
        sources = {
            cast(UUID, composition_id): image
            for composition_id, image in zip(
                composition_ids,
                images,
                strict=True,
            )
        }
        document.workspace.resize(960, 640)
        document.workspace.show()

        for iteration in range(12):
            primary_index = iteration % len(image_ids)
            secondary_index = (iteration + 1) % len(image_ids)
            split_position = ((iteration * 23) % 101) / 100.0
            orientation = "vertical" if iteration % 2 else "horizontal"
            assert document.present_comparison(
                image_ids[primary_index],
                image_ids[secondary_index],
                split_position=split_position,
                orientation=orientation,
            )
            application.processEvents()
            pane_widget = document.workspace.currentCanvas()
            assert pane_widget is not None
            pane = cast(ComparisonPaneProbe, pane_widget)
            document.workspace.resize(
                803 + iteration * 11,
                581 + (iteration * 13) % 79,
            )
            application.processEvents()
            pane.viewport.setZoomAndPan(
                1.15 + (iteration % 4) * 0.41,
                QPointF(
                    float((iteration * 47) % 211 - 105),
                    float((iteration * 31) % 167 - 83),
                ),
            )
            if iteration % 4 == 3:
                abuse_comparison_pan(application, pane_widget)
            wait_for_dense_pixels(
                pane,
                sources,
                horizontal=orientation == "horizontal",
            )
    finally:
        document.close()
        destroy_qt_object(document)


def _application() -> QApplication:
    """Return the existing Qt application required by mounted Output tests."""

    application = QApplication.instance()
    return application if isinstance(application, QApplication) else QApplication([])
