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

"""Provide the toolbar-owned Settings search field."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

SETTINGS_TOOLBAR_SEARCH_OBJECT_NAME = "SettingsToolbarSearchLineEdit"
SETTINGS_TOOLBAR_SEARCH_WIDTH = 420
SETTINGS_SEARCH_DEBOUNCE_MS = 125


class SettingsToolbarSearchBox(SearchLineEdit):  # type: ignore[misc]
    """Emit debounced Settings search queries from shell chrome."""

    searchQueryChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the toolbar search field with Settings-specific chrome."""

        super().__init__(parent)
        self.setObjectName(SETTINGS_TOOLBAR_SEARCH_OBJECT_NAME)
        self.setPlaceholderText("Search settings")
        self.setClearButtonEnabled(True)
        self.setFixedWidth(SETTINGS_TOOLBAR_SEARCH_WIDTH)
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(SETTINGS_SEARCH_DEBOUNCE_MS)
        self._search_debounce_timer.timeout.connect(self._emit_debounced_search_query)
        self.textChanged.connect(self._schedule_search_query_emit)

    def search_text(self) -> str:
        """Return the current Settings search text."""

        return str(self.text())

    def set_search_text(self, text: str) -> None:
        """Set the search text without sending a new query request."""

        if self.search_text() == text:
            return
        self.blockSignals(True)
        try:
            self.setText(text)
        finally:
            self.blockSignals(False)

    def _schedule_search_query_emit(self, _query: str) -> None:
        """Debounce Settings search edits before notifying the panel."""

        self._search_debounce_timer.start()

    def _emit_debounced_search_query(self) -> None:
        """Emit the current Settings search text after debounce."""

        self.searchQueryChanged.emit(self.search_text())


__all__ = [
    "SETTINGS_SEARCH_DEBOUNCE_MS",
    "SETTINGS_TOOLBAR_SEARCH_OBJECT_NAME",
    "SETTINGS_TOOLBAR_SEARCH_WIDTH",
    "SettingsToolbarSearchBox",
]
