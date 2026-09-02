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
class CubeModelPillMetrics:
    """Describe shared model-pill type and capsule geometry."""

    font: QFont
    height: float
    horizontal_padding: float
    gap: float
    corner_radius: float


class CubeModelPillPainter:
    """Render model pills while leaving each surface in charge of placement."""

    _ICON_FONT_SIZE = 8
    _ICON_HEIGHT = 10.0
    _ICON_HORIZONTAL_PADDING = 2.0
    _ICON_RIGHT_OVERHANG = 3.0
    _ICON_BOTTOM_OVERHANG = 2.0

    @classmethod
    def icon_overlay_metrics(cls, base_font: QFont) -> CubeModelPillMetrics:
        """Return compact metrics that keep an overlaid cube icon legible."""

        font = QFont(base_font)
        font.setPixelSize(cls._ICON_FONT_SIZE)
        font.setWeight(QFont.Weight.DemiBold)
        return CubeModelPillMetrics(
            font=font,
            height=cls._ICON_HEIGHT,
            horizontal_padding=cls._ICON_HORIZONTAL_PADDING,
            gap=0.0,
            corner_radius=cls._ICON_HEIGHT / 2,
        )

    @classmethod
    def icon_overlay_rect(
        cls,
        painter: QPainter,
        *,
        icon_rect: QRectF,
        text: str,
    ) -> QRectF:
        """Return a natural-width pill anchored over the icon's lower right."""

        metrics = cls.icon_overlay_metrics(painter.font())
        painter.save()
        painter.setFont(metrics.font)
        measured_width = painter.fontMetrics().horizontalAdvance(text)
        painter.restore()
        width = max(
            metrics.height,
            ceil(measured_width + (metrics.horizontal_padding * 2)),
        )
        return QRectF(
            icon_rect.right() + cls._ICON_RIGHT_OVERHANG - width,
            icon_rect.bottom() + cls._ICON_BOTTOM_OVERHANG - metrics.height,
            width,
            metrics.height,
        )

    @classmethod
    def draw_icon_overlay(
        cls,
        painter: QPainter,
        *,
        icon_rect: QRectF,
        text: str,
        accent_color: QColor | None = None,
        punchout_color: QColor | None = None,
    ) -> QRectF | None:
        """Draw a complete compact label over a cube icon's lower-right edge."""

        label = text.strip()
        if not label:
            return None
        metrics = cls.icon_overlay_metrics(painter.font())
        rect = cls.icon_overlay_rect(painter, icon_rect=icon_rect, text=label)
        cls._draw_rect(
            painter,
            rect=rect,
            label=label,
            metrics=metrics,
            elide_label=False,
            accent_color=accent_color,
            punchout_color=punchout_color,
        )
        return rect

    @classmethod
    def draw_title(
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
            metrics=metrics,
            elide_label=True,
            accent_color=accent_color,
            punchout_color=punchout_color,
        )
        return rect

    @staticmethod
    def title_metrics(base_font: QFont) -> CubeModelPillMetrics:
        """Return the exact proportional geometry used by SugarCubes titles."""

        configured_pixel_size = base_font.pixelSize()
        base_pixel_size = max(
            1,
            configured_pixel_size
            if configured_pixel_size > 0
            else QFontInfo(base_font).pixelSize(),
        )
        pill_font = QFont(base_font)
        pill_font.setPixelSize(max(1, round(base_pixel_size * 0.78)))
        pill_font.setWeight(QFont.Weight.Bold)
        pill_height = base_pixel_size * 0.94
        return CubeModelPillMetrics(
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
        metrics: CubeModelPillMetrics,
        elide_label: bool,
        accent_color: QColor | None,
        punchout_color: QColor | None,
    ) -> None:
        """Paint one measured pill and its window-wash letterforms."""

        painter.save()
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing,
        )
        painter.setFont(metrics.font)
        visible_label = (
            painter.fontMetrics().elidedText(
                label,
                Qt.TextElideMode.ElideRight,
                max(0, int(rect.width() - (metrics.horizontal_padding * 2))),
            )
            if elide_label
            else label
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(themeColor()) if accent_color is None else accent_color)
        painter.drawRoundedRect(rect, metrics.corner_radius, metrics.corner_radius)

        text_path = QPainterPath()
        text_path.addText(QPointF(0, 0), metrics.font, visible_label)
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


def _opaque_body_wash() -> QColor:
    """Return the window body wash as an opaque punched-letter surface."""

    red, green, blue, _alpha = body_material_wash_color()
    return QColor(red, green, blue)


__all__ = ["CubeModelPillMetrics", "CubeModelPillPainter"]
