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

"""Contract tests for Cube Library presentation icon resolution."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize
from PySide6.QtGui import QColor, QIcon, QImage
from PySide6.QtWidgets import QApplication

from substitute.domain.cube_library import CubeIconDescriptor
from substitute.application.ports import (
    CubeIconAsset,
    CubeIconCacheKey,
    RenderedCubeIconAsset,
)
from substitute.presentation.resources.cube_icon_factory import (
    CubeIconFactory,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail

_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAACXBIWXMAAA9hAAAP"
    "YQGoP6dpAAAAFUlEQVQImWP8z/D/PwMDAwMTAxQAAC4IAwGxhHEgAAAAAElFTkSuQmCC"
)


@dataclass(frozen=True)
class _FakeAssetFetcher:
    """Provide deterministic asset fetching for CubeIconFactory tests."""

    asset: CubeIconAsset | None
    calls: list[str]

    def fetch_icon_asset(self, relative_url: str) -> CubeIconAsset | None:
        """Record the requested asset URL and return configured bytes."""

        self.calls.append(relative_url)
        return self.asset


@dataclass
class _FakeRenderedIconCache:
    """Provide deterministic durable rendered-icon cache behavior."""

    assets: dict[str, RenderedCubeIconAsset]
    reads: list[str]
    writes: list[str]

    def read_rendered_icon(
        self,
        key: CubeIconCacheKey,
    ) -> RenderedCubeIconAsset | None:
        """Return the configured rendered asset for one key."""

        stable_key = key.stable_hash()
        self.reads.append(stable_key)
        return self.assets.get(stable_key)

    def write_rendered_icon(
        self,
        key: CubeIconCacheKey,
        asset: RenderedCubeIconAsset,
    ) -> None:
        """Store one rendered asset by stable key."""

        stable_key = key.stable_hash()
        self.writes.append(stable_key)
        self.assets[stable_key] = asset

    def delete_for_target(self, _target_key: str) -> int:
        """Return zero because factory tests do not prune targets."""

        return 0

    def delete_except_catalog_revision(
        self,
        _target_key: str,
        _catalog_revision: str,
    ) -> int:
        """Return zero because factory tests do not prune catalogs."""

        return 0

    def clear(self) -> int:
        """Clear stored assets."""

        count = len(self.assets)
        self.assets.clear()
        return count

    def prune(self, *, maximum_rows: int, maximum_bytes: int) -> int:
        """Return zero because factory tests do not exercise pruning."""

        _ = maximum_rows, maximum_bytes
        return 0


def _ensure_qapp() -> QApplication:
    """Return a QApplication for pixmap-backed icon tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _alpha_bounds(image: QImage) -> tuple[int, int, int, int] | None:
    """Return the bounds of non-transparent pixels in one rendered icon image."""

    min_x = image.width()
    min_y = image.height()
    max_x = -1
    max_y = -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < min_x or max_y < min_y:
        return None
    return (min_x, min_y, max_x, max_y)


def _first_opaque_rgb(image: QImage) -> tuple[int, int, int] | None:
    """Return one high-alpha RGB sample from rendered icon text."""

    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() >= 240:
                return (color.red(), color.green(), color.blue())
    return None


def _png_bytes(
    rows: list[list[tuple[int, int, int, int]]],
) -> bytes:
    """Encode RGBA rows into PNG bytes for icon rendering tests."""

    image = QImage(len(rows[0]), len(rows), QImage.Format.Format_ARGB32)
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            image.setPixelColor(x, y, QColor(*color))
    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")  # type: ignore[call-overload]
    return cast(bytes, payload.data())


def _rendered_asset(key: CubeIconCacheKey, color: QColor) -> RenderedCubeIconAsset:
    """Return one prepared durable rendered icon asset."""

    image = QImage(2, 2, QImage.Format.Format_ARGB32_Premultiplied)
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


def _icon_image(icon: QIcon, width: int, height: int | None = None) -> QImage:
    """Render one icon into an image with deterministic dimensions."""

    target_height = height if height is not None else width
    return icon.pixmap(QSize(width, target_height)).toImage()


def _rgb_at(image: QImage, x: int, y: int) -> tuple[int, int, int]:
    """Return the RGB channels at one image pixel."""

    color = image.pixelColor(x, y)
    return (color.red(), color.green(), color.blue())


def _icon_for_asset(
    *,
    content: bytes,
    media_type: str,
    color_behavior: str = "auto",
    url: str = "/sugarcubes/assets/icon?cube_id=demo",
    render_size: int = 96,
) -> tuple[QIcon, _FakeAssetFetcher]:
    """Return an icon resolved through a fake asset fetcher."""

    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=content, media_type=media_type),
        calls=[],
    )
    factory = CubeIconFactory(
        asset_fetcher=fetcher,
        fallback_render_size=render_size,
    )
    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/demo.cube",
        display_name="Demo",
        icon=CubeIconDescriptor(
            kind="asset",
            url=url,
            media_type=media_type,
            color_behavior=color_behavior,
        ),
    )
    return icon, fetcher


def _cache_key(
    *,
    target_key: str = "target",
    catalog_revision: str = "catalog",
    cube_id: str = "Artificial-Sweetener/Base-Cubes/cache.cube",
    cube_content_hash: str = "content",
    icon_url: str = "/sugarcubes/assets/icon?cube_id=cache",
    media_type: str = "image/png",
    color_behavior: str = "auto",
    theme_name: str = "light",
    logical_size: int = 2,
    device_pixel_ratio: float = 1.0,
    renderer_version: int = 3,
) -> CubeIconCacheKey:
    """Return one rendered icon cache key matching factory requests."""

    return CubeIconCacheKey(
        target_key=target_key,
        catalog_revision=catalog_revision,
        cube_id=cube_id,
        cube_content_hash=cube_content_hash,
        icon_kind="asset",
        icon_url=icon_url,
        media_type=media_type,
        repo_relative_path="",
        color_behavior=color_behavior,
        theme_name=theme_name,
        logical_size=logical_size,
        device_pixel_ratio=device_pixel_ratio,
        renderer_version=renderer_version,
    )
