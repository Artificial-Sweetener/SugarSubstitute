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

"""Verify media wall thumbnail cache identity, roles, and eviction."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.presentation.widgets.media_wall import MediaWallThumbnailCache
from tests.presentation.widgets.media_wall.support import (
    AssetRepository,
    ensure_qapp,
    install_ready_thumbnail,
    thumbnail_asset,
    thumbnail_variant,
)


def test_thumbnail_cache_reuses_ready_pixmaps() -> None:
    """Reuse the installed GUI-thread pixmap on cache hits."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    variants = (thumbnail_variant("one"),)
    install_ready_thumbnail(cache, variants, QSize(10, 10), QColor("red"))

    first = cache.pixmap_for_variants(variants, QSize(10, 10))
    second = cache.pixmap_for_variants(variants, QSize(10, 10))

    assert first is not None
    assert second is first


def test_thumbnail_cache_evicts_least_recently_used_pixmaps() -> None:
    """Evict the least recently used pixmap when the byte budget is exceeded."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=850)
    install_ready_thumbnail(
        cache, (thumbnail_variant("one"),), QSize(10, 10), QColor("red")
    )
    install_ready_thumbnail(
        cache, (thumbnail_variant("two"),), QSize(10, 10), QColor("green")
    )
    assert cache.pixmap_for_variants((thumbnail_variant("one"),), QSize(10, 10))
    install_ready_thumbnail(
        cache, (thumbnail_variant("three"),), QSize(10, 10), QColor("blue")
    )

    assert cache.pixmap_for_variants((thumbnail_variant("one"),), QSize(10, 10))
    assert cache.pixmap_for_variants((thumbnail_variant("three"),), QSize(10, 10))
    assert cache.pixmap_for_variants((thumbnail_variant("two"),), QSize(10, 10)) is None


def test_thumbnail_cache_reads_local_asset_immediately() -> None:
    """Hydrate a local banner asset during its first lookup."""

    ensure_qapp()
    repository = AssetRepository({"banner": thumbnail_asset("banner", QColor("blue"))})
    cache = MediaWallThumbnailCache(
        asset_repository=repository,
        maximum_bytes=4096,
    )
    variants = (thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)

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


def test_thumbnail_cache_uses_later_local_asset() -> None:
    """Retry a missing local asset on a later cache lookup."""

    ensure_qapp()
    repository = AssetRepository({})
    cache = MediaWallThumbnailCache(
        asset_repository=repository,
        maximum_bytes=4096,
    )
    variants = (thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),)

    first = cache.pixmap_for_role(variants, BANNER_THUMBNAIL_ROLE, QSize(20, 12))
    repository.assets["banner"] = thumbnail_asset("banner", QColor("blue"))
    second = cache.pixmap_for_role(variants, BANNER_THUMBNAIL_ROLE, QSize(20, 12))

    assert first is None
    assert second is not None
    assert repository.reads_by_key == {"banner": 2}


def test_thumbnail_cache_loads_matching_role_only() -> None:
    """Filter variants by role before consulting the shared pixmap cache."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)
    variants = (
        thumbnail_variant("standard", role=STANDARD_THUMBNAIL_ROLE),
        thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),
    )
    install_ready_thumbnail(
        cache,
        (thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),),
        QSize(10, 10),
        QColor("blue"),
    )

    assert (
        cache.pixmap_for_role(variants, BANNER_THUMBNAIL_ROLE, QSize(10, 10))
        is not None
    )


def test_thumbnail_cache_role_lookup_returns_none_without_role() -> None:
    """Avoid asset reads when no variant matches the requested role."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)

    assert (
        cache.pixmap_for_role(
            (thumbnail_variant("standard", role=STANDARD_THUMBNAIL_ROLE),),
            BANNER_THUMBNAIL_ROLE,
            QSize(10, 10),
        )
        is None
    )


def test_thumbnail_cache_role_lookup_rejects_invalid_size() -> None:
    """Preserve invalid-size rejection for role-specific lookup."""

    ensure_qapp()
    cache = MediaWallThumbnailCache(maximum_bytes=4096)

    assert (
        cache.pixmap_for_role(
            (thumbnail_variant("banner", role=BANNER_THUMBNAIL_ROLE),),
            BANNER_THUMBNAIL_ROLE,
            QSize(0, 10),
        )
        is None
    )
