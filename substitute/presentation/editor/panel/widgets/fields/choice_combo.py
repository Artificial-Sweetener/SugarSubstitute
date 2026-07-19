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

"""Render and reconcile ordinary finite-choice fields in the editor."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets import ComboBox

EMPTY_CHOICE_PLACEHOLDER = "No options available"


class EditorChoiceComboBox(ComboBox):
    """Own editor choice rows, empty presentation, and silent replacement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize an editor combo with no backend-value mappings."""

        super().__init__(parent)
        self._editor_choice_values_by_label: dict[str, object] = {}

    def reconcile_choice_items(
        self,
        items: Sequence[tuple[str, object]],
        selected_label: str,
    ) -> None:
        """Replace choices without emitting signals or creating an invalid item."""

        previous_block_state = self.blockSignals(True)
        try:
            self.clear()
            self._editor_choice_values_by_label = dict(items)
            self.addItems([label for label, _value in items])
            has_options = bool(items)
            self.setEnabled(has_options)
            self.setPlaceholderText("" if has_options else EMPTY_CHOICE_PLACEHOLDER)
            if has_options:
                self.setCurrentText(selected_label or items[0][0])
        finally:
            self.blockSignals(previous_block_state)

    def editor_choice_value(self, label: str) -> object | None:
        """Return the backend value represented by one visible label."""

        return self._editor_choice_values_by_label.get(label)


__all__ = ["EMPTY_CHOICE_PLACEHOLDER", "EditorChoiceComboBox"]
