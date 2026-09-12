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

"""Prompt for a CivitAI credential after an authenticated model is chosen."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
)

from substitute.application.civitai import CivitaiCredentialService
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedSubtitleLabel,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_placeholder,
)


class CivitaiApiKeyPromptDialog(QDialog):
    """Collect and securely store a key for one explicit protected download."""

    def __init__(
        self,
        *,
        credential_service: CivitaiCredentialService,
        parent: QWidget,
    ) -> None:
        """Build a focused credential prompt over the suggestion modal."""

        super().__init__(parent)
        self._credential_service = credential_service
        self.setModal(True)
        self.setWindowTitle(render_application_text(app_text("CivitAI API key")))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.addWidget(
            LocalizedSubtitleLabel(
                app_text("This model requires a CivitAI API key"), self
            )
        )
        explanation = LocalizedBodyLabel(
            app_text(
                "Add your key to download this model. The key is stored securely and can be changed later in Settings."
            ),
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.api_key_edit = PasswordLineEdit(self)
        set_localized_placeholder(self.api_key_edit, "Paste CivitAI API key")
        layout.addWidget(self.api_key_edit)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = PushButton(render_application_text(app_text("Cancel")), self)
        cancel.clicked.connect(self.reject)
        self.save_button = PrimaryPushButton(
            render_application_text(app_text("Save and continue")), self
        )
        self.save_button.setEnabled(False)
        self.api_key_edit.textChanged.connect(
            lambda text: self.save_button.setEnabled(bool(text.strip()))
        )
        self.save_button.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

    def request_key(self) -> bool:
        """Return whether a non-empty key was securely stored."""

        return self.exec() == QDialog.DialogCode.Accepted

    def _save(self) -> None:
        """Persist the entered key through the application credential owner."""

        self._credential_service.save_api_key(self.api_key_edit.text())
        self.accept()


__all__ = ["CivitaiApiKeyPromptDialog"]
