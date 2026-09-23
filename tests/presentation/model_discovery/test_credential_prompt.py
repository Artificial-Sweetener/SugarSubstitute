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

"""Verify explicit protected-model credential collection."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from substitute.application.civitai import CivitaiCredentialService
from substitute.presentation.model_discovery import CivitaiApiKeyPromptDialog
from substitute.presentation.model_discovery.credential_prompt import (
    CredentialPromptChoice,
)
from tests.presentation.settings.civitai.support import MemoryCivitaiCredentialStore


def test_prompt_stores_trimmed_key_only_after_explicit_confirmation() -> None:
    """The protected-download prompt should use the secure credential owner."""

    store = MemoryCivitaiCredentialStore()
    parent = QWidget()
    dialog = CivitaiApiKeyPromptDialog(
        credential_service=CivitaiCredentialService(store),
        parent=parent,
    )

    def confirm() -> None:
        """Enter and explicitly submit one synthetic credential."""

        assert not dialog.isWindow()
        assert dialog.parentWidget() is parent
        dialog.api_key_edit.setText("  synthetic-secret  ")
        dialog.save_button.click()

    QTimer.singleShot(0, confirm)

    assert dialog.request_key()
    assert store.saved_key == "synthetic-secret"
    dialog.deleteLater()
    parent.deleteLater()


def test_prompt_explains_where_to_get_a_key_without_leaving_the_shell() -> None:
    """Keep account guidance and the secure editor in one contained layer."""

    opened_urls: list[str] = []

    def open_account_settings(url: str) -> bool:
        """Record the guidance link without leaving the test shell."""

        opened_urls.append(url)
        return True

    parent = QWidget()
    parent.resize(800, 600)
    parent.show()
    dialog = CivitaiApiKeyPromptDialog(
        credential_service=CivitaiCredentialService(MemoryCivitaiCredentialStore()),
        parent=parent,
        open_url=open_account_settings,
    )
    button = dialog.findChild(QPushButton, "CivitaiAccountSettingsButton")
    assert button is not None
    assert "account settings" in button.text().lower()
    assert any(
        label.text() == "Sign in to CivitAI or create an account.\n"
        "Then create an API key in Account Settings and paste it here."
        for label in dialog.findChildren(QLabel)
    )

    def inspect_and_cancel() -> None:
        """Exercise the external help action without storing a key."""

        assert not dialog.isWindow()
        assert dialog.geometry() == parent.rect()
        button.click()
        dialog.reject()

    QTimer.singleShot(0, inspect_and_cancel)
    assert not dialog.request_key()
    assert opened_urls == ["https://civitai.com/user/account"]
    dialog.deleteLater()
    parent.deleteLater()


def test_prompt_summarizes_multiple_models_and_offers_key_free_results() -> None:
    """Keep the protected-selection explanation compact at any count."""

    store = MemoryCivitaiCredentialStore()
    parent = QWidget()
    dialog = CivitaiApiKeyPromptDialog(
        credential_service=CivitaiCredentialService(store),
        parent=parent,
        protected_model_count=10,
    )
    assert any(
        label.text() == "10 selected models need a CivitAI API key"
        for label in dialog.findChildren(QLabel)
    )
    assert dialog.public_only_button.text() == "Show models that don't require a key"
    QTimer.singleShot(0, dialog.public_only_button.click)

    assert dialog.request_choice() is CredentialPromptChoice.PUBLIC_ONLY
    assert store.saved_key is None
    dialog.deleteLater()
    parent.deleteLater()


def test_prompt_uses_singular_copy_for_one_protected_model() -> None:
    """Avoid exposing a model name or plural wording for one selection."""

    parent = QWidget()
    dialog = CivitaiApiKeyPromptDialog(
        credential_service=CivitaiCredentialService(MemoryCivitaiCredentialStore()),
        parent=parent,
        protected_model_count=1,
    )
    assert any(
        label.text() == "This model needs a CivitAI API key"
        for label in dialog.findChildren(QLabel)
    )
    dialog.deleteLater()
    parent.deleteLater()


def test_prompt_cancellation_never_changes_credentials() -> None:
    """Closing the prompt must not persist the unsubmitted editor value."""

    store = MemoryCivitaiCredentialStore()
    parent = QWidget()
    dialog = CivitaiApiKeyPromptDialog(
        credential_service=CivitaiCredentialService(store),
        parent=parent,
    )

    def cancel() -> None:
        """Enter a value and cancel without invoking the save action."""

        dialog.api_key_edit.setText("not-saved")
        dialog.reject()

    QTimer.singleShot(0, cancel)

    assert not dialog.request_key()
    assert store.saved_key is None
    dialog.deleteLater()
    parent.deleteLater()
