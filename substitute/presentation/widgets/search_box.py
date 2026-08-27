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

"""Provide a context-aware search bar used by the floating editor search view."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import set_localized_placeholder

from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtCore import QObject
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QComboBox as _RuntimeComboBox
    from PySide6.QtWidgets import QLineEdit as _RuntimeSearchLineEdit
else:
    from qfluentwidgets import ComboBox as _RuntimeComboBox  # type: ignore[import-untyped]
    from qfluentwidgets import (  # type: ignore[import-untyped]
        SearchLineEdit as _RuntimeSearchLineEdit,
    )


class ContextSearchBox(QWidget):
    """Combine search text and context selection with command-prefix parsing."""

    contextSearchChanged = Signal(str, str)
    cycleSearchMatchRequested = Signal()
    cycleSearchMatchRequestedBackward = Signal()

    def __init__(
        self, parent: QWidget | None = None, contexts: list[str] | None = None
    ) -> None:
        """Create context combo and search line-edit controls."""

        super().__init__(parent)
        self.setFixedHeight(32)
        self.setContentsMargins(0, 0, 0, 0)

        self.comboBox = _RuntimeComboBox(self)
        self.comboBox.setFixedWidth(80)
        fixed_policy = QSizePolicy.Policy.Fixed
        self.comboBox.setSizePolicy(fixed_policy, fixed_policy)
        self.comboBox.setObjectName("SearchContextComboBox")
        self.comboBox.setFixedHeight(32)

        if contexts is None:
            contexts = ["Text", "Field", "Node"]
        self.comboBox.addItems(contexts)
        self.comboBox.setCurrentIndex(0)

        self.searchLineEdit = _RuntimeSearchLineEdit(self)
        set_localized_placeholder(self.searchLineEdit, "Search…")
        self.searchLineEdit.setFixedHeight(32)
        self.searchLineEdit.setFixedWidth(296)
        self.searchLineEdit.setSizePolicy(fixed_policy, fixed_policy)
        self.searchLineEdit.setTextMargins(self.comboBox.width() - 4, 0, 0, 0)
        self.searchLineEdit.setAlignment(
            cast(
                Any,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
        )

        self.searchLineEdit.move(0, 0)
        self.comboBox.move(0, 0)
        self.comboBox.raise_()

        self.setFixedWidth(self.searchLineEdit.width())

        self.comboBox.currentTextChanged.connect(self._emit_change)
        self.searchLineEdit.textChanged.connect(self._emit_change)
        self.searchLineEdit.installEventFilter(self)

    def resizeEvent(self, event: QEvent) -> None:
        """Keep overlaid combo and search line-edit aligned on resize."""

        self.searchLineEdit.move(0, 0)
        self.comboBox.move(0, 0)
        if hasattr(event, "accept"):
            event.accept()

    def _emit_change(self) -> None:
        """Emit context/query updates and apply `@context` command prefixes."""

        text = self.searchLineEdit.text()
        lowered = text.lower().lstrip()

        command_prefixes = {
            "@text ": "Text",
            "@field ": "Field",
            "@node ": "Node",
        }
        for prefix, context_label in command_prefixes.items():
            if lowered.startswith(prefix):
                stripped = text[len(prefix) :].lstrip()
                self.comboBox.setCurrentText(context_label)
                self.searchLineEdit.setText(stripped)
                return

        if lowered.startswith("@"):
            return

        self.contextSearchChanged.emit(
            self.comboBox.currentText(),
            self.searchLineEdit.text(),
        )

    def context(self) -> str:
        """Return selected context label."""

        return self.comboBox.currentText()

    def searchText(self) -> str:
        """Return current free-text query."""

        return self.searchLineEdit.text()

    def setContext(self, text: str) -> None:
        """Select a context by label when present."""

        index = self.comboBox.findText(text)
        if index >= 0:
            self.comboBox.setCurrentIndex(index)

    def setQuery(self, text: str) -> None:
        """Set query text programmatically."""

        self.searchLineEdit.setText(text)

    def setSearchText(self, text: str) -> None:
        """Set query text programmatically (legacy API name)."""

        self.searchLineEdit.setText(text)

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """Handle Enter/Shift+Enter navigation shortcuts from search line-edit."""

        if source is self.searchLineEdit and event.type() == QEvent.Type.KeyPress:
            key_event = event if isinstance(event, QKeyEvent) else None
            if key_event is None:
                return False
            if key_event.key() in {Qt.Key.Key_Enter, Qt.Key.Key_Return}:
                if self.context() == "Text":
                    if key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.cycleSearchMatchRequestedBackward.emit()
                    else:
                        self.cycleSearchMatchRequested.emit()
                    return True
        return bool(super().eventFilter(source, event))


__all__ = [
    "ContextSearchBox",
]
