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

"""Define the native expansion lifecycle for contextual canvas options."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class CanvasToolOptionsControl(QWidget):
    """Own one options control's authoritative collapsed or expanded state."""

    expandedChanged = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        """Create one initially collapsed contextual control."""

        super().__init__(parent)
        self._expanded = False

    @property
    def expanded(self) -> bool:
        """Return whether the detailed options body is currently exposed."""

        return self._expanded

    def expand(self) -> None:
        """Expose detailed options once."""

        self.set_expanded(True)

    def collapse(self) -> None:
        """Return to the compact top-bar presentation once."""

        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        """Apply one expansion state and notify layout ownership."""

        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.apply_expanded_state(expanded)
        self.updateGeometry()
        self.expandedChanged.emit(expanded)

    def apply_expanded_state(self, expanded: bool) -> None:
        """Project expansion into subclass-owned widgets."""

        raise NotImplementedError


__all__ = ["CanvasToolOptionsControl"]
