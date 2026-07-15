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

"""Display the single recovery surface for uncertain or failed shutdown."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ShutdownRecoveryDialog(QDialog):
    """Render the retry-or-force-close recovery surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the recovery dialog widgets and button wiring."""

        super().__init__(parent)
        self._allow_close = False
        self.setWindowTitle("Could Not Finish Closing")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(440)

        self.primary_label = QLabel("", self)
        self.secondary_label = QLabel("", self)
        self.warning_label = QLabel(
            "If you close anyway, a background service may still be running.",
            self,
        )
        self.details_toggle_button = QPushButton("Show Details", self)
        self.details_toggle_button.setCheckable(True)
        self.details_label = QLabel("", self)
        self.retry_button = QPushButton("Retry", self)
        self.force_close_button = QPushButton("Close Substitute Anyway", self)

        self.primary_label.setWordWrap(True)
        self.secondary_label.setWordWrap(True)
        self.warning_label.setWordWrap(True)
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details_label.hide()
        self.retry_button.setDefault(True)
        self.details_toggle_button.clicked.connect(self._toggle_details_visibility)

        button_row = QHBoxLayout()
        button_row.addWidget(self.retry_button)
        button_row.addStretch(1)
        button_row.addWidget(self.force_close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(self.primary_label)
        layout.addWidget(self.secondary_label)
        layout.addWidget(self.warning_label)
        layout.addWidget(self.details_toggle_button)
        layout.addWidget(self.details_label)
        layout.addLayout(button_row)

    def show_uncertain_outcome(self, detail_text: str) -> None:
        """Render the recovery copy for an uncertain shutdown outcome."""

        self._set_copy(
            primary_text="Substitute could not confirm that shutdown finished.",
            secondary_text="You can retry shutdown or close Substitute anyway.",
            detail_text=detail_text,
        )

    def show_failed_outcome(self, detail_text: str) -> None:
        """Render the recovery copy for a failed shutdown outcome."""

        self._set_copy(
            primary_text="Substitute could not finish closing completely.",
            secondary_text="You can retry shutdown or close Substitute anyway.",
            detail_text=detail_text,
        )

    def set_retry_callback(self, callback: Callable[[], None]) -> None:
        """Connect the retry action to one coordinator callback."""

        self.retry_button.clicked.connect(callback)

    def set_force_close_callback(self, callback: Callable[[], None]) -> None:
        """Connect the force-close action to one coordinator callback."""

        self.force_close_button.clicked.connect(callback)

    def allow_close(self) -> None:
        """Permit the dialog to close after one explicit coordinator action."""

        self._allow_close = True

    def closeEvent(self, event: QCloseEvent) -> None:
        """Block user-initiated closes while the dialog is active."""

        if not self._allow_close:
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Ignore Escape so the dialog can only close through explicit actions."""

        if not self._allow_close and event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _set_copy(
        self,
        *,
        primary_text: str,
        secondary_text: str,
        detail_text: str,
    ) -> None:
        """Apply one recovery copy set and reset the details expander."""

        self.primary_label.setText(primary_text)
        self.secondary_label.setText(secondary_text)
        self.details_label.setText(detail_text)
        self.details_toggle_button.setChecked(False)
        self.details_toggle_button.setText("Show Details")
        self.details_label.hide()

    def _toggle_details_visibility(self) -> None:
        """Toggle the visibility of the sanitized detail text."""

        details_visible = self.details_toggle_button.isChecked()
        self.details_toggle_button.setText(
            "Hide Details" if details_visible else "Show Details"
        )
        self.details_label.setVisible(details_visible)
