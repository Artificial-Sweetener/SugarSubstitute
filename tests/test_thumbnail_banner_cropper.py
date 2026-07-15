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

"""Tests for deterministic thumbnail banner crop generation."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_WIDTH,
)
from substitute.infrastructure.persistence.thumbnail_banner_cropper import (
    ThumbnailBannerCropper,
)


def test_banner_cropper_outputs_exact_banner_size() -> None:
    """Banner crop output should use the shared exact banner dimensions."""

    source = _image(320, 480, QColor("#303030"))

    result = ThumbnailBannerCropper().crop_banner(source)

    assert result.image.width() == BANNER_THUMBNAIL_WIDTH
    assert result.image.height() == BANNER_THUMBNAIL_HEIGHT
    assert not result.image.isNull()


def test_banner_cropper_rejects_null_images() -> None:
    """Null source images should fail before crop scoring."""

    with pytest.raises(ValueError, match="null image"):
        ThumbnailBannerCropper().crop_banner(QImage())


def test_banner_cropper_is_deterministic_for_identical_input() -> None:
    """Repeated crops of the same image should choose the same source rect."""

    source = _image_with_detail_band()
    cropper = ThumbnailBannerCropper()

    first = cropper.crop_banner(source)
    second = cropper.crop_banner(source)

    assert first.source_rect == second.source_rect
    assert first.image.pixelColor(120, 30) == second.image.pixelColor(120, 30)


def test_banner_cropper_prefers_high_detail_band_over_flat_regions() -> None:
    """Synthetic detail should beat flat background when choosing a banner band."""

    source = _image_with_detail_band()

    result = ThumbnailBannerCropper().crop_banner(source)

    detail_band = QRect(0, 160, source.width(), 70)
    assert result.source_rect.intersects(detail_band)


def test_banner_cropper_accepts_small_sources() -> None:
    """Small provider images should still produce a usable exact-size banner."""

    source = _image(32, 24, QColor("#8060aa"))

    result = ThumbnailBannerCropper().crop_banner(source)

    assert result.image.size() == _image(768, 160, QColor("black")).size()
    assert result.source_rect.width() > 0
    assert result.source_rect.height() > 0


def test_banner_cropper_handles_portrait_sources_without_blank_output() -> None:
    """Portrait images should produce a nonblank banner crop."""

    source = _image_with_detail_band(width=240, height=520)

    result = ThumbnailBannerCropper().crop_banner(source)

    assert result.image.width() == BANNER_THUMBNAIL_WIDTH
    assert result.image.height() == BANNER_THUMBNAIL_HEIGHT
    assert result.image.pixelColor(384, 80) != QColor("#303030")


def _image(width: int, height: int, color: QColor) -> QImage:
    """Return a filled ARGB test image."""

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _image_with_detail_band(
    *,
    width: int = 320,
    height: int = 420,
) -> QImage:
    """Return a portrait image with a detailed band surrounded by flat color."""

    image = _image(width, height, QColor("#303030"))
    band_top = max(0, min(height - 1, round(height * 0.38)))
    band_bottom = max(band_top + 1, min(height, band_top + round(height * 0.17)))
    for y in range(band_top, band_bottom):
        for x in range(width):
            color = (
                QColor("#e8d850") if (x // 4 + y // 4) % 2 == 0 else QColor("#4068d8")
            )
            image.setPixelColor(x, y, color)
    return image
