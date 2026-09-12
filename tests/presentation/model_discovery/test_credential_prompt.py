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
from PySide6.QtWidgets import QWidget

from substitute.application.civitai import CivitaiCredentialService
from substitute.presentation.model_discovery import CivitaiApiKeyPromptDialog
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

        dialog.api_key_edit.setText("  synthetic-secret  ")
        dialog.save_button.click()

    QTimer.singleShot(0, confirm)

    assert dialog.request_key()
    assert store.saved_key == "synthetic-secret"
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
