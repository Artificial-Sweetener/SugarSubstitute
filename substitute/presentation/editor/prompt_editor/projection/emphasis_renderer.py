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

"""Render emphasis decorations and exact prompt weights."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPalette
from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]

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

from .inline_renderer_typography import centered_text_baseline, inline_weight_font
from .metrics import projection_text_line_height

_EMPHASIS_PREFIX_RENDERER_KEY = "emphasis_prefix"
_EMPHASIS_SUFFIX_RENDERER_KEY = "emphasis_suffix"
_EMPHASIS_DECORATION_CONTENT_GAP = 2.5
_EMPHASIS_WEIGHT_GAP = 1.0


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


def _emphasis_decoration_metrics(base_font: QFont) -> _EmphasisDecorationMetrics:
    """Return one shared metrics bundle so both emphasis parens stay symmetrical."""

    return _cached_emphasis_decoration_metrics(base_font.toString())


@lru_cache(maxsize=16)
def _cached_emphasis_decoration_metrics(
    base_font_key: str,
) -> _EmphasisDecorationMetrics:
    """Memoize immutable decoration metrics by complete Qt font identity."""

    base_font = QFont()
    if not base_font.fromString(base_font_key):
        raise ValueError("Invalid serialized emphasis base font.")
    parenthesis_font = _emphasis_parenthesis_font(base_font)
    weight_font = inline_weight_font(base_font)
    return _EmphasisDecorationMetrics(
        parenthesis_font=parenthesis_font,
        parenthesis_metrics=QFontMetricsF(parenthesis_font),
        weight_font=weight_font,
        weight_metrics=QFontMetricsF(weight_font),
        content_gap=_EMPHASIS_DECORATION_CONTENT_GAP,
        weight_gap=_EMPHASIS_WEIGHT_GAP,
    )


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
                centered_text_baseline(rect, decoration_metrics.parenthesis_metrics),
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

    def weight_edit_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Use the painted emphasis glyph slot for native exact editing."""

        return self._weight_text_rect(rect, token, run, base_font=base_font)

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
                centered_text_baseline(
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
