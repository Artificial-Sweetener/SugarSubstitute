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


from PySide6.QtGui import QColor

from substitute.domain.cube_library import CubeIconDescriptor
from substitute.application.ports import (
    CubeIconAsset,
)
from substitute.presentation.resources.cube_icon_factory import (
    CubeIconFactory,
)


from pytest import MonkeyPatch
from tests.presentation.resources.cube_icon_factory.support import (
    _PNG_BYTES,
    _FakeAssetFetcher,
    _FakeRenderedIconCache,
    _cache_key,
    _ensure_qapp,
    _icon_image,
    _png_bytes,
    _rendered_asset,
    _rgb_at,
)


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
