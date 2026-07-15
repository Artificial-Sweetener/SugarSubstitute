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
from pytest import MonkeyPatch

from substitute.domain.cube_library import CubeIconDescriptor
from substitute.application.ports import (
    CubeIconAsset,
    CubeIconCacheKey,
    RenderedCubeIconAsset,
)
from substitute.presentation.resources.cube_icon_factory import (
    CubeIconFactory,
    derive_cube_initials,
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


def test_derive_cube_initials_uses_sugarcubes_two_letter_rules() -> None:
    """Fallback initials should match current SugarCubes display behavior."""

    assert derive_cube_initials("Text to Image") == "TI"
    assert derive_cube_initials("Image to Image") == "II"
    assert derive_cube_initials("Inpaint") == "IN"
    assert derive_cube_initials("Promptmask Detailer") == "PD"
    assert derive_cube_initials("Diffusion Upscale") == "DU"


def test_derive_cube_initials_ignores_styled_model_prefix() -> None:
    """Fallback initials should use the cube name body after a styled model prefix."""

    assert derive_cube_initials("SDXL/Text to Image") == "TI"
    assert derive_cube_initials("Flux/Image to Image") == "II"
    assert derive_cube_initials("SDXL/Inpaint") == "IN"
    assert derive_cube_initials("Pony/Promptmask Detailer") == "PD"


def test_derive_cube_initials_keeps_boundary_slash_labels() -> None:
    """Fallback initials should only strip complete leading prefix tokens."""

    assert derive_cube_initials("/Text to Image") == "TI"
    assert derive_cube_initials("SDXL/") == "SD"


def test_derive_cube_initials_ignores_prefix_in_fallback_text() -> None:
    """Fallback text should use the same prefix policy when the primary label is blank."""

    assert derive_cube_initials("", fallback_text="SDXL/Text to Image") == "TI"


def test_fallback_icon_generation_returns_text_only_normalized_icon() -> None:
    """Cubes without asset descriptors should receive a normalized text icon."""

    _ensure_qapp()
    factory = CubeIconFactory()

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    pixmap = icon.pixmap(96, 96)
    image = pixmap.toImage()
    bounds = _alpha_bounds(image)
    assert not icon.isNull()
    assert not pixmap.isNull()
    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    text_width = max_x - min_x + 1
    text_height = max_y - min_y + 1
    assert text_width >= 50
    assert text_height >= 40
    assert text_height <= 55
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() - 1, 0).alpha() == 0
    assert image.pixelColor(0, image.height() - 1).alpha() == 0
    assert image.pixelColor(image.width() - 1, image.height() - 1).alpha() == 0


def test_fallback_icon_normalizes_narrow_and_wide_initial_heights() -> None:
    """Fallback initials should not upscale narrow pairs more than wide pairs."""

    _ensure_qapp()
    factory = CubeIconFactory()
    text_to_image = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        display_name="Text to Image",
        icon=None,
    )
    diffusion_alpha = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Diffusion Alpha.cube",
        display_name="Diffusion Alpha",
        icon=None,
    )

    text_bounds = _alpha_bounds(text_to_image.pixmap(96, 96).toImage())
    alpha_bounds = _alpha_bounds(diffusion_alpha.pixmap(96, 96).toImage())

    assert text_bounds is not None
    assert alpha_bounds is not None
    text_height = text_bounds[3] - text_bounds[1] + 1
    alpha_height = alpha_bounds[3] - alpha_bounds[1] + 1
    assert abs(text_height - alpha_height) <= 4


def test_fallback_icon_shrinks_only_extreme_width_overflow_pairs() -> None:
    """Very wide initials should stay inside the icon footprint after shrink."""

    _ensure_qapp()
    icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Wide Wide.cube",
        display_name="Wide Wide",
        icon=None,
    )

    image = icon.pixmap(96, 96).toImage()
    bounds = _alpha_bounds(image)

    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    assert min_x >= 2
    assert max_x <= 93
    assert max_y - min_y + 1 >= 30


def test_fallback_icon_text_color_follows_theme(monkeypatch: MonkeyPatch) -> None:
    """Fallback text should render black in light mode and white in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    light_icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)
    dark_icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    light_rgb = _first_opaque_rgb(light_icon.pixmap(96, 96).toImage())
    dark_rgb = _first_opaque_rgb(dark_icon.pixmap(96, 96).toImage())
    assert light_rgb is not None
    assert dark_rgb is not None
    assert max(light_rgb) <= 5
    assert min(dark_rgb) >= 250


def test_asset_icon_response_with_valid_png_returns_asset_icon() -> None:
    """Valid target-relative PNG descriptors should load the fetched asset icon."""

    _ensure_qapp()
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        display_name="Text to Image",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Text%20to%20Image",
            media_type="image/png",
        ),
    )

    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    assert icon.actualSize(QSize(48, 48)) == QSize(48, 48)
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=Text%20to%20Image"]


def test_bright_grayscale_png_inverts_in_light_mode_preserving_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bright grayscale PNG assets should become dark in light mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(255, 255, 255, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    black = _rgb_at(image, 0, 0)
    dark_gray = _rgb_at(image, 1, 0)
    assert max(black) <= 5
    assert 45 <= dark_gray[0] <= 60
    assert black != dark_gray


def test_bright_grayscale_png_is_preserved_in_dark_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bright grayscale PNG assets should remain bright in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(255, 255, 255, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    white = _rgb_at(image, 0, 0)
    light_gray = _rgb_at(image, 1, 0)
    assert min(white) >= 250
    assert 198 <= light_gray[0] <= 210


def test_dark_grayscale_png_inverts_in_dark_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Dark grayscale PNG assets should become light in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(0, 0, 0, 255), (51, 51, 51, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    white = _rgb_at(image, 0, 0)
    light_gray = _rgb_at(image, 1, 0)
    assert min(white) >= 250
    assert 198 <= light_gray[0] <= 210


def test_full_color_png_auto_asset_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Automatic color behavior should not transform confidently colored PNGs."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(220, 24, 40, 255), (20, 120, 220, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    assert _rgb_at(image, 0, 0) == (220, 24, 40)
    assert _rgb_at(image, 1, 0) == (20, 120, 220)


def test_full_color_png_declared_full_color_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Full-color color behavior should never transform PNG assets."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(250, 250, 250, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        color_behavior="fullColor",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    assert _rgb_at(image, 0, 0) == (250, 250, 250)
    assert _rgb_at(image, 1, 0) == (204, 204, 204)


def test_asset_cache_reuses_bytes_but_renders_per_theme(
    monkeypatch: MonkeyPatch,
) -> None:
    """Raw asset bytes should fetch once while rendered icons vary by theme."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=cache",
        media_type="image/png",
    )

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    light_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
    )
    repeated_light_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
    )
    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)
    dark_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
    )

    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=cache"]
    assert max(_rgb_at(_icon_image(light_icon, 1), 0, 0)) <= 5
    assert max(_rgb_at(_icon_image(repeated_light_icon, 1), 0, 0)) <= 5
    assert min(_rgb_at(_icon_image(dark_icon, 1), 0, 0)) >= 250


def test_clear_asset_cache_forces_asset_refetch(monkeypatch: MonkeyPatch) -> None:
    """Clearing asset cache should discard raw bytes and rendered icons."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=clear",
        media_type="image/png",
    )

    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/clear.cube",
        display_name="Clear",
        icon=descriptor,
    )
    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/clear.cube",
        display_name="Clear",
        icon=descriptor,
    )
    factory.clear_asset_cache()
    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/clear.cube",
        display_name="Clear",
        icon=descriptor,
    )

    assert fetcher.calls == [
        "/sugarcubes/assets/icon?cube_id=clear",
        "/sugarcubes/assets/icon?cube_id=clear",
    ]


def test_warm_icon_for_cube_uses_normal_resolution_path() -> None:
    """Icon warmup should populate the same cache used by visible rendering."""

    _ensure_qapp()
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=warm",
        media_type="image/png",
    )

    warmed = factory.warm_icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/warm.cube",
        display_name="Warm",
        icon=descriptor,
    )
    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/warm.cube",
        display_name="Warm",
        icon=descriptor,
    )

    assert warmed is True
    assert not icon.isNull()
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=warm"]


def test_clear_asset_cache_removes_all_theme_rendered_variants(
    monkeypatch: MonkeyPatch,
) -> None:
    """Clearing asset cache should discard rendered light and dark variants."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=themes",
        media_type="image/png",
    )

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    light_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/themes.cube",
        display_name="Themes",
        icon=descriptor,
    )
    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)
    dark_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/themes.cube",
        display_name="Themes",
        icon=descriptor,
    )
    factory.clear_asset_cache()
    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    refreshed_light_icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/themes.cube",
        display_name="Themes",
        icon=descriptor,
    )

    assert max(_rgb_at(_icon_image(light_icon, 1), 0, 0)) <= 5
    assert min(_rgb_at(_icon_image(dark_icon, 1), 0, 0)) >= 250
    assert max(_rgb_at(_icon_image(refreshed_light_icon, 1), 0, 0)) <= 5
    assert fetcher.calls == [
        "/sugarcubes/assets/icon?cube_id=themes",
        "/sugarcubes/assets/icon?cube_id=themes",
    ]


def test_durable_rendered_icon_cache_hit_avoids_asset_fetch(
    monkeypatch: MonkeyPatch,
) -> None:
    """Durable rendered cache hits should bypass source asset fetching."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    key = _cache_key()
    rendered_cache = _FakeRenderedIconCache(
        assets={key.stable_hash(): _rendered_asset(key, QColor("#123456"))},
        reads=[],
        writes=[],
    )
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(
        asset_fetcher=fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
    )

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=cache",
            media_type="image/png",
        ),
        catalog_revision="catalog",
        cube_content_hash="content",
    )

    assert _rgb_at(_icon_image(icon, 2), 0, 0) == (18, 52, 86)
    assert rendered_cache.reads == [key.stable_hash()]
    assert rendered_cache.writes == []
    assert fetcher.calls == []


def test_first_render_writes_durable_cache(monkeypatch: MonkeyPatch) -> None:
    """Source-rendered icons should be written to durable cache."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    rendered_cache = _FakeRenderedIconCache(assets={}, reads=[], writes=[])
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    factory = CubeIconFactory(
        asset_fetcher=fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
    )

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=cache",
            media_type="image/png",
        ),
        catalog_revision="catalog",
        cube_content_hash="content",
    )

    key = _cache_key()
    assert not icon.isNull()
    assert rendered_cache.reads == [key.stable_hash(), key.stable_hash()]
    assert rendered_cache.writes == [key.stable_hash()]
    assert key.stable_hash() in rendered_cache.assets
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=cache"]


def test_durable_cache_survives_factory_instances(monkeypatch: MonkeyPatch) -> None:
    """A second factory should read a durable row written by the first factory."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    rendered_cache = _FakeRenderedIconCache(assets={}, reads=[], writes=[])
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=cache",
        media_type="image/png",
    )
    first_fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    first_factory = CubeIconFactory(
        asset_fetcher=first_fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
    )
    first_factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
    )
    second_fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    second_factory = CubeIconFactory(
        asset_fetcher=second_fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
    )

    icon = second_factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
    )

    assert not icon.isNull()
    assert first_fetcher.calls == ["/sugarcubes/assets/icon?cube_id=cache"]
    assert second_fetcher.calls == []


def test_durable_cache_separates_theme_size_dpr_and_renderer(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rendered cache keys should separate theme, size, DPR, and renderer version."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    rendered_cache = _FakeRenderedIconCache(assets={}, reads=[], writes=[])
    descriptor = CubeIconDescriptor(
        kind="asset",
        url="/sugarcubes/assets/icon?cube_id=cache",
        media_type="image/png",
    )
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(
            content=_png_bytes([[(255, 255, 255, 255)]]),
            media_type="image/png",
        ),
        calls=[],
    )
    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    factory = CubeIconFactory(
        asset_fetcher=fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
        device_pixel_ratio_provider=lambda: 1.0,
    )
    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
    )
    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)
    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
    )
    factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
        render_size=3,
    )
    dpr_factory = CubeIconFactory(
        asset_fetcher=fetcher,
        rendered_cache=rendered_cache,
        target_key="target",
        fallback_render_size=2,
        device_pixel_ratio_provider=lambda: 2.0,
    )
    dpr_factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/cache.cube",
        display_name="Cache",
        icon=descriptor,
        catalog_revision="catalog",
        cube_content_hash="content",
    )
    stale_key = _cache_key(renderer_version=2)

    assert len(rendered_cache.assets) == 4
    assert stale_key.stable_hash() not in rendered_cache.assets


def test_png_resize_before_adjust_preserves_gray_details(
    monkeypatch: MonkeyPatch,
) -> None:
    """Target-size PNG adjustment should invert neutral detail after scaling."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    rows = [
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
    ]

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes(rows),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2)
    assert max(_rgb_at(image, 0, 0)) <= 5
    dark_gray = _rgb_at(image, 1, 0)
    assert 45 <= dark_gray[0] <= 60


def test_white_gray_svg_template_inverts_in_light_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Template SVG assets should preserve gray detail when inverted."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 1">'
        b'<rect width="1" height="1" fill="#ffffff"/>'
        b'<rect x="1" width="1" height="1" fill="#cccccc"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        color_behavior="template",
        render_size=20,
    )

    image = _icon_image(icon, 20, 20)
    black = _rgb_at(image, 5, 10)
    dark_gray = _rgb_at(image, 15, 10)
    assert max(black) <= 5
    assert 45 <= dark_gray[0] <= 60


def test_colored_svg_auto_asset_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Automatic color behavior should not transform colored SVG assets."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
        b'<rect width="1" height="1" fill="#dc1828"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        render_size=20,
    )

    red = _rgb_at(_icon_image(icon, 20, 20), 10, 10)
    assert red[0] >= 210
    assert red[1] <= 35
    assert red[2] <= 50


def test_current_color_svg_template_uses_theme_foreground(
    monkeypatch: MonkeyPatch,
) -> None:
    """Template SVG currentColor declarations should use the theme foreground."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
        b'<rect width="1" height="1" fill="currentColor"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        color_behavior="template",
        render_size=20,
    )

    foreground = _rgb_at(_icon_image(icon, 20, 20), 10, 10)
    assert 25 <= foreground[0] <= 40
    assert 25 <= foreground[1] <= 40
    assert 25 <= foreground[2] <= 40


def test_asset_icon_fetch_failure_returns_fallback_icon() -> None:
    """Icon fetch failures should fail closed to the generated fallback."""

    _ensure_qapp()

    fetcher = _FakeAssetFetcher(asset=None, calls=[])
    factory = CubeIconFactory(asset_fetcher=fetcher)

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Image to Image.cube",
        display_name="Image to Image",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Image%20to%20Image",
            media_type="image/png",
        ),
    )

    assert not icon.isNull()
    assert fetcher.calls == ["/sugarcubes/assets/icon?cube_id=Image%20to%20Image"]


def test_unsupported_or_external_asset_icon_descriptor_returns_fallback() -> None:
    """Only target-relative PNG/SVG asset descriptors should be fetched."""

    _ensure_qapp()
    fetcher = _FakeAssetFetcher(
        asset=CubeIconAsset(content=_PNG_BYTES, media_type="image/png"),
        calls=[],
    )
    factory = CubeIconFactory(asset_fetcher=fetcher)

    unsupported = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=CubeIconDescriptor(
            kind="asset",
            url="/sugarcubes/assets/icon?cube_id=Inpaint",
            media_type="image/gif",
        ),
    )
    external = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=CubeIconDescriptor(
            kind="asset",
            url="https://example.invalid/icon.png",
            media_type="image/png",
        ),
    )

    assert not unsupported.isNull()
    assert not external.isNull()
    assert fetcher.calls == []
