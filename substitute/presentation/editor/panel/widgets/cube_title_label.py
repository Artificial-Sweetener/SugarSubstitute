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

"""Render editor cube titles with suffix-aware elision."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from typing import cast

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import SubtitleLabel  # type: ignore[import-untyped]

from substitute.presentation.cubes.cube_model_pill import CubeModelPillPainter

_BYPASSED_SUFFIX = " (bypassed)"


class CubeTitleLabel(SubtitleLabel):  # type: ignore[misc]
    """Display an editor cube title while preserving bypass context when elided."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create a subtitle label that can shrink within the editor header."""

        super().__init__(parent)
        self._full_text = ""
        self._target_model = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setTitleText(text)

    def setText(self, text: str) -> None:
        """Store the full title and repaint with suffix-aware elision."""

        self.setTitleText(text)

    def setTitleText(self, text: str) -> None:
        """Set the raw cube title used by custom painting and tooltips."""

        self._full_text = text
        super().setText(text)
        set_fluent_tooltip_text(self, text)
        self.updateGeometry()
        self.update()

    def setTargetModel(self, target_model: str) -> None:
        """Refresh the canonical model independently from the editable title."""

        self._target_model = target_model.strip()
        self.updateGeometry()
        self.update()

    def targetModel(self) -> str:
        """Return the canonical model painted by this cube identity header."""

        return self._target_model

    def sizeHint(self) -> QSize:
        """Return a shrinkable preferred size for header layout negotiation."""

        hint = super().sizeHint()
        pill_metrics = CubeModelPillPainter.title_metrics(self.font())
        pill_font_metrics = QFontMetrics(pill_metrics.font)
        identity_width = (
            pill_font_metrics.horizontalAdvance(self._target_model)
            + (pill_metrics.horizontal_padding * 2)
            + pill_metrics.gap
            if self._target_model
            else 0
        )
        pill_height = pill_metrics.height if self._target_model else 0
        return QSize(
            min(hint.width() + identity_width, 420),
            max(hint.height(), pill_height),
        )

    def minimumSizeHint(self) -> QSize:
        """Return the smallest useful title size while keeping layout stable."""

        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def paintEvent(self, event: object) -> None:
        """Draw the title elided to the available label rectangle."""

        _ = event
        painter = QPainter(self)
        painter.setFont(self.font())
        text_rect = QRectF(self.rect())
        if self._target_model:
            pill_rect = CubeModelPillPainter.draw_standalone(
                painter,
                bounds=text_rect,
                text=self._target_model,
            )
            if pill_rect is not None:
                gap = CubeModelPillPainter.title_metrics(self.font()).gap
                text_rect.setLeft(pill_rect.right() + gap)
        color = self.palette().color(self.foregroundRole())
        painter.setPen(QPen(color))
        text = self._elided_text_for_width(int(text_rect.width()))
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), text)

    def _elided_text_for_width(self, width: int) -> str:
        """Return title text elided while preserving the bypass suffix."""

        metrics = self.fontMetrics()
        if width <= 0:
            return ""
        text = self._full_text
        if metrics.horizontalAdvance(text) <= width:
            return text
        if not text.endswith(_BYPASSED_SUFFIX):
            return cast(
                str,
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, width),
            )

        title = text[: -len(_BYPASSED_SUFFIX)]
        suffix_width = metrics.horizontalAdvance(_BYPASSED_SUFFIX)
        if suffix_width >= width:
            return cast(
                str,
                metrics.elidedText(
                    _BYPASSED_SUFFIX.strip(),
                    Qt.TextElideMode.ElideRight,
                    width,
                ),
            )
        title_width = max(0, width - suffix_width)
        return (
            cast(
                str,
                metrics.elidedText(
                    title,
                    Qt.TextElideMode.ElideRight,
                    title_width,
                ),
            )
            + _BYPASSED_SUFFIX
        )


__all__ = ["CubeTitleLabel"]
