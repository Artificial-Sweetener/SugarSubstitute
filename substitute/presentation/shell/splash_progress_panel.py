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

"""Present startup completion independently from activity and optional diagnostics."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from substitute.presentation.localization import LocalizedBodyLabel
from sugarsubstitute_shared.presentation.activity_progress_bar import (
    ActivityProgressBar,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import set_localized_text
from sugarsubstitute_shared.launch_splash.progress import SplashProgress


_STATUS_PROGRESS_GAP = 8


class SplashProgressPanel(QWidget):
    """Own the visible startup status, honest fill and expandable diagnostic surface."""

    detailsVisibilityChanged = Signal(bool)

    def __init__(self, *, details: QWidget, parent: QWidget | None = None) -> None:
        """Mount supplied diagnostics without taking ownership of startup execution."""
        super().__init__(parent)
        self._complete = False
        self._failed = False
        self._progress_status = ""
        self._activity_status = ""
        self._details_visible = False
        self.details = details
        details_layout = details.layout()
        if details_layout is None:
            details_layout = QVBoxLayout(details)
            details_layout.setContentsMargins(1, 1, 1, 1)
            details_layout.setSpacing(0)
        if not isinstance(details_layout, QVBoxLayout):
            raise TypeError("Splash diagnostics require a vertical content layout.")
        self._details_layout = details_layout
        self._details_layout.setContentsMargins(0, 0, 0, 0)
        self.status = LocalizedBodyLabel(app_text("Loading..."), self)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored
        )
        self.progress = ActivityProgressBar(self)
        layout = QVBoxLayout(self)
        self._layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.status.setContentsMargins(0, 0, 0, _STATUS_PROGRESS_GAP)
        self.status.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        layout.addWidget(self.status, 1)
        layout.addWidget(self.progress)
        layout.addWidget(details, 1)
        self.details.hide()
        self.status.installEventFilter(self)
        self.details.installEventFilter(self)

    def set_progress(self, value: SplashProgress, *, status: str) -> None:
        """Display producer-owned completion and translated status without estimation."""
        if self._failed:
            return
        self._progress_status = status
        self.set_activity_status(self._activity_status)
        self.progress.set_progress(value.completed, value.total)
        self._complete = value.completed == value.total
        self._update_activity()

    def set_activity_status(self, message: str) -> None:
        """Project operation feedback while retaining authoritative completion units."""
        if self._failed:
            return
        self._activity_status = message
        self._render_status()

    def _render_status(self) -> None:
        """Keep localized explanation boundaries intact when a caption needs two lines."""
        message = self._activity_status or self._progress_status
        if message:
            inline = message.replace("\n", " ")
            # Reserve the widest ellipsis frame so animation cannot toggle wrapping.
            widest_frame = inline.rstrip(".") + "..."
            fits = (
                self.status.fontMetrics().horizontalAdvance(widest_frame)
                <= self.status.contentsRect().width()
            )
            self.status.setText(inline if fits else message)
        else:
            set_localized_text(self.status, app_text("Loading..."))
        self.progress.setAccessibleName(self.status.text().replace("\n", " "))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Reflow the caption when its actual width or font changes."""
        if (
            watched is self.status
            and event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange)
            and not self._failed
        ):
            self._render_status()
        if watched is self.details and event.type() == QEvent.Type.Resize:
            self._position_console_progress()
        return super().eventFilter(watched, event)

    def show_failure(self, message: str) -> None:
        """Retain terminal failure and expose diagnostics without advancing completion."""
        self._failed = True
        self.status.setText(message)
        self.progress.setAccessibleName(message)
        self.set_details_visible(True)
        self._update_activity()

    def record_activity(self) -> None:
        """Pulse on actual output without changing completion or the step label."""
        self.progress.record_activity()

    def reset_progress(self) -> None:
        """Begin a separate startup attempt from empty visible completion."""

        self._complete = False
        self._failed = False
        self.progress.reset_progress()
        self._update_activity()

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop hidden animation work while retaining stage state."""
        self.progress.set_activity_enabled(False)
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Rearm visible activity without manufacturing an activity event."""
        super().showEvent(event)
        self._update_activity()

    def _update_activity(self) -> None:
        """Arm only the currently visible unfinished progress surface."""
        active = self.isVisible() and not self._complete and not self._failed
        self.progress.set_activity_enabled(active)

    @property
    def details_visible(self) -> bool:
        """Return disclosure state independently of the containing window's visibility."""
        return self._details_visible

    def set_details_visible(self, visible: bool) -> None:
        """Expose retained diagnostics without altering execution or progress state."""
        if self._details_visible == visible:
            return
        self._details_visible = visible
        self.status.setVisible(not visible)
        if visible:
            self._layout.removeWidget(self.progress)
            self.progress.setParent(self.details)
            self.progress.set_console_attached(True)
            self._details_layout.setContentsMargins(0, self.progress.height() + 8, 0, 0)
            self._position_console_progress()
        else:
            self.progress.set_console_attached(False)
            self._details_layout.setContentsMargins(0, 0, 0, 0)
            self._layout.insertWidget(1, self.progress)
        self.progress.show()
        self.details.setVisible(visible)
        self.detailsVisibilityChanged.emit(visible)

    def _position_console_progress(self) -> None:
        """Cover the console's top border without inheriting its content inset."""
        if self._details_visible:
            self.progress.setGeometry(
                0, 0, self.details.width(), self.progress.height()
            )
            self.progress.raise_()
