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

"""Wrap one Settings page in the Windows-like detail-page shell."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import TitleLabel  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import (
    ApplicationText,
    set_localized_text,
)

from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CONTENT_MAX_WIDTH,
    SETTINGS_PAGE_BOTTOM_MARGIN,
    SETTINGS_PAGE_HEADER_TO_FIRST_GROUP_SPACING,
    SETTINGS_PAGE_HORIZONTAL_MARGIN,
    SETTINGS_PAGE_TOP_MARGIN,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.settings.settings_page_shell")


class SettingsPageShell(QWidget):
    """Render a centered, scrollable Windows Settings detail page."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        """Create the shell around one page widget."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.title = title
        self.page_widget = widget
        self._build_layout(title, widget)

    def content_column_width(self) -> int:
        """Return the current centered content column width."""

        return int(self._content_column.width())

    def content_column_x(self) -> int:
        """Return the centered content column x coordinate in viewport space."""

        return int(self._content_column.x())

    def content_widget(self) -> QWidget:
        """Return the page widget hosted inside this shell."""

        return self.page_widget

    def schedule_metrics_refresh(self) -> None:
        """Refresh scroll metrics after child content changes."""

        self._sync_content_column_width()
        self._scroll_surface.schedule_metrics_refresh()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the page content clamped and centered after resizing."""

        super().resizeEvent(event)
        self._sync_content_column_width()
        self._scroll_surface.schedule_metrics_refresh()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh stale hidden-route geometry before the page is painted."""

        super().showEvent(event)
        self._sync_content_column_width()
        self._scroll_surface.schedule_metrics_refresh()

    def _build_layout(self, title: ApplicationText, widget: QWidget) -> None:
        """Create the centered scroll surface and compact page header."""

        self._content = QWidget(self)
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content.setStyleSheet("background-color: transparent;")
        content_shell_layout = QHBoxLayout(self._content)
        content_shell_layout.setContentsMargins(
            SETTINGS_PAGE_HORIZONTAL_MARGIN,
            SETTINGS_PAGE_TOP_MARGIN,
            SETTINGS_PAGE_HORIZONTAL_MARGIN,
            SETTINGS_PAGE_BOTTOM_MARGIN,
        )
        content_shell_layout.setSpacing(0)
        content_shell_layout.addStretch(1)

        self._content_column = QWidget(self._content)
        self._content_column.setMaximumWidth(SETTINGS_CONTENT_MAX_WIDTH)
        self._content_column.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        self._content_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content_column.setStyleSheet("background-color: transparent;")
        self._content_layout = QVBoxLayout(self._content_column)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SETTINGS_PAGE_HEADER_TO_FIRST_GROUP_SPACING)
        self.breadcrumb_label = TitleLabel("", self._content_column)
        set_localized_text(
            self.breadcrumb_label,
            "Settings > %1",
            title,
        )
        self._content_layout.addWidget(self.breadcrumb_label)
        self._content_layout.addWidget(widget)
        self._content_layout.addStretch(1)

        content_shell_layout.addWidget(self._content_column)
        content_shell_layout.addStretch(1)

        self._scroll_surface = EditorPanelScrollSurface(self)
        self._scroll_surface.setWidgetResizable(True)
        self._scroll_surface.setWidget(self._content)
        self._scroll_surface.setObjectName("SettingsPageShellScroll")
        self._scroll_surface.setStyleSheet(
            """
            QWidget#SettingsPageShellScroll {
                background-color: transparent;
                border: none;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._scroll_surface)

    def _sync_content_column_width(self) -> None:
        """Clamp the content column to the Toolkit sample maximum width."""

        viewport_width = max(1, self._scroll_surface.viewport().width())
        if viewport_width <= 1:
            viewport_width = max(1, self.width())
        available_width = max(1, viewport_width - (SETTINGS_PAGE_HORIZONTAL_MARGIN * 2))
        self._content_column.setFixedWidth(
            min(SETTINGS_CONTENT_MAX_WIDTH, available_width)
        )


__all__ = ["SettingsPageShell"]
