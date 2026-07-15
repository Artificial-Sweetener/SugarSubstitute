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

"""Render prepared prompt token-weight controls without owning editor policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPaintEvent,
    QPainter,
    QPalette,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class PromptTokenWeightControlPaintState:
    """Describe the prepared local rects and feedback for visible controls."""

    increase_rect: QRectF | None = None
    decrease_rect: QRectF | None = None
    hovered_control: Literal["increase", "decrease"] | None = None
    pressed_control: Literal["increase", "decrease"] | None = None


@dataclass(frozen=True, slots=True)
class PromptTokenWeightPreviewPaintState:
    """Describe one prepared pointer-owned weight preview label."""

    text: str
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptTokenWeightViewRenderState:
    """Describe all prepared token-weight chrome needed for one paint pass."""

    controls: PromptTokenWeightControlPaintState | None = None
    preview: PromptTokenWeightPreviewPaintState | None = None


class PromptTokenWeightView(QWidget):
    """Paint token-weight controls and preview labels from prepared state."""

    def __init__(self, parent: QWidget, *, surface_widget: QWidget) -> None:
        """Create the passive view bound to the prompt surface palette."""

        super().__init__(parent)
        self._surface_widget = surface_widget
        self._render_state = PromptTokenWeightViewRenderState()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_render_state(self, state: PromptTokenWeightViewRenderState) -> None:
        """Replace the prepared paint state and schedule a repaint."""

        self._render_state = state
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint controls and feedback from prepared local geometry."""

        state = self._render_state
        if state.controls is None and state.preview is None:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setClipRect(event.rect())
            if state.controls is not None:
                self._paint_controls(painter, state.controls)
            if state.preview is not None:
                self._paint_weight_preview(painter, state.preview)
        finally:
            painter.end()

    def _paint_controls(
        self,
        painter: QPainter,
        state: PromptTokenWeightControlPaintState,
    ) -> None:
        """Paint prepared increase and decrease controls."""

        if state.increase_rect is not None:
            self._paint_control(
                painter,
                rect=state.increase_rect,
                direction="up",
                is_hovered=state.hovered_control == "increase",
                is_pressed=state.pressed_control == "increase",
            )
        if state.decrease_rect is not None:
            self._paint_control(
                painter,
                rect=state.decrease_rect,
                direction="down",
                is_hovered=state.hovered_control == "decrease",
                is_pressed=state.pressed_control == "decrease",
            )

    def _paint_control(
        self,
        painter: QPainter,
        *,
        rect: QRectF,
        direction: Literal["up", "down"],
        is_hovered: bool,
        is_pressed: bool,
    ) -> None:
        """Paint one tiny arrow control with subtle feedback."""

        fill = QColor(Qt.GlobalColor.transparent)
        if is_pressed:
            fill = _theme_contrast_fill(28)
        elif is_hovered:
            fill = _theme_contrast_fill(18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 4.0, 4.0)

        center = rect.center()
        horizontal_inset = max(2.5, rect.width() * 0.26)
        vertical_inset = triangle_vertical_inset(rect.height())
        if direction == "up":
            triangle = QPolygonF(
                [
                    QPointF(center.x(), rect.top() + vertical_inset),
                    QPointF(
                        rect.right() - horizontal_inset,
                        rect.bottom() - vertical_inset,
                    ),
                    QPointF(
                        rect.left() + horizontal_inset,
                        rect.bottom() - vertical_inset,
                    ),
                ]
            )
        else:
            triangle = QPolygonF(
                [
                    QPointF(
                        rect.left() + horizontal_inset,
                        rect.top() + vertical_inset,
                    ),
                    QPointF(
                        rect.right() - horizontal_inset,
                        rect.top() + vertical_inset,
                    ),
                    QPointF(center.x(), rect.bottom() - vertical_inset),
                ]
            )
        painter.setBrush(surface_text_color(self._surface_widget))
        painter.drawPolygon(triangle)

    def _paint_weight_preview(
        self,
        painter: QPainter,
        state: PromptTokenWeightPreviewPaintState,
    ) -> None:
        """Paint one short-lived floating weight label above the pointer."""

        text_color = surface_text_color(self._surface_widget)
        shadow_color = weight_preview_shadow_color()
        painter.save()
        painter.setFont(self._weight_preview_font())
        painter.setPen(shadow_color)
        for dx, dy in ((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (-1.0, 1.0)):
            painter.drawText(
                state.rect.translated(dx, dy),
                Qt.AlignmentFlag.AlignCenter,
                state.text,
            )
        painter.setPen(text_color)
        painter.drawText(state.rect, Qt.AlignmentFlag.AlignCenter, state.text)
        painter.restore()

    def _weight_preview_font(self) -> QFont:
        """Return the font used by the floating weight preview label."""

        font = QFont(self.font())
        if font.pointSizeF() > 0:
            font.setPointSizeF(max(8.0, font.pointSizeF() - 1.0))
        else:
            font.setPixelSize(max(12, font.pixelSize() - 1))
        return font


def triangle_vertical_inset(control_height: float) -> float:
    """Return the vertical inset applied to one painted triangle."""

    return max(2.0, control_height * 0.30)


def surface_text_color(surface_widget: QWidget) -> QColor:
    """Return the prompt surface text color used by overlay glyphs."""

    return QColor(surface_widget.palette().color(QPalette.ColorRole.Text))


def weight_preview_shadow_color() -> QColor:
    """Return the floating weight preview halo color for the active theme."""

    if isDarkTheme():
        return QColor(0, 0, 0, 216)
    return QColor(255, 255, 255, 230)


def _theme_contrast_fill(alpha: int) -> QColor:
    """Return a subtle same-polarity hover fill for the active theme."""

    channel = 255 if isDarkTheme() else 0
    return QColor(channel, channel, channel, alpha)


__all__ = [
    "PromptTokenWeightControlPaintState",
    "PromptTokenWeightPreviewPaintState",
    "PromptTokenWeightView",
    "PromptTokenWeightViewRenderState",
    "surface_text_color",
    "triangle_vertical_inset",
    "weight_preview_shadow_color",
]
