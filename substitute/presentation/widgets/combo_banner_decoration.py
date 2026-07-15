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

"""Paint opt-in banner decoration for closed combo-like fields."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPalette,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.widgets.banner_text_painter import BannerTextPainter
from substitute.presentation.widgets.media_wall import (
    MediaWallThumbnailCache,
    ThumbnailVariantReference,
)


@dataclass(frozen=True, slots=True)
class ComboBannerDisplay:
    """Describe banner-backed closed-state combo display content."""

    title: str
    subtitle: str | None
    banner_variants: tuple[ThumbnailVariantReference, ...]
    fallback_key: str
    tooltip: str

    def display_label(self) -> str:
        """Return the single-line label used by compact combo fields."""

        title = self.title.strip()
        subtitle = "" if self.subtitle is None else self.subtitle.strip()
        if title and subtitle:
            return f"{title} - {subtitle}"
        return title


class ComboBannerDecoration:
    """Paint a banner-backed closed-state label inside a combo-like field."""

    def __init__(
        self,
        *,
        thumbnail_cache: MediaWallThumbnailCache,
        banner_text_painter: BannerTextPainter | None = None,
        paint_fallback: bool = False,
    ) -> None:
        """Store shared banner lookup and painter collaborators."""

        self._thumbnail_cache = thumbnail_cache
        self._banner_text_painter = banner_text_painter or BannerTextPainter()
        self._paint_fallback = paint_fallback

    def paint_closed_display(
        self,
        painter: QPainter,
        widget: QWidget,
        *,
        display: ComboBannerDisplay,
        rect: QRect,
        text_rect: QRect,
        chevron_rect: QRectF | None,
        palette: QPalette,
        font: QFont,
        border_radius: float,
    ) -> bool:
        """Paint closed-state combo decoration and return whether it painted."""

        banner = self._thumbnail_cache.pixmap_for_role(
            display.banner_variants,
            BANNER_THUMBNAIL_ROLE,
            rect.size(),
            device_pixel_ratio=widget.devicePixelRatioF(),
        )
        if banner is None and not self._paint_fallback:
            return False

        shape = _rounded_rect_path(QRectF(rect), border_radius)
        fallback_fill = _fallback_fill(display.fallback_key, palette)
        self._banner_text_painter.paint_banner_backing(
            painter,
            rect=QRectF(rect),
            shape=shape,
            banner=banner,
            fallback_fill=fallback_fill,
            fallback_border=None,
        )
        self._paint_label(
            painter,
            display,
            text_rect,
            font=font,
            color=QColor(Qt.GlobalColor.white),
        )
        if chevron_rect is not None:
            self._paint_chevron(
                painter,
                chevron_rect,
                color=QColor(Qt.GlobalColor.white),
            )
        return True

    def _paint_label(
        self,
        painter: QPainter,
        display: ComboBannerDisplay,
        text_rect: QRect,
        *,
        font: QFont,
        color: QColor,
    ) -> None:
        """Paint the display label centered inside the supplied text rect."""

        if text_rect.width() <= 0 or text_rect.height() <= 0:
            return
        painter.save()
        try:
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            label = metrics.elidedText(
                display.display_label(),
                Qt.TextElideMode.ElideRight,
                max(0.0, float(text_rect.width())),
            )
            baseline = (
                text_rect.top()
                + (text_rect.height() + metrics.ascent() - metrics.descent()) / 2.0
            )
            self._banner_text_painter.paint_shadowed_text(
                painter,
                QPointF(float(text_rect.left()), baseline),
                label,
                color=color,
            )
        finally:
            painter.restore()

    def _paint_chevron(
        self,
        painter: QPainter,
        chevron_rect: QRectF,
        *,
        color: QColor,
    ) -> None:
        """Paint the closed combo chevron with shared banner icon shadows."""

        if chevron_rect.width() <= 0.0 or chevron_rect.height() <= 0.0:
            return
        self._banner_text_painter.paint_shadowed_icon(
            painter,
            chevron_rect,
            _render_combo_chevron_icon,
            color=color,
        )


def _rounded_rect_path(rect: QRectF, radius: float) -> QPainterPath:
    """Return a rounded rectangle path for combo banner clipping."""

    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def _fallback_fill(fallback_key: str, palette: QPalette) -> QColor:
    """Return a deterministic fallback fill for optional fallback painting."""

    digest = hashlib.sha1(fallback_key.encode("utf-8", errors="ignore")).digest()
    hue = int.from_bytes(digest[:2], byteorder="big") % 360
    fill = QColor.fromHsv(hue, 95, 115)
    fill.setAlpha(150 if palette.window().color().lightness() < 128 else 115)
    return fill


def _render_combo_chevron_icon(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
) -> None:
    """Render qfluent's combo chevron asset in a supplied color."""

    painter.save()
    try:
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        FIF.ARROW_DOWN.render(painter, rect, fill=color.name())
    finally:
        painter.restore()


__all__ = ["ComboBannerDecoration", "ComboBannerDisplay"]
