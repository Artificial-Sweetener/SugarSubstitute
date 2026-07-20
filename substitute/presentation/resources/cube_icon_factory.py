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

"""Resolve Cube Library icon descriptors into Qt presentation icons."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
import re
from time import perf_counter
from typing import cast
from xml.etree import ElementTree

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

from substitute.application.ports import (
    CubeIconAsset,
    CubeIconAssetFetcher,
    CubeIconCacheKey,
    RenderedCubeIconAsset,
    RenderedCubeIconCacheRepository,
)
from substitute.presentation.cubes.cube_alias_text_layout import split_cube_alias_prefix
from substitute.shared.qt_thumbnail_codec import (
    image_from_qt_thumbnail_payload,
    prepare_qt_thumbnail,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.resources.cube_icon_factory")
_ICON_WORD_SEPARATOR = re.compile(r"[\s/_-]+")
_SUPPORTED_ASSET_MEDIA_TYPES = {"image/png", "image/svg+xml"}
_FALLBACK_RENDER_SIZE = 96
_FALLBACK_FONT_SCALE = 62 / _FALLBACK_RENDER_SIZE
_ICON_COLOR_BEHAVIORS = {"auto", "template", "fullColor", "themeVariants"}
_GRAYSCALE_SPREAD_LIMIT = 18
_GRAYSCALE_CONFIDENCE_THRESHOLD = 0.88
_BRIGHT_LUMINANCE_THRESHOLD = 170.0
_DARK_LUMINANCE_THRESHOLD = 85.0
_VISIBLE_ALPHA_THRESHOLD = 16
_PNG_SAMPLE_SIZE = 32
_LIGHT_ICON_FOREGROUND = "#1F1F1F"
_DARK_ICON_FOREGROUND = "#FFFFFF"
_CUBE_ICON_RENDERER_VERSION = 3
_DEFAULT_MEMORY_CACHE_MAXIMUM_BYTES = 32 * 1024 * 1024
_CSS_RGB_PATTERN = re.compile(
    r"^rgb\(\s*(\d{1,3})(?:\s*,\s*|\s+)(\d{1,3})(?:\s*,\s*|\s+)(\d{1,3})\s*\)$",
    re.IGNORECASE,
)
_CSS_NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
}


@dataclass(frozen=True)
class CubeIconRequest:
    """Describe all data needed to resolve one cube icon."""

    cube_id: str
    display_name: str
    icon: object | None
    catalog_revision: str = ""
    cube_content_hash: str = ""
    logical_render_size: int = _FALLBACK_RENDER_SIZE
    device_pixel_ratio: float = 1.0


@dataclass(frozen=True)
class _ToneProfile:
    """Describe sampled visible-pixel tone characteristics for one asset."""

    visible_count: int
    grayscale_ratio: float
    mean_luminance: float


@dataclass(frozen=True)
class _SvgColorReference:
    """Describe one editable SVG color declaration."""

    element: ElementTree.Element
    attribute: str
    style_property: str
    raw_value: str
    rgb: tuple[int, int, int] | None
    current_color: bool


@dataclass(frozen=True)
class _CachedRenderedIcon:
    """Track one process-local rendered icon and its estimated size."""

    icon: QIcon
    byte_size: int


class _RenderedIconMemoryCache:
    """Keep a bounded LRU cache of rendered Qt icons for this process."""

    def __init__(self, *, maximum_bytes: int) -> None:
        """Create a rendered-icon memory cache with an approximate byte budget."""

        self._maximum_bytes = max(0, maximum_bytes)
        self._cached_bytes = 0
        self._icons: OrderedDict[str, _CachedRenderedIcon] = OrderedDict()

    def get(self, cache_key: str) -> QIcon | None:
        """Return a cached icon and mark it recently used."""

        cached = self._icons.get(cache_key)
        if cached is None:
            return None
        self._icons.move_to_end(cache_key)
        return cached.icon

    def store(self, cache_key: str, icon: QIcon, *, byte_size: int) -> None:
        """Store one icon and evict least-recently-used entries over budget."""

        previous = self._icons.pop(cache_key, None)
        if previous is not None:
            self._cached_bytes -= previous.byte_size
        normalized_size = max(0, byte_size)
        if self._maximum_bytes <= 0 or normalized_size > self._maximum_bytes:
            self._cached_bytes = max(0, self._cached_bytes)
            self._evict_over_budget()
            return
        self._icons[cache_key] = _CachedRenderedIcon(
            icon=icon,
            byte_size=normalized_size,
        )
        self._cached_bytes += normalized_size
        self._evict_over_budget()

    def clear(self) -> None:
        """Clear all process-local rendered icon entries."""

        self._icons.clear()
        self._cached_bytes = 0

    def _evict_over_budget(self) -> None:
        """Evict least-recently-used icons until the cache is under budget."""

        while self._cached_bytes > self._maximum_bytes and self._icons:
            _key, cached = self._icons.popitem(last=False)
            self._cached_bytes -= cached.byte_size
        self._cached_bytes = max(0, self._cached_bytes)


class CubeIconFactory:
    """Resolve Cube Library descriptors into Qt icons for presentation widgets."""

    def __init__(
        self,
        *,
        asset_fetcher: CubeIconAssetFetcher | None = None,
        rendered_cache: RenderedCubeIconCacheRepository | None = None,
        target_key: str = "",
        fallback_render_size: int = _FALLBACK_RENDER_SIZE,
        memory_cache_maximum_bytes: int = _DEFAULT_MEMORY_CACHE_MAXIMUM_BYTES,
        device_pixel_ratio_provider: Callable[[], float] | None = None,
    ) -> None:
        """Initialize icon resolution with optional target asset fetching."""

        self._asset_fetcher = asset_fetcher
        self._rendered_cache = rendered_cache
        self._target_key = target_key
        self._fallback_render_size = fallback_render_size
        self._device_pixel_ratio_provider = device_pixel_ratio_provider or (lambda: 1.0)
        self._asset_bytes_cache: dict[tuple[str, str], CubeIconAsset] = {}
        self._rendered_icon_cache = _RenderedIconMemoryCache(
            maximum_bytes=memory_cache_maximum_bytes,
        )
        self._fallback_cache: dict[tuple[str, str, int], QIcon] = {}

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> QIcon:
        """Return a declared asset icon or generated punchout fallback icon."""

        started_at = perf_counter()
        request = CubeIconRequest(
            cube_id=cube_id,
            display_name=display_name,
            icon=icon,
            catalog_revision=catalog_revision,
            cube_content_hash=cube_content_hash,
            logical_render_size=render_size or self._fallback_render_size,
            device_pixel_ratio=self._current_device_pixel_ratio(),
        )
        asset_icon = self._asset_icon(request)
        if asset_icon is not None and not asset_icon.isNull():
            _log_icon_debug_timing(
                "Cube icon resolved cube asset icon",
                started_at=started_at,
                cube_id=cube_id,
                display_name=display_name,
            )
            return asset_icon
        fallback_started_at = perf_counter()
        fallback_icon = self._fallback_icon(request)
        _log_icon_debug_timing(
            "Cube icon resolved cube fallback icon",
            started_at=started_at,
            cube_id=cube_id,
            display_name=display_name,
            fallback_elapsed_ms=_elapsed_ms(fallback_started_at),
        )
        return fallback_icon

    def icon_for_request(self, request: CubeIconRequest) -> QIcon:
        """Return an icon using the explicit request object form."""

        return self.icon_for_cube(
            cube_id=request.cube_id,
            display_name=request.display_name,
            icon=request.icon,
            catalog_revision=request.catalog_revision,
            cube_content_hash=request.cube_content_hash,
            render_size=request.logical_render_size,
        )

    def clear_asset_cache(self) -> None:
        """Clear fetched Cube Library asset bytes and rendered asset icons."""

        self._asset_bytes_cache.clear()
        self._rendered_icon_cache.clear()

    def warm_icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> bool:
        """Resolve one cube icon into cache for later presentation use."""

        resolved_icon = self.icon_for_cube(
            cube_id=cube_id,
            display_name=display_name,
            icon=icon,
            catalog_revision=catalog_revision,
            cube_content_hash=cube_content_hash,
            render_size=render_size,
        )
        return not resolved_icon.isNull()

    def _asset_icon(self, request: CubeIconRequest) -> QIcon | None:
        """Resolve a valid asset descriptor into a cached Qt icon."""

        descriptor = request.icon
        if descriptor is None or self._asset_fetcher is None:
            log_debug(
                _LOGGER,
                "Cube icon asset resolution skipped",
                cube_id=request.cube_id,
                reason="missing_descriptor_or_fetcher",
                has_descriptor=descriptor is not None,
                has_fetcher=self._asset_fetcher is not None,
            )
            return None
        kind = _icon_text_field(descriptor, "kind")
        relative_url = _icon_text_field(descriptor, "url")
        media_type = _icon_text_field(descriptor, "media_type").lower()
        color_behavior = _icon_color_behavior(descriptor)
        if kind != "asset":
            log_debug(
                _LOGGER,
                "Cube icon asset resolution skipped",
                cube_id=request.cube_id,
                reason="non_asset_descriptor",
                icon_kind=kind,
            )
            return None
        if media_type and media_type not in _SUPPORTED_ASSET_MEDIA_TYPES:
            log_debug(
                _LOGGER,
                "Cube icon asset resolution skipped",
                cube_id=request.cube_id,
                reason="unsupported_media_type",
                icon_url=relative_url,
                media_type=media_type,
                color_behavior=color_behavior,
            )
            return None
        if not _is_target_relative_url(relative_url):
            log_debug(
                _LOGGER,
                "Cube icon asset resolution skipped",
                cube_id=request.cube_id,
                reason="unsafe_or_empty_url",
                icon_url=relative_url,
                media_type=media_type,
                color_behavior=color_behavior,
            )
            return None
        theme_name = "dark" if _is_dark_theme() else "light"
        if media_type:
            cache_key = self._cache_key(
                request,
                icon_kind=kind,
                relative_url=relative_url,
                media_type=media_type,
                color_behavior=color_behavior,
                theme_name=theme_name,
            )
            cached_icon = self._cached_rendered_icon(cache_key, request.cube_id)
            if cached_icon is not None:
                return cached_icon
        asset_started_at = perf_counter()
        asset = self._fetch_asset(
            relative_url=relative_url,
            declared_media_type=media_type,
            cube_id=request.cube_id,
        )
        asset_elapsed_ms = _elapsed_ms(asset_started_at)
        if asset is None:
            log_debug(
                _LOGGER,
                "Cube icon asset unavailable",
                cube_id=request.cube_id,
                icon_url=relative_url,
                media_type=media_type,
                color_behavior=color_behavior,
                theme_name=theme_name,
                asset_elapsed_ms=f"{asset_elapsed_ms:.3f}",
            )
            return None
        resolved_media_type = asset.media_type.lower()
        cache_key = self._cache_key(
            request,
            icon_kind=kind,
            relative_url=relative_url,
            media_type=resolved_media_type,
            color_behavior=color_behavior,
            theme_name=theme_name,
        )
        cached_icon = self._cached_rendered_icon(cache_key, request.cube_id)
        if cached_icon is not None:
            return cached_icon
        decode_started_at = perf_counter()
        loaded_image = _decode_icon_bytes(
            asset.content,
            resolved_media_type,
            request.logical_render_size,
            device_pixel_ratio=request.device_pixel_ratio,
            color_behavior=color_behavior,
            theme_name=theme_name,
            cube_id=request.cube_id,
            icon_url=relative_url,
        )
        decode_elapsed_ms = _elapsed_ms(decode_started_at)
        if loaded_image is not None and not loaded_image.isNull():
            loaded_icon = _icon_from_image(
                loaded_image,
                device_pixel_ratio=request.device_pixel_ratio,
            )
            self._rendered_icon_cache.store(
                cache_key.stable_hash(),
                loaded_icon,
                byte_size=_estimated_image_bytes(loaded_image),
            )
            self._write_rendered_icon(cache_key, loaded_image)
            log_debug(
                _LOGGER,
                "Cube rendered icon cache miss filled",
                cube_id=request.cube_id,
                icon_url=relative_url,
                media_type=resolved_media_type,
                color_behavior=color_behavior,
                theme_name=theme_name,
                asset_elapsed_ms=f"{asset_elapsed_ms:.3f}",
                decode_elapsed_ms=f"{decode_elapsed_ms:.3f}",
                content_bytes=len(asset.content),
                render_size=request.logical_render_size,
                device_pixel_ratio=f"{request.device_pixel_ratio:.3f}",
            )
            return loaded_icon
        log_debug(
            _LOGGER,
            "Cube rendered icon decode failed",
            cube_id=request.cube_id,
            icon_url=relative_url,
            media_type=resolved_media_type,
            color_behavior=color_behavior,
            theme_name=theme_name,
            asset_elapsed_ms=f"{asset_elapsed_ms:.3f}",
            decode_elapsed_ms=f"{decode_elapsed_ms:.3f}",
            content_bytes=len(asset.content),
            render_size=request.logical_render_size,
            device_pixel_ratio=f"{request.device_pixel_ratio:.3f}",
        )
        return None

    def _cache_key(
        self,
        request: CubeIconRequest,
        *,
        icon_kind: str,
        relative_url: str,
        media_type: str,
        color_behavior: str,
        theme_name: str,
    ) -> CubeIconCacheKey:
        """Return the complete rendered-icon cache key for one request."""

        descriptor = request.icon
        repo_relative_path = (
            _icon_text_field(descriptor, "repo_relative_path")
            if descriptor is not None
            else ""
        )
        return CubeIconCacheKey(
            target_key=self._target_key,
            catalog_revision=request.catalog_revision,
            cube_id=request.cube_id,
            cube_content_hash=request.cube_content_hash,
            icon_kind=icon_kind,
            icon_url=relative_url,
            media_type=media_type,
            repo_relative_path=repo_relative_path,
            color_behavior=color_behavior,
            theme_name=theme_name,
            logical_size=request.logical_render_size,
            device_pixel_ratio=request.device_pixel_ratio,
            renderer_version=_CUBE_ICON_RENDERER_VERSION,
        )

    def _cached_rendered_icon(
        self,
        cache_key: CubeIconCacheKey,
        cube_id: str,
    ) -> QIcon | None:
        """Return a memory or durable rendered icon cache hit."""

        stable_key = cache_key.stable_hash()
        cached_icon = self._rendered_icon_cache.get(stable_key)
        if cached_icon is not None:
            log_debug(
                _LOGGER,
                "Cube icon memory cache hit",
                cube_id=cube_id,
                cache_key=stable_key,
                theme_name=cache_key.theme_name,
                render_size=cache_key.logical_size,
                device_pixel_ratio=f"{cache_key.device_pixel_ratio:.3f}",
            )
            return cached_icon
        if self._rendered_cache is None:
            return None
        try:
            asset = self._rendered_cache.read_rendered_icon(cache_key)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Cube icon durable cache read failed",
                cube_id=cube_id,
                cache_key=stable_key,
                error=repr(error),
            )
            return None
        if asset is None:
            log_debug(
                _LOGGER,
                "Cube icon durable cache miss",
                cube_id=cube_id,
                cache_key=stable_key,
                theme_name=cache_key.theme_name,
                render_size=cache_key.logical_size,
                device_pixel_ratio=f"{cache_key.device_pixel_ratio:.3f}",
            )
            return None
        image = image_from_qt_thumbnail_payload(
            width=asset.width,
            height=asset.height,
            qt_format=asset.qt_format,
            bytes_per_line=asset.bytes_per_line,
            payload=asset.payload,
        )
        if image is None:
            log_warning(
                _LOGGER,
                "Cube icon durable cache payload was invalid",
                cube_id=cube_id,
                cache_key=stable_key,
            )
            return None
        icon = _icon_from_image(image, device_pixel_ratio=cache_key.device_pixel_ratio)
        if icon.isNull():
            return None
        self._rendered_icon_cache.store(
            stable_key,
            icon,
            byte_size=asset.byte_size,
        )
        log_debug(
            _LOGGER,
            "Cube icon durable cache hit",
            cube_id=cube_id,
            cache_key=stable_key,
            theme_name=cache_key.theme_name,
            render_size=cache_key.logical_size,
            device_pixel_ratio=f"{cache_key.device_pixel_ratio:.3f}",
            byte_size=asset.byte_size,
        )
        return icon

    def _write_rendered_icon(
        self,
        cache_key: CubeIconCacheKey,
        image: QImage,
    ) -> None:
        """Persist one rendered image in the durable rendered icon cache."""

        if self._rendered_cache is None:
            return
        prepared = prepare_qt_thumbnail(image)
        asset = RenderedCubeIconAsset(
            cache_key=cache_key.stable_hash(),
            width=prepared.width,
            height=prepared.height,
            qt_format=prepared.qt_format,
            bytes_per_line=prepared.bytes_per_line,
            content_format=prepared.content_format,
            payload=prepared.payload,
        )
        try:
            self._rendered_cache.write_rendered_icon(cache_key, asset)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Cube icon durable cache write failed",
                cube_id=cache_key.cube_id,
                cache_key=asset.cache_key,
                error=repr(error),
            )

    def _current_device_pixel_ratio(self) -> float:
        """Return a valid current device pixel ratio for icon rendering."""

        try:
            value = float(self._device_pixel_ratio_provider())
        except Exception:
            return 1.0
        if value <= 0.0:
            return 1.0
        return value

    def _fetch_asset(
        self,
        *,
        relative_url: str,
        declared_media_type: str,
        cube_id: str,
    ) -> CubeIconAsset | None:
        """Fetch one remote asset icon and cache raw bytes for theme rendering."""

        cache_key = (relative_url, declared_media_type)
        cached_asset = self._asset_bytes_cache.get(cache_key)
        if cached_asset is not None:
            log_debug(
                _LOGGER,
                "Cube raw icon asset cache hit",
                cube_id=cube_id,
                icon_url=relative_url,
                declared_media_type=declared_media_type,
                resolved_media_type=cached_asset.media_type,
                content_bytes=len(cached_asset.content),
            )
            return cached_asset
        try:
            if self._asset_fetcher is None:
                return None
            fetch_started_at = perf_counter()
            asset = self._asset_fetcher.fetch_icon_asset(relative_url)
            fetch_elapsed_ms = _elapsed_ms(fetch_started_at)
            if asset is None:
                log_debug(
                    _LOGGER,
                    "Cube raw icon asset fetch returned none",
                    cube_id=cube_id,
                    icon_url=relative_url,
                    declared_media_type=declared_media_type,
                    fetch_elapsed_ms=f"{fetch_elapsed_ms:.3f}",
                )
                return None
            media_type = declared_media_type or asset.media_type.lower()
            if media_type not in _SUPPORTED_ASSET_MEDIA_TYPES:
                log_debug(
                    _LOGGER,
                    "Cube raw icon asset unsupported after fetch",
                    cube_id=cube_id,
                    icon_url=relative_url,
                    declared_media_type=declared_media_type,
                    resolved_media_type=media_type,
                    fetch_elapsed_ms=f"{fetch_elapsed_ms:.3f}",
                    content_bytes=len(asset.content),
                )
                return None
            cached_asset = CubeIconAsset(content=asset.content, media_type=media_type)
            self._asset_bytes_cache[cache_key] = cached_asset
            self._asset_bytes_cache[(relative_url, media_type)] = cached_asset
            log_debug(
                _LOGGER,
                "Cube raw icon asset cache miss filled",
                cube_id=cube_id,
                icon_url=relative_url,
                declared_media_type=declared_media_type,
                resolved_media_type=media_type,
                fetch_elapsed_ms=f"{fetch_elapsed_ms:.3f}",
                content_bytes=len(asset.content),
            )
            return cached_asset
        except Exception as error:
            log_warning(
                _LOGGER,
                "Fell back after Cube Library icon fetch failed",
                cube_id=cube_id,
                icon_url=relative_url,
                error=f"{type(error).__name__}: {error}",
            )
            return None

    def _fallback_icon(self, request: CubeIconRequest) -> QIcon:
        """Return a cached text-only fallback icon for one cube."""

        initials = derive_cube_initials(
            request.display_name,
            fallback_text=request.cube_id,
        )
        theme_name = "dark" if _is_dark_theme() else "light"
        cache_key = (initials, theme_name, self._fallback_render_size)
        cached_icon = self._fallback_cache.get(cache_key)
        if cached_icon is not None:
            return cached_icon
        icon = QIcon(
            _render_text_fallback_pixmap(
                initials=initials,
                render_size=self._fallback_render_size,
            )
        )
        self._fallback_cache[cache_key] = icon
        return icon


def derive_cube_initials(label: str, *, fallback_text: str = "?") -> str:
    """Return SugarCubes-style two-letter initials for a cube display label."""

    words = _initial_words(_fallback_initials_label(label))
    if not words:
        words = _initial_words(_fallback_initials_label(fallback_text))
    if not words:
        return "?"
    if len(words) == 1:
        initials = words[0][:2]
    else:
        initials = f"{words[0][0]}{words[-1][0]}"
    return initials.upper()[:2]


def _fallback_initials_label(label: str) -> str:
    """Return the cube-name body used for generated fallback icon initials."""

    parts = split_cube_alias_prefix(label)
    return parts.body if parts.prefix else label


def _initial_words(label: str) -> list[str]:
    """Return alphanumeric words used by the fallback initials algorithm."""

    words: list[str] = []
    for raw_word in _ICON_WORD_SEPARATOR.split(label.strip()):
        word = "".join(character for character in raw_word if character.isalnum())
        if word:
            words.append(word)
    return words


def _decode_icon_bytes(
    content: bytes,
    media_type: str,
    render_size: int,
    *,
    device_pixel_ratio: float,
    color_behavior: str,
    theme_name: str,
    cube_id: str,
    icon_url: str,
) -> QImage | None:
    """Decode PNG or SVG bytes into a target-sized Qt image."""

    started_at = perf_counter()
    physical_size = _physical_render_size(render_size, device_pixel_ratio)
    if media_type == "image/png":
        image = QImage()
        if not image.loadFromData(QByteArray(content)):
            _log_icon_debug_timing(
                "Cube icon PNG icon loadFromData failed",
                started_at=started_at,
                cube_id=cube_id,
                icon_url=icon_url,
                media_type=media_type,
                color_behavior=color_behavior,
                theme_name=theme_name,
                content_bytes=len(content),
            )
            return None
        source_width = image.width()
        source_height = image.height()
        scale_started_at = perf_counter()
        image = _scale_image_for_icon(image, physical_size)
        scale_elapsed_ms = _elapsed_ms(scale_started_at)
        adjust_started_at = perf_counter()
        image = _theme_adjust_png_image(
            image,
            color_behavior=color_behavior,
            theme_name=theme_name,
            cube_id=cube_id,
            icon_url=icon_url,
        )
        adjust_elapsed_ms = _elapsed_ms(adjust_started_at)
        _log_icon_debug_timing(
            "Cube icon decoded PNG cube icon",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            media_type=media_type,
            color_behavior=color_behavior,
            theme_name=theme_name,
            content_bytes=len(content),
            render_size=render_size,
            device_pixel_ratio=f"{device_pixel_ratio:.3f}",
            physical_size=physical_size,
            source_width=source_width,
            source_height=source_height,
            image_width=image.width(),
            image_height=image.height(),
            scale_elapsed_ms=f"{scale_elapsed_ms:.3f}",
            adjust_elapsed_ms=f"{adjust_elapsed_ms:.3f}",
        )
        return image
    if media_type == "image/svg+xml":
        adjust_started_at = perf_counter()
        adjusted_content = _theme_adjust_svg_content(
            content,
            color_behavior=color_behavior,
            theme_name=theme_name,
            cube_id=cube_id,
            icon_url=icon_url,
        )
        adjust_elapsed_ms = _elapsed_ms(adjust_started_at)
        renderer_started_at = perf_counter()
        renderer = QSvgRenderer(QByteArray(adjusted_content))
        renderer_elapsed_ms = _elapsed_ms(renderer_started_at)
        if not renderer.isValid():
            _log_icon_debug_timing(
                "Cube icon SVG icon renderer invalid",
                started_at=started_at,
                cube_id=cube_id,
                icon_url=icon_url,
                media_type=media_type,
                color_behavior=color_behavior,
                theme_name=theme_name,
                content_bytes=len(content),
                adjusted_content_bytes=len(adjusted_content),
                adjust_elapsed_ms=f"{adjust_elapsed_ms:.3f}",
                renderer_elapsed_ms=f"{renderer_elapsed_ms:.3f}",
            )
            return None
        image = QImage(
            physical_size,
            physical_size,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            render_started_at = perf_counter()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(
                painter,
                QRectF(0.0, 0.0, float(physical_size), float(physical_size)),
            )
        finally:
            painter.end()
        _log_icon_debug_timing(
            "Cube icon decoded SVG cube icon",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            media_type=media_type,
            color_behavior=color_behavior,
            theme_name=theme_name,
            content_bytes=len(content),
            adjusted_content_bytes=len(adjusted_content),
            render_size=render_size,
            device_pixel_ratio=f"{device_pixel_ratio:.3f}",
            physical_size=physical_size,
            adjust_elapsed_ms=f"{adjust_elapsed_ms:.3f}",
            renderer_elapsed_ms=f"{renderer_elapsed_ms:.3f}",
            svg_render_elapsed_ms=f"{_elapsed_ms(render_started_at):.3f}",
        )
        return image
    return None


def _icon_text_field(descriptor: object, name: str) -> str:
    """Read one string field from a descriptor-like object."""

    value = getattr(descriptor, name, "")
    return value.strip() if isinstance(value, str) else ""


def _icon_color_behavior(descriptor: object) -> str:
    """Return the normalized icon color behavior from a descriptor-like object."""

    value = _icon_text_field(descriptor, "color_behavior")
    if value in _ICON_COLOR_BEHAVIORS:
        return value
    return "auto"


def _is_target_relative_url(relative_url: str) -> bool:
    """Return whether a descriptor URL is safe to fetch from the active target."""

    return (
        relative_url.startswith("/")
        and not relative_url.startswith("//")
        and not any(character.isspace() for character in relative_url)
    )


def _elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds for icon diagnostic timing."""

    return max(0.0, (perf_counter() - started_at) * 1000.0)


def _log_icon_debug_timing(
    message: str,
    *,
    started_at: float,
    **context: object,
) -> None:
    """Emit one debug-only icon timing log entry with elapsed milliseconds."""

    log_context = dict(context)
    log_context["elapsed_ms"] = f"{_elapsed_ms(started_at):.3f}"
    log_debug(_LOGGER, message, **log_context)


def _physical_render_size(logical_size: int, device_pixel_ratio: float) -> int:
    """Return the physical pixel size for one logical icon size."""

    return max(1, round(max(1, logical_size) * max(0.1, device_pixel_ratio)))


def _scale_image_for_icon(image: QImage, physical_size: int) -> QImage:
    """Return the source image scaled to the rendered icon target size."""

    if image.isNull():
        return image
    if image.width() == physical_size and image.height() == physical_size:
        return image
    scaled_image: QImage = image.scaled(
        physical_size,
        physical_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return scaled_image


def _icon_from_image(image: QImage, *, device_pixel_ratio: float) -> QIcon:
    """Return a Qt icon for a rendered image payload."""

    pixmap = QPixmap.fromImage(image)
    if not pixmap.isNull():
        pixmap.setDevicePixelRatio(max(0.1, device_pixel_ratio))
    return QIcon(pixmap)


def _estimated_image_bytes(image: QImage) -> int:
    """Return a conservative memory byte estimate for one image."""

    return max(0, image.width()) * max(0, image.height()) * 4


def _theme_adjust_png_image(
    image: QImage,
    *,
    color_behavior: str,
    theme_name: str,
    cube_id: str,
    icon_url: str,
) -> QImage:
    """Return a theme-adjusted PNG image when it is safely template-like."""

    started_at = perf_counter()
    if color_behavior in {"fullColor", "themeVariants"}:
        _log_icon_debug_timing(
            "Cube icon PNG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="declared_passthrough",
            image_width=image.width(),
            image_height=image.height(),
        )
        return image
    profile = _sample_image_tone_profile(image)
    if profile is None:
        _log_icon_debug_timing(
            "Cube icon PNG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="no_visible_pixels",
            image_width=image.width(),
            image_height=image.height(),
        )
        return image
    if profile.grayscale_ratio < _GRAYSCALE_CONFIDENCE_THRESHOLD:
        if color_behavior == "template":
            log_warning(
                _LOGGER,
                "Template Cube Library PNG icon contained color and was left unchanged",
                cube_id=cube_id,
                icon_url=icon_url,
                color_behavior=color_behavior,
                theme_name=theme_name,
            )
        _log_icon_debug_timing(
            "Cube icon PNG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="not_grayscale_confident",
            image_width=image.width(),
            image_height=image.height(),
            visible_count=profile.visible_count,
            grayscale_ratio=f"{profile.grayscale_ratio:.3f}",
            mean_luminance=f"{profile.mean_luminance:.3f}",
        )
        return image
    if not _tone_profile_mismatches_theme(profile, theme_name):
        _log_icon_debug_timing(
            "Cube icon PNG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="theme_polarity_already_ok",
            image_width=image.width(),
            image_height=image.height(),
            visible_count=profile.visible_count,
            grayscale_ratio=f"{profile.grayscale_ratio:.3f}",
            mean_luminance=f"{profile.mean_luminance:.3f}",
        )
        return image
    invert_started_at = perf_counter()
    adjusted = _invert_neutral_image_pixels(image)
    _log_icon_debug_timing(
        "Cube icon PNG icon color adjustment applied",
        started_at=started_at,
        cube_id=cube_id,
        icon_url=icon_url,
        color_behavior=color_behavior,
        theme_name=theme_name,
        reason="theme_polarity_mismatch",
        image_width=image.width(),
        image_height=image.height(),
        visible_count=profile.visible_count,
        grayscale_ratio=f"{profile.grayscale_ratio:.3f}",
        mean_luminance=f"{profile.mean_luminance:.3f}",
        invert_elapsed_ms=f"{_elapsed_ms(invert_started_at):.3f}",
    )
    return adjusted


def _sample_image_tone_profile(image: QImage) -> _ToneProfile | None:
    """Return a low-cost grayscale and luminance profile for one image."""

    sample = image
    if image.width() > _PNG_SAMPLE_SIZE or image.height() > _PNG_SAMPLE_SIZE:
        sample = image.scaled(
            _PNG_SAMPLE_SIZE,
            _PNG_SAMPLE_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    visible_count = 0
    grayscale_count = 0
    luminance_total = 0.0
    for y in range(sample.height()):
        for x in range(sample.width()):
            color = sample.pixelColor(x, y)
            if color.alpha() < _VISIBLE_ALPHA_THRESHOLD:
                continue
            visible_count += 1
            spread = max(color.red(), color.green(), color.blue()) - min(
                color.red(), color.green(), color.blue()
            )
            if spread <= _GRAYSCALE_SPREAD_LIMIT:
                grayscale_count += 1
            luminance_total += _rgb_luminance(
                color.red(),
                color.green(),
                color.blue(),
            )
    if visible_count == 0:
        return None
    return _ToneProfile(
        visible_count=visible_count,
        grayscale_ratio=grayscale_count / visible_count,
        mean_luminance=luminance_total / visible_count,
    )


def _tone_profile_mismatches_theme(profile: _ToneProfile, theme_name: str) -> bool:
    """Return whether one neutral asset has the wrong polarity for the theme."""

    if theme_name == "light":
        return profile.mean_luminance >= _BRIGHT_LUMINANCE_THRESHOLD
    return profile.mean_luminance <= _DARK_LUMINANCE_THRESHOLD


def _invert_neutral_image_pixels(image: QImage) -> QImage:
    """Invert neutral visible pixels while preserving alpha and colored details."""

    adjusted: QImage = image.convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(adjusted.height()):
        for x in range(adjusted.width()):
            color = adjusted.pixelColor(x, y)
            if color.alpha() <= 0:
                continue
            spread = max(color.red(), color.green(), color.blue()) - min(
                color.red(), color.green(), color.blue()
            )
            if spread > _GRAYSCALE_SPREAD_LIMIT:
                continue
            color.setRed(255 - color.red())
            color.setGreen(255 - color.green())
            color.setBlue(255 - color.blue())
            adjusted.setPixelColor(x, y, color)
    return adjusted


def _theme_adjust_svg_content(
    content: bytes,
    *,
    color_behavior: str,
    theme_name: str,
    cube_id: str,
    icon_url: str,
) -> bytes:
    """Return theme-adjusted SVG bytes when the markup is safely template-like."""

    started_at = perf_counter()
    if color_behavior in {"fullColor", "themeVariants"}:
        _log_icon_debug_timing(
            "Cube icon SVG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="declared_passthrough",
            content_bytes=len(content),
        )
        return content
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        log_warning(
            _LOGGER,
            "Cube Library SVG icon parse failed and was left unchanged",
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            error=repr(error),
        )
        _log_icon_debug_timing(
            "Cube icon SVG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="parse_failed",
            content_bytes=len(content),
            error=repr(error),
        )
        return content
    references = _svg_color_references(root)
    if not references:
        _log_icon_debug_timing(
            "Cube icon SVG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="no_color_references",
            content_bytes=len(content),
        )
        return content
    if any(_svg_reference_is_colored(reference) for reference in references):
        if color_behavior == "template":
            log_warning(
                _LOGGER,
                "Template Cube Library SVG icon contained color and was left unchanged",
                cube_id=cube_id,
                icon_url=icon_url,
                color_behavior=color_behavior,
                theme_name=theme_name,
            )
        _log_icon_debug_timing(
            "Cube icon SVG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="colored_or_unsupported_references",
            content_bytes=len(content),
            reference_count=len(references),
        )
        return content
    neutral_colors = [
        reference.rgb for reference in references if reference.rgb is not None
    ]
    has_current_color = any(reference.current_color for reference in references)
    should_invert = False
    if neutral_colors:
        profile = _profile_svg_colors(neutral_colors)
        should_invert = _tone_profile_mismatches_theme(profile, theme_name)
    if not should_invert and not has_current_color:
        _log_icon_debug_timing(
            "Cube icon SVG icon color adjustment skipped",
            started_at=started_at,
            cube_id=cube_id,
            icon_url=icon_url,
            color_behavior=color_behavior,
            theme_name=theme_name,
            reason="theme_polarity_already_ok",
            content_bytes=len(content),
            reference_count=len(references),
            neutral_color_count=len(neutral_colors),
            has_current_color=has_current_color,
        )
        return content
    for reference in references:
        replacement = _svg_replacement_color(
            reference,
            theme_name=theme_name,
            should_invert=should_invert,
        )
        if replacement is not None:
            _apply_svg_color_reference(reference, replacement)
    adjusted = cast(bytes, ElementTree.tostring(root, encoding="utf-8"))
    _log_icon_debug_timing(
        "Cube icon SVG icon color adjustment applied",
        started_at=started_at,
        cube_id=cube_id,
        icon_url=icon_url,
        color_behavior=color_behavior,
        theme_name=theme_name,
        reason="current_color_or_theme_polarity_mismatch",
        content_bytes=len(content),
        adjusted_content_bytes=len(adjusted),
        reference_count=len(references),
        neutral_color_count=len(neutral_colors),
        has_current_color=has_current_color,
        should_invert=should_invert,
    )
    return adjusted


def _svg_color_references(
    root: ElementTree.Element,
) -> list[_SvgColorReference]:
    """Return editable SVG fill and stroke color references."""

    references: list[_SvgColorReference] = []
    for element in root.iter():
        for attribute in ("fill", "stroke"):
            raw_value = element.attrib.get(attribute)
            if raw_value is not None:
                reference = _svg_color_reference(
                    element,
                    attribute=attribute,
                    style_property="",
                    raw_value=raw_value,
                )
                if reference is not None:
                    references.append(reference)
        references.extend(_svg_style_color_references(element))
    return references


def _svg_style_color_references(
    element: ElementTree.Element,
) -> list[_SvgColorReference]:
    """Return editable fill and stroke references from one style attribute."""

    style = element.attrib.get("style", "")
    if not style:
        return []
    references: list[_SvgColorReference] = []
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        property_name, raw_value = declaration.split(":", maxsplit=1)
        property_name = property_name.strip()
        if property_name not in {"fill", "stroke"}:
            continue
        reference = _svg_color_reference(
            element,
            attribute="style",
            style_property=property_name,
            raw_value=raw_value,
        )
        if reference is not None:
            references.append(reference)
    return references


def _svg_color_reference(
    element: ElementTree.Element,
    *,
    attribute: str,
    style_property: str,
    raw_value: str,
) -> _SvgColorReference | None:
    """Return a parsed SVG color reference when it is relevant to icon tone."""

    normalized = raw_value.strip()
    if not normalized or normalized.lower() == "none":
        return None
    if normalized.lower().startswith("url("):
        return _SvgColorReference(
            element=element,
            attribute=attribute,
            style_property=style_property,
            raw_value=raw_value,
            rgb=None,
            current_color=False,
        )
    if normalized.lower() == "currentcolor":
        return _SvgColorReference(
            element=element,
            attribute=attribute,
            style_property=style_property,
            raw_value=raw_value,
            rgb=None,
            current_color=True,
        )
    return _SvgColorReference(
        element=element,
        attribute=attribute,
        style_property=style_property,
        raw_value=raw_value,
        rgb=_parse_css_rgb(normalized),
        current_color=False,
    )


def _svg_reference_is_colored(reference: _SvgColorReference) -> bool:
    """Return whether one SVG color reference is unsupported or chromatic."""

    if reference.current_color:
        return False
    if reference.rgb is None:
        return True
    return _rgb_spread(reference.rgb) > _GRAYSCALE_SPREAD_LIMIT


def _profile_svg_colors(colors: list[tuple[int, int, int]]) -> _ToneProfile:
    """Return a tone profile for parsed SVG color declarations."""

    grayscale_count = sum(
        1 for color in colors if _rgb_spread(color) <= _GRAYSCALE_SPREAD_LIMIT
    )
    luminance_total = sum(_rgb_luminance(*color) for color in colors)
    return _ToneProfile(
        visible_count=len(colors),
        grayscale_ratio=grayscale_count / len(colors),
        mean_luminance=luminance_total / len(colors),
    )


def _svg_replacement_color(
    reference: _SvgColorReference,
    *,
    theme_name: str,
    should_invert: bool,
) -> str | None:
    """Return the replacement CSS color for one editable SVG reference."""

    if reference.current_color:
        return _theme_icon_foreground(theme_name)
    if reference.rgb is None:
        return None
    if should_invert:
        red, green, blue = reference.rgb
        return _format_rgb((255 - red, 255 - green, 255 - blue))
    return None


def _apply_svg_color_reference(
    reference: _SvgColorReference,
    replacement: str,
) -> None:
    """Apply one replacement SVG color to an attribute or style declaration."""

    if reference.attribute != "style":
        reference.element.set(reference.attribute, replacement)
        return
    declarations: list[str] = []
    style = reference.element.attrib.get("style", "")
    for declaration in style.split(";"):
        if not declaration.strip():
            continue
        if ":" not in declaration:
            declarations.append(declaration.strip())
            continue
        property_name, raw_value = declaration.split(":", maxsplit=1)
        if property_name.strip() == reference.style_property:
            declarations.append(f"{property_name.strip()}: {replacement}")
        else:
            declarations.append(f"{property_name.strip()}: {raw_value.strip()}")
    reference.element.set("style", "; ".join(declarations))


def _parse_css_rgb(raw_value: str) -> tuple[int, int, int] | None:
    """Parse common CSS RGB color forms used by authored icon SVGs."""

    normalized = raw_value.strip().lower()
    if normalized in _CSS_NAMED_COLORS:
        return _CSS_NAMED_COLORS[normalized]
    if normalized.startswith("#"):
        return _parse_hex_rgb(normalized)
    match = _CSS_RGB_PATTERN.match(normalized)
    if match is None:
        return None
    red, green, blue = (int(group) for group in match.groups())
    if red > 255 or green > 255 or blue > 255:
        return None
    return (red, green, blue)


def _parse_hex_rgb(raw_value: str) -> tuple[int, int, int] | None:
    """Parse short and long hex RGB color values."""

    value = raw_value.removeprefix("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6 or not all(
        character in "0123456789abcdef" for character in value
    ):
        return None
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _rgb_spread(color: tuple[int, int, int]) -> int:
    """Return the maximum channel spread for one RGB color."""

    return max(color) - min(color)


def _rgb_luminance(red: int, green: int, blue: int) -> float:
    """Return relative luminance for one sRGB color."""

    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _format_rgb(color: tuple[int, int, int]) -> str:
    """Return a normalized CSS hex RGB color."""

    return f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"


def _theme_icon_foreground(theme_name: str) -> str:
    """Return the primary icon foreground token for one theme."""

    if theme_name == "light":
        return _LIGHT_ICON_FOREGROUND
    return _DARK_ICON_FOREGROUND


def _render_text_fallback_pixmap(*, initials: str, render_size: int) -> QPixmap:
    """Render maximum-size text initials for cubes without asset icons."""

    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        _draw_scaled_fallback_text(
            painter,
            initials=initials,
            text_area=_fallback_text_area(render_size),
            render_size=render_size,
        )
    finally:
        painter.end()
    return pixmap


def _draw_scaled_fallback_text(
    painter: QPainter,
    *,
    initials: str,
    text_area: QRectF,
    render_size: int,
) -> None:
    """Draw fallback initials at normalized size, shrinking only on overflow."""

    path = QPainterPath()
    path.addText(0.0, 0.0, _fallback_font(render_size), initials)
    bounds = path.boundingRect()
    if bounds.isEmpty():
        return

    scale = min(
        1.0,
        text_area.width() / bounds.width(),
        text_area.height() / bounds.height(),
    )
    drawn_width = bounds.width() * scale
    drawn_height = bounds.height() * scale
    offset_x = text_area.x() + ((text_area.width() - drawn_width) / 2.0)
    offset_y = text_area.y() + ((text_area.height() - drawn_height) / 2.0)

    painter.save()
    painter.translate(offset_x, offset_y)
    painter.scale(scale, scale)
    painter.translate(-bounds.x(), -bounds.y())
    painter.fillPath(path, _fallback_text_color())
    painter.restore()


def _fallback_text_color() -> QColor:
    """Return theme-aware text color for transparent fallback icons."""

    if _is_dark_theme():
        return QColor("#ffffff")
    return QColor("#000000")


def _is_dark_theme() -> bool:
    """Return the active Fluent theme only when icon rendering needs it."""

    return bool(isDarkTheme())


def isDarkTheme() -> bool:
    """Return the active Fluent dark-theme state through a lazy import boundary."""

    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme as fluent_is_dark_theme,
    )

    return bool(fluent_is_dark_theme())


def _fallback_font(render_size: int) -> QFont:
    """Return the normalized fallback font for the requested icon footprint."""

    font = QFont()
    font.setBold(True)
    font.setPixelSize(max(10, round(render_size * _FALLBACK_FONT_SCALE)))
    return font


def _fallback_text_area(render_size: int) -> QRectF:
    """Return the full icon footprint available to fallback text."""

    text_area: QRectF = QRectF(
        0.0,
        0.0,
        float(render_size),
        float(render_size),
    ).adjusted(
        2.0,
        2.0,
        -2.0,
        -2.0,
    )
    return text_area


__all__ = [
    "CubeIconFactory",
    "CubeIconRequest",
    "derive_cube_initials",
]
