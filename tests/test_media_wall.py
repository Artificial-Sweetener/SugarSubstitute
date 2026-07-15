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

"""Tests for reusable media wall layout and view behavior."""

from __future__ import annotations

from collections.abc import Callable
import os
import time
from typing import TypeVar, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QApplication
from qfluentwidgets import ScrollBar  # type: ignore[import-untyped]

from tests.execution_testing import ImmediateTaskSubmitter, ManualTaskHandle
from substitute.application.execution import (
    CancellationToken,
    ExecutionLaneSaturatedError,
    TaskRequest,
)
from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from substitute.presentation.widgets.cursor_tooltip_filter import CursorToolTipFilter
from substitute.presentation.widgets.media_wall import (
    JustifiedLayoutInput,
    JustifiedLayoutItem,
    MediaWallItem,
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
    MediaThumbnailReadinessStatus,
    MediaWallView,
    PickerJustifiedWallProfile,
    ThumbnailVariantReference,
    build_justified_rows,
    normalize_aspect_ratio,
)
from substitute.presentation.widgets.media_wall.media_wall_marquee import (
    TitleMarqueeState,
    resolve_title_marquee_state,
)
from substitute.presentation.widgets.media_wall.media_wall_painter import (
    paint_media_wall_tile,
    title_and_subtitle_rects,
)
from substitute.presentation.widgets.media_wall.media_wall_style import (
    media_wall_current_border,
    media_wall_hover_border,
)

TResult = TypeVar("TResult")


def ensure_qapp() -> QApplication:
    """Return a running Qt application for widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _wait_for_thumbnail_preloader_idle(
    preloader: MediaWallThumbnailPreloader,
    timeout_ms: int,
) -> bool:
    """Pump Qt events in tests until thumbnail preload work settles."""

    app = ensure_qapp()
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while preloader.has_pending_work() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    return not preloader.has_pending_work()


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int) -> bool:
    """Pump Qt events until a deterministic asynchronous condition is true."""

    app = ensure_qapp()
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    return predicate()


def test_justified_layout_fills_non_final_rows() -> None:
    """Non-final justified rows should visually fill the container width."""

    rows = build_justified_rows(
        JustifiedLayoutInput(
            items=tuple(
                JustifiedLayoutItem(
                    aspect_ratio=1.0 + (index % 3) * 0.25, payload=index
                )
                for index in range(16)
            ),
            container_width=420,
            target_row_height=110,
            min_row_height=90,
            max_row_height=130,
            gutter=4,
            minimum_tile_width=80,
        )
    )

    assert len(rows) > 1
    for row in rows[:-1]:
        occupied = sum(item.width for item in row.items) + (len(row.items) - 1) * 4
        assert round(occupied) == 420


def test_justified_layout_allows_ragged_final_row() -> None:
    """The final row may stay narrower than the container."""

    rows = build_justified_rows(
        JustifiedLayoutInput(
            items=tuple(
                JustifiedLayoutItem(aspect_ratio=0.7, payload=index)
                for index in range(5)
            ),
            container_width=500,
            target_row_height=120,
            min_row_height=100,
            max_row_height=140,
            gutter=4,
            minimum_tile_width=90,
        )
    )

    final_row = rows[-1]
    occupied = (
        sum(item.width for item in final_row.items) + (len(final_row.items) - 1) * 4
    )
    assert occupied <= 500


def test_normalize_aspect_ratio_handles_invalid_values() -> None:
    """Invalid aspect ratios should fall back safely."""

    assert normalize_aspect_ratio(0) == 0.72
    assert normalize_aspect_ratio(-1) == 0.72


def test_media_wall_filtering_does_not_load_thumbnails() -> None:
    """Replacing hidden wall items should not read thumbnail assets."""

    ensure_qapp()
    repository = _CountingAssetRepository()
    view = MediaWallView(asset_repository=repository)
    view.resize(400, 260)

    view.set_items((_wall_item("one"), _wall_item("two")))
    view.set_items((_wall_item("one"),))

    assert repository.reads == 0
    assert len(view.items()) == 1


def test_media_wall_thumbnail_cache_reuses_ready_pixmaps() -> None:
    """Cache hits should reuse GUI-thread pixmaps installed by preloaders."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    variants = (_thumbnail_variant("one"),)
    _install_ready_thumbnail(cache, variants, QSize(10, 10), QColor("red"))

    first = cache.pixmap_for_variants(variants, QSize(10, 10))
    second = cache.pixmap_for_variants(variants, QSize(10, 10))

    assert first is not None
    assert second is first


def test_media_wall_thumbnail_cache_evicts_least_recently_used_pixmaps() -> None:
    """The pixmap cache should use LRU eviction when it exceeds its byte budget."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=850)

    _install_ready_thumbnail(
        cache, (_thumbnail_variant("one"),), QSize(10, 10), QColor("red")
    )
    _install_ready_thumbnail(
        cache, (_thumbnail_variant("two"),), QSize(10, 10), QColor("green")
    )
    assert cache.pixmap_for_variants((_thumbnail_variant("one"),), QSize(10, 10))
    _install_ready_thumbnail(
        cache, (_thumbnail_variant("three"),), QSize(10, 10), QColor("blue")
    )

    assert cache.pixmap_for_variants((_thumbnail_variant("one"),), QSize(10, 10))
    assert cache.pixmap_for_variants((_thumbnail_variant("three"),), QSize(10, 10))
    assert (
        cache.pixmap_for_variants((_thumbnail_variant("two"),), QSize(10, 10)) is None
    )


def test_media_wall_thumbnail_preloader_marks_missing_assets_failed() -> None:
    """Missing thumbnail reads should become prompt-safe failed readiness."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("media wall thumbnail preloader can abort under Windows xdist")

    ensure_qapp()
    repository = _AssetRepository({})
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    variants = (_thumbnail_variant("missing"),)

    assert preloader.preload_pixmap_for_variants(variants, QSize(10, 10))
    assert _wait_for_thumbnail_preloader_idle(preloader, 1000)

    readiness = preloader.readiness_for_variants(variants, QSize(10, 10))
    assert repository.reads_by_key == {"missing": 1}
    assert readiness.status is MediaThumbnailReadinessStatus.FAILED
    assert readiness.storage_key == "missing"
    preloader.shutdown()


def test_media_wall_thumbnail_preloader_installs_cached_asset_immediately() -> None:
    """Closed model pickers should hydrate selected banners before first paint."""

    ensure_qapp()
    repository = _AssetRepository(
        {"banner": _thumbnail_asset("banner", QColor("blue"))}
    )
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    variants = (_thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)

    installed = preloader.install_pixmap_for_role_now(
        variants,
        BANNER_THUMBNAIL_ROLE,
        QSize(20, 12),
        device_pixel_ratio=1.25,
    )

    assert installed is True
    assert preloader.has_pending_work() is False
    assert repository.reads_by_key == {"banner": 1}
    pixmap = cache.pixmap_for_role(
        variants,
        BANNER_THUMBNAIL_ROLE,
        QSize(20, 12),
        device_pixel_ratio=1.25,
    )
    assert pixmap is not None
    assert pixmap.width() == 25
    assert pixmap.height() == 15
    assert pixmap.devicePixelRatioF() == 1.25
    preloader.shutdown()


def test_media_wall_thumbnail_preloader_bounds_submitted_work() -> None:
    """Visible thumbnail bursts should remain queued behind a small in-flight set."""

    ensure_qapp()
    repository = _AssetRepository(
        {
            key: _thumbnail_asset(key, QColor("blue"))
            for key in ("one", "two", "three", "four", "five")
        }
    )
    submitter = _CapacityLimitedTaskSubmitter(capacity=8)
    preloader = MediaWallThumbnailPreloader(
        cache=MediaWallThumbnailCache(maximum_bytes=32_000),
        asset_repository=repository,
        submitter=submitter,
        maximum_pending_requests=5,
        maximum_in_flight_requests=2,
    )

    for key in ("one", "two", "three", "four", "five"):
        assert preloader.preload_pixmap_for_variants(
            (_thumbnail_variant(key),),
            QSize(10, 10),
        )

    assert submitter.submission_count == 2
    assert preloader.has_pending_work()
    assert (
        preloader.preload_pixmap_for_variants(
            (_thumbnail_variant("five"),),
            QSize(10, 10),
        )
        is False
    )
    assert submitter.submission_count == 2

    for _ in range(5):
        submitter.complete_next()

    assert _wait_for_thumbnail_preloader_idle(preloader, 1000)
    assert repository.reads_by_key == {
        "one": 1,
        "two": 1,
        "three": 1,
        "four": 1,
        "five": 1,
    }
    preloader.shutdown()


def test_media_wall_thumbnail_preloaders_retry_shared_lane_saturation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent picker owners should eventually load without saturation tracebacks."""

    ensure_qapp()
    repository = _AssetRepository(
        {
            "regular": _thumbnail_asset("regular", QColor("blue")),
            "override": _thumbnail_asset("override", QColor("green")),
        }
    )
    submitter = _CapacityLimitedTaskSubmitter(capacity=1)
    regular_cache = MediaWallThumbnailCache(maximum_bytes=4096)
    override_cache = MediaWallThumbnailCache(maximum_bytes=4096)
    regular_preloader = MediaWallThumbnailPreloader(
        cache=regular_cache,
        asset_repository=repository,
        submitter=submitter,
        maximum_in_flight_requests=1,
    )
    override_preloader = MediaWallThumbnailPreloader(
        cache=override_cache,
        asset_repository=repository,
        submitter=submitter,
        maximum_in_flight_requests=1,
    )
    regular_variants = (_thumbnail_variant("regular"),)
    override_variants = (_thumbnail_variant("override"),)

    assert regular_preloader.preload_pixmap_for_variants(
        regular_variants,
        QSize(10, 10),
    )
    assert override_preloader.preload_pixmap_for_variants(
        override_variants,
        QSize(10, 10),
    )
    assert submitter.submission_count == 1

    submitter.complete_next()
    assert _wait_until(lambda: submitter.submission_count == 2, timeout_ms=1000)
    submitter.complete_next()
    assert _wait_for_thumbnail_preloader_idle(regular_preloader, 1000)
    assert _wait_for_thumbnail_preloader_idle(override_preloader, 1000)

    assert regular_cache.pixmap_for_variants(regular_variants, QSize(10, 10))
    assert override_cache.pixmap_for_variants(override_variants, QSize(10, 10))
    assert "thumbnail preload submission failed" not in caplog.text.lower()
    regular_preloader.shutdown()
    override_preloader.shutdown()


def test_media_wall_thumbnail_cache_reads_local_asset_immediately() -> None:
    """Model picker decoration cache should hydrate local assets on first lookup."""

    ensure_qapp()
    repository = _AssetRepository(
        {"banner": _thumbnail_asset("banner", QColor("blue"))}
    )
    cache = MediaWallThumbnailCache(
        asset_repository=repository,
        maximum_bytes=4096,
    )
    variants = (_thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)

    pixmap = cache.pixmap_for_role(
        variants,
        BANNER_THUMBNAIL_ROLE,
        QSize(20, 12),
        device_pixel_ratio=1.25,
    )

    assert pixmap is not None
    assert repository.reads_by_key == {"banner": 1}
    assert pixmap.width() == 25
    assert pixmap.height() == 15
    assert pixmap.devicePixelRatioF() == 1.25


def test_media_wall_thumbnail_cache_uses_later_local_asset() -> None:
    """Missing model thumbnail assets should be retried by later cache lookups."""

    ensure_qapp()
    repository = _AssetRepository({})
    cache = MediaWallThumbnailCache(
        asset_repository=repository,
        maximum_bytes=4096,
    )
    variants = (_thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)

    first_pixmap = cache.pixmap_for_role(
        variants,
        BANNER_THUMBNAIL_ROLE,
        QSize(20, 12),
    )
    repository.assets["banner"] = _thumbnail_asset("banner", QColor("blue"))
    second_pixmap = cache.pixmap_for_role(
        variants,
        BANNER_THUMBNAIL_ROLE,
        QSize(20, 12),
    )

    assert first_pixmap is None
    assert second_pixmap is not None
    assert repository.reads_by_key == {"banner": 2}


def test_media_wall_thumbnail_cache_loads_matching_role_only() -> None:
    """Role lookup should filter variants before using the shared pixmap cache."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    variants = (
        _thumbnail_variant("standard", role=STANDARD_THUMBNAIL_ROLE),
        _thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),
    )
    _install_ready_thumbnail(
        cache,
        (_thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),),
        QSize(10, 10),
        QColor("blue"),
    )

    pixmap = cache.pixmap_for_role(variants, BANNER_THUMBNAIL_ROLE, QSize(10, 10))

    assert pixmap is not None


def test_media_wall_thumbnail_cache_role_lookup_returns_none_without_role() -> None:
    """Role lookup should not read assets when no variant has that role."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)

    pixmap = cache.pixmap_for_role(
        (_thumbnail_variant("standard", role=STANDARD_THUMBNAIL_ROLE),),
        BANNER_THUMBNAIL_ROLE,
        QSize(10, 10),
    )

    assert pixmap is None


def test_media_wall_thumbnail_cache_role_lookup_rejects_invalid_size() -> None:
    """Role lookup should preserve invalid-size behavior from normal lookup."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)

    pixmap = cache.pixmap_for_role(
        (_thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),),
        BANNER_THUMBNAIL_ROLE,
        QSize(0, 10),
    )

    assert pixmap is None


def test_media_wall_uses_row_appropriate_scroll_step() -> None:
    """The pixel-based wall should not keep Qt's tiny default scroll step."""

    ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)

    view.set_items(tuple(_wall_item(str(index)) for index in range(20)))

    assert view.verticalScrollBar().singleStep() >= 72


def test_media_wall_uses_qfluent_scrollbar_chrome() -> None:
    """The wall should expose QFluent scrollbar chrome synced to the view range."""

    app = ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.show()
    app.processEvents()

    view.set_items(tuple(_wall_item(str(index)) for index in range(30)))
    app.processEvents()
    fluent_scrollbar = view.findChild(ScrollBar)

    assert fluent_scrollbar is not None
    assert fluent_scrollbar.maximum() == view.verticalScrollBar().maximum()
    assert fluent_scrollbar.pageStep() == view.verticalScrollBar().pageStep()
    assert fluent_scrollbar.singleStep() == view.verticalScrollBar().singleStep()


def test_media_wall_qfluent_scrollbar_value_tracks_wheel_and_partner() -> None:
    """Wheel and programmatic partner scroll changes should sync Fluent chrome."""

    app = ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.show()
    app.processEvents()
    view.set_items(tuple(_wall_item(str(index)) for index in range(30)))
    fluent_scrollbar = view.findChild(ScrollBar)
    assert fluent_scrollbar is not None
    assert view.verticalScrollBar().maximum() > 0

    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(view.viewport().mapToGlobal(QPoint(10, 10))),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    view.wheelEvent(event)
    app.processEvents()

    assert view.verticalScrollBar().value() == view.verticalScrollBar().singleStep()
    assert fluent_scrollbar.value() == view.verticalScrollBar().value()

    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    app.processEvents()

    assert fluent_scrollbar.value() == view.verticalScrollBar().maximum()


def test_media_wall_tile_style_uses_accent_current_border() -> None:
    """Tile state colors should be QFluent-derived instead of hard-coded white."""

    current = media_wall_current_border()
    hover = media_wall_hover_border()

    assert current.isValid()
    assert hover.isValid()
    assert current.alpha() > hover.alpha()
    assert (current.red(), current.green(), current.blue()) != (255, 255, 255)


def test_media_wall_paints_subtitle_without_hover() -> None:
    """Tile subtitles should be visible without requiring hover or selection."""

    ensure_qapp()
    widget = MediaWallView()
    widget.resize(180, 240)
    rect = widget.viewport().rect()
    item_with_subtitle = MediaWallItem(
        item_id="one",
        title="Page Name",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )
    item_without_subtitle = MediaWallItem(
        item_id="one",
        title="Page Name",
        subtitle=None,
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )

    image_with_subtitle = _paint_wall_item_image(
        widget,
        item_with_subtitle,
        rect,
    )
    image_without_subtitle = _paint_wall_item_image(
        widget,
        item_without_subtitle,
        rect,
    )
    _title_rect, subtitle_rect = title_and_subtitle_rects(
        rect,
        widget.fontMetrics(),
        subtitle_visible=True,
    )

    assert _rect_images_differ(
        image_with_subtitle,
        image_without_subtitle,
        subtitle_rect,
    )


def test_media_wall_marquee_edge_fade_masks_text_without_touching_background() -> None:
    """Marquee edge fades should affect only title glyphs, not tile pixels."""

    ensure_qapp()
    widget = MediaWallView()
    widget.resize(180, 240)
    rect = widget.viewport().rect()
    item = MediaWallItem(
        item_id="one",
        title="A Very Long Page Name That Needs Marquee",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )

    background_item = MediaWallItem(
        item_id="one",
        title="",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )
    background_image = _paint_wall_item_image(widget, background_item, rect)
    unmasked_marquee_image = _paint_wall_item_image(
        widget,
        item,
        rect,
        title_marquee_state=TitleMarqueeState(
            phase="scroll",
            offset=12.0,
            show_left_fade=False,
            show_right_fade=False,
        ),
    )
    masked_marquee_image = _paint_wall_item_image(
        widget,
        item,
        rect,
        title_marquee_state=TitleMarqueeState(
            phase="scroll",
            offset=12.0,
            show_left_fade=True,
            show_right_fade=True,
        ),
    )
    title_rect, subtitle_rect = title_and_subtitle_rects(
        rect,
        widget.fontMetrics(),
        subtitle_visible=True,
    )

    left_fade_rect = QRect(
        title_rect.left(),
        title_rect.top(),
        18,
        title_rect.height(),
    )
    text_point = _find_pixel_different_from_background(
        unmasked_marquee_image,
        background_image,
        left_fade_rect,
    )
    background_point = _find_pixel_matching_background(
        unmasked_marquee_image,
        background_image,
        left_fade_rect,
    )
    subtitle_left_edge = QPoint(
        subtitle_rect.left() + 2,
        subtitle_rect.center().y(),
    )
    assert _pixel_color_difference(
        masked_marquee_image,
        background_image,
        text_point,
    ) < _pixel_color_difference(
        unmasked_marquee_image,
        background_image,
        text_point,
    )
    assert masked_marquee_image.pixelColor(
        background_point
    ) == background_image.pixelColor(background_point)
    assert masked_marquee_image.pixelColor(
        subtitle_left_edge
    ) == background_image.pixelColor(subtitle_left_edge)


def test_media_wall_public_selection_api_moves_and_clamps_current_item() -> None:
    """Selection helpers should expose generic current-item navigation."""

    ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.set_items(tuple(_wall_item(str(index)) for index in range(3)))

    assert view.current_index() == 0

    view.move_current(2)
    assert view.current_index() == 2

    view.move_current(8)
    assert view.current_index() == 2

    view.set_current_index(1)
    assert view.current_index() == 1
    assert view.current_payload() == "1"

    view.set_current_index(12)
    assert view.current_index() == -1
    assert view.current_payload() is None


def test_media_wall_public_activation_api_emits_current_payload() -> None:
    """Activation helper should emit the current payload without mouse focus."""

    ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    activated: list[object] = []
    view.itemActivated.connect(activated.append)
    view.set_items((_wall_item("one"), _wall_item("two")))
    view.set_current_index(1)

    assert view.activate_current() is True
    assert activated == ["two"]

    view.set_items(())
    assert view.activate_current() is False


def test_media_wall_right_click_emits_context_menu_payload() -> None:
    """Right-clicking a tile should request a payload context menu."""

    app = ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.show()
    app.processEvents()
    view.set_items((_wall_item("one"), _wall_item("two")))
    emitted: list[tuple[object, QPoint]] = []
    view.itemContextMenuRequested.connect(
        lambda payload, point: emitted.append((payload, point))
    )

    point = QPoint(10, 10)
    event = _mouse_press_event(
        view,
        point,
        button=Qt.MouseButton.RightButton,
    )
    view.mousePressEvent(event)

    assert emitted == [("one", view.mapToGlobal(point))]
    assert view.current_payload() == "one"
    assert event.isAccepted()


def test_media_wall_right_click_empty_space_does_not_emit_context_menu() -> None:
    """Right-clicking empty wall space should leave context menu requests untouched."""

    app = ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.show()
    app.processEvents()
    view.set_items(())
    emitted: list[tuple[object, QPoint]] = []
    view.itemContextMenuRequested.connect(
        lambda payload, point: emitted.append((payload, point))
    )

    event = _mouse_press_event(
        view,
        QPoint(10, 10),
        button=Qt.MouseButton.RightButton,
    )
    view.mousePressEvent(event)

    assert emitted == []


def test_media_wall_left_click_activation_still_emits_payload() -> None:
    """Left-clicking a tile should keep activating the payload."""

    app = ensure_qapp()
    view = MediaWallView()
    view.resize(400, 260)
    view.show()
    app.processEvents()
    view.set_items((_wall_item("one"), _wall_item("two")))
    activated: list[object] = []
    view.itemActivated.connect(activated.append)

    event = _mouse_press_event(
        view,
        QPoint(10, 10),
        button=Qt.MouseButton.LeftButton,
    )
    view.mousePressEvent(event)

    assert activated == ["one"]
    assert event.isAccepted()


def test_media_wall_directional_navigation_follows_visual_rows() -> None:
    """Arrow-style movement should navigate by visual rows and columns."""

    app = ensure_qapp()
    view = MediaWallView(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        )
    )
    view.resize(300, 220)
    view.setUpdatesEnabled(False)
    view.viewport().setUpdatesEnabled(False)
    view._fluent_vertical_scroll_bar.setUpdatesEnabled(False)
    view.show()
    app.processEvents()
    view.set_items(tuple(_square_wall_item(str(index)) for index in range(6)))
    app.processEvents()

    view.set_current_index(1)
    view.move_current_down()
    assert view.current_index() == 4

    view.move_current_up()
    assert view.current_index() == 1

    view.move_current_up()
    assert view.current_index() == 4

    view.move_current_down()
    assert view.current_index() == 1

    view.set_current_index(2)
    view.move_current_right()
    assert view.current_index() == 3

    view.move_current_left()
    assert view.current_index() == 2


def test_media_wall_preloads_only_visible_and_overscan_rows() -> None:
    """Visible-row preload requests should not load every wall item."""

    app = ensure_qapp()
    repository = _AssetRepository(
        {str(index): _thumbnail_asset(str(index), QColor("red")) for index in range(30)}
    )
    cache = MediaWallThumbnailCache()
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    view = MediaWallView(
        thumbnail_cache=cache,
        thumbnail_preloader=preloader,
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        ),
    )
    view.resize(300, 220)
    view.show()
    app.processEvents()
    view.set_items(tuple(_square_wall_item(str(index)) for index in range(30)))
    assert _wait_for_thumbnail_preloader_idle(preloader, 1000)
    cache.clear()
    preloader.clear()
    repository.reads_by_key.clear()
    view.verticalScrollBar().setValue(500)

    app.processEvents()
    assert _wait_for_thumbnail_preloader_idle(preloader, 1000)

    assert set(repository.reads_by_key) == {str(index) for index in range(12, 27)}
    preloader.shutdown()


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real QFluent scroll-bar paint can abort Windows xdist workers",
)
def test_media_wall_hit_testing_uses_scrolled_document_rows() -> None:
    """Hit testing should resolve the correct tile in a scrolled viewport."""

    ensure_qapp()
    view = MediaWallView(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        ),
    )
    view.resize(300, 220)
    view.setUpdatesEnabled(False)
    view.viewport().setUpdatesEnabled(False)
    view._fluent_vertical_scroll_bar.setUpdatesEnabled(False)
    view.show()
    ensure_qapp().processEvents()
    view.set_items(tuple(_square_wall_item(str(index)) for index in range(30)))
    view.verticalScrollBar().setValue(500)

    hit = view._item_at(QPoint(150, 50))

    assert hit is not None
    assert hit.item_id == "16"
    view.close()
    view.deleteLater()


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real QFluent scroll-bar paint can abort Windows xdist workers",
)
def test_media_wall_qfluent_tooltip_tracks_hovered_tile_path() -> None:
    """Tile hover tooltips should use the shared QFluent cursor tooltip filter."""

    app = ensure_qapp()
    view = MediaWallView(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        )
    )
    view.resize(300, 220)
    view.show()
    app.processEvents()
    view.set_items(
        (
            _wall_item("one", tooltip="checkpoints/one.safetensors"),
            _wall_item("two", tooltip="checkpoints/two.safetensors"),
        )
    )

    event = _mouse_move_event(view, QPoint(10, 10))
    assert isinstance(view._tooltip_filter, CursorToolTipFilter)
    assert view._tooltip_filter.eventFilter(view.viewport(), event) is False

    assert view.toolTip() == "checkpoints/one.safetensors"
    assert view.tooltip_text_at(QPoint(100, 10)) == "checkpoints/two.safetensors"
    assert view.tooltip_text_at(QPoint(10, 150)) is None


def test_title_marquee_holds_scrolls_and_holds_end() -> None:
    """Overflowing active titles should start readable, scroll, then end readable."""

    start_state = resolve_title_marquee_state(elapsed_ms=0, overflow_width=120)
    scrolling_state = resolve_title_marquee_state(
        elapsed_ms=1400,
        overflow_width=120,
    )
    end_state = resolve_title_marquee_state(
        elapsed_ms=3700,
        overflow_width=120,
    )

    assert start_state.phase == "start"
    assert start_state.show_right_fade is True
    assert scrolling_state.phase == "scroll"
    assert scrolling_state.offset > 0
    assert scrolling_state.show_left_fade is True
    assert scrolling_state.show_right_fade is True
    assert end_state.phase == "end"
    assert end_state.show_left_fade is True


class _CapacityLimitedTaskSubmitter:
    """Hold submitted work and reject requests beyond a shared capacity."""

    def __init__(self, *, capacity: int) -> None:
        """Create a deterministic bounded submitter for concurrent-owner tests."""

        self._capacity = capacity
        self._entries: list[
            tuple[
                TaskRequest[object],
                CancellationToken,
                ManualTaskHandle[object],
            ]
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
        """Run and complete the oldest admitted request that is still active."""

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


class _CountingAssetRepository:
    """Count thumbnail asset reads."""

    def __init__(self) -> None:
        """Initialize the read counter."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record asset reads and return no asset."""

        _ = storage_key
        self.reads += 1
        return None


class _AssetRepository:
    """Return configured thumbnail assets and count storage-key reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store assets for deterministic thumbnail-cache tests."""

        self.assets = assets
        self.reads_by_key: dict[str, int] = {}

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one read and return the configured asset when present."""

        self.reads_by_key[storage_key] = self.reads_by_key.get(storage_key, 0) + 1
        return self.assets.get(storage_key)


def _wall_item(item_id: str, *, tooltip: str | None = None) -> MediaWallItem:
    """Return one minimal media wall item."""

    return MediaWallItem(
        item_id=item_id,
        title=item_id.title(),
        subtitle=None,
        aspect_ratio=0.72,
        thumbnail_variants=(_thumbnail_variant(item_id),),
        payload=item_id,
        tooltip=tooltip,
    )


def _square_wall_item(item_id: str) -> MediaWallItem:
    """Return one square media wall item."""

    return MediaWallItem(
        item_id=item_id,
        title=item_id.title(),
        subtitle=None,
        aspect_ratio=1.0,
        thumbnail_variants=(_thumbnail_variant(item_id),),
        payload=item_id,
    )


def _paint_wall_item_image(
    widget: MediaWallView,
    item: MediaWallItem,
    rect: QRect,
    *,
    title_marquee_state: TitleMarqueeState | None = None,
) -> QImage:
    """Render one media wall item to an offscreen image for pixel comparisons."""

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


def _rect_images_differ(first: QImage, second: QImage, rect: QRect) -> bool:
    """Return whether two rendered images differ inside the supplied rect."""

    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            if first.pixelColor(x, y) != second.pixelColor(x, y):
                return True
    return False


def _find_pixel_different_from_background(
    image: QImage,
    background: QImage,
    rect: QRect,
) -> QPoint:
    """Return one point where rendered text differs from the background."""

    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            point = QPoint(x, y)
            if _pixel_color_difference(image, background, point) > 0:
                return point
    raise AssertionError("Expected a text pixel inside the sampled rect")


def _find_pixel_matching_background(
    image: QImage,
    background: QImage,
    rect: QRect,
) -> QPoint:
    """Return one point where rendered text leaves the background unchanged."""

    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            point = QPoint(x, y)
            if image.pixelColor(point) == background.pixelColor(point):
                return point
    raise AssertionError("Expected a background pixel inside the sampled rect")


def _pixel_color_difference(first: QImage, second: QImage, point: QPoint) -> int:
    """Return channel-distance between two image pixels at one point."""

    first_color = first.pixelColor(point)
    second_color = second.pixelColor(point)
    return (
        abs(first_color.red() - second_color.red())
        + abs(first_color.green() - second_color.green())
        + abs(first_color.blue() - second_color.blue())
        + abs(first_color.alpha() - second_color.alpha())
    )


def _mouse_press_event(
    view: MediaWallView,
    point: QPoint,
    *,
    button: Qt.MouseButton,
) -> QMouseEvent:
    """Return one mouse-press event at the given wall-local point."""

    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(point),
        QPointF(view.mapToGlobal(point)),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )


def _mouse_move_event(view: MediaWallView, point: QPoint) -> QMouseEvent:
    """Return one mouse-move event at the given viewport-local point."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(point),
        QPointF(view.viewport().mapToGlobal(point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _thumbnail_variant(
    storage_key: str,
    *,
    role: str = STANDARD_THUMBNAIL_ROLE,
) -> ThumbnailVariantReference:
    """Return one prepared thumbnail reference for media wall tests."""

    return ThumbnailVariantReference(
        storage_key=storage_key,
        size=10,
        width=10,
        height=10,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=400,
        role=role,
    )


def _thumbnail_asset(storage_key: str, color: QColor) -> ThumbnailAsset:
    """Return one valid Qt-ready thumbnail asset for cache tests."""

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


def _install_ready_thumbnail(
    cache: MediaWallThumbnailCache,
    variants: tuple[ThumbnailVariantReference, ...],
    size: QSize,
    color: QColor,
) -> None:
    """Install one ready thumbnail image into the media wall cache."""

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
