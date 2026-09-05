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

"""Provide the compact binary choice shared by onboarding questions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text

from substitute.presentation.localization import LocalizedPushButton


class OnboardingBinaryChoice(QWidget):
    """Present an explicit compact Yes/No choice without a field-card wrapper."""

    answer_changed = Signal(bool)

    def __init__(
        self,
        *,
        yes_object_name: str,
        no_object_name: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build two exclusive, checkable push buttons with stable automation names."""

        super().__init__(parent)
        self.setObjectName("OnboardingBinaryChoice")
        self.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.yes_button = LocalizedPushButton(app_text("Yes"), self)
        self.yes_button.setObjectName(yes_object_name)
        self.no_button = LocalizedPushButton(app_text("No"), self)
        self.no_button.setObjectName(no_object_name)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for button in (self.yes_button, self.no_button):
            button.setCheckable(True)
            button.setFixedWidth(76)
            button.setProperty("binarySelected", "false")
            self._group.addButton(button)
            button.toggled.connect(self._publish_answer)
            layout.addWidget(button)

        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def answer(self) -> bool | None:
        """Return the explicit selection or ``None`` before either button is chosen."""

        if self.yes_button.isChecked():
            return True
        if self.no_button.isChecked():
            return False
        return None

    def set_answer(self, answer: bool | None) -> None:
        """Restore a previous answer without inventing a default selection."""

        if answer is None:
            self._group.setExclusive(False)
            self.yes_button.setChecked(False)
            self.no_button.setChecked(False)
            self._group.setExclusive(True)
            return
        (self.yes_button if answer else self.no_button).setChecked(True)

    def _publish_answer(self, checked: bool) -> None:
        """Publish only the button transition that establishes an answer."""

        for button in (self.yes_button, self.no_button):
            selected = button.isChecked()
            button.setProperty("binarySelected", "true" if selected else "false")
            button.setIcon(FIF.ACCEPT_MEDIUM if selected else QIcon())
            button.style().unpolish(button)
            button.style().polish(button)
        if not checked:
            return
        answer = self.answer()
        if answer is not None:
            self.answer_changed.emit(answer)


__all__ = ["OnboardingBinaryChoice"]
