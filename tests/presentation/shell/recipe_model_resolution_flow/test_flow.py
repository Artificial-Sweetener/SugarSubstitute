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

"""Tests for missing recipe model resolution UI flow coordination."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from substitute.application.civitai import CivitaiCredentialService
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
    CredentialStoreStatus,
)
from substitute.application.recipes import (
    RecipeModelDownloadResolutionService,
    RecipeModelResolutionRequired,
)
from substitute.presentation.dialogs import RecipeModelResolutionAction
from substitute.presentation.shell import recipe_model_resolution_flow


def test_missing_model_resolution_uses_typed_key_once_when_storage_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolver should keep the current download usable when key persistence fails."""

    warnings: list[str] = []
    monkeypatch.setattr(
        recipe_model_resolution_flow,
        "RecipeModelResolutionDialog",
        _DownloadDialog,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(str(message)),
    )

    service = cast(RecipeModelDownloadResolutionService, _DownloadService())
    required = cast(RecipeModelResolutionRequired, object())

    result = recipe_model_resolution_flow.resolve_missing_recipe_models_with_dialog(
        parent=cast(QWidget, object()),
        required=required,
        download_service=service,
        credential_service=CivitaiCredentialService(_UnavailableCredentialStore()),
        open_settings=lambda: None,
    )

    assert isinstance(result, recipe_model_resolution_flow.DeferredRecipeModelDownload)
    assert result.service is service
    assert result.required is required
    assert result.api_key_override == "typed-secret"
    assert warnings
    assert "Secret Service-compatible keyring" in warnings[0]


class _DownloadDialog:
    """Dialog double that selects download with a typed API key."""

    selected_action = RecipeModelResolutionAction.DOWNLOAD

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Accept dialog construction."""

    def exec(self) -> object:
        """Accept the dialog."""

        return QDialog.DialogCode.Accepted

    def entered_api_key(self) -> str:
        """Return a typed API key for the resolver flow."""

        return "typed-secret"


class _DownloadService:
    """Download service double exposing the resolver policy method."""

    def downloads_enabled(self) -> bool:
        """Allow downloads in the fake dialog."""

        return True


class _UnavailableCredentialStore:
    """Credential store double that fails closed on save."""

    def status(self) -> CredentialStoreStatus:
        """Return unavailable Linux storage status."""

        return CredentialStoreStatus(
            available=False,
            backend_name="Linux Secret Service/KWallet",
            reason="No compatible operating-system credential store is available.",
            remediation=(
                "Install and enable GNOME Keyring, KWallet, or another "
                "Secret Service-compatible keyring through your distribution's "
                "package manager, then sign in or unlock it and restart Substitute."
            ),
        )

    def has_api_key(self) -> bool:
        """Return no stored API key."""

        return False

    def load_api_key(self) -> str | None:
        """Return no stored API key."""

        return None

    def save_api_key(self, _api_key: str) -> None:
        """Fail closed because secure storage is unavailable."""

        status = self.status()
        raise CredentialStorageUnavailableError(
            f"Secure credential storage is unavailable. {status.remediation}"
        )

    def clear_api_key(self) -> None:
        """Clear no stored API key."""
