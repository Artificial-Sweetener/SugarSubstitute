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

"""Host crash report content in an independently visible Fluent window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import isDarkTheme, qconfig  # type: ignore[import-untyped]
from qframelesswindow import FramelessDialog, StandardTitleBar  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.error_report_presentation import (
    ErrorReportPresentation,
)
from sugarsubstitute_shared.presentation.error_report_view import SharedErrorReportView
from sugarsubstitute_shared.presentation.localization import render_application_text


class SharedErrorReportWindow(FramelessDialog):  # type: ignore[misc]
    """Own native report visibility when no application frame survives."""

    def __init__(
        self,
        *,
        presentation: ErrorReportPresentation,
        restart: Callable[[], None] | None = None,
    ) -> None:
        """Compose the shared report beneath standard native caption controls."""

        super().__init__()
        self.setObjectName("SharedErrorReportWindow")
        self.setTitleBar(StandardTitleBar(self))
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()
        self.titleBar.setDoubleClickEnabled(False)
        self.setResizeEnabled(False)
        self.setWindowTitle(render_application_text(presentation.title))
        self.setWindowIcon(QGuiApplication.windowIcon())
        screen = self.screen()
        maximum_height = max(280, screen.availableGeometry().height() - 48)
        title_height = self.titleBar.height()
        self.content = SharedErrorReportView(
            presentation=presentation,
            maximum_height=maximum_height - title_height,
            restart=restart,
            parent=self,
        )
        self._report_layout = QVBoxLayout(self)
        self._report_layout.setContentsMargins(0, title_height, 0, 0)
        self._report_layout.setSpacing(0)
        self._report_layout.addWidget(self.content)
        self.setFixedWidth(self.content.width())
        self.content.dismissed.connect(self.accept)
        self.content.size_changed.connect(self._sync_content_geometry)
        self._sync_content_geometry()
        self.move(screen.availableGeometry().center() - self.rect().center())
        self._apply_theme()
        qconfig.themeChangedFinished.connect(self._apply_theme)
        self.titleBar.raise_()

    def _sync_content_geometry(self) -> None:
        """Fit report details while keeping recovery actions within the screen."""

        self._report_layout.invalidate()
        self._report_layout.activate()
        self.setFixedHeight(self.content.sizeHint().height() + self.titleBar.height())
        available = self.screen().availableGeometry()
        self.move(
            max(available.left(), min(self.x(), available.right() - self.width() + 1)),
            max(available.top(), min(self.y(), available.bottom() - self.height() + 1)),
        )

    def _apply_theme(self) -> None:
        """Match the standard caption and window surface to the report theme."""

        foreground = QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)
        background = "#2b2b2b" if isDarkTheme() else "#f9f9f9"
        self.setStyleSheet(
            f"QDialog#SharedErrorReportWindow {{ background: {background}; }}"
        )
        self.titleBar.titleLabel.setStyleSheet(
            f"background: transparent; color: {foreground.name()}; padding: 0 4px;"
        )
        self.titleBar.closeBtn.setNormalColor(foreground)
        self.titleBar.closeBtn.setHoverColor(QColor(255, 255, 255))
