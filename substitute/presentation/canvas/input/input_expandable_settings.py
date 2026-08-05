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

"""Compose one compact Input settings header over an expandable details body."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, SegmentedItem, TransparentToolButton  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.tools import CanvasToolOptionsControl

_HEADER_MINIMUM_WIDTH = 132


class InputSettingsSection(Protocol):
    """Describe independently owned header and details widgets."""

    header_button: SegmentedItem
    details: QWidget

    def set_details_visible(self, visible: bool) -> None:
        """Project expansion into section-owned details."""


class InputExpandableSettingsControl(CanvasToolOptionsControl):
    """Own shared expansion chrome for one focused settings responsibility."""

    def __init__(self, section: InputSettingsSection, parent: QWidget) -> None:
        """Mount one section without assuming anything about its settings."""
        super().__init__(parent)
        if not isinstance(section, QObject):
            raise TypeError("Input settings sections must be QObject-owned")
        section.setParent(self)
        self.section = section
        self._configure_header(section.header_button)
        section.header_button.clicked.connect(self.expand)

        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setObjectName("InputExpandableSettingsCloseButton")
        self.close_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        set_localized_tooltip(self.close_button, "Close")
        set_localized_accessible_name(self.close_button, "Close")
        self.close_button.clicked.connect(self.collapse)
        self.close_button.hide()

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(section.header_button)
        header_layout.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addLayout(header_layout)
        layout.addWidget(section.details)

    def apply_expanded_state(self, expanded: bool) -> None:
        """Show this section's details and shared close action together."""
        self.close_button.setVisible(expanded)
        self.section.set_details_visible(expanded)
        self.adjustSize()

    @staticmethod
    def _configure_header(header: SegmentedItem) -> None:
        """Apply the shared compact canvas-chrome header geometry."""
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
        header.setMinimumWidth(_HEADER_MINIMUM_WIDTH)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


__all__ = ["InputExpandableSettingsControl", "InputSettingsSection"]
