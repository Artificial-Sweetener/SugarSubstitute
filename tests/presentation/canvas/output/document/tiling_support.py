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

"""Provide the typed rendering oracle for hostile Output comparison tiling."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QApplication, QWidget

from tests.support.qt.semantic_wait import wait_for_qt_condition


class StrategyProbe(Protocol):
    """Expose a renderer strategy without importing its implementation package."""

    @property
    def value(self) -> str:
        """Return the stable strategy value."""


class SourceProbe(Protocol):
    """Expose the stable source identity carried by one render item."""

    @property
    def resource_id(self) -> UUID:
        """Return the source identity."""


class DescriptorProbe(Protocol):
    """Expose the source metadata needed for pixel verification."""

    @property
    def source(self) -> SourceProbe:
        """Return the rendered source."""


class CoordinateSpaceProbe(Protocol):
    """Expose the stable name of one renderer-neutral coordinate space."""

    @property
    def value(self) -> str:
        """Return the serialized coordinate-space name."""


class ClipProbe(Protocol):
    """Expose normalized scene reveal geometry."""

    coordinate_space: CoordinateSpaceProbe
    x: float
    y: float
    width: float
    height: float


class PlacementProbe(Protocol):
    """Expose one scene-space render-item placement."""

    x: float
    y: float
    width: float
    height: float


class RenderItemProbe(Protocol):
    """Expose immutable frame geometry needed by the abuse oracle."""

    descriptor: DescriptorProbe
    transform: QTransform
    clip: ClipProbe | None
    placement: PlacementProbe
    source_size: QSize


class RasterRenderItemProbe(RenderItemProbe, Protocol):
    """Expose one pyramid-backed raster tile plan."""

    strategy: StrategyProbe
    pyramid_scale: float
    visible_tile_range: tuple[int, int, int, int] | None
    tiles_to_draw: tuple[object, ...]


class RenderPlanProbe(Protocol):
    """Expose one settled comparison frame."""

    qpane_rect: QRectF
    scene_bounds: PlacementProbe
    render_items: tuple[RenderItemProbe, ...]


class ViewportProbe(Protocol):
    """Expose exact mounted navigation for hostile fixture setup."""

    def setZoomAndPan(self, zoom: float, pan: QPointF) -> None:  # noqa: N802
        """Apply one exact zoom and pan."""


class ComparisonPaneProbe(Protocol):
    """Expose only the native comparison behavior owned by CuteCanvas."""

    viewport: ViewportProbe

    def calculateRenderPlan(self) -> RenderPlanProbe | None:  # noqa: N802
        """Return the current immutable render plan."""

    def grab(self) -> QPixmap:
        """Capture the current settled widget pixels."""


def abuse_comparison_pan(application: QApplication, pane: QWidget) -> None:
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
        send(
            QEvent.Type.MouseButtonRelease,
            start + delta,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )


def normalized_pattern_image(
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


def wait_for_dense_pixels(
    pane: ComparisonPaneProbe,
    sources: dict[UUID, QImage],
    *,
    horizontal: bool,
) -> None:
    """Require coherent pixels through every frame until all tiles arrive."""

    def dense_pixels_are_complete() -> bool:
        """Validate the current frame and report terminal tile completeness."""

        plan = pane.calculateRenderPlan()
        assert plan is not None
        assert len(plan.render_items) == 2
        assert all(_uses_dense_tile_product(item) for item in plan.render_items)
        frame = pane.grab().toImage()
        mismatch = _first_mismatch(plan, frame, sources, horizontal=horizontal)
        assert mismatch is None, mismatch
        return all(_visible_tiles_complete(item) for item in plan.render_items)

    wait_for_qt_condition(dense_pixels_are_complete, timeout_ms=5_000)


def _visible_tiles_complete(item: RenderItemProbe) -> bool:
    """Return whether every tile in one visible range has arrived."""

    sampled_tiles = getattr(item, "tiles", None)
    if isinstance(sampled_tiles, tuple):
        return bool(sampled_tiles)
    raster_item = cast(RasterRenderItemProbe, item)
    visible_range = raster_item.visible_tile_range
    if visible_range is None:
        return True
    start_row, end_row, start_column, end_column = visible_range
    expected = (end_row - start_row + 1) * (end_column - start_column + 1)
    return len(raster_item.tiles_to_draw) == expected


def _uses_dense_tile_product(item: RenderItemProbe) -> bool:
    """Accept pyramid tiles or the native sampled-tile replacement contract."""

    strategy = getattr(item, "strategy", None)
    if strategy is not None:
        return cast(StrategyProbe, strategy).value == "tile"
    return isinstance(getattr(item, "tiles", None), tuple)


def _first_mismatch(
    plan: RenderPlanProbe,
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
            primary_point = primary_product_point / _source_product_scale(primary)
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
            if not _matches_reconstructed_source(expected, actual):
                return point, expected, actual
    return None


def _source_product_scale(item: RenderItemProbe) -> float:
    """Map pyramid products to source pixels while native samples stay source-local."""

    scale = getattr(item, "pyramid_scale", 1.0)
    if not isinstance(scale, (int, float)):
        raise TypeError("render-item source product scale must be numeric")
    return max(float(scale), 1e-9)


def _matches_reconstructed_source(expected: QColor, actual: QColor) -> bool:
    """Allow only the one-channel-step quantization of encoded raster reconstruction."""

    return (
        max(
            abs(expected.red() - actual.red()),
            abs(expected.green() - actual.green()),
            abs(expected.blue() - actual.blue()),
            abs(expected.alpha() - actual.alpha()),
        )
        <= 1
    )


def _projected_comparison_divider(
    plan: RenderPlanProbe,
    item: RenderItemProbe,
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
