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

"""Generate deterministic banner crops from provider thumbnail images."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_WIDTH,
)

_ANALYSIS_LONG_EDGE = 224
_MIN_SAMPLE_GRID = 6
_MAX_SAMPLE_GRID = 18


@dataclass(frozen=True, slots=True)
class BannerCropResult:
    """Carry a generated banner image and the original-source crop rect."""

    image: QImage
    source_rect: QRect


class ThumbnailBannerCropper:
    """Choose visually dense banner crops without model-based detection."""

    def crop_banner(
        self,
        source: QImage,
        *,
        width: int = BANNER_THUMBNAIL_WIDTH,
        height: int = BANNER_THUMBNAIL_HEIGHT,
    ) -> BannerCropResult:
        """Return one exact-size banner crop from ``source``.

        The crop decision is made on a small analysis image for speed, then the
        selected normalized rect is mapped back to the source image so the final
        banner keeps as much source detail as possible.
        """

        if source.isNull():
            raise ValueError("Cannot crop a banner from a null image.")
        if width <= 0 or height <= 0:
            raise ValueError("Banner crop dimensions must be positive.")

        analysis = _analysis_image(source)
        analysis_rect = _best_analysis_rect(analysis, width / height)
        source_rect = _map_analysis_rect_to_source(analysis_rect, analysis, source)
        cropped = source.copy(source_rect)
        banner = _cover_scaled_image(cropped, width, height)
        return BannerCropResult(image=banner, source_rect=source_rect)


def _analysis_image(source: QImage) -> QImage:
    """Return a small RGB image used only for crop scoring."""

    longest_edge = max(source.width(), source.height())
    if longest_edge <= _ANALYSIS_LONG_EDGE:
        return source.convertToFormat(QImage.Format.Format_RGB32)
    return source.scaled(
        _ANALYSIS_LONG_EDGE,
        _ANALYSIS_LONG_EDGE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).convertToFormat(QImage.Format.Format_RGB32)


def _best_analysis_rect(image: QImage, target_aspect: float) -> QRect:
    """Return the highest-scoring crop rect in analysis-image coordinates."""

    crop_width, crop_height = _crop_size_for_aspect(
        image.width(),
        image.height(),
        target_aspect,
    )
    best_rect = QRect(0, 0, crop_width, crop_height)
    best_score = float("-inf")
    for rect in _candidate_rects(
        image.width(), image.height(), crop_width, crop_height
    ):
        score = _score_rect(image, rect)
        if score > best_score:
            best_rect = rect
            best_score = score
    return best_rect


def _crop_size_for_aspect(
    width: int,
    height: int,
    target_aspect: float,
) -> tuple[int, int]:
    """Return the largest crop size fitting ``width``/``height`` at target aspect."""

    image_aspect = width / max(1, height)
    if image_aspect >= target_aspect:
        crop_height = height
        crop_width = max(1, min(width, round(crop_height * target_aspect)))
    else:
        crop_width = width
        crop_height = max(1, min(height, round(crop_width / target_aspect)))
    return crop_width, crop_height


def _candidate_rects(
    image_width: int,
    image_height: int,
    crop_width: int,
    crop_height: int,
) -> tuple[QRect, ...]:
    """Return deterministic candidate rects that cover the possible crop range."""

    x_positions = _axis_positions(image_width, crop_width)
    y_positions = _axis_positions(image_height, crop_height)
    return tuple(
        QRect(x, y, crop_width, crop_height) for y in y_positions for x in x_positions
    )


def _axis_positions(axis_size: int, crop_size: int) -> tuple[int, ...]:
    """Return candidate start positions for one crop axis."""

    maximum = max(0, axis_size - crop_size)
    if maximum == 0:
        return (0,)
    steps = max(2, min(16, maximum // max(1, crop_size // 6) + 1))
    positions = {round(maximum * index / (steps - 1)) for index in range(steps)}
    positions.add(maximum // 2)
    return tuple(sorted(positions))


def _score_rect(image: QImage, rect: QRect) -> float:
    """Return a saliency-like score for one candidate crop rect."""

    samples_x = max(_MIN_SAMPLE_GRID, min(_MAX_SAMPLE_GRID, rect.width() // 8))
    samples_y = max(_MIN_SAMPLE_GRID, min(_MAX_SAMPLE_GRID, rect.height() // 8))
    brightness_values: list[float] = []
    saturation_total = 0.0
    edge_total = 0.0
    sample_count = 0
    for y_index in range(samples_y):
        y = rect.top() + round((y_index + 0.5) * rect.height() / samples_y)
        y = min(image.height() - 1, max(0, y))
        for x_index in range(samples_x):
            x = rect.left() + round((x_index + 0.5) * rect.width() / samples_x)
            x = min(image.width() - 1, max(0, x))
            color = QColor(image.pixel(x, y))
            brightness = _brightness(color)
            brightness_values.append(brightness)
            saturation_total += color.hslSaturationF()
            edge_total += _local_edge(image, x, y, brightness)
            sample_count += 1

    if sample_count == 0:
        return float("-inf")
    average = sum(brightness_values) / sample_count
    contrast = sum(abs(value - average) for value in brightness_values) / sample_count
    saturation = saturation_total / sample_count
    edge = edge_total / sample_count
    center_prior = _center_prior(image, rect)
    upper_prior = _upper_middle_prior(image, rect)
    flat_penalty = 0.35 if contrast < 0.025 and edge < 0.025 else 0.0
    return (
        edge * 3.2
        + contrast * 1.9
        + saturation * 0.65
        + center_prior * 0.32
        + upper_prior * 0.22
        - flat_penalty
    )


def _brightness(color: QColor) -> float:
    """Return perceived brightness in the range 0..1."""

    return color.redF() * 0.2126 + color.greenF() * 0.7152 + color.blueF() * 0.0722


def _local_edge(image: QImage, x: int, y: int, brightness: float) -> float:
    """Return a cheap local edge estimate around one sampled pixel."""

    right = min(image.width() - 1, x + 1)
    down = min(image.height() - 1, y + 1)
    return (
        abs(brightness - _brightness(QColor(image.pixel(right, y))))
        + abs(brightness - _brightness(QColor(image.pixel(x, down))))
    ) / 2.0


def _center_prior(image: QImage, rect: QRect) -> float:
    """Return a score favoring crops near the image center."""

    center_x = rect.center().x() / max(1, image.width() - 1)
    center_y = rect.center().y() / max(1, image.height() - 1)
    distance = abs(center_x - 0.5) + abs(center_y - 0.5)
    return max(0.0, 1.0 - distance)


def _upper_middle_prior(image: QImage, rect: QRect) -> float:
    """Return a slight bias toward upper-middle character-preview regions."""

    center_y = rect.center().y() / max(1, image.height() - 1)
    return max(0.0, 1.0 - abs(center_y - 0.42) * 2.0)


def _map_analysis_rect_to_source(
    rect: QRect,
    analysis: QImage,
    source: QImage,
) -> QRect:
    """Map one analysis-image crop rect back to original source coordinates."""

    scale_x = source.width() / max(1, analysis.width())
    scale_y = source.height() / max(1, analysis.height())
    left = round(rect.left() * scale_x)
    top = round(rect.top() * scale_y)
    width = max(1, round(rect.width() * scale_x))
    height = max(1, round(rect.height() * scale_y))
    if left + width > source.width():
        left = max(0, source.width() - width)
    if top + height > source.height():
        top = max(0, source.height() - height)
    return QRect(left, top, min(width, source.width()), min(height, source.height()))


def _cover_scaled_image(source: QImage, width: int, height: int) -> QImage:
    """Return an exact-size image produced with proportional cover scaling."""

    scaled = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = max(0, (scaled.width() - width) // 2)
    top = max(0, (scaled.height() - height) // 2)
    return scaled.copy(left, top, width, height)


__all__ = ["BannerCropResult", "ThumbnailBannerCropper"]
