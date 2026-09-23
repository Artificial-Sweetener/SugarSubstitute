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

from enum import StrEnum

from PySide6.QtCore import QEvent, QEventLoop, QObject, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
)

from substitute.application.civitai import CivitaiCredentialService
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedSubtitleLabel,
)
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_placeholder,
)


class CredentialPromptChoice(StrEnum):
    """Describe the user's explicit choice in the contained key layer."""

    SAVED = "saved"
    PUBLIC_ONLY = "public_only"
    CANCELLED = "cancelled"


class CivitaiApiKeyPromptDialog(QDialog):
    """Collect and securely store a key for selected protected downloads."""

    def __init__(
        self,
        *,
        credential_service: CivitaiCredentialService,
        parent: QWidget,
        open_url: UrlOpener | None = None,
        protected_model_count: int = 0,
    ) -> None:
        """Build a focused credential prompt over the suggestion modal."""

        super().__init__(parent)
        self._credential_service = credential_service
        self._open_url = open_url or open_external_url
        self._show_public_only = False
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setObjectName("CivitaiApiKeyLayer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QDialog#CivitaiApiKeyLayer { background-color: rgba(0, 0, 0, 180); }"
            "QFrame#CivitaiApiKeyPanel { background-color: #29292d;"
            "border: 1px solid #505056; border-radius: 14px; }"
        )
        self.setWindowTitle(render_application_text(app_text("CivitAI API key")))
        self.setGeometry(parent.rect())
        parent.installEventFilter(self)
        backdrop = QVBoxLayout(self)
        backdrop.addStretch(1)
        panel = QFrame(self)
        panel.setObjectName("CivitaiApiKeyPanel")
        panel.setFixedWidth(560)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        if protected_model_count == 1:
            heading = app_text("This model needs a CivitAI API key")
        elif protected_model_count > 1:
            heading = app_text(
                "%1 selected models need a CivitAI API key",
                protected_model_count,
            )
        else:
            heading = app_text("CivitAI API key")
        title_label = LocalizedSubtitleLabel(heading, panel)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        explanation = LocalizedBodyLabel(
            app_text(
                "Sign in to CivitAI or create an account.\n"
                "Then create an API key in Account Settings and paste it here."
            ),
            panel,
        )
        explanation.setWordWrap(True)
        explanation.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(explanation)
        account_button = PushButton(
            render_application_text(app_text("Open CivitAI account settings")),
            panel,
        )
        account_button.setObjectName("CivitaiAccountSettingsButton")
        account_button.setIcon(FIF.GLOBE)
        account_button.clicked.connect(
            lambda: self._open_url("https://civitai.com/user/account")
        )
        layout.addWidget(account_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.api_key_edit = PasswordLineEdit(panel)
        set_localized_placeholder(self.api_key_edit, "Paste CivitAI API key")
        layout.addWidget(self.api_key_edit)
        self.public_only_button = PushButton(
            render_application_text(app_text("Show models that don't require a key")),
            panel,
        )
        self.public_only_button.clicked.connect(self._choose_public_only)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 10, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)
        self.cancel_button = PushButton(
            render_application_text(app_text("Cancel")), panel
        )
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = PrimaryPushButton(
            render_application_text(app_text("Save and continue")), panel
        )
        self.save_button.setEnabled(False)
        self.api_key_edit.textChanged.connect(
            lambda text: self.save_button.setEnabled(bool(text.strip()))
        )
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.public_only_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        backdrop.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        backdrop.addStretch(1)

    def request_key(self) -> bool:
        """Return whether a non-empty key was securely stored."""

        return self.request_choice() is CredentialPromptChoice.SAVED

    def request_choice(self) -> CredentialPromptChoice:
        """Return whether to save a key, browse public models, or cancel."""

        event_loop = QEventLoop(self)
        self.finished.connect(event_loop.quit)
        self.show()
        self.raise_()
        self.api_key_edit.setFocus()
        event_loop.exec()
        if self.result() == QDialog.DialogCode.Accepted:
            return CredentialPromptChoice.SAVED
        if self._show_public_only:
            return CredentialPromptChoice.PUBLIC_ONLY
        return CredentialPromptChoice.CANCELLED

    def _choose_public_only(self) -> None:
        """Return to discovery with a public-only provider query."""

        self._show_public_only = True
        self.reject()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Keep the credential wash fitted to its parent gallery panel."""

        parent = self.parentWidget()
        if (
            parent is not None
            and watched is parent
            and event.type() is QEvent.Type.Resize
        ):
            self.setGeometry(parent.rect())
        return bool(super().eventFilter(watched, event))

    def _save(self) -> None:
        """Persist the entered key through the application credential owner."""

        self._credential_service.save_api_key(self.api_key_edit.text())
        self.accept()


__all__ = ["CivitaiApiKeyPromptDialog", "CredentialPromptChoice"]
