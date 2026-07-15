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

"""Paint reusable media wall tiles."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.media_wall.media_wall_marquee import (
    TitleMarqueeState,
)
from substitute.presentation.widgets.media_wall.media_wall_item import MediaWallItem
from substitute.presentation.widgets.media_wall.media_wall_style import (
    media_wall_current_border,
    media_wall_hover_border,
    media_wall_placeholder_fill,
    media_wall_placeholder_text,
    media_wall_subtitle_text,
    media_wall_title_text,
)
from substitute.presentation.widgets.media_wall.media_wall_thumbnail_cache import (
    MediaWallThumbnailCache,
)

_TEXT_PADDING_X = 8
_TEXT_PADDING_BOTTOM = 7
_TEXT_LINE_GAP = 2
_TITLE_FADE_WIDTH = 18


def paint_media_wall_tile(
    painter: QPainter,
    widget: QWidget,
    *,
    item: MediaWallItem,
    rect: QRect,
    hovered: bool,
    current: bool,
    thumbnail_cache: MediaWallThumbnailCache,
    title_marquee_state: TitleMarqueeState | None = None,
) -> None:
    """Paint one wall tile thumbnail, placeholder, and hover/focus overlay."""

    painter.save()
    painter.setClipRect(rect)
    pixmap = thumbnail_cache.pixmap_for_variants(
        item.thumbnail_variants,
        rect.size(),
        device_pixel_ratio=widget.devicePixelRatioF(),
    )
    if pixmap is None:
        painter.fillRect(rect, media_wall_placeholder_fill())
        _paint_placeholder_text(painter, rect, widget.fontMetrics())
    else:
        dpr = max(1.0, pixmap.devicePixelRatio())
        target = _centered_cover_rect(
            rect,
            QSize(round(pixmap.width() / dpr), round(pixmap.height() / dpr)),
        )
        painter.drawPixmap(target, pixmap)
    _paint_overlay(
        painter,
        rect,
        item,
        widget.fontMetrics(),
        emphasized=hovered or current,
        title_marquee_state=title_marquee_state,
    )
    if current:
        pen = QPen(media_wall_current_border())
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(1, 1, -2, -2))
    elif hovered:
        pen = QPen(media_wall_hover_border())
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(1, 1, -2, -2))
    painter.restore()


def _paint_placeholder_text(
    painter: QPainter,
    rect: QRect,
    metrics: QFontMetrics,
) -> None:
    """Paint a small placeholder label for tiles without thumbnails."""

    painter.setPen(media_wall_placeholder_text())
    text = metrics.elidedText(
        "No image", Qt.TextElideMode.ElideRight, rect.width() - 12
    )
    painter.drawText(rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignCenter, text)


def _paint_overlay(
    painter: QPainter,
    rect: QRect,
    item: MediaWallItem,
    metrics: QFontMetrics,
    *,
    emphasized: bool,
    title_marquee_state: TitleMarqueeState | None,
) -> None:
    """Paint the bottom vignette and item text overlay."""

    gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(0.42, QColor(0, 0, 0, 12 if not emphasized else 24))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 178 if not emphasized else 220))
    painter.fillRect(rect, gradient)
    subtitle_is_visible = bool(item.subtitle)
    title_rect, subtitle_rect = title_and_subtitle_rects(
        rect,
        metrics,
        subtitle_visible=subtitle_is_visible,
    )
    if subtitle_is_visible and item.subtitle is not None:
        subtitle = metrics.elidedText(
            item.subtitle,
            Qt.TextElideMode.ElideRight,
            title_rect.width(),
        )
        painter.setPen(media_wall_subtitle_text())
        painter.drawText(
            subtitle_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )
    _paint_title_text(
        painter,
        title_rect,
        metrics,
        item.title,
        title_marquee_state=title_marquee_state,
    )


def title_and_subtitle_rects(
    tile_rect: QRect,
    metrics: QFontMetrics,
    *,
    subtitle_visible: bool,
) -> tuple[QRect, QRect]:
    """Return stable text rects used by painting and marquee measurement."""

    title_height = metrics.height()
    line_count = 2 if subtitle_visible else 1
    text_height = line_count * title_height + (line_count - 1) * _TEXT_LINE_GAP
    text_top = tile_rect.bottom() - _TEXT_PADDING_BOTTOM - text_height + 1
    title_rect = QRect(
        tile_rect.left() + _TEXT_PADDING_X,
        text_top,
        max(1, tile_rect.width() - _TEXT_PADDING_X * 2),
        title_height + 2,
    )
    subtitle_rect = QRect(
        title_rect.left(),
        title_rect.bottom() + _TEXT_LINE_GAP,
        title_rect.width(),
        title_height + 2,
    )
    return title_rect, subtitle_rect


def _paint_title_text(
    painter: QPainter,
    title_rect: QRect,
    metrics: QFontMetrics,
    title: str,
    *,
    title_marquee_state: TitleMarqueeState | None,
) -> None:
    """Paint one title with static elision or active marquee behavior."""

    painter.setPen(media_wall_title_text())
    if title_marquee_state is None or title_marquee_state.phase == "start":
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width()),
        )
        return
    if title_marquee_state.phase == "end":
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(title, Qt.TextElideMode.ElideLeft, title_rect.width()),
        )
        return
    title_image = _marquee_title_image(
        painter,
        title_rect,
        metrics,
        title,
        title_marquee_state=title_marquee_state,
    )
    painter.drawImage(title_rect.topLeft(), title_image)


def _marquee_title_image(
    painter: QPainter,
    title_rect: QRect,
    metrics: QFontMetrics,
    title: str,
    *,
    title_marquee_state: TitleMarqueeState,
) -> QImage:
    """Return marquee title text with edge fading applied to glyph alpha only."""

    title_image = QImage(title_rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
    title_image.fill(QColor(0, 0, 0, 0))
    image_painter = QPainter(title_image)
    try:
        image_painter.setFont(painter.font())
        image_painter.setPen(media_wall_title_text())
        local_title_rect = QRect(0, 0, title_rect.width(), title_rect.height())
        image_painter.drawText(
            local_title_rect.translated(
                -round(title_marquee_state.offset),
                0,
            ).adjusted(
                0,
                0,
                metrics.horizontalAdvance(title) + title_rect.width(),
                0,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )
        _apply_title_alpha_mask(
            image_painter,
            title_image.rect(),
            title_marquee_state=title_marquee_state,
        )
    finally:
        image_painter.end()
    return title_image


def _apply_title_alpha_mask(
    painter: QPainter,
    rect: QRect,
    *,
    title_marquee_state: TitleMarqueeState,
) -> None:
    """Fade only existing title glyph alpha at marquee edges."""

    if rect.width() <= 0:
        return
    width = max(1, rect.width() - 1)
    fade_width = min(_TITLE_FADE_WIDTH, max(1, rect.width() // 2))
    left_fade_stop = fade_width / width
    right_fade_start = 1.0 - left_fade_stop
    transparent = QColor(0, 0, 0, 0)
    opaque = QColor(0, 0, 0, 255)
    gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
    if title_marquee_state.show_left_fade:
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(left_fade_stop, opaque)
    else:
        gradient.setColorAt(0.0, opaque)
    if title_marquee_state.show_right_fade:
        gradient.setColorAt(right_fade_start, opaque)
        gradient.setColorAt(1.0, transparent)
    else:
        gradient.setColorAt(1.0, opaque)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.fillRect(rect, gradient)


def _centered_cover_rect(tile_rect: QRect, pixmap_size: QSize) -> QRect:
    """Return the target rect that covers one tile while preserving aspect ratio."""

    if pixmap_size.width() <= 0 or pixmap_size.height() <= 0:
        return QRect(tile_rect)
    scale = max(
        tile_rect.width() / pixmap_size.width(),
        tile_rect.height() / pixmap_size.height(),
    )
    width = round(pixmap_size.width() * scale)
    height = round(pixmap_size.height() * scale)
    left = tile_rect.left() + (tile_rect.width() - width) // 2
    top = tile_rect.top() + (tile_rect.height() - height) // 2
    return QRect(left, top, width, height)


__all__ = ["paint_media_wall_tile", "title_and_subtitle_rects"]
