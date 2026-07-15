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

"""Paint reusable banner-backed text treatments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


class BannerIconRenderer(Protocol):
    """Render one existing icon asset in a requested color."""

    def __call__(
        self,
        painter: QPainter,
        rect: QRectF,
        color: QColor,
    ) -> None:
        """Paint the icon asset into rect using color."""
        ...


@dataclass(frozen=True, slots=True)
class BannerTextStyle:
    """Describe reusable banner wash and text-shadow styling."""

    wash_alpha: int = 64
    shadow_alpha: int = 168
    strong_shadow_alpha: int = 232


class BannerTextPainter:
    """Paint readable text over optional banner artwork."""

    def __init__(self, style: BannerTextStyle | None = None) -> None:
        """Store the banner text style used for future paint calls."""

        self._style = style or BannerTextStyle()

    @property
    def style(self) -> BannerTextStyle:
        """Return the immutable banner text style."""

        return self._style

    def paint_banner_backing(
        self,
        painter: QPainter,
        *,
        rect: QRectF,
        shape: QPainterPath | None,
        banner: QPixmap | None,
        fallback_fill: QColor,
        fallback_border: QColor | None,
        wash_alpha: int | None = None,
    ) -> bool:
        """Paint banner or fallback backing and return whether a banner was used."""

        used_banner = banner is not None and not banner.isNull()
        painter.save()
        try:
            if shape is not None:
                painter.setClipPath(shape)
            else:
                painter.setClipRect(rect)
            if used_banner:
                assert banner is not None
                painter.drawPixmap(
                    _centered_cover_rect(rect, banner),
                    banner,
                    QRectF(banner.rect()),
                )
                self._paint_wash(painter, rect, shape, wash_alpha)
            else:
                painter.fillRect(rect, fallback_fill)
        finally:
            painter.restore()

        if fallback_border is not None:
            painter.save()
            try:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(fallback_border))
                if shape is not None:
                    painter.drawPath(shape)
                else:
                    painter.drawRect(rect)
            finally:
                painter.restore()
        return used_banner

    def paint_shadowed_text(
        self,
        painter: QPainter,
        position: QPointF,
        text: str,
        *,
        color: QColor,
    ) -> None:
        """Paint high-contrast text with a shared soft and directional shadow."""

        diffuse_shadow = QColor(0, 0, 0, self._style.shadow_alpha)
        painter.setPen(diffuse_shadow)
        for offset in _diffuse_shadow_offsets():
            painter.drawText(position + offset, text)
        directional_shadow = QColor(0, 0, 0, self._style.strong_shadow_alpha)
        painter.setPen(directional_shadow)
        painter.drawText(position + QPointF(1.0, 1.0), text)
        painter.setPen(color)
        painter.drawText(position, text)

    def paint_shadowed_path(
        self,
        painter: QPainter,
        path: QPainterPath,
        *,
        pen: QPen,
    ) -> None:
        """Paint an icon path with the same shadow treatment as banner text."""

        painter.save()
        try:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            diffuse_pen = QPen(pen)
            diffuse_pen.setColor(QColor(0, 0, 0, self._style.shadow_alpha))
            painter.setPen(diffuse_pen)
            for offset in _diffuse_shadow_offsets():
                painter.drawPath(path.translated(offset))

            directional_pen = QPen(pen)
            directional_pen.setColor(QColor(0, 0, 0, self._style.strong_shadow_alpha))
            painter.setPen(directional_pen)
            painter.drawPath(path.translated(QPointF(1.0, 1.0)))

            painter.setPen(pen)
            painter.drawPath(path)
        finally:
            painter.restore()

    def paint_shadowed_icon(
        self,
        painter: QPainter,
        rect: QRectF,
        render_icon: BannerIconRenderer,
        *,
        color: QColor,
    ) -> None:
        """Paint an existing icon asset with the shared banner shadow treatment."""

        diffuse_shadow = QColor(0, 0, 0, self._style.shadow_alpha)
        for offset in _diffuse_shadow_offsets():
            _render_icon_with_alpha(
                painter,
                rect.translated(offset),
                render_icon,
                diffuse_shadow,
            )

        _render_icon_with_alpha(
            painter,
            rect.translated(QPointF(1.0, 1.0)),
            render_icon,
            QColor(0, 0, 0, self._style.strong_shadow_alpha),
        )
        _render_icon_with_alpha(painter, rect, render_icon, color)

    def _paint_wash(
        self,
        painter: QPainter,
        rect: QRectF,
        shape: QPainterPath | None,
        wash_alpha: int | None,
    ) -> None:
        """Paint the black readability wash over banner artwork."""

        wash = QColor(
            0, 0, 0, self._style.wash_alpha if wash_alpha is None else wash_alpha
        )
        if shape is not None:
            painter.fillPath(shape, wash)
        else:
            painter.fillRect(rect, wash)


def _centered_cover_rect(rect: QRectF, pixmap: QPixmap) -> QRectF:
    """Return a target rect that covers without changing pixmap aspect ratio."""

    source_width = _logical_pixmap_width(pixmap)
    source_height = _logical_pixmap_height(pixmap)
    if source_width <= 0.0 or source_height <= 0.0:
        return QRectF(rect)
    scale = max(rect.width() / source_width, rect.height() / source_height)
    target_width = source_width * scale
    target_height = source_height * scale
    return QRectF(
        rect.left() + (rect.width() - target_width) / 2.0,
        rect.top() + (rect.height() - target_height) / 2.0,
        target_width,
        target_height,
    )


def _logical_pixmap_width(pixmap: QPixmap) -> float:
    """Return pixmap width in painter logical coordinates."""

    return pixmap.width() / max(1.0, pixmap.devicePixelRatioF())


def _logical_pixmap_height(pixmap: QPixmap) -> float:
    """Return pixmap height in painter logical coordinates."""

    return pixmap.height() / max(1.0, pixmap.devicePixelRatioF())


def _render_icon_with_alpha(
    painter: QPainter,
    rect: QRectF,
    render_icon: BannerIconRenderer,
    color: QColor,
) -> None:
    """Render one icon pass while preserving alpha for SVG-backed assets."""

    painter.save()
    try:
        pass_color = QColor(color)
        if pass_color.alpha() < 255:
            painter.setOpacity(painter.opacity() * pass_color.alphaF())
            pass_color.setAlpha(255)
        render_icon(painter, rect, pass_color)
    finally:
        painter.restore()


def _diffuse_shadow_offsets() -> tuple[QPointF, ...]:
    """Return the shared soft-shadow offsets for banner text and icon paths."""

    return (
        QPointF(-1.0, 0.0),
        QPointF(1.0, 0.0),
        QPointF(0.0, -1.0),
        QPointF(0.0, 1.0),
        QPointF(-0.7, -0.7),
        QPointF(0.7, 0.7),
        QPointF(-0.7, 0.7),
        QPointF(0.7, -0.7),
    )


__all__ = ["BannerIconRenderer", "BannerTextPainter", "BannerTextStyle"]
