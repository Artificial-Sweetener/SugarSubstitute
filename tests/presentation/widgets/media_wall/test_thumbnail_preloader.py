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

"""Verify bounded asynchronous media wall thumbnail preload ownership."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor
from shiboken6 import delete

from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.widgets.media_wall import (
    MediaThumbnailReadinessStatus,
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.presentation.widgets.media_wall.support import (
    AssetRepository,
    CapacityLimitedTaskSubmitter,
    ensure_qapp,
    thumbnail_asset,
    thumbnail_variant,
    wait_for_preloader_idle,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_thumbnail_preloader_marks_missing_assets_failed() -> None:
    """Publish missing thumbnail reads as prompt-safe failed readiness."""

    ensure_qapp()
    repository = AssetRepository({})
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    variants = (thumbnail_variant("missing"),)
    try:
        assert preloader.preload_pixmap_for_variants(variants, QSize(10, 10))
        wait_for_preloader_idle(preloader)

        readiness = preloader.readiness_for_variants(variants, QSize(10, 10))
        assert repository.reads_by_key == {"missing": 1}
        assert readiness.status is MediaThumbnailReadinessStatus.FAILED
        assert readiness.storage_key == "missing"
    finally:
        preloader.shutdown()
        delete(preloader)


def test_thumbnail_preloader_installs_cached_asset_immediately() -> None:
    """Hydrate a selected banner synchronously before first paint."""

    ensure_qapp()
    repository = AssetRepository({"banner": thumbnail_asset("banner", QColor("blue"))})
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    variants = (thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)
    try:
        assert preloader.install_pixmap_for_role_now(
            variants,
            BANNER_THUMBNAIL_ROLE,
            QSize(20, 12),
            device_pixel_ratio=1.25,
        )
        assert not preloader.has_pending_work()
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
    finally:
        preloader.shutdown()
        delete(preloader)


def test_thumbnail_preloader_bounds_submitted_work() -> None:
    """Keep visible bursts queued behind a bounded in-flight set."""

    ensure_qapp()
    repository = AssetRepository(
        {
            key: thumbnail_asset(key, QColor("blue"))
            for key in ("one", "two", "three", "four", "five")
        }
    )
    submitter = CapacityLimitedTaskSubmitter(capacity=8)
    preloader = MediaWallThumbnailPreloader(
        cache=MediaWallThumbnailCache(maximum_bytes=32_000),
        asset_repository=repository,
        submitter=submitter,
        maximum_pending_requests=5,
        maximum_in_flight_requests=2,
    )
    try:
        for key in ("one", "two", "three", "four", "five"):
            assert preloader.preload_pixmap_for_variants(
                (thumbnail_variant(key),),
                QSize(10, 10),
            )

        assert submitter.submission_count == 2
        assert preloader.has_pending_work()
        assert not preloader.preload_pixmap_for_variants(
            (thumbnail_variant("five"),),
            QSize(10, 10),
        )
        for _ in range(5):
            submitter.complete_next()
        wait_for_preloader_idle(preloader)
        assert repository.reads_by_key == {
            "one": 1,
            "two": 1,
            "three": 1,
            "four": 1,
            "five": 1,
        }
    finally:
        preloader.shutdown()
        delete(preloader)


def test_thumbnail_preloaders_retry_shared_lane_saturation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Eventually load concurrent owners after shared-lane saturation."""

    ensure_qapp()
    repository = AssetRepository(
        {
            "regular": thumbnail_asset("regular", QColor("blue")),
            "override": thumbnail_asset("override", QColor("green")),
        }
    )
    submitter = CapacityLimitedTaskSubmitter(capacity=1)
    regular_cache = MediaWallThumbnailCache(maximum_bytes=4096)
    override_cache = MediaWallThumbnailCache(maximum_bytes=4096)
    regular = MediaWallThumbnailPreloader(
        cache=regular_cache,
        asset_repository=repository,
        submitter=submitter,
        maximum_in_flight_requests=1,
    )
    override = MediaWallThumbnailPreloader(
        cache=override_cache,
        asset_repository=repository,
        submitter=submitter,
        maximum_in_flight_requests=1,
    )
    regular_variants = (thumbnail_variant("regular"),)
    override_variants = (thumbnail_variant("override"),)
    try:
        assert regular.preload_pixmap_for_variants(regular_variants, QSize(10, 10))
        assert override.preload_pixmap_for_variants(override_variants, QSize(10, 10))
        assert submitter.submission_count == 1

        submitter.complete_next()
        wait_for_qt_condition(lambda: submitter.submission_count == 2)
        submitter.complete_next()
        wait_for_preloader_idle(regular)
        wait_for_preloader_idle(override)

        assert regular_cache.pixmap_for_variants(regular_variants, QSize(10, 10))
        assert override_cache.pixmap_for_variants(override_variants, QSize(10, 10))
        assert "thumbnail preload submission failed" not in caplog.text.lower()
    finally:
        regular.shutdown()
        delete(regular)
        override.shutdown()
        delete(override)
