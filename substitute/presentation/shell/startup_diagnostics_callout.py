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

"""Adapt qfluent TeachingTip for startup diagnostics titlebar hints."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QPoint, QPointF, QObject
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    TeachingTip,
    TeachingTipTailPosition,
)
from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]

from substitute.presentation.semantic_colors import (
    legible_text_color_for_background,
    semantic_error_color,
)

_AUTO_DISMISS_MS = 6000


class StartupDiagnosticsCallout(QObject):
    """Show a Fluent teaching tip anchored to a diagnostics titlebar button."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        auto_dismiss_ms: int = _AUTO_DISMISS_MS,
    ) -> None:
        """Initialize the callout adapter."""

        super().__init__(parent)
        self._parent = parent
        self._message = ""
        self._pointer_x = 0
        self._tip: TeachingTip | None = None
        self._accent_bubble: QWidget | None = None
        self._auto_dismiss_ms = auto_dismiss_ms
        self._has_errors = False

    def show_for(self, anchor: QWidget, message: str, *, has_errors: bool) -> None:
        """Show a Fluent teaching tip with its tail aimed at the anchor."""

        self.dismiss()
        self._message = message
        self._has_errors = has_errors
        duration = self._auto_dismiss_ms if self._auto_dismiss_ms > 0 else -1
        target_bottom_center = anchor.mapToGlobal(
            QPoint(anchor.width() // 2, anchor.height())
        )
        self._tip = TeachingTip.create(
            target=anchor,
            title="",
            content=message,
            isClosable=False,
            duration=duration,
            tailPosition=TeachingTipTailPosition.TOP,
            parent=self._parent or anchor.window(),
            isDeleteOnClose=False,
        )
        self._tip.destroyed.connect(self._clear_tip)
        self._apply_bubble_palette()
        self._tip.adjustSize()
        self._align_tip_tail_to_target(target_bottom_center)

    def dismiss(self) -> None:
        """Hide the active callout immediately."""

        if self._tip is None:
            return
        tip = self._tip
        self._tip = None
        self._clear_accent_bubble()
        tip.close()
        tip.deleteLater()

    def message(self) -> str:
        """Return the current callout message."""

        return self._message

    def pointer_x(self) -> int:
        """Return the local x coordinate where the pointer is aimed."""

        return self._pointer_x

    def is_visible(self) -> bool:
        """Return whether the qfluent teaching tip is currently visible."""

        return self._tip is not None and self._tip.isVisible()

    def x(self) -> int:
        """Return the active teaching tip global x coordinate."""

        return 0 if self._tip is None else self._tip.x()

    def y(self) -> int:
        """Return the active teaching tip global y coordinate."""

        return 0 if self._tip is None else self._tip.y()

    def _clear_tip(self) -> None:
        """Forget the current teaching tip after qfluent destroys it."""

        self._tip = None
        self._accent_bubble = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Paint the active qfluent bubble with the selected diagnostics color."""

        if watched is self._accent_bubble and event.type() == QEvent.Type.Paint:
            self._paint_accent_bubble(watched)
            return True
        return super().eventFilter(watched, event)

    def _align_tip_tail_to_target(self, target_bottom_center: QPoint) -> None:
        """Move the TeachingTip so qfluent's actual painted tail hits the target."""

        if self._tip is None:
            return
        actual_tail_x = self._actual_tail_global_x()
        self._tip.move(
            self._tip.x() + target_bottom_center.x() - actual_tail_x, self._tip.y()
        )
        self._pointer_x = self._actual_tail_global_x() - self._tip.x()

    def _actual_tail_global_x(self) -> int:
        """Return the x coordinate of qfluent's actual top-tail center."""

        if self._tip is None:
            return 0
        bubble = cast(QWidget, getattr(self._tip, "bubble"))
        return bubble.mapToGlobal(QPoint(bubble.width() // 2, 0)).x()

    def _apply_bubble_palette(self) -> None:
        """Apply diagnostics bubble paint and readable label colors to qfluent tip."""

        if self._tip is None:
            return
        self._clear_accent_bubble()
        bubble = cast(QWidget, getattr(self._tip, "bubble"))
        bubble.installEventFilter(self)
        bubble.update()
        self._accent_bubble = bubble

        text_color = _legible_text_color(
            _diagnostics_bubble_color(has_errors=self._has_errors)
        )
        view = self._tip.view
        for label_name in ("titleLabel", "contentLabel"):
            label = getattr(view, label_name, None)
            if isinstance(label, QLabel):
                label.setStyleSheet(
                    f"color: {text_color.name()}; background: transparent;"
                )

    def _clear_accent_bubble(self) -> None:
        """Remove the temporary paint filter from the current accent bubble."""

        if self._accent_bubble is None:
            return
        self._accent_bubble.removeEventFilter(self)
        self._accent_bubble = None

    def _paint_accent_bubble(self, bubble: QWidget) -> None:
        """Paint the qfluent top-tail bubble using the diagnostics color."""

        painter = QPainter(bubble)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = _diagnostics_bubble_color(has_errors=self._has_errors)
        border = QColor(background)
        border.setAlpha(255)
        painter.setBrush(background)
        painter.setPen(border)

        width = bubble.width()
        height = bubble.height()
        layout = bubble.layout()
        top_margin = 0 if layout is None else layout.contentsMargins().top()
        path = QPainterPath()
        path.addRoundedRect(1, top_margin, width - 2, height - top_margin - 1, 8, 8)
        path.addPolygon(
            QPolygonF(
                [
                    QPointF(width / 2 - 7, top_margin),
                    QPointF(width / 2, 1),
                    QPointF(width / 2 + 7, top_margin),
                ]
            )
        )
        painter.drawPath(path.simplified())


def startup_diagnostics_callout_message(*, has_errors: bool) -> str:
    """Return the titlebar callout message for startup diagnostics severity."""

    issue_type = "errors" if has_errors else "warnings"
    return f"ComfyUI reported {issue_type} during startup"


def _diagnostics_bubble_color(*, has_errors: bool) -> QColor:
    """Return the semi-opaque color used for the startup diagnostics callout."""

    color = semantic_error_color() if has_errors else QColor(themeColor())
    color.setAlpha(235)
    return color


def _legible_text_color(background: QColor) -> QColor:
    """Return black or white text with better contrast on the background color."""

    return legible_text_color_for_background(background)


__all__ = [
    "StartupDiagnosticsCallout",
    "startup_diagnostics_callout_message",
]
