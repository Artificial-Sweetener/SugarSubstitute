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

"""Render shared cube-stack card visuals for live and draft cube surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from typing import TypeAlias

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIconBase,
    drawIcon,
)
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.cubes.cube_alias_text_layout import (
    layout_cube_alias_text,
)
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_TEXT_RESERVE,
    CUBE_ITEM_ICON_INSET_EXPANDED,
    CUBE_ITEM_ICON_SIZE_COMPACT,
    CUBE_ITEM_ICON_SIZE_EXPANDED,
    CUBE_ITEM_ICON_X,
    CUBE_ITEM_TEXT_BLOCK_HEIGHT,
    CUBE_ITEM_TEXT_GAP_EXPANDED,
    CUBE_ITEM_TEXT_PRIMARY_HEIGHT,
    CUBE_ITEM_TEXT_ROW_OVERLAP,
    CUBE_ITEM_TEXT_SECONDARY_HEIGHT,
)
from substitute.presentation.shell.chrome_style import (
    resolved_backdrop_mode,
    winui_card_fill_color,
)

CubeCardIcon: TypeAlias = QIcon | FluentIconBase | str | None
IconPaintCallback: TypeAlias = Callable[[int, int, int], None]


class CubeCardIssueSeverity(StrEnum):
    """Describe presentation-local cube card issue severity."""

    ERROR = "error"


@dataclass(frozen=True)
class CubeCardVisualState:
    """Describe host-owned state needed to paint one cube card."""

    primary_text: str
    secondary_text: str
    icon: CubeCardIcon
    selected: bool
    hovered: bool
    pressed: bool
    enabled: bool
    close_visible: bool
    compact_progress: float
    text_color: QColor | None = None
    selected_fill_color: tuple[int, int, int, int] | None = None
    inactive_text_alpha: int | None = None
    selected_font_weight: int | None = None
    editing_primary_text: bool = False
    issue_severity: CubeCardIssueSeverity | None = None
    bypassed: bool = False


class CubeCardVisual:
    """Draw and measure cube stack cards without owning widget behavior."""

    _BORDER_RADIUS = 5
    _SELECTED_FILL_RADIUS = 4.0
    _SELECTED_BOTTOM_BORDER_MODE = "cube"

    @classmethod
    def selected_fill_color_for_widget(
        cls,
        widget: object | None,
    ) -> tuple[int, int, int, int]:
        """Return the canonical selected cube-card fill for one widget context."""

        return winui_card_fill_color(resolved_backdrop_mode(widget))

    @staticmethod
    def has_icon(icon: CubeCardIcon) -> bool:
        """Return whether the visual state carries a drawable icon."""

        if icon is None:
            return False
        if isinstance(icon, QIcon):
            return not icon.isNull()
        return True

    @staticmethod
    def icon_x() -> int:
        """Return the stable cube icon X used by every compactness state."""

        return CUBE_ITEM_ICON_X

    @staticmethod
    def text_opacity(compact_progress: float) -> float:
        """Return text opacity for one compactness progress value."""

        return max(0.0, min(1.0, 1.0 - compact_progress))

    @staticmethod
    def close_button_x(item_width: int, button_width: int) -> int:
        """Return close-button X centered between text cutoff and card edge."""

        text_cutoff_x = item_width - CUBE_ITEM_CLOSE_TEXT_RESERVE
        reserve_center_x = text_cutoff_x + (CUBE_ITEM_CLOSE_TEXT_RESERVE / 2)
        return round(reserve_center_x - (button_width / 2))

    @classmethod
    def text_rect_for_width(
        cls,
        item_width: int,
        item_height: int,
        *,
        has_icon: bool,
        close_visible: bool,
        compact_progress: float,
    ) -> QRectF:
        """Return text bounds for a rendered width and compactness progress."""

        if compact_progress >= 0.999:
            return QRectF(0, 0, 0, item_height)

        text_left = (
            CUBE_ITEM_ICON_INSET_EXPANDED
            + CUBE_ITEM_ICON_SIZE_EXPANDED
            + CUBE_ITEM_TEXT_GAP_EXPANDED
            if has_icon
            else 12
        )
        close_padding = CUBE_ITEM_CLOSE_TEXT_RESERVE if close_visible else 12
        return QRectF(
            text_left,
            0,
            max(0, item_width - text_left - close_padding),
            item_height,
        )

    @staticmethod
    def text_row_rects(rect: QRectF) -> tuple[QRectF, QRectF]:
        """Return text rows centered vertically within the cube card."""

        block_height = CUBE_ITEM_TEXT_BLOCK_HEIGHT
        block_top = rect.y() + ((rect.height() - block_height) / 2)
        return (
            QRectF(
                rect.x(),
                block_top,
                rect.width(),
                CUBE_ITEM_TEXT_PRIMARY_HEIGHT,
            ),
            QRectF(
                rect.x(),
                block_top + CUBE_ITEM_TEXT_PRIMARY_HEIGHT - CUBE_ITEM_TEXT_ROW_OVERLAP,
                rect.width(),
                CUBE_ITEM_TEXT_SECONDARY_HEIGHT,
            ),
        )

    @classmethod
    def draw(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        font: QFont,
        state: CubeCardVisualState,
        icon_paint_callback: IconPaintCallback | None = None,
    ) -> None:
        """Draw one cube card using canonical stack-card visual rules."""

        cls._draw_background(painter, rect=rect, state=state)
        cls._draw_issue_wash(painter, rect=rect, state=state)
        cls._draw_icon(
            painter,
            rect=rect,
            state=state,
            icon_paint_callback=icon_paint_callback,
        )
        text_opacity = cls.text_opacity(state.compact_progress)
        if text_opacity > 0.0:
            cls._draw_text(painter, rect=rect, font=font, state=state)

    @classmethod
    def _draw_background(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        state: CubeCardVisualState,
    ) -> None:
        """Draw selected or idle cube-card background chrome."""

        if state.selected:
            cls._draw_selected_background(painter, rect=rect, state=state)
            return
        cls._draw_not_selected_background(painter, rect=rect, state=state)

    @classmethod
    def _draw_selected_background(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        state: CubeCardVisualState,
    ) -> None:
        """Draw the selected cube-card frame and highlighted fill."""

        width, height = rect.width(), rect.height()
        radius = cls._BORDER_RADIUS
        diameter = 2 * radius
        is_dark = isDarkTheme()

        top_border_path = QPainterPath()
        top_border_path.arcMoveTo(1, height - diameter - 1, diameter, diameter, 225)
        top_border_path.arcTo(1, height - diameter - 1, diameter, diameter, 225, -45)
        top_border_path.lineTo(1, radius)
        top_border_path.arcTo(1, 1, diameter, diameter, -180, -90)
        top_border_path.lineTo(width - radius, 1)
        top_border_path.arcTo(width - diameter - 1, 1, diameter, diameter, 90, -90)
        top_border_path.lineTo(width - 1, height - radius)
        top_border_path.arcTo(
            width - diameter - 1,
            height - diameter - 1,
            diameter,
            diameter,
            0,
            -45,
        )

        top_border_color = QColor(0, 0, 0, 20)
        if is_dark:
            if state.pressed:
                top_border_color = QColor(255, 255, 255, 18)
            elif state.hovered:
                top_border_color = QColor(255, 255, 255, 13)
        else:
            top_border_color = QColor(0, 0, 0, 16)
        painter.strokePath(top_border_path, top_border_color)

        bottom_border_path = QPainterPath()
        bottom_border_path.arcMoveTo(1, height - diameter - 1, diameter, diameter, 225)
        bottom_border_path.arcTo(1, height - diameter - 1, diameter, diameter, 225, 45)
        bottom_border_path.lineTo(width - radius - 1, height - 1)
        bottom_border_path.arcTo(
            width - diameter - 1,
            height - diameter - 1,
            diameter,
            diameter,
            270,
            45,
        )
        painter.strokePath(
            bottom_border_path,
            cls._resolve_bottom_border_color(top_border_color, is_dark),
        )

        selected_rect = rect.adjusted(1, 1, -1, -1)
        painter.setBrush(cls._resolve_selected_fill_color(state))
        painter.setPen(QColor(255, 255, 255, 25))
        painter.drawRoundedRect(
            selected_rect,
            cls._SELECTED_FILL_RADIUS,
            cls._SELECTED_FILL_RADIUS,
        )

    @classmethod
    def _resolve_selected_fill_color(cls, state: CubeCardVisualState) -> QColor:
        """Return selected cube-card fill color for one visual state."""

        if state.selected_fill_color is not None:
            return QColor(*state.selected_fill_color)
        return QColor(255, 255, 255, 20)

    @classmethod
    def _resolve_bottom_border_color(
        cls,
        top_border_color: QColor,
        is_dark: bool,
    ) -> QColor:
        """Resolve the cube selected-card bottom border color."""

        if cls._SELECTED_BOTTOM_BORDER_MODE == "cube" and not is_dark:
            return QColor(0, 0, 0, 63)
        return QColor(top_border_color)

    @classmethod
    def _draw_not_selected_background(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        state: CubeCardVisualState,
    ) -> None:
        """Draw hover/pressed affordance for unselected cube cards."""

        if not (state.pressed or state.hovered):
            return

        is_dark = isDarkTheme()
        if state.pressed:
            color = QColor(255, 255, 255, 12) if is_dark else QColor(0, 0, 0, 7)
        else:
            color = QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 10)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            rect.adjusted(1, 1, -1, -1),
            cls._BORDER_RADIUS,
            cls._BORDER_RADIUS,
        )

    @classmethod
    def _draw_issue_wash(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        state: CubeCardVisualState,
    ) -> None:
        """Draw a translucent issue wash above the normal card background."""

        if state.issue_severity is not CubeCardIssueSeverity.ERROR:
            return
        painter.save()
        painter.setPen(QPen(QColor(210, 48, 58, 180), 1.5))
        painter.setBrush(QColor(210, 48, 58, 38))
        painter.drawRoundedRect(
            rect.adjusted(1, 1, -1, -1),
            cls._BORDER_RADIUS,
            cls._BORDER_RADIUS,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 210))
        painter.drawRoundedRect(1, 8, 4, max(0, rect.height() - 16), 2, 2)
        painter.restore()

    @classmethod
    def _draw_icon(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        state: CubeCardVisualState,
        icon_paint_callback: IconPaintCallback | None,
    ) -> None:
        """Draw the cube icon centered in its reserved area."""

        if not cls.has_icon(state.icon):
            return

        icon_size = CUBE_ITEM_ICON_SIZE_COMPACT
        icon_x = cls.icon_x()
        icon_y = int((rect.height() - icon_size) / 2)
        if icon_paint_callback is not None:
            icon_paint_callback(icon_x, icon_y, icon_size)
        icon_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
        painter.save()
        if state.bypassed:
            painter.setOpacity(0.42)
        elif not state.selected:
            painter.setOpacity(0.79 if isDarkTheme() else 0.61)
        drawIcon(state.icon, painter, icon_rect)
        if state.bypassed:
            painter.setOpacity(1.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(130, 130, 130, 100 if isDarkTheme() else 120))
            painter.drawRoundedRect(icon_rect, 4.0, 4.0)
        painter.restore()

    @classmethod
    def _draw_text(
        cls,
        painter: QPainter,
        *,
        rect: QRect,
        font: QFont,
        state: CubeCardVisualState,
    ) -> None:
        """Draw primary and secondary text rows for one cube card."""

        text_rect = cls.text_rect_for_width(
            rect.width(),
            rect.height(),
            has_icon=cls.has_icon(state.icon),
            close_visible=state.close_visible,
            compact_progress=state.compact_progress,
        )
        if text_rect.width() <= 0:
            return

        primary_font = QFont(font)
        if state.selected and state.selected_font_weight is not None:
            primary_font.setWeight(QFont.Weight(state.selected_font_weight))

        secondary_font = QFont(font)
        secondary_font.setPointSize(max(8, font.pointSize() - 2))

        color: QColor | Qt.GlobalColor = (
            Qt.GlobalColor.white if isDarkTheme() else Qt.GlobalColor.black
        )
        primary_color = QColor(state.text_color or color)
        if not state.selected and state.inactive_text_alpha is not None:
            primary_color.setAlpha(state.inactive_text_alpha)

        secondary_color = QColor(primary_color)
        secondary_color.setAlpha(150 if isDarkTheme() else 125)

        primary_rect, secondary_rect = cls.text_row_rects(text_rect)

        painter.save()
        painter.setOpacity(cls.text_opacity(state.compact_progress))
        if not state.editing_primary_text:
            cls._draw_primary_text(
                painter,
                rect=primary_rect,
                text=state.primary_text,
                color=primary_color,
                font=primary_font,
            )
        if state.secondary_text:
            cls._draw_elided_text(
                painter,
                rect=secondary_rect,
                text=state.secondary_text,
                color=secondary_color,
                font=secondary_font,
            )
        painter.restore()

    @classmethod
    def _draw_primary_text(
        cls,
        painter: QPainter,
        *,
        rect: QRectF,
        text: str,
        color: QColor,
        font: QFont,
    ) -> None:
        """Draw primary text with a reduced leading slash prefix when present."""

        layout = layout_cube_alias_text(
            painter,
            text=text,
            row_rect=rect,
            primary_font=font,
        )
        if layout.prefix_segment is None:
            cls._draw_elided_text(
                painter,
                rect=rect,
                text=text,
                color=color,
                font=font,
            )
            return

        prefix_segment = layout.prefix_segment
        cls._draw_elided_text_on_baseline(
            painter,
            rect=prefix_segment.rect,
            text=prefix_segment.text,
            color=color,
            font=prefix_segment.font,
            baseline_y=prefix_segment.baseline_y,
        )
        cls._draw_elided_text_on_baseline(
            painter,
            rect=layout.body_segment.rect,
            text=layout.body_segment.text,
            color=color,
            font=layout.body_segment.font,
            baseline_y=layout.body_segment.baseline_y,
        )

    @staticmethod
    def _draw_elided_text_on_baseline(
        painter: QPainter,
        *,
        rect: QRectF,
        text: str,
        color: QColor,
        font: QFont,
        baseline_y: float,
    ) -> None:
        """Draw one elided line with an externally controlled baseline."""

        if not text or rect.width() <= 0:
            return
        painter.setFont(font)
        painter.setPen(QPen(color))
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            ceil(rect.width()),
        )
        painter.drawText(QPointF(rect.x(), baseline_y), elided)

    @staticmethod
    def _draw_elided_text(
        painter: QPainter,
        *,
        rect: QRectF,
        text: str,
        color: QColor,
        font: QFont,
    ) -> None:
        """Draw one line of text constrained to a fixed row."""

        if not text:
            return
        painter.setFont(font)
        painter.setPen(QPen(color))
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            int(rect.width()),
        )
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided,
        )


__all__ = [
    "CubeCardIcon",
    "CubeCardIssueSeverity",
    "CubeCardVisual",
    "CubeCardVisualState",
]
