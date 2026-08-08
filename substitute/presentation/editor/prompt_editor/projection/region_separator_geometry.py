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

"""Own authored regional-separator label and inline-edit geometry."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF

from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetrics,
)
from substitute.presentation.editor.prompt_editor.projection.region_chrome_state import (
    PromptRegionChromeEditTarget,
    PromptRegionChromeLabel,
)

_LABEL_RULE_GAP = 8.0
_INLINE_EDITOR_HORIZONTAL_PADDING = 12.0


def prepare_separator_paint_geometry(
    *,
    region_index: int,
    separator_name: str | None,
    divider_y: float,
    row_height: float,
    metrics: PromptProjectionMetrics,
    base_font: QFont,
    color: QColor,
    plain_divider: QLineF,
) -> tuple[
    tuple[QLineF, ...],
    PromptRegionChromeLabel | None,
    PromptRegionChromeEditTarget,
]:
    """Prepare a plain rule or centered authored title from layout metrics."""

    label_font = _separator_label_font(base_font)
    font_metrics = QFontMetricsF(label_font)
    rule_length = plain_divider.length()
    content_center = metrics.content_left + metrics.content_width / 2.0
    maximum_title_width = max(
        1.0,
        metrics.content_width - (2.0 * (rule_length + _LABEL_RULE_GAP)),
    )
    maximum_editor_width = max(
        1.0,
        min(
            metrics.content_width,
            maximum_title_width + _INLINE_EDITOR_HORIZONTAL_PADDING,
        ),
    )
    if separator_name is None:
        separator_lines = (plain_divider,)
        return (
            separator_lines,
            None,
            _edit_target(
                region_index=region_index,
                center=QPointF(content_center, divider_y),
                row_height=row_height,
                text="",
                maximum_width=maximum_editor_width,
                rule_length=rule_length,
                separator_line_count=len(separator_lines),
                color=color,
                font=label_font,
            ),
        )

    label_text = font_metrics.elidedText(
        separator_name,
        Qt.TextElideMode.ElideRight,
        int(maximum_title_width),
    )
    label_width = font_metrics.horizontalAdvance(label_text)
    label_left = content_center - label_width / 2.0
    lines = framing_rule_lines(
        center=QPointF(content_center, divider_y),
        title_width=label_width,
        rule_length=rule_length,
    )
    baseline_y = divider_y + (font_metrics.ascent() - font_metrics.descent()) / 2.0
    label = PromptRegionChromeLabel(
        region_index=region_index,
        text=label_text,
        baseline=QPointF(label_left, baseline_y),
        rect=QRectF(
            label_left,
            divider_y - row_height / 2.0,
            label_width,
            row_height,
        ),
        color=QColor(color),
        font=label_font,
    )
    return (
        lines,
        label,
        _edit_target(
            region_index=region_index,
            center=QPointF(content_center, divider_y),
            row_height=row_height,
            text=separator_name,
            maximum_width=maximum_editor_width,
            rule_length=rule_length,
            separator_line_count=len(lines),
            color=color,
            font=label_font,
        ),
    )


def prepare_separator_draft_geometry(
    target: PromptRegionChromeEditTarget,
    draft: str,
) -> tuple[PromptRegionChromeEditTarget, tuple[QLineF, QLineF]]:
    """Derive editor and fixed-rule geometry directly from authored draft text."""

    editor_width = _inline_editor_width(
        font=target.font,
        text=draft,
        maximum_width=target.maximum_width,
    )
    title_width = _inline_title_width(
        font=target.font,
        text=draft,
        maximum_editor_width=target.maximum_width,
    )
    separator_lines = framing_rule_lines(
        center=target.center,
        title_width=title_width,
        rule_length=target.rule_length,
    )
    return (
        PromptRegionChromeEditTarget(
            region_index=target.region_index,
            center=target.center,
            row_height=target.row_height,
            width=editor_width,
            maximum_width=target.maximum_width,
            rule_length=target.rule_length,
            separator_line_count=len(separator_lines),
            color=target.color,
            font=target.font,
        ),
        separator_lines,
    )


def framing_rule_lines(
    *,
    center: QPointF,
    title_width: float,
    rule_length: float,
) -> tuple[QLineF, QLineF]:
    """Frame one title with two rules of the plain-divider design length."""

    title_left = center.x() - title_width / 2.0
    title_right = center.x() + title_width / 2.0
    return (
        QLineF(
            title_left - _LABEL_RULE_GAP - rule_length,
            center.y(),
            title_left - _LABEL_RULE_GAP,
            center.y(),
        ),
        QLineF(
            title_right + _LABEL_RULE_GAP,
            center.y(),
            title_right + _LABEL_RULE_GAP + rule_length,
            center.y(),
        ),
    )


def _edit_target(
    *,
    region_index: int,
    center: QPointF,
    row_height: float,
    text: str,
    maximum_width: float,
    rule_length: float,
    separator_line_count: int,
    color: QColor,
    font: QFont,
) -> PromptRegionChromeEditTarget:
    """Build one immutable edit target from separator-owned measurements."""

    return PromptRegionChromeEditTarget(
        region_index=region_index,
        center=center,
        row_height=row_height,
        width=_inline_editor_width(
            font=font,
            text=text,
            maximum_width=maximum_width,
        ),
        maximum_width=maximum_width,
        rule_length=rule_length,
        separator_line_count=separator_line_count,
        color=QColor(color),
        font=font,
    )


def _inline_editor_width(*, font: QFont, text: str, maximum_width: float) -> float:
    """Measure draft text once with fixed cursor padding and a hard upper bound."""

    title_width = _inline_title_width(
        font=font,
        text=text,
        maximum_editor_width=maximum_width,
    )
    return max(
        1.0,
        min(maximum_width, title_width + _INLINE_EDITOR_HORIZONTAL_PADDING),
    )


def _inline_title_width(
    *,
    font: QFont,
    text: str,
    maximum_editor_width: float,
) -> float:
    """Measure the visible draft independently from its cursor-bearing editor."""

    maximum_title_width = max(
        0.0,
        maximum_editor_width - _INLINE_EDITOR_HORIZONTAL_PADDING,
    )
    return min(maximum_title_width, QFontMetricsF(font).horizontalAdvance(text))


def _separator_label_font(base_font: QFont) -> QFont:
    """Return the normal editor font with bold title emphasis."""

    label_font = QFont(base_font)
    label_font.setWeight(QFont.Weight.Bold)
    return label_font


__all__ = [
    "framing_rule_lines",
    "prepare_separator_draft_geometry",
    "prepare_separator_paint_geometry",
]
