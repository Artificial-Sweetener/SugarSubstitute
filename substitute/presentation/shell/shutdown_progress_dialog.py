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

"""Display a blocking shutdown surface while Substitute is still closing."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget


class ShutdownProgressDialog(QDialog):
    """Render the delayed in-progress shutdown surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the lightweight shutdown surface and its fixed copy."""

        super().__init__(parent)
        self._allow_close = False
        self.setWindowTitle("Closing Substitute")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(360)

        self.headline_label = QLabel("Closing Substitute...", self)
        self.body_label = QLabel("Please wait a moment.", self)

        self.body_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(self.headline_label)
        layout.addWidget(self.body_label)

    def allow_close(self) -> None:
        """Permit the dialog to close after shutdown completes or is bypassed."""

        self._allow_close = True

    def closeEvent(self, event: QCloseEvent) -> None:
        """Block user-initiated closes while shutdown is still in progress."""

        if not self._allow_close:
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Ignore Escape while shutdown is still active."""

        if not self._allow_close and event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)
