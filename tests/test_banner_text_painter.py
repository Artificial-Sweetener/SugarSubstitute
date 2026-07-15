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

"""Tests for shared banner-backed text painting."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from substitute.presentation.widgets.banner_text_painter import BannerTextPainter


def ensure_qapp() -> QApplication:
    """Return a running Qt application for painter tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_banner_text_painter_applies_wash_over_banner() -> None:
    """Banner backing should paint the pixmap and darken it with the wash."""

    ensure_qapp()
    painter_helper = BannerTextPainter()
    banner = _pixmap(QColor("#ff0000"), width=48, height=20)
    image = _blank_image()
    painter = QPainter(image)

    try:
        used_banner = painter_helper.paint_banner_backing(
            painter,
            rect=QRectF(4.0, 4.0, 48.0, 20.0),
            shape=None,
            banner=banner,
            fallback_fill=QColor("#0000ff"),
            fallback_border=None,
        )
    finally:
        painter.end()

    center = image.pixelColor(24, 14)
    assert used_banner is True
    assert center.alpha() == 255
    assert 185 <= center.red() <= 200
    assert center.blue() == 0


def test_banner_text_painter_cover_crops_without_stretching() -> None:
    """Banner backing should preserve image aspect ratio with centered cover crop."""

    ensure_qapp()
    painter_helper = BannerTextPainter()
    banner = _banded_wide_pixmap()
    image = _blank_image()
    painter = QPainter(image)

    try:
        used_banner = painter_helper.paint_banner_backing(
            painter,
            rect=QRectF(0.0, 0.0, 20.0, 20.0),
            shape=None,
            banner=banner,
            fallback_fill=QColor("#0000ff"),
            fallback_border=None,
            wash_alpha=0,
        )
    finally:
        painter.end()

    assert used_banner is True
    left = image.pixelColor(1, 10)
    center = image.pixelColor(10, 10)
    right = image.pixelColor(18, 10)
    assert left.green() > 200
    assert center.green() > 200
    assert right.green() > 200
    assert left.red() < 30
    assert right.blue() < 30


def test_banner_text_painter_paints_fallback_without_banner() -> None:
    """Missing banner artwork should paint fallback fill and return False."""

    ensure_qapp()
    painter_helper = BannerTextPainter()
    image = _blank_image()
    painter = QPainter(image)

    try:
        used_banner = painter_helper.paint_banner_backing(
            painter,
            rect=QRectF(4.0, 4.0, 48.0, 20.0),
            shape=None,
            banner=None,
            fallback_fill=QColor("#0000ff"),
            fallback_border=None,
            wash_alpha=50,
        )
    finally:
        painter.end()

    center = image.pixelColor(24, 14)
    assert used_banner is False
    assert center.blue() > 200
    assert center.red() < 20


def test_banner_text_painter_shadowed_text_paints_visible_pixels() -> None:
    """Shared shadowed text should produce visible text pixels."""

    app = ensure_qapp()
    painter_helper = BannerTextPainter()
    image = _blank_image()
    painter = QPainter(image)

    try:
        painter.setFont(app.font())
        painter_helper.paint_shadowed_text(
            painter,
            QPointF(10.0, 22.0),
            "Model",
            color=QColor(Qt.GlobalColor.white),
        )
    finally:
        painter.end()

    assert _has_nontransparent_pixel(image, QRectF(0.0, 0.0, 96.0, 36.0))


def _pixmap(color: QColor, *, width: int, height: int) -> QPixmap:
    """Return a pixmap filled with one color."""

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return QPixmap.fromImage(image)


def _banded_wide_pixmap() -> QPixmap:
    """Return a wide pixmap whose edges reveal stretching regressions."""

    image = QImage(40, 20, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#00ff00"))
    painter = QPainter(image)
    try:
        painter.fillRect(0, 0, 10, 20, QColor("#ff0000"))
        painter.fillRect(30, 0, 10, 20, QColor("#0000ff"))
    finally:
        painter.end()
    return QPixmap.fromImage(image)


def _blank_image() -> QImage:
    """Return a transparent test image."""

    image = QImage(96, 36, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#00000000"))
    return image


def _has_nontransparent_pixel(image: QImage, rect: QRectF) -> bool:
    """Return whether an image contains any visible pixel in the rect."""

    pixel_rect = rect.toAlignedRect().intersected(image.rect())
    for y in range(pixel_rect.top(), pixel_rect.bottom() + 1):
        for x in range(pixel_rect.left(), pixel_rect.right() + 1):
            if image.pixelColor(QPoint(x, y)).alpha() > 0:
                return True
    return False
