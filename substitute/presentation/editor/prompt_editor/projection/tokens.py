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

"""Provide reusable measurement and paint contracts for inline projection objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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

from substitute.application.prompt_editor.prompt_lora_resolution_service import (
    PromptLoraResolutionStatus,
)
from substitute.presentation.semantic_colors import semantic_error_color
from substitute.presentation.widgets.banner_text_painter import BannerTextPainter

from .model import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionRun,
    PromptProjectionToken,
)
from .metrics import projection_text_line_height
from ..lora_thumbnail_cache import PromptLoraThumbnailCache

_EMPHASIS_PREFIX_RENDERER_KEY = "emphasis_prefix"
_EMPHASIS_SUFFIX_RENDERER_KEY = "emphasis_suffix"
_LORA_CHIP_RENDERER_KEY = "lora_chip"
_WILDCARD_CHIP_RENDERER_KEY = "wildcard_chip"
_EMPHASIS_DECORATION_CONTENT_GAP = 2.5
_EMPHASIS_WEIGHT_GAP = 1.0


class PromptRichInlineObjectRenderer(Protocol):
    """Describe one renderer used by the projection layout for inline objects."""

    renderer_key: str

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Return the inline size required to render one visible object run."""

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
        """Paint one inline object run inside the supplied rect."""

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the rect used for non-clipping controls anchored to this object."""

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve one object-local point into the nearest logical caret state."""

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
        """Return the selection rects owned by one inline object run."""


@dataclass(frozen=True, slots=True)
class _EmphasisDecorationMetrics:
    """Store the shared fonts and spacing used by emphasis decoration runs."""

    parenthesis_font: QFont
    parenthesis_metrics: QFontMetricsF
    weight_font: QFont
    weight_metrics: QFontMetricsF
    content_gap: float
    weight_gap: float

    def parenthesis_width(self, character: str) -> float:
        """Return the rendered width of one decorative parenthesis glyph."""

        return self.parenthesis_metrics.horizontalAdvance(character)


def _emphasis_parenthesis_font(base_font: QFont) -> QFont:
    """Return the smaller font used for decorative emphasis parentheses."""

    parenthesis_font = QFont(base_font)
    if base_font.pointSizeF() > 0:
        parenthesis_font.setPointSizeF(max(6.2, base_font.pointSizeF() - 1.9))
    elif base_font.pixelSize() > 0:
        parenthesis_font.setPixelSize(max(7, base_font.pixelSize() - 3))
    parenthesis_font.setWeight(QFont.Weight.Medium)
    return parenthesis_font


def _emphasis_weight_font(base_font: QFont) -> QFont:
    """Return the slightly smaller raised font used for emphasis weights."""

    weight_font = QFont(base_font)
    if base_font.pointSizeF() > 0:
        weight_font.setPointSizeF(max(5.4, base_font.pointSizeF() - 4.0))
    elif base_font.pixelSize() > 0:
        weight_font.setPixelSize(max(6, base_font.pixelSize() - 4))
    weight_font.setWeight(QFont.Weight.DemiBold)
    return weight_font


def emphasis_weight_font(base_font: QFont) -> QFont:
    """Return the public weight font used by emphasis numbers and exact edit chrome."""

    return _emphasis_weight_font(base_font)


def _emphasis_decoration_metrics(base_font: QFont) -> _EmphasisDecorationMetrics:
    """Return one shared metrics bundle so both emphasis parens stay symmetrical."""

    parenthesis_font = _emphasis_parenthesis_font(base_font)
    weight_font = _emphasis_weight_font(base_font)
    return _EmphasisDecorationMetrics(
        parenthesis_font=parenthesis_font,
        parenthesis_metrics=QFontMetricsF(parenthesis_font),
        weight_font=weight_font,
        weight_metrics=QFontMetricsF(weight_font),
        content_gap=_EMPHASIS_DECORATION_CONTENT_GAP,
        weight_gap=_EMPHASIS_WEIGHT_GAP,
    )


def _centered_text_baseline(
    rect: QRectF,
    metrics: QFontMetricsF,
) -> float:
    """Return the baseline that vertically centers text inside the supplied rect."""

    return rect.center().y() + ((metrics.ascent() - metrics.descent()) / 2.0)


def _emphasis_parenthesis_color(
    palette: QPalette,
    token: PromptProjectionToken,
    *,
    selected: bool = False,
) -> QColor:
    """Return the decorative paren color for one emphasis token."""

    if selected:
        return QColor(palette.color(QPalette.ColorRole.HighlightedText))
    if token.decoration_accented:
        return QColor(themeColor())
    return QColor(palette.color(QPalette.ColorRole.Text))


def _emphasis_weight_color(palette: QPalette, *, selected: bool = False) -> QColor:
    """Return the superscript weight color, which should stay on the normal text path."""

    if selected:
        return QColor(palette.color(QPalette.ColorRole.HighlightedText))
    return QColor(palette.color(QPalette.ColorRole.Text))


def _emphasis_edit_text(token: PromptProjectionToken, run: PromptProjectionRun) -> str:
    """Return the weight text currently rendered for one emphasis suffix run."""

    return (
        token.editing_value_text
        if token.editing_value_text is not None
        else run.display_text
    )


def paint_exact_weight_edit_buffer(
    painter: QPainter,
    *,
    token: PromptProjectionToken,
    weight_rect: QRectF,
    text: str,
    metrics: QFontMetricsF,
    palette: QPalette,
) -> None:
    """Paint the shared projection-owned exact-edit weight buffer."""

    highlight_rect = QRectF(weight_rect)
    if token.editing_select_all:
        painter.fillRect(highlight_rect, palette.color(QPalette.ColorRole.Highlight))
    painter.setPen(
        palette.color(
            QPalette.ColorRole.HighlightedText
            if token.editing_select_all
            else QPalette.ColorRole.Text
        )
    )
    painter.drawText(
        QPointF(
            weight_rect.left(),
            weight_rect.top() + metrics.ascent(),
        ),
        text,
    )
    if token.editing_select_all:
        return
    caret_index = 0 if token.editing_caret_index is None else token.editing_caret_index
    caret_x = weight_rect.left() + metrics.horizontalAdvance(text[:caret_index])
    painter.fillRect(
        QRectF(
            caret_x,
            weight_rect.top(),
            1.0,
            weight_rect.height(),
        ),
        palette.color(QPalette.ColorRole.Text),
    )


class PromptEmphasisPrefixRenderer:
    """Render the decorative leading parenthesis for one emphasis token."""

    renderer_key = _EMPHASIS_PREFIX_RENDERER_KEY

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Measure the decorative parenthesis plus the gap before content."""

        _ = (run, token)
        decoration_metrics = _emphasis_decoration_metrics(base_font)
        return QSizeF(
            decoration_metrics.parenthesis_width("(") + decoration_metrics.content_gap,
            max(
                projection_text_line_height(base_font),
                decoration_metrics.parenthesis_metrics.height(),
            ),
        )

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
        """Paint the decorative leading parenthesis inside the supplied rect."""

        _ = (run, token)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        decoration_metrics = _emphasis_decoration_metrics(base_font)
        text_color = _emphasis_parenthesis_color(palette, token, selected=selected)
        painter.setFont(decoration_metrics.parenthesis_font)
        painter.setPen(text_color)
        painter.drawText(
            QPointF(
                rect.left(),
                _centered_text_baseline(rect, decoration_metrics.parenthesis_metrics),
            ),
            "(",
        )
        painter.restore()

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return no anchor because the leading decoration is presentation-only."""

        _ = (run, token, rect, base_font)
        return None

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve leading-decoration clicks to the token leading-edge caret."""

        _ = (run, rect, position, base_font)
        return PromptProjectionCaretState(
            source_position=token.source_start,
            placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
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
        """Return the decorative rect when the outer token range is selected."""

        _ = (run, base_font)
        if selection_start <= token.source_start and token.source_end <= selection_end:
            return (QRectF(rect),)
        return ()


class PromptEmphasisSuffixRenderer:
    """Render the decorative closing parenthesis plus the raised weight label."""

    renderer_key = _EMPHASIS_SUFFIX_RENDERER_KEY

    def _weight_text_left(
        self,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> float:
        """Return the left edge used to paint the emphasis weight text."""

        decoration_metrics = _emphasis_decoration_metrics(base_font)
        return (
            rect.left()
            + decoration_metrics.content_gap
            + decoration_metrics.parenthesis_width(")")
            + decoration_metrics.weight_gap
        )

    def _actual_weight_text_width(
        self,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> float:
        """Return the width of the exact text currently painted for the weight."""

        decoration_metrics = _emphasis_decoration_metrics(base_font)
        return decoration_metrics.weight_metrics.horizontalAdvance(
            _emphasis_edit_text(token, run)
        )

    def _resolved_weight_slot_width(
        self,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> float:
        """Return the projection-owned width floor for the visible weight slot."""

        actual_width = self._actual_weight_text_width(
            token,
            run,
            base_font=base_font,
        )
        if token.editing_value_text is None:
            return actual_width
        slot_width = token.editing_slot_width
        if slot_width is None:
            return actual_width
        return max(actual_width, slot_width)

    def _weight_text_rect(
        self,
        rect: QRectF,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the projection-owned slot used to paint the superscript weight text."""

        if token.editing_value_text is None and not token.value_text:
            return None
        decoration_metrics = _emphasis_decoration_metrics(base_font)
        baseline_y = rect.top() + max(
            decoration_metrics.weight_metrics.ascent() - 1.0,
            rect.height() * 0.42,
        )
        return QRectF(
            self._weight_text_left(rect, base_font=base_font),
            baseline_y - decoration_metrics.weight_metrics.ascent(),
            self._resolved_weight_slot_width(
                token,
                run,
                base_font=base_font,
            ),
            decoration_metrics.weight_metrics.height(),
        )

    def _weight_anchor_rect(
        self,
        rect: QRectF,
        token: PromptProjectionToken,
        run: PromptProjectionRun,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return a stable numeric slot so emphasis controls do not jitter between values."""

        weight_rect = self._weight_text_rect(
            rect,
            token,
            run,
            base_font=base_font,
        )
        if weight_rect is None:
            return None
        stable_text = "".join(
            "8" if character.isdigit() else character for character in run.display_text
        )
        decoration_metrics = _emphasis_decoration_metrics(base_font)
        stable_width = decoration_metrics.weight_metrics.horizontalAdvance(stable_text)
        return QRectF(
            weight_rect.left(),
            weight_rect.top(),
            max(
                stable_width,
                self._resolved_weight_slot_width(
                    token,
                    run,
                    base_font=base_font,
                ),
            ),
            weight_rect.height(),
        )

    def weight_text_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the projection-owned slot rect for one emphasis weight label."""

        _ = token
        return self._weight_text_rect(
            rect,
            token,
            run,
            base_font=base_font,
        )

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Measure the closing parenthesis plus the raised weight label."""

        _ = token
        decoration_metrics = _emphasis_decoration_metrics(base_font)
        width = decoration_metrics.content_gap + decoration_metrics.parenthesis_width(
            ")"
        )
        if token.editing_value_text is not None or run.display_text:
            width += decoration_metrics.weight_gap + self._resolved_weight_slot_width(
                token,
                run,
                base_font=base_font,
            )
        return QSizeF(
            width,
            max(
                projection_text_line_height(base_font),
                decoration_metrics.parenthesis_metrics.height(),
                decoration_metrics.weight_metrics.height() + 4.0,
            ),
        )

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
        """Paint the decorative closing parenthesis and raised weight label."""

        _ = token
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        text_color = _emphasis_parenthesis_color(palette, token, selected=selected)

        decoration_metrics = _emphasis_decoration_metrics(base_font)
        painter.setFont(decoration_metrics.parenthesis_font)
        painter.setPen(text_color)
        painter.drawText(
            QPointF(
                rect.left() + decoration_metrics.content_gap,
                _centered_text_baseline(
                    rect,
                    decoration_metrics.parenthesis_metrics,
                ),
            ),
            ")",
        )

        weight_text = _emphasis_edit_text(token, run)
        if token.editing_value_text is not None or weight_text:
            weight_rect = self._weight_text_rect(
                rect,
                token,
                run,
                base_font=base_font,
            )
            assert weight_rect is not None
            painter.setFont(decoration_metrics.weight_font)
            if token.editing_value_text is None:
                painter.setPen(_emphasis_weight_color(palette, selected=selected))
                painter.drawText(
                    QPointF(
                        weight_rect.left(),
                        weight_rect.top() + decoration_metrics.weight_metrics.ascent(),
                    ),
                    weight_text,
                )
            else:
                self._paint_exact_weight_edit(
                    painter,
                    token=token,
                    weight_rect=weight_rect,
                    text=weight_text,
                    metrics=decoration_metrics.weight_metrics,
                    palette=palette,
                )
        painter.restore()

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the painted weight-label rect used for emphasis control anchoring."""

        _ = token
        weight_rect = self._weight_anchor_rect(
            rect,
            token,
            run,
            base_font=base_font,
        )
        if weight_rect is None:
            return None
        return weight_rect

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve suffix-decoration clicks to the content-end or trailing-edge caret."""

        assert token.content_end is not None
        if token.editing_value_text is None and not run.display_text:
            return PromptProjectionCaretState(
                source_position=token.source_end,
                placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                token_id=token.token_id,
            )
        weight_rect = self._weight_text_rect(
            rect,
            token,
            run,
            base_font=base_font,
        )
        assert weight_rect is not None
        if position.x() >= weight_rect.center().x():
            return PromptProjectionCaretState(
                source_position=token.source_end,
                placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                token_id=token.token_id,
            )
        return PromptProjectionCaretState(
            source_position=token.content_end,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_id=token.token_id,
            token_slot=len(token.display_text),
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
        """Return the decorative rect when the outer token range is selected."""

        _ = (run, base_font)
        if selection_start <= token.source_start and token.source_end <= selection_end:
            return (QRectF(rect),)
        return ()

    def _paint_exact_weight_edit(
        self,
        painter: QPainter,
        *,
        token: PromptProjectionToken,
        weight_rect: QRectF,
        text: str,
        metrics: QFontMetricsF,
        palette: QPalette,
    ) -> None:
        """Paint the projection-owned exact-edit weight buffer for one emphasis token."""

        paint_exact_weight_edit_buffer(
            painter,
            token=token,
            weight_rect=weight_rect,
            text=text,
            metrics=metrics,
            palette=palette,
        )


class PromptWildcardInlineObjectRenderer:
    """Render one wildcard placeholder as inline decorated prompt syntax."""

    renderer_key = _WILDCARD_CHIP_RENDERER_KEY
    _BRACE_GAP = 1.0
    _TAG_GAP = 0.0

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Measure the inline wildcard syntax plus optional italic tag text."""

        metrics = QFontMetricsF(base_font)
        brace_metrics = QFontMetricsF(self._brace_font(base_font))
        tag_metrics = QFontMetricsF(self._tag_font(base_font))
        tag_width = 0.0
        if token.wildcard_display_tag:
            tag_width = self._TAG_GAP + tag_metrics.horizontalAdvance(
                token.wildcard_display_tag
            )
        return QSizeF(
            brace_metrics.horizontalAdvance("{")
            + self._BRACE_GAP
            + metrics.horizontalAdvance(run.display_text)
            + self._BRACE_GAP
            + brace_metrics.horizontalAdvance("}")
            + tag_width,
            max(metrics.height(), tag_metrics.height()),
        )

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
        """Paint wildcard braces, body text, and optional inline italic group tag."""

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body_color = QColor(
            palette.color(
                QPalette.ColorRole.HighlightedText
                if selected
                else QPalette.ColorRole.Text
            )
        )
        accent_color = (
            QColor(palette.color(QPalette.ColorRole.HighlightedText))
            if selected
            else self._accent_color_for_token(token, palette=palette)
        )
        brace_font = self._brace_font(base_font)
        tag_font = self._tag_font(base_font)
        metrics = QFontMetricsF(base_font)
        brace_metrics = QFontMetricsF(brace_font)
        baseline = (
            rect.top()
            + max(0.0, (rect.height() - metrics.height()) / 2.0)
            + metrics.ascent()
        )
        x = rect.left()

        painter.setFont(brace_font)
        painter.setPen(accent_color)
        painter.drawText(QPointF(x, baseline), "{")
        x += brace_metrics.horizontalAdvance("{") + self._BRACE_GAP

        painter.setFont(base_font)
        painter.setPen(body_color)
        painter.drawText(QPointF(x, baseline), run.display_text)
        x += metrics.horizontalAdvance(run.display_text) + self._BRACE_GAP

        painter.setFont(brace_font)
        painter.setPen(accent_color)
        painter.drawText(QPointF(x, baseline), "}")
        x += brace_metrics.horizontalAdvance("}")

        if token.wildcard_display_tag:
            x += self._TAG_GAP
            painter.setFont(tag_font)
            painter.setPen(accent_color)
            painter.drawText(
                QPointF(x, baseline),
                token.wildcard_display_tag,
            )

        painter.restore()

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the tag rect used for numeric wildcard controls."""

        return self.weight_text_rect(run, token, rect, base_font=base_font)

    def weight_text_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the viewport-local tag rect when the wildcard tag is numeric."""

        if not token.wildcard_can_step_tag or not token.wildcard_display_tag:
            return None
        return self._tag_text_rect(run, token, rect, base_font=base_font)

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve one wildcard-local point into its leading or trailing edge."""

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
        """Return the whole wildcard syntax rect whenever selection overlaps it."""

        _ = (run, base_font)
        if token.source_start < selection_end and selection_start < token.source_end:
            return (QRectF(rect),)
        return ()

    def _accent_color_for_token(
        self,
        token: PromptProjectionToken,
        *,
        palette: QPalette,
    ) -> QColor:
        """Return the brace and tag accent color for one wildcard token."""

        if not token.decoration_accented:
            return QColor(palette.color(QPalette.ColorRole.Text))

        color = QColor(themeColor())
        color.setAlpha(204 if isDarkTheme() else 182)
        return color

    def _brace_font(self, base_font: QFont) -> QFont:
        """Return the compact font used for wildcard brace decoration."""

        brace_font = QFont(base_font)
        if base_font.pointSizeF() > 0:
            brace_font.setPointSizeF(max(7.5, base_font.pointSizeF() - 1.0))
        elif base_font.pixelSize() > 0:
            brace_font.setPixelSize(max(8, base_font.pixelSize() - 1))
        brace_font.setWeight(QFont.Weight.DemiBold)
        return brace_font

    def _tag_font(self, base_font: QFont) -> QFont:
        """Return the inline italic font used for wildcard group tags."""

        tag_font = QFont(base_font)
        if base_font.pointSizeF() > 0:
            tag_font.setPointSizeF(max(7.0, base_font.pointSizeF() - 2.0))
        elif base_font.pixelSize() > 0:
            tag_font.setPixelSize(max(8, base_font.pixelSize() - 3))
        tag_font.setItalic(True)
        tag_font.setWeight(QFont.Weight.Normal)
        return tag_font

    def _tag_text_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF:
        """Return the measured rect occupied by one inline wildcard tag."""

        metrics = QFontMetricsF(base_font)
        brace_metrics = QFontMetricsF(self._brace_font(base_font))
        tag_font = self._tag_font(base_font)
        tag_metrics = QFontMetricsF(tag_font)
        baseline = (
            rect.top()
            + max(0.0, (rect.height() - metrics.height()) / 2.0)
            + metrics.ascent()
        )
        x = (
            rect.left()
            + brace_metrics.horizontalAdvance("{")
            + self._BRACE_GAP
            + metrics.horizontalAdvance(run.display_text)
            + self._BRACE_GAP
            + brace_metrics.horizontalAdvance("}")
            + self._TAG_GAP
        )
        tag_baseline = baseline
        tag_width = tag_metrics.horizontalAdvance(token.wildcard_display_tag or "")
        return QRectF(
            x,
            tag_baseline - tag_metrics.ascent(),
            tag_width,
            tag_metrics.height(),
        )


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

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            fill, border, accent = self._colors_for_token(token)
            path = self._chevron_path(rect)
            banner = (
                None
                if self._suppress_banners or not token.thumbnail_variants
                else self._banner_for_token(painter, token, rect)
            )
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
                QPointF(text_left, _centered_text_baseline(rect, metrics)),
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
        device_pixel_ratio = _painter_device_pixel_ratio(painter)
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
                QPointF(text_rect.left(), _centered_text_baseline(text_rect, metrics)),
                text,
                color=color,
            )
            return
        self._paint_edit_backing(painter, rect, banner_backed=banner_backed)
        paint_exact_weight_edit_buffer(
            painter,
            token=token,
            weight_rect=text_rect,
            text=text,
            metrics=metrics,
            palette=_banner_edit_palette(palette) if banner_backed else palette,
        )

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

        return _emphasis_weight_font(base_font)

    def _status_font(self, base_font: QFont) -> QFont:
        """Return the font used for compact LoRA status text."""

        status_font = QFont(base_font)
        if base_font.pointSizeF() > 0:
            status_font.setPointSizeF(max(7.0, base_font.pointSizeF() - 2.0))
        elif base_font.pixelSize() > 0:
            status_font.setPixelSize(max(8, base_font.pixelSize() - 2))
        return status_font


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


def _painter_device_pixel_ratio(painter: QPainter) -> float:
    """Return the active paint device pixel ratio for pixmap requests."""

    device = painter.device()
    if device is None:
        return 1.0
    return max(1.0, float(device.devicePixelRatioF()))


def _banner_edit_palette(palette: QPalette) -> QPalette:
    """Return a palette that keeps exact weight edits legible on banner art."""

    adjusted = QPalette(palette)
    adjusted.setColor(QPalette.ColorRole.Text, QColor(Qt.GlobalColor.white))
    adjusted.setColor(QPalette.ColorRole.HighlightedText, QColor(Qt.GlobalColor.white))
    adjusted.setColor(QPalette.ColorRole.Highlight, QColor(255, 255, 255, 70))
    return adjusted


@dataclass(frozen=True, slots=True)
class PromptProjectionInlineObjectRendererRegistry:
    """Resolve the inline-object renderer registered for one renderer key."""

    renderers: tuple[PromptRichInlineObjectRenderer, ...]

    def renderer_for(
        self,
        renderer_key: str | None,
    ) -> PromptRichInlineObjectRenderer | None:
        """Return the renderer registered for the requested key."""

        if renderer_key is None:
            return None
        for renderer in self.renderers:
            if renderer.renderer_key == renderer_key:
                return renderer
        return None


__all__ = [
    "PromptEmphasisPrefixRenderer",
    "PromptEmphasisSuffixRenderer",
    "PromptLoraInlineObjectRenderer",
    "PromptProjectionInlineObjectRendererRegistry",
    "PromptRichInlineObjectRenderer",
    "PromptWildcardInlineObjectRenderer",
    "emphasis_weight_font",
    "paint_exact_weight_edit_buffer",
]
