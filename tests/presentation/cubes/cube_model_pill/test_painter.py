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

"""Rendering contract tests for transparent target-model pills."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath

from substitute.presentation.cubes.cube_model_pill import CubeModelPillPainter


def test_model_pill_clears_label_through_fill_and_underlying_icon() -> None:
    """Pill letterforms should expose the surface below an overlapping icon."""

    wash = QColor(238, 238, 238)
    accent = QColor(0, 120, 215)
    overlays: list[QImage] = []
    pill_rects: list[QRectF] = []
    for punchout_color in (wash, accent):
        overlay = QImage(64, 48, QImage.Format.Format_ARGB32_Premultiplied)
        overlay.fill(wash)
        painter = QPainter(overlay)
        icon_rect = QRectF(8, 6, 36, 36)
        painter.fillRect(icon_rect, QColor(220, 70, 90))
        pill_rect = CubeModelPillPainter.draw_icon_overlay(
            painter,
            icon_rect=icon_rect,
            text="Anima",
            accent_color=accent,
            punchout_color=punchout_color,
        )
        painter.end()
        assert pill_rect is not None
        overlays.append(overlay)
        pill_rects.append(pill_rect)

    assert pill_rects[0] == pill_rects[1]
    interior = pill_rects[0].adjusted(3, 2, -3, -2).toAlignedRect()
    assert any(
        overlays[0].pixelColor(x, y) != overlays[1].pixelColor(x, y)
        for y in range(interior.top(), interior.bottom() + 1)
        for x in range(interior.left(), interior.right() + 1)
    )


def test_icon_pill_is_compact_and_preserves_the_complete_anima_label() -> None:
    """Icon pills should retain Anima without obscuring the whole icon base."""

    image = QImage(64, 48, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(238, 238, 238))
    painter = QPainter(image)
    icon_rect = QRectF(8, 6, 36, 36)
    pill_rect = CubeModelPillPainter.icon_overlay_rect(
        painter,
        icon_rect=icon_rect,
        text="Anima",
    )
    metrics = CubeModelPillPainter.icon_overlay_metrics(painter.font())
    label_path = QPainterPath()
    label_path.addText(QPointF(0, 0), metrics.font, "Anima")
    painter.end()

    assert pill_rect.height() == 10
    assert label_path.boundingRect().width() <= (
        pill_rect.width() - (metrics.horizontal_padding * 2)
    )
    assert pill_rect.right() == icon_rect.right() + 3
    assert pill_rect.bottom() == icon_rect.bottom() + 2
    overlap = icon_rect.intersected(pill_rect)
    assert (overlap.width() * overlap.height()) <= (
        icon_rect.width() * icon_rect.height() * 0.23
    )


def test_shared_pill_painter_antialiases_capsule_edges() -> None:
    """Every pill surface should receive blended edge pixels from its owner."""

    background = QColor(238, 238, 238)
    accent = QColor(0, 120, 215)
    image = QImage(180, 48, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(background)
    painter = QPainter(image)
    font = QFont(painter.font())
    font.setPixelSize(18)
    painter.setFont(font)
    metrics = CubeModelPillPainter.title_metrics(font)
    pill_rect = CubeModelPillPainter.draw_title(
        painter,
        bounds=QRectF(8, 4, 150, 36),
        text="Anima",
        accent_color=accent,
        punchout_color=background,
    )
    painter.end()

    assert pill_rect is not None
    cap_region = QRectF(
        pill_rect.left(),
        pill_rect.top(),
        metrics.horizontal_padding,
        pill_rect.height(),
    ).toAlignedRect()
    cap_colors = {
        image.pixelColor(x, y).rgba()
        for y in range(cap_region.top(), cap_region.bottom() + 1)
        for x in range(cap_region.left(), cap_region.right() + 1)
    }
    assert background.rgba() in cap_colors
    assert accent.rgba() in cap_colors
    assert cap_colors - {background.rgba(), accent.rgba()}


def test_identical_title_models_use_identical_pixel_snapped_capsules() -> None:
    """Equal model labels should not change silhouette between row geometries."""

    image = QImage(240, 120, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(238, 238, 238))
    painter = QPainter(image)
    first = CubeModelPillPainter.draw_title(
        painter,
        bounds=QRectF(12, 5, 200, 43),
        text="SDXL",
        accent_color=QColor(0, 120, 215),
    )
    second = CubeModelPillPainter.draw_title(
        painter,
        bounds=QRectF(12, 58, 200, 44),
        text="SDXL",
        accent_color=QColor(0, 120, 215),
    )
    painter.end()

    assert first is not None
    assert second is not None
    assert first.x() == second.x()
    assert first.size() == second.size()
    assert first.height() == round(
        CubeModelPillPainter.title_metrics(painter.font()).height
    )
    assert image.copy(first.toRect()) == image.copy(second.toRect())
