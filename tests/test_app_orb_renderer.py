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

"""Contract tests for the layered application orb renderer."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]
import pytest

from substitute.presentation.resources.app_orb_assets import (
    APP_ORB_LAYER_NAMES,
    AppOrbLayerName,
    app_orb_layer_resource_path,
    ensure_app_orb_resources_registered,
)
from substitute.presentation.shell.app_orb_renderer import AppOrbRenderer
from substitute.presentation.shell.app_orb_renderer import _OrbLayerImages
from substitute.presentation.shell.app_orb_renderer import _accent_color_for_layer_pixel
from substitute.presentation.shell.app_orb_renderer import _orb_accent_color

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "app-orb renderer Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def test_app_orb_layer_resource_paths_resolve_expected_qt_aliases() -> None:
    """Orb layers should resolve through stable Qt resource aliases."""

    assert APP_ORB_LAYER_NAMES == (
        "orb_base",
        "orb_lower_overlay",
        "orb_upper_overlay",
    )
    assert app_orb_layer_resource_path("orb_base") == (
        ":/substitute/app/orb/orb_base.png"
    )


def test_app_orb_layer_resources_are_loadable() -> None:
    """Packaged orb layer PNGs should be available after resource registration."""

    _app()
    ensure_app_orb_resources_registered()

    for layer_name in APP_ORB_LAYER_NAMES:
        image = QImage(app_orb_layer_resource_path(cast(AppOrbLayerName, layer_name)))
        assert not image.isNull()
        assert image.size() == QSize(256, 256)


def test_app_orb_renderer_tints_glass_layers_with_accent_color() -> None:
    """Changing accent color should change rendered orb pixels outside the icon."""

    _app()
    renderer = AppOrbRenderer()
    blue_orb = renderer.render(
        QSize(46, 46),
        device_pixel_ratio=1.0,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#0078D4"),
        dark_theme=False,
    )
    red_orb = renderer.render(
        QSize(46, 46),
        device_pixel_ratio=1.0,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#D83B01"),
        dark_theme=False,
    )

    blue_pixel = blue_orb.toImage().pixelColor(6, 22)
    red_pixel = red_orb.toImage().pixelColor(6, 22)

    assert blue_pixel.alpha() > 0
    assert red_pixel.alpha() > 0
    assert blue_pixel != red_pixel
    assert blue_pixel.blue() > blue_pixel.red()
    assert red_pixel.red() > red_pixel.blue()


def test_app_orb_renderer_preserves_clear_top_highlight() -> None:
    """Bright translucent layer pixels should become clear highlights, not flat accent."""

    accent = QColor("#D83B8C")
    opaque_base = _accent_color_for_layer_pixel(QColor(244, 244, 244, 255), accent)
    translucent_glass = _accent_color_for_layer_pixel(
        QColor(244, 244, 244, 186), accent
    )

    assert opaque_base.toHsv().hsvSaturation() > 120
    assert translucent_glass.value() > opaque_base.value()
    assert (
        translucent_glass.toHsv().hsvSaturation() < opaque_base.toHsv().hsvSaturation()
    )


def test_app_orb_renderer_uses_raw_configured_accent_in_dark_mode() -> None:
    """The orb should not use QFluent's dark-mode-brightened accent token."""

    _app()
    setTheme(Theme.DARK)
    setThemeColor(QColor("#D83B8C"))

    assert QColor(themeColor()).name().upper() == "#FF63B4"
    assert _orb_accent_color().name().upper() == "#D83B8C"


def test_app_orb_renderer_caches_final_pixmap_for_visual_state() -> None:
    """Lanczos resampling should happen only when a cache key is missing."""

    _app()
    renderer = AppOrbRenderer()

    first = renderer.render(
        QSize(46, 46),
        device_pixel_ratio=1.5,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#D83B8C"),
        dark_theme=False,
    )
    second = renderer.render(
        QSize(46, 46),
        device_pixel_ratio=1.5,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#D83B8C"),
        dark_theme=False,
    )

    assert first.cacheKey() == second.cacheKey()


def test_app_orb_renderer_returns_pixmap_at_requested_logical_size() -> None:
    """The final pixmap should be ready for natural-size high-DPI painting."""

    _app()
    renderer = AppOrbRenderer()

    pixmap = renderer.render(
        QSize(46, 46),
        device_pixel_ratio=1.5,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#D83B8C"),
        dark_theme=False,
    )

    assert pixmap.width() == 69
    assert pixmap.height() == 69
    assert pixmap.devicePixelRatioF() == 1.5
    assert pixmap.width() / pixmap.devicePixelRatioF() == 46
    assert pixmap.height() / pixmap.devicePixelRatioF() == 46


def test_app_orb_renderer_does_not_tint_the_app_icon_layer() -> None:
    """The icon should be painted as its own layer instead of accent-tinted."""

    app = _app()
    _ = app
    renderer = AppOrbRenderer(
        _solid_icon(QColor("#FF0000")),
        _OrbLayerImages(
            base=_transparent_image(),
            lower_overlay=_transparent_image(),
            upper_overlay=_transparent_image(),
        ),
    )

    blue_orb = renderer.render(
        QSize(32, 32),
        device_pixel_ratio=1.0,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#0078D4"),
        dark_theme=False,
    )
    green_orb = renderer.render(
        QSize(32, 32),
        device_pixel_ratio=1.0,
        enabled=True,
        hovered=False,
        pressed=False,
        accent_color=QColor("#107C10"),
        dark_theme=False,
    )

    assert blue_orb.toImage().pixelColor(16, 16) == QColor("#FF0000")
    assert green_orb.toImage().pixelColor(16, 16) == QColor("#FF0000")


def _solid_icon(color: QColor) -> QIcon:
    """Return a single-color test icon."""

    pixmap = QPixmap(32, 32)
    pixmap.fill(color)
    return QIcon(pixmap)


def _transparent_image() -> QImage:
    """Return a transparent source layer for isolated icon tests."""

    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    return image


def _app() -> QApplication:
    """Return the shared QApplication used by app-orb renderer tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
