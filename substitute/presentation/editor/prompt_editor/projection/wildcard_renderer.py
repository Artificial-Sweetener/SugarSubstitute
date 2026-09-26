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

"""Render wildcard decorations around source-backed editable content."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPalette
from qfluentwidgets.common.style_sheet import isDarkTheme, themeColor  # type: ignore[import-untyped]

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunRole,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.semantic_colors import semantic_error_color

_WILDCARD_CHIP_RENDERER_KEY = "wildcard_chip"


class PromptWildcardInlineObjectRenderer:
    """Render the braces and optional tag surrounding wildcard content."""

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
        """Measure one wildcard decoration without duplicating body width."""

        metrics = QFontMetricsF(base_font)
        brace_metrics = QFontMetricsF(self._brace_font(base_font))
        tag_metrics = QFontMetricsF(self._tag_font(base_font))
        if run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
            return QSizeF(
                brace_metrics.horizontalAdvance("{") + self._BRACE_GAP,
                metrics.height(),
            )
        tag_width = 0.0
        if token.wildcard_display_tag:
            tag_width = self._TAG_GAP + tag_metrics.horizontalAdvance(
                token.wildcard_display_tag
            )
        return QSizeF(
            self._BRACE_GAP + brace_metrics.horizontalAdvance("}") + tag_width,
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
        """Paint the source shell and display-only group tag around body text."""

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
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
        if run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
            painter.drawText(QPointF(x, baseline), "{")
            painter.restore()
            return

        x += self._BRACE_GAP
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

        if run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
            return None
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

        if (
            run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION
            or not token.wildcard_can_step_tag
            or not token.wildcard_display_tag
        ):
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
        """Map braces and tag clicks to adjacent editable caret boundaries."""

        _ = base_font
        if run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
            return PromptProjectionCaretState(
                source_position=token.source_start,
                placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                token_id=token.token_id,
            )
        assert token.content_end is not None
        placement = (
            PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
            if position.x() >= rect.center().x()
            else PromptProjectionCaretPlacement.TOKEN_CONTENT
        )
        return PromptProjectionCaretState(
            source_position=(
                token.source_end
                if placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                else token.content_end
            ),
            placement=placement,
            token_id=token.token_id,
            token_slot=(
                token.content_end - token.content_start
                if placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
                and token.content_start is not None
                and token.content_end is not None
                else None
            ),
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
        """Return decorated selection only when its outer shell is selected."""

        _ = (run, base_font)
        if selection_start <= token.source_start and token.source_end <= selection_end:
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
            if not token.exists and not token.wildcard_resolution_pending:
                return semantic_error_color()
            return QColor(palette.color(QPalette.ColorRole.Text))

        if not token.exists and not token.wildcard_resolution_pending:
            return semantic_error_color()

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
