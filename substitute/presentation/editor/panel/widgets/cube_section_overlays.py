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

"""Present runtime-issue and update washes over a cube section."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    app_text,
)

_UPDATING_WASH_ALPHA = 145
_UPDATING_ELLIPSIS_INTERVAL_MS = 350
_UPDATING_ELLIPSIS_STATES = ("", ".", "..", "...")


class CubeSectionIssueOverlay(QWidget):
    """Paint a mouse-transparent issue wash over one cube section."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize the overlay as a non-interactive child widget."""

        super().__init__(parent)
        self._issue_severity: str | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_issue_severity(self, severity: str | None) -> None:
        """Set the issue severity used by the overlay painter."""

        self._issue_severity = severity
        self.update()

    def paintEvent(self, event: object) -> None:
        """Paint the current issue wash."""

        _ = event
        if self._issue_severity != "error":
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(210, 48, 58, 170), 2))
        painter.setBrush(QColor(210, 48, 58, 34))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 190))
        painter.drawRoundedRect(0, 0, 4, max(0, self.height()), 2, 2)


class CubeSectionUpdatingOverlay(QWidget):
    """Paint a local black update wash over one rebuilding cube section."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize the overlay as an input-blocking child widget."""

        super().__init__(parent)
        self._message: ApplicationText = app_text("Updating")
        self._ellipsis_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_UPDATING_ELLIPSIS_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_ellipsis)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 230);
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

    def show_updating(self, message: ApplicationText = app_text("Updating")) -> None:
        """Show this overlay and start the lightweight ellipsis animation."""

        self._message = message if message.strip() else app_text("Updating")
        self._ellipsis_index = 0
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self._refresh_label()
        self.raise_()
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def hide_updating(self) -> None:
        """Hide this overlay and stop the ellipsis animation."""

        self._timer.stop()
        self.hide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the update label centered when the section changes size."""

        super().resizeEvent(event)
        self._position_label()

    def paintEvent(self, event: object) -> None:
        """Paint the translucent black wash."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, _UPDATING_WASH_ALPHA))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

    def _advance_ellipsis(self) -> None:
        """Advance the update ellipsis by one frame."""

        self._ellipsis_index = (self._ellipsis_index + 1) % len(
            _UPDATING_ELLIPSIS_STATES
        )
        self._refresh_label()

    def _refresh_label(self) -> None:
        """Apply the current update message."""

        apply_application_text(
            self._label,
            app_text(
                "%1%2",
                self._message,
                _UPDATING_ELLIPSIS_STATES[self._ellipsis_index],
            ),
        )
        self._position_label()

    def _position_label(self) -> None:
        """Center the update label inside the overlay."""

        hint = self._label.sizeHint()
        self._label.setGeometry(
            (self.width() - hint.width()) // 2,
            (self.height() - hint.height()) // 2,
            hint.width(),
            hint.height(),
        )


__all__ = ["CubeSectionIssueOverlay", "CubeSectionUpdatingOverlay"]
