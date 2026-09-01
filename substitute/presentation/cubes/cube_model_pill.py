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

"""Paint accent target-model pills with true transparent letterforms."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontInfo,
    QPainter,
    QPainterPath,
)
from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]

from substitute.presentation.shell.chrome_style import body_material_wash_color


@dataclass(frozen=True)
class CubeModelTitlePillMetrics:
    """Describe SugarCubes title-pill geometry derived from a title font."""

    font: QFont
    height: float
    horizontal_padding: float
    gap: float
    corner_radius: float


class CubeModelPillPainter:
    """Draw a target-model badge anchored over a cube icon's lower right."""

    _HEIGHT = 14.0
    _HORIZONTAL_PADDING = 4.0
    _RIGHT_OVERHANG = 5.0
    _BOTTOM_OVERHANG = 3.0

    @classmethod
    def pill_rect(
        cls,
        painter: QPainter,
        *,
        icon_rect: QRectF,
        text: str,
    ) -> QRectF:
        """Return badge geometry whose lower-right edge tracks the cube icon."""

        font = cls._font(painter.font())
        painter.save()
        painter.setFont(font)
        measured_width = painter.fontMetrics().horizontalAdvance(text)
        painter.restore()
        width = min(
            max(cls._HEIGHT, measured_width + (cls._HORIZONTAL_PADDING * 2)),
            icon_rect.width() + cls._RIGHT_OVERHANG,
        )
        return QRectF(
            icon_rect.right() + cls._RIGHT_OVERHANG - width,
            icon_rect.bottom() + cls._BOTTOM_OVERHANG - cls._HEIGHT,
            width,
            cls._HEIGHT,
        )

    @classmethod
    def draw(
        cls,
        painter: QPainter,
        *,
        icon_rect: QRectF,
        text: str,
        accent_color: QColor | None = None,
        punchout_color: QColor | None = None,
    ) -> QRectF | None:
        """Draw one accent pill and clear its label through the paint device."""

        label = text.strip()
        if not label:
            return None
        rect = cls.pill_rect(painter, icon_rect=icon_rect, text=label)
        cls._draw_rect(
            painter,
            rect=rect,
            label=label,
            font=cls._font(painter.font()),
            horizontal_padding=cls._HORIZONTAL_PADDING,
            corner_radius=rect.height() / 2,
            accent_color=accent_color,
            punchout_color=punchout_color,
        )
        return rect

    @classmethod
    def draw_standalone(
        cls,
        painter: QPainter,
        *,
        bounds: QRectF,
        text: str,
        accent_color: QColor | None = None,
        punchout_color: QColor | None = None,
    ) -> QRectF | None:
        """Draw a model pill centered vertically without an accompanying icon."""

        label = text.strip()
        if not label:
            return None
        metrics = cls.title_metrics(painter.font())
        painter.save()
        painter.setFont(metrics.font)
        pill_height = max(1, round(metrics.height))
        left = round(bounds.x())
        top = round(bounds.center().y() - (pill_height / 2))
        available_width = max(0, int(bounds.right()) - left)
        natural_width = ceil(
            painter.fontMetrics().horizontalAdvance(label)
            + (metrics.horizontal_padding * 2)
        )
        width = min(available_width, max(pill_height, natural_width))
        painter.restore()
        rect = QRectF(
            left,
            top,
            width,
            pill_height,
        )
        cls._draw_rect(
            painter,
            rect=rect,
            label=label,
            font=metrics.font,
            horizontal_padding=metrics.horizontal_padding,
            corner_radius=pill_height / 2,
            accent_color=accent_color,
            punchout_color=punchout_color,
        )
        return rect

    @staticmethod
    def title_metrics(base_font: QFont) -> CubeModelTitlePillMetrics:
        """Return the exact proportional geometry used by SugarCubes titles."""

        base_pixel_size = max(1, QFontInfo(base_font).pixelSize())
        pill_font = QFont(base_font)
        pill_font.setPixelSize(max(1, round(base_pixel_size * 0.78)))
        pill_font.setWeight(QFont.Weight.Bold)
        pill_height = base_pixel_size * 0.94
        return CubeModelTitlePillMetrics(
            font=pill_font,
            height=pill_height,
            horizontal_padding=base_pixel_size * 0.30,
            gap=base_pixel_size * 0.30,
            corner_radius=pill_height / 2,
        )

    @classmethod
    def _draw_rect(
        cls,
        painter: QPainter,
        *,
        rect: QRectF,
        label: str,
        font: QFont,
        horizontal_padding: float,
        corner_radius: float,
        accent_color: QColor | None,
        punchout_color: QColor | None,
    ) -> None:
        """Paint one measured pill and its window-wash letterforms."""

        painter.save()
        painter.setFont(font)
        elided = painter.fontMetrics().elidedText(
            label,
            Qt.TextElideMode.ElideRight,
            max(0, int(rect.width() - (horizontal_padding * 2))),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(themeColor()) if accent_color is None else accent_color)
        painter.drawRoundedRect(rect, corner_radius, corner_radius)

        text_path = QPainterPath()
        text_path.addText(QPointF(0, 0), font, elided)
        glyph_bounds = text_path.boundingRect()
        text_path.translate(
            rect.center().x() - glyph_bounds.center().x(),
            rect.center().y() - glyph_bounds.center().y(),
        )
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillPath(text_path, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        wash = _opaque_body_wash() if punchout_color is None else QColor(punchout_color)
        wash.setAlpha(255)
        painter.fillPath(text_path, wash)
        painter.restore()

    @staticmethod
    def _font(base_font: QFont) -> QFont:
        """Return the compact bold font shared by every model pill."""

        font = QFont(base_font)
        font.setPixelSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        return font


def _opaque_body_wash() -> QColor:
    """Return the window body wash as an opaque punched-letter surface."""

    red, green, blue, _alpha = body_material_wash_color()
    return QColor(red, green, blue)


__all__ = ["CubeModelPillPainter", "CubeModelTitlePillMetrics"]
