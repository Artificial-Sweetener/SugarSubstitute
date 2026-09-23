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

"""Place the model-version affordance beside the picker chevron."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from substitute.presentation.model_updates.icon_menu import show_update_icon_menu
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.resources.fluent_app_icon import AppIcon
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text


class _PickerChrome(Protocol):
    """Describe the qfluent combo chrome owned by the model picker."""

    hBoxLayout: QHBoxLayout
    dropButton: QWidget

    def isReadOnly(self) -> bool:
        """Return whether the picker is showing its closed model banner."""

    def setTextMargins(self, left: int, top: int, right: int, bottom: int) -> None:
        """Reserve right-side space for the chevron and update action."""

    def setProperty(self, name: str, value: object) -> bool:
        """Expose badge visibility to banner text geometry."""

    def update(self) -> None:
        """Repaint after the available-action state changes."""


class ModelPickerUpdateButton(QToolButton):
    """Show a new-version icon only for the selected installed model."""

    def __init__(
        self,
        parent: QWidget,
        *,
        chrome: _PickerChrome,
        updates: ModelUpdatePickerBridge,
        selected_sha256: Callable[[], str | None],
    ) -> None:
        """Join the existing combo action row immediately before its chevron."""

        super().__init__(parent)
        self._chrome = chrome
        self._updates = updates
        self._selected_sha256 = selected_sha256
        self.setObjectName("modelPickerUpdateButton")
        self.setFixedSize(26, 25)
        self.setIconSize(QSize(18, 18))
        self.setIcon(AppIcon.ARROW_CIRCLE_UP_SPARKLE_20_REGULAR.qicon())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QToolButton#modelPickerUpdateButton { background: transparent; "
            "border: none; border-radius: 5px; }"
            "QToolButton#modelPickerUpdateButton:hover {"
            "background: rgba(255, 255, 255, 48); }"
        )
        label = render_application_text(app_text("Update available — view versions"))
        self.setAccessibleName(label)
        set_fluent_tooltip_text(self, label)
        chrome.hBoxLayout.insertWidget(
            chrome.hBoxLayout.indexOf(chrome.dropButton),
            self,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.clicked.connect(self._open_family)
        updates.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """Reserve banner space only while this exact model has an update."""

        available = (
            self._chrome.isReadOnly()
            and self._updates.proposal_for_sha(self._selected_sha256()) is not None
        )
        self.setVisible(available)
        self._chrome.setProperty("modelUpdateAvailable", available)
        self._chrome.setTextMargins(0, 0, 58 if available else 29, 0)
        self._chrome.update()

    def _open_family(self) -> None:
        """Open the chosen model's chronology without changing picker selection."""

        self._updates.request_family(self._selected_sha256())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """Offer dismissal and page opt-out only on the update icon."""

        if show_update_icon_menu(
            parent=self,
            updates=self._updates,
            sha256=self._selected_sha256(),
            global_pos=event.globalPos(),
        ):
            event.accept()
            return
        super().contextMenuEvent(event)


__all__ = ["ModelPickerUpdateButton"]
