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

"""Build and paint the inline cube runtime-issue card."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.editor.panel.widgets.field_row_geometry import (
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HEIGHT,
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_ICON_SIZE,
    EDITOR_ROW_SPACING,
)
from substitute.presentation.localization import LocalizedLabel
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    resolved_backdrop_mode,
    winui_card_border_color,
    winui_card_fill_color,
)

_CORNER_RADIUS = 4.0
_ERROR_COLOR = QColor(210, 48, 58)


def build_runtime_issue_card(issue_lines: tuple[str, ...]) -> QWidget:
    """Build the visible inline error details for one cube section."""

    card = _RuntimeIssueNodeCard()
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 0)
    card_layout.setSpacing(0)

    header = _RuntimeIssueCardHeaderSurface(card)
    header.setFixedHeight(EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2))
    header.set_accordion_content_attached(True)
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(
        EDITOR_ROW_HORIZONTAL_MARGINS[0],
        EDITOR_ROW_BODY_SPACING,
        EDITOR_ROW_HORIZONTAL_MARGINS[2],
        EDITOR_ROW_BODY_SPACING,
    )
    header_layout.setSpacing(EDITOR_ROW_SPACING)

    glyph = _RuntimeIssueGlyph(header)
    glyph.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
    header_layout.addWidget(glyph)
    title = LocalizedLabel(app_text("Cube disabled"), header)
    title.setObjectName("CubeRuntimeIssueTitle")
    title_font = title.font()
    title_font.setPointSize(14)
    title_font.setWeight(QFont.Weight.DemiBold)
    title.setFont(title_font)
    title.setWordWrap(True)
    header_layout.addWidget(title)
    header_layout.addStretch()
    card_layout.addWidget(header)

    content = _RuntimeIssueCardContentSurface(card)
    content.set_accordion_content_attached(True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(0)
    for index, line in enumerate(issue_lines):
        divider = _RuntimeIssueDivider(content)
        divider.setObjectName(
            "NodeCardTitleBodyDivider" if index == 0 else "NodeCardBodyDivider"
        )
        content_layout.addWidget(divider)
        detail_row = _RuntimeIssueDetailRow(content)
        detail_layout = QHBoxLayout(detail_row)
        detail_layout.setContentsMargins(
            EDITOR_ROW_HORIZONTAL_MARGINS[0],
            EDITOR_ROW_BODY_SPACING,
            EDITOR_ROW_HORIZONTAL_MARGINS[2],
            EDITOR_ROW_BODY_SPACING,
        )
        detail_layout.setSpacing(EDITOR_ROW_SPACING)
        detail = QLabel(line, detail_row)
        detail.setWordWrap(True)
        detail.setObjectName(
            "CubeRuntimeIssueAction"
            if index == len(issue_lines) - 1 and "ComfyUI" in line
            else "CubeRuntimeIssueDetail"
        )
        detail_layout.addWidget(detail)
        content_layout.addWidget(detail_row)
    card_layout.addWidget(content)
    return card


class _RuntimeIssueNodeCard(QWidget):
    """Compose issue header and body surfaces like an editor node card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the transparent issue-card root."""

        super().__init__(parent)
        self.setObjectName("CubeRuntimeIssueNodeCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)


class _RuntimeIssueCardSurface(QWidget):
    """Paint one red-washed node-card segment with attached-corner rules."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create one themed issue card paint surface."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content_attached = False
        connect_theme_refresh(self, self.update)

    def set_accordion_content_attached(self, attached: bool) -> None:
        """Set whether this surface is visually attached to another segment."""

        self._content_attached = attached
        self.update()

    def paintEvent(self, event: object) -> None:
        """Paint the card segment fill, required red wash, and issue stroke."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill_path = self._paint_path(self.rect())
        stroke_path = self._stroke_path(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*winui_card_fill_color(resolved_backdrop_mode(self))))
        painter.drawPath(fill_path)
        wash = QColor(_ERROR_COLOR)
        wash.setAlpha(42)
        painter.setBrush(wash)
        painter.drawPath(fill_path)
        painter.setPen(QPen(QColor(*winui_card_border_color()), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(stroke_path)
        error_stroke = QColor(_ERROR_COLOR)
        error_stroke.setAlpha(142)
        painter.setPen(QPen(error_stroke, 1))
        painter.drawPath(stroke_path)

    def _paint_path(self, rect: QRect) -> QPainterPath:
        """Return the rounded segment path for the current attachment state."""

        path = QPainterPath()
        x, y = float(rect.x()), float(rect.y())
        width, height = float(rect.width()), float(rect.height())
        radius = min(_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)
        path.moveTo(x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.closeSubpath()
        return path

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the border path for this surface."""

        return self._paint_path(rect)

    def _top_left_radius(self, radius: float) -> float:
        """Return the top-left corner radius for this surface."""

        return radius

    def _top_right_radius(self, radius: float) -> float:
        """Return the top-right corner radius for this surface."""

        return radius

    def _bottom_right_radius(self, radius: float) -> float:
        """Return the bottom-right corner radius for this surface."""

        return radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Return the bottom-left corner radius for this surface."""

        return radius


class _RuntimeIssueCardHeaderSurface(_RuntimeIssueCardSurface):
    """Paint the issue card title segment like a node-card header."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the issue card header segment."""

        super().__init__(parent)
        self.setObjectName("NodeCardHeaderSurface")

    def paintEvent(self, event: object) -> None:
        """Paint the attached header and the red issue rail."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 190))
        painter.drawRoundedRect(0, 0, 4, max(0, self.height()), 2, 2)

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the header border path without the attached body seam."""

        if not self._content_attached:
            return super()._stroke_path(rect)
        path = QPainterPath()
        x, y = float(rect.x()), float(rect.y())
        width, height = float(rect.width()), float(rect.height())
        radius = min(_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)
        path.moveTo(x, y + height)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height)
        return path

    def _bottom_right_radius(self, radius: float) -> float:
        """Square the bottom-right corner while body content is attached."""

        return 0.0 if self._content_attached else radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Square the bottom-left corner while body content is attached."""

        return 0.0 if self._content_attached else radius


class _RuntimeIssueCardContentSurface(_RuntimeIssueCardSurface):
    """Paint the issue card body segment like a node-card content surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the issue card content segment."""

        super().__init__(parent)
        self.setObjectName("NodeCardContentSurface")

    def _top_left_radius(self, radius: float) -> float:
        """Square the top-left corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _top_right_radius(self, radius: float) -> float:
        """Square the top-right corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the body border path without the attached top edge."""

        if not self._content_attached:
            return super()._stroke_path(rect)
        path = QPainterPath()
        x, y = float(rect.x()), float(rect.y())
        width, height = float(rect.width()), float(rect.height())
        radius = min(_CORNER_RADIUS, width / 2.0, height / 2.0)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)
        path.moveTo(x + width, y)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y)
        return path


class _RuntimeIssueDetailRow(QWidget):
    """Render one body row inside the issue card content segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a transparent row with node-card field-row height behavior."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2))


class _RuntimeIssueDivider(QWidget):
    """Paint one node-card-style separator inside the issue body."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a one-pixel separator row."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(1)
        connect_theme_refresh(self, self.update)

    def paintEvent(self, event: object) -> None:
        """Paint the card divider with a subtle red issue tint."""

        _ = event
        painter = QPainter(self)
        base = QColor(*winui_card_border_color())
        issue = QColor(_ERROR_COLOR)
        issue.setAlpha(72)
        painter.setPen(QPen(base, 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.setPen(QPen(issue, 1))
        painter.drawLine(0, 0, self.width(), 0)


class _RuntimeIssueGlyph(QWidget):
    """Paint a compact error glyph for the issue node card title row."""

    def paintEvent(self, event: object) -> None:
        """Paint a small Fluent-style error indicator."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 205))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(255, 255, 255, 235), 2))
        center_x = rect.center().x()
        painter.drawLine(center_x, rect.top() + 4, center_x, rect.bottom() - 6)
        painter.drawPoint(center_x, rect.bottom() - 3)


__all__ = ["build_runtime_issue_card"]
