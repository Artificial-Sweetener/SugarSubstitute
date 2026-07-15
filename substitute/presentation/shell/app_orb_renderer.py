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

"""Render the accent-aware layered application orb."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PIL import Image

try:
    from qfluentwidgets.common.config import qconfig  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs
    qconfig = None
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.resources.app_orb_assets import (
    AppOrbLayerName,
    app_orb_layer_resource_path,
    ensure_app_orb_resources_registered,
)

_ORB_SOURCE_CANVAS_WIDTH = 1146
_ORB_SOURCE_CANVAS_HEIGHT = 1160
_ICON_SOURCE_LEFT = 109
_ICON_SOURCE_TOP = 98
_ICON_SOURCE_WIDTH = 928
_ICON_SOURCE_HEIGHT = 928
_ORB_RENDER_OVERSAMPLE_FACTOR = 3
_ORB_RENDER_MIN_COMPOSE_EDGE = 256


@dataclass(frozen=True)
class _OrbLayerImages:
    """Hold source images for the three tintable orb layers."""

    base: QImage
    lower_overlay: QImage
    upper_overlay: QImage


@dataclass(frozen=True)
class _RenderCacheKey:
    """Identify one rendered orb pixmap variant."""

    width: int
    height: int
    device_pixel_ratio: float
    accent_rgba: tuple[int, int, int, int]
    dark_theme: bool
    enabled: bool
    hovered: bool
    pressed: bool


class AppOrbRenderer:
    """Compose cached orb pixmaps from tintable layers and the app icon."""

    def __init__(
        self,
        app_icon: QIcon | None = None,
        layer_images: _OrbLayerImages | None = None,
    ) -> None:
        """Create a renderer using the shared application icon by default."""

        self._app_icon = app_icon if app_icon is not None else application_icon()
        self._layer_images = (
            layer_images if layer_images is not None else _load_orb_layer_images()
        )
        self._pixmap_cache: dict[_RenderCacheKey, QPixmap] = {}

    def app_icon(self) -> QIcon:
        """Return the icon painted between the orb glass layers."""

        return self._app_icon

    def clear_cache(self) -> None:
        """Discard cached orb pixmaps after a theme or accent change."""

        self._pixmap_cache.clear()

    def render(
        self,
        size: QSize,
        *,
        device_pixel_ratio: float,
        enabled: bool,
        hovered: bool,
        pressed: bool,
        accent_color: QColor | None = None,
        dark_theme: bool | None = None,
    ) -> QPixmap:
        """Return one rendered orb pixmap for the requested visual state."""

        logical_width = max(1, size.width())
        logical_height = max(1, size.height())
        resolved_accent = _orb_accent_color() if accent_color is None else accent_color
        resolved_dark_theme = isDarkTheme() if dark_theme is None else dark_theme
        key = _RenderCacheKey(
            width=logical_width,
            height=logical_height,
            device_pixel_ratio=round(max(1.0, device_pixel_ratio), 3),
            accent_rgba=_rgba_tuple(resolved_accent),
            dark_theme=resolved_dark_theme,
            enabled=enabled,
            hovered=hovered,
            pressed=pressed,
        )
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached

        pixmap = self._render_uncached(
            QSize(logical_width, logical_height),
            device_pixel_ratio=key.device_pixel_ratio,
            accent_color=resolved_accent,
            dark_theme=resolved_dark_theme,
            enabled=enabled,
            hovered=hovered,
            pressed=pressed,
        )
        self._pixmap_cache[key] = pixmap
        return pixmap

    def _render_uncached(
        self,
        size: QSize,
        *,
        device_pixel_ratio: float,
        accent_color: QColor,
        dark_theme: bool,
        enabled: bool,
        hovered: bool,
        pressed: bool,
    ) -> QPixmap:
        """Compose and downsample one pixmap without consulting the render cache."""

        physical_size = QSize(
            max(1, round(size.width() * device_pixel_ratio)),
            max(1, round(size.height() * device_pixel_ratio)),
        )
        compose_size = _compose_size_for_target(physical_size)
        compose_image = QImage(
            compose_size,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        compose_image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(compose_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        try:
            target_rect = QRect(0, 0, compose_size.width(), compose_size.height())
            painter.drawImage(
                target_rect,
                _tinted_layer(
                    self._layer_images.base,
                    accent_color=accent_color,
                    dark_theme=dark_theme,
                    enabled=enabled,
                    hovered=hovered,
                    pressed=pressed,
                ),
            )
            self._app_icon.paint(
                painter,
                _icon_rect_for_size(compose_size),
                Qt.AlignmentFlag.AlignCenter,
                QIcon.Mode.Normal if enabled else QIcon.Mode.Disabled,
            )
            painter.drawImage(
                target_rect,
                _tinted_layer(
                    self._layer_images.lower_overlay,
                    accent_color=accent_color,
                    dark_theme=dark_theme,
                    enabled=enabled,
                    hovered=hovered,
                    pressed=pressed,
                ),
            )
            painter.drawImage(
                target_rect,
                _tinted_layer(
                    self._layer_images.upper_overlay,
                    accent_color=accent_color,
                    dark_theme=dark_theme,
                    enabled=enabled,
                    hovered=hovered,
                    pressed=pressed,
                ),
            )
        finally:
            painter.end()

        final_image = _lanczos_downsample(compose_image, physical_size)
        pixmap = QPixmap.fromImage(
            final_image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        )
        pixmap.setDevicePixelRatio(device_pixel_ratio)
        return pixmap


def _load_orb_layer_images() -> _OrbLayerImages:
    """Load the three packaged orb layer images from Qt resources."""

    ensure_app_orb_resources_registered()
    return _OrbLayerImages(
        base=_load_layer("orb_base"),
        lower_overlay=_load_layer("orb_lower_overlay"),
        upper_overlay=_load_layer("orb_upper_overlay"),
    )


def _load_layer(layer_name: AppOrbLayerName) -> QImage:
    """Return one orb layer image or fail if the resource is unavailable."""

    image = QImage(app_orb_layer_resource_path(layer_name))
    if image.isNull():
        raise RuntimeError(
            f"Application orb layer resource is unavailable: {layer_name}"
        )
    return image.convertToFormat(QImage.Format.Format_ARGB32)


def _orb_accent_color() -> QColor:
    """Return the raw configured accent color used only by the orb."""

    if qconfig is None:
        return QColor(themeColor())
    color = QColor(qconfig.themeColor.value)
    return color if color.isValid() else QColor(themeColor())


def _compose_size_for_target(target_size: QSize) -> QSize:
    """Return the oversampled physical compose size for one final pixmap."""

    width = max(
        target_size.width() * _ORB_RENDER_OVERSAMPLE_FACTOR,
        _ORB_RENDER_MIN_COMPOSE_EDGE,
    )
    height = max(
        target_size.height() * _ORB_RENDER_OVERSAMPLE_FACTOR,
        _ORB_RENDER_MIN_COMPOSE_EDGE,
    )
    return QSize(width, height)


def _lanczos_downsample(source: QImage, target_size: QSize) -> QImage:
    """Return ``source`` resized to ``target_size`` with Pillow Lanczos filtering."""

    if source.size() == target_size:
        return source.copy()
    source_image = _qimage_to_pil_image(source)
    resized = source_image.resize(
        (target_size.width(), target_size.height()),
        Image.Resampling.LANCZOS,
    )
    return _pil_image_to_qimage(resized)


def _qimage_to_pil_image(image: QImage) -> Image.Image:
    """Return one Pillow RGBA image copied from a ``QImage``."""

    rgba_image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes(
        "RGBA",
        (rgba_image.width(), rgba_image.height()),
        bytes(rgba_image.constBits()),
        "raw",
        "RGBA",
    )


def _pil_image_to_qimage(image: Image.Image) -> QImage:
    """Return one detached RGBA8888 ``QImage`` from a Pillow image."""

    rgba_image = image.convert("RGBA")
    width, height = rgba_image.size
    data = rgba_image.tobytes("raw", "RGBA")
    return QImage(
        data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


def _rgba_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """Return RGBA pixels from a Pillow image without deprecated accessors."""

    data = image.tobytes("raw", "RGBA")
    return [
        (data[index], data[index + 1], data[index + 2], data[index + 3])
        for index in range(0, len(data), 4)
    ]


def _tinted_layer(
    source: QImage,
    *,
    accent_color: QColor,
    dark_theme: bool,
    enabled: bool,
    hovered: bool,
    pressed: bool,
) -> QImage:
    """Tint a white orb layer with the active accent while preserving shading."""

    accent = _state_accent(
        accent_color,
        dark_theme=dark_theme,
        enabled=enabled,
        hovered=hovered,
        pressed=pressed,
    )
    alpha_scale = 0.58 if not enabled else 1.0
    source_image = _qimage_to_pil_image(source)
    pixels = _rgba_pixels(source_image)
    transformed_pixels = {
        pixel: _accent_rgba_for_layer_pixel(pixel, accent, alpha_scale=alpha_scale)
        for pixel in set(pixels)
    }
    result = Image.new("RGBA", source_image.size)
    result.putdata([transformed_pixels[pixel] for pixel in pixels])
    return _pil_image_to_qimage(result)


def _accent_color_for_layer_pixel(pixel: QColor, accent_color: QColor) -> QColor:
    """Return one uniformly transformed orb-layer pixel color."""

    red, green, blue, alpha = _accent_rgba_for_layer_pixel(
        _rgba_tuple(pixel),
        accent_color,
        alpha_scale=1.0,
    )
    return QColor(red, green, blue, alpha)


def _accent_rgba_for_layer_pixel(
    pixel: tuple[int, int, int, int],
    accent_color: QColor,
    *,
    alpha_scale: float,
) -> tuple[int, int, int, int]:
    """Return one uniformly transformed orb-layer pixel tuple."""

    red, green, blue, alpha_channel = pixel
    if alpha_channel == 0:
        return (0, 0, 0, 0)
    luminance = _luminance_tuple(red, green, blue) / 255.0
    alpha = alpha_channel / 255.0
    glass_strength = _glass_highlight_strength(luminance=luminance, alpha=alpha)
    shaded_accent = _shaded_accent_color(accent_color, luminance=luminance)
    color = _mix_color(shaded_accent, QColor(255, 255, 255), glass_strength)
    return (
        color.red(),
        color.green(),
        color.blue(),
        _clamp_channel(round(alpha_channel * alpha_scale)),
    )


def _glass_highlight_strength(*, luminance: float, alpha: float) -> float:
    """Return how strongly a bright translucent pixel should become a highlight."""

    bright_source = _smoothstep(0.80, 1.0, luminance)
    translucent_source = 1.0 - (alpha**5.0)
    return _clamp_unit((bright_source**1.02) * translucent_source * 1.18)


def _shaded_accent_color(accent_color: QColor, *, luminance: float) -> QColor:
    """Return accent color shaded by the orb layer's source luminance."""

    hsv = QColor(accent_color).toHsv()
    hue = max(0, hsv.hsvHue())
    saturation = hsv.hsvSaturation()
    value = hsv.value()
    shade = 0.58 + (0.42 * _smoothstep(0.0, 1.0, luminance))
    return QColor.fromHsv(
        hue,
        _clamp_channel(saturation),
        _clamp_channel(round(value * shade)),
        hsv.alpha(),
    )


def _state_accent(
    accent_color: QColor,
    *,
    dark_theme: bool,
    enabled: bool,
    hovered: bool,
    pressed: bool,
) -> QColor:
    """Return a state-adjusted accent for one orb render."""

    if not enabled:
        return QColor(108, 108, 108) if dark_theme else QColor(176, 176, 176)

    hsv = QColor(accent_color).toHsv()
    value = hsv.value()
    if pressed:
        value = round(value * 0.88)
    elif hovered:
        value = round(value * 1.08)
    return QColor.fromHsv(
        max(0, hsv.hsvHue()),
        _clamp_channel(hsv.hsvSaturation()),
        _clamp_channel(value),
        hsv.alpha(),
    )


def _icon_rect_for_size(size: QSize) -> QRect:
    """Return the app-icon rect that matches the PSD icon layer placement."""

    left = round(size.width() * _ICON_SOURCE_LEFT / _ORB_SOURCE_CANVAS_WIDTH)
    top = round(size.height() * _ICON_SOURCE_TOP / _ORB_SOURCE_CANVAS_HEIGHT)
    width = round(size.width() * _ICON_SOURCE_WIDTH / _ORB_SOURCE_CANVAS_WIDTH)
    height = round(size.height() * _ICON_SOURCE_HEIGHT / _ORB_SOURCE_CANVAS_HEIGHT)
    return QRect(left, top, width, height)


def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
    """Return a stable RGBA tuple for cache keys."""

    return (color.red(), color.green(), color.blue(), color.alpha())


def _luminance(color: QColor) -> int:
    """Return one perceived luminance channel for a source layer pixel."""

    return _luminance_tuple(color.red(), color.green(), color.blue())


def _luminance_tuple(red: int, green: int, blue: int) -> int:
    """Return one perceived luminance channel for source RGB channels."""

    return _clamp_channel(round((red * 0.299) + (green * 0.587) + (blue * 0.114)))


def _mix_color(start: QColor, end: QColor, amount: float) -> QColor:
    """Return a linear interpolation between two colors."""

    factor = _clamp_unit(amount)
    return QColor(
        _clamp_channel(round(_lerp(start.red(), end.red(), factor))),
        _clamp_channel(round(_lerp(start.green(), end.green(), factor))),
        _clamp_channel(round(_lerp(start.blue(), end.blue(), factor))),
        _clamp_channel(round(_lerp(start.alpha(), end.alpha(), factor))),
    )


def _smoothstep(edge_start: float, edge_end: float, value: float) -> float:
    """Return a smooth 0..1 ramp between two edges."""

    if edge_start == edge_end:
        return 1.0 if value >= edge_end else 0.0
    ratio = _clamp_unit((value - edge_start) / (edge_end - edge_start))
    return ratio * ratio * (3.0 - (2.0 * ratio))


def _lerp(start: float, end: float, amount: float) -> float:
    """Return a linear interpolation between two numeric values."""

    return start + ((end - start) * amount)


def _clamp_unit(value: float) -> float:
    """Clamp one numeric value to the 0..1 range."""

    return max(0.0, min(1.0, value))


def _clamp_channel(value: int) -> int:
    """Clamp one color channel to Qt's byte range."""

    return max(0, min(255, value))


__all__ = ["AppOrbRenderer"]
