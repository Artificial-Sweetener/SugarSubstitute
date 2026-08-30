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

"""Provide deterministic media wall test values and mounted ownership."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from substitute.application.execution import (
    CancellationToken,
    ExecutionLaneSaturatedError,
    TaskRequest,
)
from substitute.domain.model_metadata import STANDARD_THUMBNAIL_ROLE, ThumbnailAsset
from substitute.presentation.widgets.media_wall import (
    MediaWallItem,
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
    MediaWallView,
    ThumbnailVariantReference,
)
from substitute.presentation.widgets.media_wall.media_wall_marquee import (
    TitleMarqueeState,
)
from substitute.presentation.widgets.media_wall.media_wall_painter import (
    paint_media_wall_tile,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from tests.support.execution import ManualTaskHandle
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition

TResult = TypeVar("TResult")


def ensure_qapp() -> QApplication:
    """Return the worker-owned Qt application."""

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        raise RuntimeError("Media wall tests require the session QApplication owner.")
    return application


def wait_for_preloader_idle(
    preloader: MediaWallThumbnailPreloader,
    *,
    timeout_ms: int = 1000,
) -> None:
    """Wait until the preloader's authoritative pending state clears."""

    wait_for_qt_condition(
        lambda: not preloader.has_pending_work(),
        timeout_ms=timeout_ms,
    )


class MediaWallOwner:
    """Own mounted media walls through synchronous native teardown."""

    def __init__(self) -> None:
        """Track views in construction order."""

        self._views: list[MediaWallView] = []

    def create(self, **kwargs: Any) -> MediaWallView:
        """Create and retain one configured production media wall."""

        view = MediaWallView(**kwargs)
        self._views.append(view)
        return view

    def destroy_all(self) -> None:
        """Destroy every retained wall in reverse construction order."""

        for view in reversed(self._views):
            destroy_qt_object(view)
        self._views.clear()


class CapacityLimitedTaskSubmitter:
    """Hold submitted work and reject requests beyond a shared capacity."""

    def __init__(self, *, capacity: int) -> None:
        """Create a deterministic bounded submitter."""

        self._capacity = capacity
        self._entries: list[
            tuple[TaskRequest[object], CancellationToken, ManualTaskHandle[object]]
        ] = []

    @property
    def submission_count(self) -> int:
        """Return the number of requests admitted by the fake lane."""

        return len(self._entries)

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Admit work while capacity is available or report saturation."""

        active_count = sum(not handle.is_finished for _, _, handle in self._entries)
        if active_count >= self._capacity:
            raise ExecutionLaneSaturatedError(
                lane_name="thumbnail_decode",
                queue_capacity=self._capacity,
            )
        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self._entries.append(
            (
                cast(TaskRequest[object], request),
                cancellation,
                cast(ManualTaskHandle[object], handle),
            )
        )
        return handle

    def complete_next(self) -> None:
        """Run and complete the oldest active request."""

        entry = next(
            (entry for entry in self._entries if not entry[2].is_finished),
            None,
        )
        if entry is None:
            raise AssertionError("Expected an active thumbnail request")
        request, cancellation, handle = entry
        try:
            result = request.work(cancellation)
        except BaseException as error:  # noqa: BLE001
            handle.complete_failed(error)
        else:
            handle.complete_success(result)


class CountingAssetRepository:
    """Count thumbnail asset reads while returning no asset."""

    def __init__(self) -> None:
        """Initialize the read counter."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one read and return no asset."""

        del storage_key
        self.reads += 1
        return None


class AssetRepository:
    """Return configured thumbnail assets and count reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store deterministic assets."""

        self.assets = assets
        self.reads_by_key: dict[str, int] = {}

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one read and return the configured asset."""

        self.reads_by_key[storage_key] = self.reads_by_key.get(storage_key, 0) + 1
        return self.assets.get(storage_key)


def wall_item(item_id: str, *, tooltip: str | None = None) -> MediaWallItem:
    """Return one minimal media wall item."""

    return MediaWallItem(
        item_id=item_id,
        title=item_id.title(),
        subtitle=None,
        aspect_ratio=0.72,
        thumbnail_variants=(thumbnail_variant(item_id),),
        payload=item_id,
        tooltip=tooltip,
    )


def square_wall_item(item_id: str) -> MediaWallItem:
    """Return one square media wall item."""

    return MediaWallItem(
        item_id=item_id,
        title=item_id.title(),
        subtitle=None,
        aspect_ratio=1.0,
        thumbnail_variants=(thumbnail_variant(item_id),),
        payload=item_id,
    )


def mouse_press_event(
    view: MediaWallView,
    point: QPoint,
    *,
    button: Qt.MouseButton,
) -> QMouseEvent:
    """Return one mouse-press event at a wall-local point."""

    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(point),
        QPointF(view.mapToGlobal(point)),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )


def mouse_move_event(view: MediaWallView, point: QPoint) -> QMouseEvent:
    """Return one mouse-move event at a viewport-local point."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(point),
        QPointF(view.viewport().mapToGlobal(point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def thumbnail_variant(
    storage_key: str,
    *,
    role: str = STANDARD_THUMBNAIL_ROLE,
) -> ThumbnailVariantReference:
    """Return one prepared thumbnail reference."""

    return ThumbnailVariantReference(
        storage_key=storage_key,
        size=10,
        width=10,
        height=10,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=400,
        role=role,
    )


def thumbnail_asset(storage_key: str, color: QColor) -> ThumbnailAsset:
    """Return one valid Qt-ready thumbnail asset."""

    image = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )


def install_ready_thumbnail(
    cache: MediaWallThumbnailCache,
    variants: tuple[ThumbnailVariantReference, ...],
    size: QSize,
    color: QColor,
) -> None:
    """Install one ready image into a media wall cache."""

    cache_key = cache.cache_key_for_variants(variants, size)
    assert cache_key is not None
    image = QImage(
        max(1, size.width()),
        max(1, size.height()),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(color)
    assert cache.install_ready_image(
        cache_key=cache_key,
        image=image,
        device_pixel_ratio=1.0,
        generation=cache.generation,
    )


def paint_wall_item_image(
    widget: MediaWallView,
    item: MediaWallItem,
    rect: QRect,
    *,
    title_marquee_state: TitleMarqueeState | None = None,
) -> QImage:
    """Render one item to an offscreen image."""

    image = QImage(rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("transparent"))
    painter = QPainter(image)
    try:
        paint_media_wall_tile(
            painter,
            widget,
            item=item,
            rect=rect,
            hovered=False,
            current=False,
            thumbnail_cache=MediaWallThumbnailCache(),
            title_marquee_state=title_marquee_state,
        )
    finally:
        painter.end()
    return image


def rect_images_differ(first: QImage, second: QImage, rect: QRect) -> bool:
    """Return whether two images differ inside one rectangle."""

    return any(
        first.pixelColor(x, y) != second.pixelColor(x, y)
        for y in range(rect.top(), rect.bottom() + 1)
        for x in range(rect.left(), rect.right() + 1)
    )


def find_pixel_different_from_background(
    image: QImage,
    background: QImage,
    rect: QRect,
) -> QPoint:
    """Return one rendered text pixel."""

    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            point = QPoint(x, y)
            if pixel_color_difference(image, background, point) > 0:
                return point
    raise AssertionError("Expected a text pixel inside the sampled rect")


def find_pixel_matching_background(
    image: QImage,
    background: QImage,
    rect: QRect,
) -> QPoint:
    """Return one unchanged background pixel."""

    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            point = QPoint(x, y)
            if image.pixelColor(point) == background.pixelColor(point):
                return point
    raise AssertionError("Expected a background pixel inside the sampled rect")


def pixel_color_difference(first: QImage, second: QImage, point: QPoint) -> int:
    """Return channel distance between two pixels."""

    first_color = first.pixelColor(point)
    second_color = second.pixelColor(point)
    return (
        abs(first_color.red() - second_color.red())
        + abs(first_color.green() - second_color.green())
        + abs(first_color.blue() - second_color.blue())
        + abs(first_color.alpha() - second_color.alpha())
    )
