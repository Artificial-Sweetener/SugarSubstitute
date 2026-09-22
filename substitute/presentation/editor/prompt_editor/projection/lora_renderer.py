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

"""Render LoRA schedules as interactive inline chips."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from qfluentwidgets.common.style_sheet import isDarkTheme, themeColor  # type: ignore[import-untyped]

from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from substitute.presentation.semantic_colors import semantic_error_color
from substitute.presentation.widgets.banner_text_painter import BannerTextPainter

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)

from .inline_renderer_typography import centered_text_baseline, inline_weight_font
from .lora_paint_cache import (
    PromptLoraPaintCache,
    lora_paint_cache_key,
    painter_device_pixel_ratio,
)
from .metrics import projection_text_line_height

_LORA_CHIP_RENDERER_KEY = "lora_chip"


class PromptLoraInlineObjectRenderer:
    """Render one LoRA schedule as a graphical inline chip."""

    renderer_key = _LORA_CHIP_RENDERER_KEY
    _CHEVRON_MAX_DEPTH = 14.0
    _CHEVRON_DEPTH_RATIO = 0.55
    _INNER_PADDING = 7.0
    _MINIMUM_WIDTH = 120.0
    _MAXIMUM_WIDTH = 540.0
    _TITLE_WIDTH_CAP = 430.0
    _PAGE_NAME_CHARACTER_LIMIT = 20
    _VERSION_NAME_CHARACTER_LIMIT = 15
    _TITLE_VERSION_SEPARATOR = " - "
    _VERSION_WIDTH_RATIO = 0.42
    _TITLE_WEIGHT_GAP = 8.0
    _ROW_HEIGHT_INSET = 2.0
    _WEIGHT_PADDING_X = 4.0
    _WEIGHT_PADDING_Y = 1.5
    _STABLE_WEIGHT_TEXT = "-8.88"

    def __init__(
        self,
        thumbnail_cache: PromptLoraThumbnailCache | None = None,
        *,
        suppress_banners: bool = False,
    ) -> None:
        """Store thumbnail collaborators and banner paint policy."""

        self._thumbnail_cache = thumbnail_cache or PromptLoraThumbnailCache()
        self._suppress_banners = suppress_banners
        self._banner_text_painter = BannerTextPainter()
        self._title_segments_cache: dict[
            tuple[str, str, str, int],
            tuple[str, ...],
        ] = {}
        self._paint_cache = PromptLoraPaintCache()

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Measure one LoRA bar from title and weight text."""

        title_font = self._title_font(base_font)
        metrics = QFontMetricsF(title_font)
        height = max(
            1.0, projection_text_line_height(base_font) - self._ROW_HEIGHT_INSET
        )
        chevron_depth = self._chevron_depth(height)
        title_width = min(
            self._title_text_width(metrics, run, token),
            self._TITLE_WIDTH_CAP,
        )
        width = (
            chevron_depth * 2
            + self._INNER_PADDING * 2
            + title_width
            + self._TITLE_WEIGHT_GAP
            + self._weight_text_width(token, run, base_font=base_font)
        )
        measured = QSizeF(
            max(self._MINIMUM_WIDTH, min(self._MAXIMUM_WIDTH, width)), height
        )
        return measured

    def paint_inline_object(
        self,
        painter: QPainter,
        rect: QRectF,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
        palette: QPalette,
        selected: bool = False,
    ) -> None:
        """Paint one LoRA chip inside the supplied rect."""

        banner = (
            None
            if self._suppress_banners or not token.thumbnail_variants
            else self._banner_for_token(painter, token, rect)
        )
        fill, border, accent = self._colors_for_token(token)
        text_color = self._text_color(palette, banner is not None)
        paint_key = lora_paint_cache_key(
            painter,
            rect,
            run,
            token,
            base_font=base_font,
            fill=fill,
            border=border,
            accent=accent,
            text_color=text_color,
            banner=banner,
            selected=selected,
        )

        def render_cached_chip(cache_painter: QPainter, cache_rect: QRectF) -> None:
            """Render one chip into the cache-owned local-coordinate raster."""

            self._paint_uncached(
                cache_painter,
                cache_rect,
                run,
                token,
                base_font=base_font,
                palette=palette,
                banner=banner,
            )

        self._paint_cache.paint(
            painter,
            rect,
            key=paint_key,
            render=render_cached_chip,
        )

    def _paint_uncached(
        self,
        painter: QPainter,
        rect: QRectF,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
        palette: QPalette,
        banner: QPixmap | None,
    ) -> None:
        """Render one local-coordinate LoRA chip for paint-cache reuse."""

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            fill, border, accent = self._colors_for_token(token)
            path = self._chevron_path(rect)
            if banner is None:
                painter.setBrush(fill)
                painter.setPen(border)
                painter.drawPath(path)
                self._paint_fallback_initial(
                    painter,
                    rect,
                    run,
                    base_font=base_font,
                    color=accent,
                )
            else:
                self._banner_text_painter.paint_banner_backing(
                    painter,
                    rect=rect,
                    shape=path,
                    banner=banner,
                    fallback_fill=fill,
                    fallback_border=None,
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(border)
                painter.drawPath(path)

            weight_rect = self._weight_text_rect(rect, token, run, base_font=base_font)
            assert weight_rect is not None
            chevron_depth = self._chevron_depth(rect.height())
            text_left = rect.left() + chevron_depth + self._INNER_PADDING
            text_right = weight_rect.left() - self._TITLE_WEIGHT_GAP
            title_font = self._title_font(base_font)
            metrics = QFontMetricsF(title_font)
            painter.setFont(title_font)
            text_color = self._text_color(palette, banner is not None)
            self._paint_title_text(
                painter,
                QPointF(text_left, centered_text_baseline(rect, metrics)),
                metrics,
                run,
                token,
                available_width=text_right - text_left,
                color=text_color,
                banner_backed=banner is not None,
            )
            self._paint_weight_text(
                painter,
                weight_rect,
                token,
                run,
                base_font=base_font,
                palette=palette,
                color=text_color,
                banner_backed=banner is not None,
            )
        finally:
            painter.restore()

    def _title_font(self, base_font: QFont) -> QFont:
        """Return the slightly smaller font used for LoRA page/version labels."""

        title_font = QFont(base_font)
        if base_font.pointSizeF() > 0:
            title_font.setPointSizeF(max(7.0, base_font.pointSizeF() - 0.8))
        elif base_font.pixelSize() > 0:
            title_font.setPixelSize(max(8, base_font.pixelSize() - 1))
        return title_font

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the weight rect used by shared weighted-token controls."""

        return self._weight_text_rect(rect, token, run, base_font=base_font)

    def weight_text_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the projection-owned slot rect for one LoRA weight label."""

        return self._weight_text_rect(rect, token, run, base_font=base_font)

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve one LoRA chip point into a leading or trailing caret edge."""

        _ = (run, base_font)
        placement = (
            PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
            if position.x() >= rect.center().x()
            else PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
        )
        return PromptProjectionCaretState(
            source_position=(
                token.source_end
                if placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                else token.source_start
            ),
            placement=placement,
            token_id=token.token_id,
        )

    def selection_rects(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        selection_start: int,
        selection_end: int,
        base_font: QFont,
    ) -> tuple[QRectF, ...]:
        """Return the whole LoRA chip rect whenever its source overlaps selection."""

        _ = (run, base_font)
        if token.source_start < selection_end and selection_start < token.source_end:
            return (QRectF(rect),)
        return ()

    def _chevron_path(self, rect: QRectF) -> QPainterPath:
        """Return the sharp angle-bracket-like LoRA bar path."""

        depth = self._chevron_depth(rect.height())
        path = QPainterPath()
        path.moveTo(rect.left(), rect.center().y())
        path.lineTo(rect.left() + depth, rect.top())
        path.lineTo(rect.right() - depth, rect.top())
        path.lineTo(rect.right(), rect.center().y())
        path.lineTo(rect.right() - depth, rect.bottom())
        path.lineTo(rect.left() + depth, rect.bottom())
        path.closeSubpath()
        return path

    def _chevron_depth(self, height: float) -> float:
        """Return the tapered side depth for one LoRA bar height."""

        return min(
            self._CHEVRON_MAX_DEPTH, max(4.0, height * self._CHEVRON_DEPTH_RATIO)
        )

    def _title_text_width(
        self,
        metrics: QFontMetricsF,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
    ) -> float:
        """Return the natural width of page and version LoRA labels."""

        page_text = self._capped_page_text(run.display_text)
        version_text = self._capped_version_text(_lora_version_text(token))
        if not page_text:
            return metrics.horizontalAdvance(version_text)
        if not version_text:
            return metrics.horizontalAdvance(page_text)
        return metrics.horizontalAdvance(
            f"{page_text}{self._TITLE_VERSION_SEPARATOR}{version_text}"
        )

    def _paint_title_text(
        self,
        painter: QPainter,
        position: QPointF,
        metrics: QFontMetricsF,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        available_width: float,
        color: QColor,
        banner_backed: bool,
    ) -> None:
        """Paint page and version labels while preserving room for the version."""

        segments = self._title_segments(
            metrics,
            page_text=run.display_text,
            version_text=_lora_version_text(token),
            available_width=available_width,
        )
        secondary_color = self._secondary_text_color(color, banner_backed=banner_backed)
        x = position.x()
        for index, segment in enumerate(segments):
            segment_color = secondary_color if index == 2 else color
            self._banner_text_painter.paint_shadowed_text(
                painter,
                QPointF(x, position.y()),
                segment,
                color=segment_color,
            )
            x += metrics.horizontalAdvance(segment)

    def _title_segments(
        self,
        metrics: QFontMetricsF,
        *,
        page_text: str,
        version_text: str,
        available_width: float,
    ) -> tuple[str, ...]:
        """Return elided page/separator/version text segments for one title slot."""

        cache_key = (
            f"{metrics.height():.3f}:{metrics.ascent():.3f}",
            page_text,
            version_text,
            int(max(0.0, round(available_width))),
        )
        cached_segments = self._title_segments_cache.get(cache_key)
        if cached_segments is not None:
            return cached_segments
        page = self._capped_page_text(page_text)
        version = self._capped_version_text(version_text)
        segments: tuple[str, ...]
        if not page or not version:
            text = page or version
            segments = (
                metrics.elidedText(
                    text,
                    Qt.TextElideMode.ElideRight,
                    int(max(0.0, round(available_width))),
                ),
            )
            self._remember_title_segments(cache_key, segments)
            return segments

        separator = self._TITLE_VERSION_SEPARATOR
        separator_width = metrics.horizontalAdvance(separator)
        if available_width <= separator_width:
            segments = (
                metrics.elidedText(
                    page,
                    Qt.TextElideMode.ElideRight,
                    int(max(0.0, round(available_width))),
                ),
            )
            self._remember_title_segments(cache_key, segments)
            return segments

        text_width = max(0.0, available_width - separator_width)
        page_width = metrics.horizontalAdvance(page)
        version_width = metrics.horizontalAdvance(version)
        if page_width + version_width <= text_width:
            segments = (page, separator, version)
            self._remember_title_segments(cache_key, segments)
            return segments

        minimum_segment_width = metrics.horizontalAdvance("...")
        reserved_version_width = min(
            version_width,
            max(minimum_segment_width, text_width * self._VERSION_WIDTH_RATIO),
        )
        reserved_page_width = max(0.0, text_width - reserved_version_width)
        if (
            reserved_page_width < minimum_segment_width
            and text_width >= minimum_segment_width * 2
        ):
            reserved_page_width = minimum_segment_width
            reserved_version_width = max(0.0, text_width - reserved_page_width)
        if reserved_version_width <= 0.0:
            segments = (
                metrics.elidedText(
                    page,
                    Qt.TextElideMode.ElideRight,
                    int(max(0.0, round(available_width))),
                ),
            )
            self._remember_title_segments(cache_key, segments)
            return segments
        segments = (
            metrics.elidedText(
                page,
                Qt.TextElideMode.ElideRight,
                int(max(0.0, round(reserved_page_width))),
            ),
            separator,
            metrics.elidedText(
                version,
                Qt.TextElideMode.ElideRight,
                int(max(0.0, round(reserved_version_width))),
            ),
        )
        self._remember_title_segments(cache_key, segments)
        return segments

    def _remember_title_segments(
        self,
        cache_key: tuple[str, str, str, int],
        segments: tuple[str, ...],
    ) -> None:
        """Store one LoRA title segmentation result for repeated paints."""

        if len(self._title_segments_cache) >= 512:
            self._title_segments_cache.clear()
        self._title_segments_cache[cache_key] = segments

    def _capped_page_text(self, text: str) -> str:
        """Return page/model text capped for compact inline display."""

        return _character_elided_text(text.strip(), self._PAGE_NAME_CHARACTER_LIMIT)

    def _capped_version_text(self, text: str) -> str:
        """Return version text capped for compact inline display."""

        return _character_elided_text(text.strip(), self._VERSION_NAME_CHARACTER_LIMIT)

    def _banner_for_token(
        self,
        painter: QPainter,
        token: PromptProjectionToken,
        rect: QRectF,
    ) -> QPixmap | None:
        """Return the cached banner pixmap for one LoRA token when available."""

        requested_size = QSize(
            max(1, round(rect.width())), max(1, round(rect.height()))
        )
        device_pixel_ratio = painter_device_pixel_ratio(painter)
        banner = self._thumbnail_cache.banner_pixmap_for_variants(
            token.thumbnail_variants,
            requested_size,
            device_pixel_ratio=device_pixel_ratio,
        )
        return banner

    def _paint_fallback_initial(
        self,
        painter: QPainter,
        rect: QRectF,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
        color: QColor,
    ) -> None:
        """Paint a subtle fallback initial inside the chevron bar."""

        initial = (run.display_text.strip()[:1] or "L").upper()
        font = QFont(base_font)
        if font.pointSizeF() > 0:
            font.setPointSizeF(max(8.0, font.pointSizeF() - 1.5))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fallback_color = QColor(color)
        fallback_color.setAlpha(72)
        painter.setPen(fallback_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initial)

    def _weight_text_rect(
        self,
        rect: QRectF,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the stable LoRA weight pill rect."""

        if token.editing_value_text is None and not run.display_text:
            return None
        metrics = QFontMetricsF(self._weight_font(base_font))
        width = self._weight_text_width(token, run, base_font=base_font)
        height = min(
            max(1.0, rect.height()),
            max(1.0, metrics.height() + self._WEIGHT_PADDING_Y * 2),
        )
        chevron_depth = self._chevron_depth(rect.height())
        return QRectF(
            rect.right() - chevron_depth - self._INNER_PADDING - width,
            rect.top() + max(0.0, (rect.height() - height) / 2.0),
            width,
            height,
        )

    def _weight_text_width(
        self,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> float:
        """Return the width needed by the LoRA weight text slot."""

        text = _lora_weight_text(token)
        metrics = QFontMetricsF(self._weight_font(base_font))
        stable_width = metrics.horizontalAdvance(self._STABLE_WEIGHT_TEXT)
        width = max(metrics.horizontalAdvance(text), stable_width)
        width += self._WEIGHT_PADDING_X * 2
        if token.editing_slot_width is not None:
            width = max(width, token.editing_slot_width)
        return width

    def _paint_weight_text(
        self,
        painter: QPainter,
        rect: QRectF,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
        palette: QPalette,
        color: QColor,
        banner_backed: bool,
    ) -> None:
        """Paint LoRA weight text, including exact edit state."""

        text = _lora_weight_text(token)
        font = self._weight_font(base_font)
        metrics = QFontMetricsF(font)
        painter.setFont(font)
        text_rect = rect.adjusted(
            self._WEIGHT_PADDING_X, 0.0, -self._WEIGHT_PADDING_X, 0.0
        )
        if token.editing_value_text is None:
            self._banner_text_painter.paint_shadowed_text(
                painter,
                QPointF(text_rect.left(), centered_text_baseline(text_rect, metrics)),
                text,
                color=color,
            )
            return
        self._paint_edit_backing(painter, rect, banner_backed=banner_backed)

    def _paint_edit_backing(
        self,
        painter: QPainter,
        rect: QRectF,
        *,
        banner_backed: bool,
    ) -> None:
        """Paint a stronger backing behind the active weight edit buffer."""

        fill = QColor(0, 0, 0, 132 if banner_backed else 64)
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)

    def _colors_for_token(
        self,
        token: PromptProjectionToken,
    ) -> tuple[QColor, QColor, QColor]:
        """Return fill, border, and thumbnail accent colors for one LoRA token."""

        accent = _lora_accent_color(token)
        fill = QColor(accent)
        border = QColor(accent)
        fill.setAlpha(46 if isDarkTheme() else 32)
        border.setAlpha(156 if token.active else 104)
        return fill, border, accent

    def _text_color(self, palette: QPalette, banner_backed: bool) -> QColor:
        """Return text color for banner-backed or fallback LoRA bars."""

        if banner_backed:
            return QColor(Qt.GlobalColor.white)
        return QColor(palette.color(QPalette.ColorRole.Text))

    def _secondary_text_color(self, color: QColor, *, banner_backed: bool) -> QColor:
        """Return the secondary color used for LoRA version labels."""

        secondary = QColor(color)
        secondary.setAlpha(220 if banner_backed else 190)
        return secondary

    def _weight_font(self, base_font: QFont) -> QFont:
        """Return the font used for LoRA weight text."""

        return inline_weight_font(base_font)


def _lora_weight_text(token: PromptProjectionToken) -> str:
    """Return the visible weight text for one LoRA chip."""

    return (
        token.editing_value_text
        if token.editing_value_text is not None
        else token.value_text or ""
    )


def _lora_version_text(token: PromptProjectionToken) -> str:
    """Return the visible version text for one LoRA chip."""

    return "" if token.lora_version_text is None else token.lora_version_text.strip()


def _lora_accent_color(token: PromptProjectionToken) -> QColor:
    """Return the status-aware accent color for one LoRA chip."""

    if token.lora_status in {
        PromptLoraResolutionStatus.MISSING,
        PromptLoraResolutionStatus.AMBIGUOUS,
    }:
        return semantic_error_color()
    if token.lora_status in {
        PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
        PromptLoraResolutionStatus.CATALOG_UNAVAILABLE,
    }:
        return QColor(156, 163, 175) if isDarkTheme() else QColor(107, 114, 128)
    if not token.exists:
        return semantic_error_color()
    return QColor(themeColor())


def _character_elided_text(text: str, limit: int) -> str:
    """Return text capped to a maximum number of display characters."""

    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 3:
        return "." * limit
    return f"{text[: limit - 3]}..."
