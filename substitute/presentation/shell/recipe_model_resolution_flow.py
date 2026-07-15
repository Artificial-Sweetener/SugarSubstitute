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

"""Coordinate the missing recipe model dialog and deferred backend download."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from substitute.application.civitai import CivitaiCredentialService
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
)
from substitute.application.recipes import (
    RecipeModelDownloadResolutionService,
    RecipeModelResolutionRequired,
)
from substitute.presentation.dialogs import (
    RecipeModelResolutionAction,
    RecipeModelResolutionDialog,
)


@dataclass(frozen=True, slots=True)
class DeferredRecipeModelDownload:
    """Carry an approved model-download request for workflow-scoped execution."""

    service: RecipeModelDownloadResolutionService
    required: RecipeModelResolutionRequired
    api_key_override: str | None = None


def resolve_missing_recipe_models_with_dialog(
    *,
    parent: QWidget,
    required: RecipeModelResolutionRequired,
    download_service: RecipeModelDownloadResolutionService | None,
    credential_service: CivitaiCredentialService,
    open_settings: Callable[[], None],
) -> object | None:
    """Show missing-model choices and return a resolved script when completed."""

    downloads_enabled = (
        download_service.downloads_enabled() if download_service is not None else False
    )
    dialog = RecipeModelResolutionDialog(
        required,
        has_api_key=credential_service.has_api_key(),
        downloads_enabled=downloads_enabled,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if dialog.selected_action == RecipeModelResolutionAction.SETTINGS:
        open_settings()
        return None
    if dialog.selected_action != RecipeModelResolutionAction.DOWNLOAD:
        return None
    if download_service is None:
        QMessageBox.warning(
            parent, "Model download unavailable", "Backend downloads are unavailable."
        )
        return None
    entered_key = dialog.entered_api_key()
    api_key_override: str | None = None
    if entered_key:
        try:
            credential_service.save_api_key(entered_key)
        except CredentialStorageUnavailableError as error:
            QMessageBox.warning(parent, "API key not saved", str(error))
            api_key_override = entered_key
    return DeferredRecipeModelDownload(
        service=download_service,
        required=required,
        api_key_override=api_key_override,
    )


def prepare_missing_recipe_model_download(
    *,
    parent: QWidget,
    required: RecipeModelResolutionRequired,
    download_service: RecipeModelDownloadResolutionService | None,
    credential_service: CivitaiCredentialService,
    open_settings: Callable[[], None],
) -> DeferredRecipeModelDownload | None:
    """Prompt for missing-model handling and return a deferred download request."""

    downloads_enabled = (
        download_service.downloads_enabled() if download_service is not None else False
    )
    dialog = RecipeModelResolutionDialog(
        required,
        has_api_key=credential_service.has_api_key(),
        downloads_enabled=downloads_enabled,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if dialog.selected_action == RecipeModelResolutionAction.SETTINGS:
        open_settings()
        return None
    if dialog.selected_action != RecipeModelResolutionAction.DOWNLOAD:
        return None
    if download_service is None:
        QMessageBox.warning(
            parent, "Model download unavailable", "Backend downloads are unavailable."
        )
        return None
    entered_key = dialog.entered_api_key()
    api_key_override: str | None = None
    if entered_key:
        try:
            credential_service.save_api_key(entered_key)
        except CredentialStorageUnavailableError as error:
            QMessageBox.warning(parent, "API key not saved", str(error))
            api_key_override = entered_key
    return DeferredRecipeModelDownload(
        service=download_service,
        required=required,
        api_key_override=api_key_override,
    )


__all__ = [
    "DeferredRecipeModelDownload",
    "prepare_missing_recipe_model_download",
    "resolve_missing_recipe_models_with_dialog",
]
