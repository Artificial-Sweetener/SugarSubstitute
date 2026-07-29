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

"""Abuse tiled Output comparisons through SugarSubstitute's public document owner."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID, uuid4

from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap, QTransform
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument


class _StrategyProbe(Protocol):
    """Expose a renderer strategy without importing its implementation package."""

    @property
    def value(self) -> str:
        """Return the stable strategy value."""


class _SourceProbe(Protocol):
    """Expose the stable source identity carried by one render item."""

    @property
    def resource_id(self) -> UUID:
        """Return the source identity."""


class _DescriptorProbe(Protocol):
    """Expose the source metadata needed for pixel verification."""

    @property
    def source(self) -> _SourceProbe:
        """Return the rendered source."""


class _ClipProbe(Protocol):
    """Expose normalized scene reveal geometry."""

    coordinate_space: _CoordinateSpaceProbe
    x: float
    y: float
    width: float
    height: float


class _CoordinateSpaceProbe(Protocol):
    """Expose the stable name of one renderer-neutral coordinate space."""

    @property
    def value(self) -> str:
        """Return the serialized coordinate-space name."""


class _PlacementProbe(Protocol):
    """Expose one scene-space render-item placement."""

    x: float
    y: float
    width: float
    height: float


class _RenderItemProbe(Protocol):
    """Expose immutable frame geometry needed by the abuse oracle."""

    descriptor: _DescriptorProbe
    strategy: _StrategyProbe
    transform: QTransform
    pyramid_scale: float
    clip: _ClipProbe | None
    placement: _PlacementProbe
    source_size: QSize
    visible_tile_range: tuple[int, int, int, int] | None
    tiles_to_draw: tuple[object, ...]


class _RenderPlanProbe(Protocol):
    """Expose one settled comparison frame."""

    qpane_rect: QRectF
    scene_bounds: _PlacementProbe
    render_items: tuple[_RenderItemProbe, ...]


class _ViewportProbe(Protocol):
    """Expose exact mounted navigation for hostile fixture setup."""

    def setZoomAndPan(self, zoom: float, pan: QPointF) -> None:  # noqa: N802
        """Apply one exact zoom and pan."""


class _ComparisonPaneProbe(Protocol):
    """Expose only the native comparison behavior owned by CuteCanvas."""

    viewport: _ViewportProbe

    def calculateRenderPlan(self) -> _RenderPlanProbe | None:  # noqa: N802
        """Return the current immutable render plan."""

    def grab(self) -> QPixmap:
        """Capture the current settled widget pixels."""


def test_output_comparison_tiling_survives_pair_navigation_and_resize() -> None:
    """Reject stale or cross-source tiles throughout mounted Output comparison churn."""

    application = _application()
    document = OutputCanvasDocument()
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
        _normalized_pattern_image(size, palette) for size, palette in fixtures
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
            pane = cast(_ComparisonPaneProbe, pane_widget)
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
                _abuse_comparison_pan(application, pane_widget)
            _wait_for_dense_pixels(
                application,
                pane,
                sources,
                horizontal=orientation == "horizontal",
            )
    finally:
        document.close()
        application.processEvents()


def _application() -> QApplication:
    """Return the existing Qt application required by mounted Output tests."""

    application = QApplication.instance()
    return application if isinstance(application, QApplication) else QApplication([])


def _abuse_comparison_pan(application: QApplication, pane: QWidget) -> None:
    """Traverse a tiled comparison through repeated real drag samples."""

    start = QPoint(pane.width() * 3 // 4, pane.height() // 2)

    def send(
        event_type: QEvent.Type,
        position: QPoint,
        button: Qt.MouseButton,
        buttons: Qt.MouseButton,
    ) -> None:
        """Deliver one explicit held-button mouse sample."""

        application.sendEvent(
            pane,
            QMouseEvent(
                event_type,
                QPointF(position),
                QPointF(pane.mapToGlobal(position)),
                button,
                buttons,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

    for delta in (
        QPoint(420, -280),
        QPoint(420, -280),
        QPoint(420, -280),
        QPoint(-560, 360),
        QPoint(-560, 360),
        QPoint(-560, 360),
        QPoint(-560, 360),
        QPoint(480, -320),
        QPoint(480, -320),
    ):
        send(
            QEvent.Type.MouseButtonPress,
            start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
        for step in range(1, 13):
            send(
                QEvent.Type.MouseMove,
                start
                + QPoint(
                    delta.x() * step // 12,
                    delta.y() * step // 12,
                ),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
            )
            QTest.qWait(1)
        send(
            QEvent.Type.MouseButtonRelease,
            start + delta,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
        QTest.qWait(20)


def _normalized_pattern_image(
    size: QSize,
    palette: tuple[QColor, QColor, QColor],
) -> QImage:
    """Return a high-entropy normalized pattern independent of source resolution."""

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    columns = 29
    rows = 23
    try:
        for row in range(rows):
            top = round(row * size.height() / rows)
            bottom = round((row + 1) * size.height() / rows)
            for column in range(columns):
                left = round(column * size.width() / columns)
                right = round((column + 1) * size.width() / columns)
                painter.fillRect(
                    left,
                    top,
                    right - left,
                    bottom - top,
                    palette[(column * 7 + row * 11) % len(palette)],
                )
    finally:
        painter.end()
    return image


def _wait_for_dense_pixels(
    application: QApplication,
    pane: _ComparisonPaneProbe,
    sources: dict[UUID, QImage],
    *,
    horizontal: bool,
) -> None:
    """Require coherent pixels through every frame until all tiles arrive."""

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < 5_000:
        application.processEvents()
        plan = pane.calculateRenderPlan()
        assert plan is not None
        assert len(plan.render_items) == 2
        assert all(item.strategy.value == "tile" for item in plan.render_items)
        frame = pane.grab().toImage()
        mismatch = _first_mismatch(plan, frame, sources, horizontal=horizontal)
        assert mismatch is None, mismatch
        if all(_visible_tiles_complete(item) for item in plan.render_items):
            return
    raise AssertionError("comparison tiles did not settle within 5 seconds")


def _visible_tiles_complete(item: _RenderItemProbe) -> bool:
    """Return whether every tile in one visible range has arrived."""

    visible_range = item.visible_tile_range
    if visible_range is None:
        return True
    start_row, end_row, start_column, end_column = visible_range
    expected = (end_row - start_row + 1) * (end_column - start_column + 1)
    return len(item.tiles_to_draw) == expected


def _first_mismatch(
    plan: _RenderPlanProbe,
    frame: QImage,
    sources: dict[UUID, QImage],
    *,
    horizontal: bool,
) -> tuple[QPointF, QColor, QColor] | None:
    """Return the first wrong interior source-pattern sample in one frame."""

    primary, secondary = plan.render_items
    clip = secondary.clip
    assert clip is not None
    assert clip.coordinate_space.value == "normalized-scene"
    divider_x, divider_y = _projected_comparison_divider(plan, secondary)
    primary_source = sources[primary.descriptor.source.resource_id]
    inverse, invertible = primary.transform.inverted()
    assert invertible
    for y in range(19, frame.height() - 19, 37):
        for x in range(19, frame.width() - 19, 41):
            point = QPointF(float(x), float(y))
            revealed = y >= divider_y if horizontal else x >= divider_x
            primary_product_point = inverse.map(point)
            primary_point = primary_product_point / max(
                primary.pyramid_scale,
                1e-9,
            )
            normalized_x = primary_point.x() / primary_source.width()
            normalized_y = primary_point.y() / primary_source.height()
            if not (0.0 <= normalized_x < 1.0 and 0.0 <= normalized_y < 1.0):
                continue
            source = sources[
                (
                    secondary.descriptor.source.resource_id
                    if revealed
                    else primary.descriptor.source.resource_id
                )
            ]
            source_x = min(source.width() - 1, int(normalized_x * source.width()))
            source_y = min(source.height() - 1, int(normalized_y * source.height()))
            pattern_x = normalized_x * 29
            pattern_y = normalized_y * 23
            if (
                min(pattern_x % 1.0, 1.0 - pattern_x % 1.0) < 0.12
                or min(pattern_y % 1.0, 1.0 - pattern_y % 1.0) < 0.12
                or abs(x - divider_x) < 3.0
                or abs(y - divider_y) < 3.0
            ):
                continue
            expected = source.pixelColor(source_x, source_y)
            actual = frame.pixelColor(x, y)
            if actual != expected:
                return point, expected, actual
    return None


def _projected_comparison_divider(
    plan: _RenderPlanProbe,
    item: _RenderItemProbe,
) -> tuple[float, float]:
    """Project the normalized scene seam without importing the renderer package."""

    clip = item.clip
    assert clip is not None
    placement = item.placement
    scene_bounds = plan.scene_bounds
    source_size = item.source_size
    scene_x = scene_bounds.x + clip.x * scene_bounds.width
    scene_y = scene_bounds.y + clip.y * scene_bounds.height
    source_x = (scene_x - placement.x) * source_size.width() / placement.width
    source_y = (scene_y - placement.y) * source_size.height() / placement.height
    projected = item.transform.map(QPointF(source_x, source_y))
    return projected.x(), projected.y()
