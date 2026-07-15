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

"""Contract tests for durable rendered cube icon cache persistence."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from PySide6.QtGui import QColor, QImage

from substitute.application.ports import CubeIconCacheKey, RenderedCubeIconAsset
from substitute.infrastructure.persistence import SqliteCubeIconCache
from substitute.shared.qt_thumbnail_codec import (
    image_from_qt_thumbnail_payload,
    prepare_qt_thumbnail,
)


def test_sqlite_cube_icon_cache_round_trips_prepared_qt_image(
    tmp_path: Path,
) -> None:
    """SQLite cache should persist and return one Qt-ready icon payload."""

    cache = SqliteCubeIconCache(tmp_path, clock=lambda: "2026-05-07T00:00:00Z")
    key = _key()
    asset = _asset(key, QColor("#112233"))

    cache.write_rendered_icon(key, asset)
    loaded = cache.read_rendered_icon(key)

    assert loaded is not None
    assert loaded.cache_key == key.stable_hash()
    assert loaded.width == 16
    assert loaded.height == 16
    image = image_from_qt_thumbnail_payload(
        width=loaded.width,
        height=loaded.height,
        qt_format=loaded.qt_format,
        bytes_per_line=loaded.bytes_per_line,
        payload=loaded.payload,
    )
    assert image is not None
    assert image.pixelColor(0, 0).name().lower() == "#112233"
    assert (tmp_path / "cube_icon_cache.sqlite3").exists()


def test_sqlite_cube_icon_cache_returns_none_for_missing_key(tmp_path: Path) -> None:
    """Missing rendered variants should return ``None``."""

    cache = SqliteCubeIconCache(tmp_path)

    assert cache.read_rendered_icon(_key()) is None


def test_sqlite_cube_icon_cache_replaces_same_key_atomically(tmp_path: Path) -> None:
    """Writing the same rendered key should replace the previous payload."""

    cache = SqliteCubeIconCache(tmp_path)
    key = _key()

    cache.write_rendered_icon(key, _asset(key, QColor("#ff0000")))
    cache.write_rendered_icon(key, _asset(key, QColor("#0000ff")))

    loaded = cache.read_rendered_icon(key)
    assert loaded is not None
    image = image_from_qt_thumbnail_payload(
        width=loaded.width,
        height=loaded.height,
        qt_format=loaded.qt_format,
        bytes_per_line=loaded.bytes_per_line,
        payload=loaded.payload,
    )
    assert image is not None
    assert image.pixelColor(0, 0).name().lower() == "#0000ff"


def test_sqlite_cube_icon_cache_prunes_by_target_and_catalog(
    tmp_path: Path,
) -> None:
    """Target and catalog pruning should remove only matching stale rows."""

    cache = SqliteCubeIconCache(tmp_path)
    active = _key(target_key="target-a", catalog_revision="rev-2", cube_id="cube-a")
    stale = _key(target_key="target-a", catalog_revision="rev-1", cube_id="cube-b")
    other_target = _key(
        target_key="target-b",
        catalog_revision="rev-1",
        cube_id="cube-c",
    )
    for key in (active, stale, other_target):
        cache.write_rendered_icon(key, _asset(key, QColor("#123456")))

    deleted = cache.delete_except_catalog_revision("target-a", "rev-2")

    assert deleted == 1
    assert cache.read_rendered_icon(active) is not None
    assert cache.read_rendered_icon(stale) is None
    assert cache.read_rendered_icon(other_target) is not None

    deleted_for_target = cache.delete_for_target("target-b")

    assert deleted_for_target == 1
    assert cache.read_rendered_icon(other_target) is None


def test_sqlite_cube_icon_cache_prunes_oldest_rows(tmp_path: Path) -> None:
    """Row-count pruning should remove least recently accessed variants."""

    cache = SqliteCubeIconCache(tmp_path)
    keys = [_key(cube_id=f"cube-{index}") for index in range(3)]
    for key in keys:
        cache.write_rendered_icon(key, _asset(key, QColor("#123456")))

    deleted = cache.prune(maximum_rows=2, maximum_bytes=-1)

    assert deleted == 1
    assert cache.read_rendered_icon(keys[0]) is None
    assert cache.read_rendered_icon(keys[1]) is not None
    assert cache.read_rendered_icon(keys[2]) is not None


def test_sqlite_cube_icon_cache_prunes_oldest_bytes(tmp_path: Path) -> None:
    """Byte-budget pruning should remove least recently accessed variants."""

    cache = SqliteCubeIconCache(tmp_path)
    keys = [_key(cube_id=f"cube-{index}") for index in range(2)]
    for key in keys:
        cache.write_rendered_icon(key, _asset(key, QColor("#123456")))

    deleted = cache.prune(maximum_rows=-1, maximum_bytes=16 * 16 * 4)

    assert deleted == 1
    assert cache.read_rendered_icon(keys[0]) is None
    assert cache.read_rendered_icon(keys[1]) is not None


def test_sqlite_cube_icon_cache_rejects_unsupported_schema_version(
    tmp_path: Path,
) -> None:
    """Unsupported schema versions should fail clearly instead of reusing rows."""

    database_path = tmp_path / "cube_icon_cache.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "create table cube_icon_cache_schema (key text primary key, value text not null)"
        )
        connection.execute(
            "insert into cube_icon_cache_schema(key, value) values('schema_version', '999')"
        )

    try:
        SqliteCubeIconCache(tmp_path)
    except RuntimeError as error:
        assert "Unsupported cube icon cache SQLite schema version" in str(error)
    else:
        raise AssertionError("Expected unsupported schema version to raise.")


def _key(
    *,
    target_key: str = "target",
    catalog_revision: str = "rev",
    cube_id: str = "cube",
    logical_size: int = 16,
    device_pixel_ratio: float = 1.0,
    theme_name: str = "light",
) -> CubeIconCacheKey:
    """Return one deterministic rendered icon cache key."""

    return CubeIconCacheKey(
        target_key=target_key,
        catalog_revision=catalog_revision,
        cube_id=cube_id,
        cube_content_hash="content",
        icon_kind="asset",
        icon_url=f"/icon/{cube_id}.png",
        media_type="image/png",
        repo_relative_path=f"icons/{cube_id}.png",
        color_behavior="auto",
        theme_name=theme_name,
        logical_size=logical_size,
        device_pixel_ratio=device_pixel_ratio,
        renderer_version=1,
    )


def _asset(key: CubeIconCacheKey, color: QColor) -> RenderedCubeIconAsset:
    """Return one prepared rendered cube icon asset."""

    image = QImage(16, 16, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    prepared = prepare_qt_thumbnail(image)
    return RenderedCubeIconAsset(
        cache_key=key.stable_hash(),
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
