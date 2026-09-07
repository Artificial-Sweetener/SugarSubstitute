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

"""Own dynamic onboarding-page sizing and scroll geometry."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class OnboardingPageStage(QScrollArea):
    """Keep one dynamic page centered when it fits and scrollable when it grows."""

    def __init__(self, parent: QWidget) -> None:
        """Build the page viewport and its single authoritative height owner."""

        super().__init__(parent)
        self.setObjectName("OnboardingPageStage")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scroll_content = QWidget(self)
        self.scroll_content.setObjectName("OnboardingPageScrollContent")
        self._content_layout = QVBoxLayout(self.scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        self.page_stack = QStackedWidget(self.scroll_content)
        self.page_stack.setObjectName("OnboardingPageStack")
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._content_layout.addWidget(self.page_stack)
        self.setWidget(self.scroll_content)

        self._height_refresh_timer = QTimer(self)
        self._height_refresh_timer.setSingleShot(True)
        self._height_refresh_timer.timeout.connect(self.refresh_current_page_height)

    def add_page(self, page: QWidget) -> None:
        """Add one production page to the stage."""

        self.page_stack.addWidget(page)

    def show_page(self, page: QWidget) -> None:
        """Display one page from its top and settle its current geometry."""

        self.page_stack.setCurrentWidget(page)
        self.refresh_current_page_height()
        self.verticalScrollBar().setValue(0)

    def schedule_current_page_height_refresh(self) -> None:
        """Refresh after Qt applies a dynamic child visibility change."""

        self.refresh_current_page_height()
        self._height_refresh_timer.start(0)

    def refresh_current_page_height(self) -> None:
        """Center fitting content and top-align overflowing content for scrolling."""

        page = self.page_stack.currentWidget()
        if page is None:
            return
        viewport_height = self.viewport().contentsRect().height()
        page_height = 0
        for _pass in range(2):
            viewport_width = self.viewport().contentsRect().width()
            self.page_stack.setFixedWidth(viewport_width)
            self.scroll_content.setFixedWidth(viewport_width)
            page_layout = page.layout()
            if page_layout is not None:
                page_layout.invalidate()
                page_layout.activate()
            page.updateGeometry()
            page_height = page.sizeHint().height()
            vertical_policy = (
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if page_height > viewport_height
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            if self.verticalScrollBarPolicy() is vertical_policy:
                break
            self.setVerticalScrollBarPolicy(vertical_policy)

        overflows = page_height > viewport_height
        self.verticalScrollBar().setVisible(overflows)
        self.page_stack.setFixedHeight(page_height)
        alignment = (
            Qt.AlignmentFlag.AlignVCenter
            if page_height <= viewport_height
            else Qt.AlignmentFlag.AlignTop
        )
        self._content_layout.setAlignment(self.page_stack, alignment)
        content_height = max(page_height, viewport_height)
        self.scroll_content.setFixedSize(viewport_width, content_height)
        self._content_layout.activate()
        self.page_stack.updateGeometry()
        self.scroll_content.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Recenter fitting content after the viewport receives final geometry."""

        super().resizeEvent(event)
        self.schedule_current_page_height_refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Settle page alignment once the native window becomes visible."""

        super().showEvent(event)
        self.schedule_current_page_height_refresh()


__all__ = ["OnboardingPageStage"]
