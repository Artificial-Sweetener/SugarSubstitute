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

"""Provide floating editor search UI."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import set_localized_tooltip

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QHideEvent, QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import LineEdit, TransparentToolButton

from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    floating_surface_border_rgba,
    floating_surface_rgba,
)
from substitute.presentation.widgets.search_box import ContextSearchBox
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.search_view")


class FloatingSearchBox(QWidget):
    """Render the floating editor-search affordance and forward its signals."""

    contextSearchChanged = Signal(str, str)
    cycleSearchMatchRequested = Signal()
    cycleSearchMatchRequestedBackward = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the floating search box and its navigation controls."""

        super().__init__(parent)

        self.bg = QLabel(self)
        self.bg.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.bg.lower()

        # === Main layout for search box + close button ===
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        self.contextSearchBox = ContextSearchBox(self)
        layout.addWidget(self.contextSearchBox)

        # --- Next/Prev buttons (FIF.DOWN / FIF.UP, TransparentToolButton) ---
        self.nextButton = TransparentToolButton(FIF.DOWN, self)
        set_localized_tooltip(self.nextButton, "Next match (Enter)")
        self.nextButton.setCursor(Qt.PointingHandCursor)
        self.nextButton.setFixedSize(28, 28)
        layout.addWidget(self.nextButton)

        self.prevButton = TransparentToolButton(FIF.UP, self)
        set_localized_tooltip(self.prevButton, "Previous match (Shift+Enter)")
        self.prevButton.setCursor(Qt.PointingHandCursor)
        self.prevButton.setFixedSize(28, 28)
        layout.addWidget(self.prevButton)

        # --- Close button (FIF.CLOSE, TransparentToolButton) ---
        self.closeButton = TransparentToolButton(FIF.CLOSE, self)
        set_localized_tooltip(self.closeButton, "Close search (Esc)")
        self.closeButton.setCursor(Qt.PointingHandCursor)
        self.closeButton.setFixedSize(28, 28)
        layout.addWidget(self.closeButton)

        self.nextButton.clicked.connect(self.cycleSearchMatchRequested)
        self.prevButton.clicked.connect(self.cycleSearchMatchRequestedBackward)

        self.closeButton.clicked.connect(self.hide)

        # Signal passthrough for shell-level handlers.
        self.contextSearchBox.contextSearchChanged.connect(self.contextSearchChanged)
        self.contextSearchBox.cycleSearchMatchRequested.connect(
            self.cycleSearchMatchRequested
        )
        self.contextSearchBox.cycleSearchMatchRequestedBackward.connect(
            self.cycleSearchMatchRequestedBackward
        )
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    def set_navigation_enabled(self, enabled: bool) -> None:
        """Enable or disable next/prev navigation buttons (used for Node mode)."""
        self.nextButton.setEnabled(enabled)
        self.prevButton.setEnabled(enabled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the rounded background synchronized with the widget size."""

        self.bg.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Emit the close signal when the floating search box hides."""

        try:
            self.closed.emit()
        except RuntimeError as error:
            log_warning(
                _LOGGER,
                "Floating search close signal could not be emitted",
                error_type=type(error).__name__,
            )
        super().hideEvent(event)

    def searchLineEdit(self) -> LineEdit:
        """Return the inner line edit used by the context search box."""

        return self.contextSearchBox.searchLineEdit

    def context(self) -> str:
        """Return the active search context label."""

        return self.contextSearchBox.context()

    def searchText(self) -> str:
        """Return the current raw search text."""

        return self.contextSearchBox.searchText()

    def _apply_theme_styles(self) -> None:
        """Reapply floating search chrome after theme or accent changes."""

        self.bg.setStyleSheet(
            f"""
             background-color: {floating_surface_rgba()};
            border: 1px solid {floating_surface_border_rgba()};
            border-radius: 8px;
            padding: 0px;
            """
        )


__all__ = ["FloatingSearchBox"]
