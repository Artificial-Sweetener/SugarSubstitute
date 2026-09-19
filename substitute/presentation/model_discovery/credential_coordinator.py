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

"""Route protected model selections to provider-owned credential prompts."""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from PySide6.QtWidgets import QWidget

from substitute.application.civitai import CivitaiCredentialService
from substitute.domain.model_suggestions import ModelSuggestion, ModelSuggestionAccess
from substitute.presentation.model_discovery.credential_prompt import (
    CivitaiApiKeyPromptDialog,
)


class ModelSuggestionCredentialHandler(Protocol):
    """Authorize protected downloads for one model provider."""

    @property
    def provider_id(self) -> str:
        """Return the provider identity handled by this credential flow."""

    def has_credential(self) -> bool:
        """Return whether the provider credential is already configured."""

    def request_credential(self, parent: QWidget) -> bool:
        """Request and securely store a credential after explicit selection."""


class CivitaiModelSuggestionCredentialHandler:
    """Authorize protected CivitAI choices through secure key storage."""

    provider_id = "civitai"

    def __init__(self, credential_service: CivitaiCredentialService) -> None:
        """Store the application credential owner."""

        self._credential_service = credential_service

    def has_credential(self) -> bool:
        """Return whether a CivitAI key is already configured."""

        return self._credential_service.has_api_key()

    def request_credential(self, parent: QWidget) -> bool:
        """Prompt for and securely store a CivitAI key."""

        dialog = CivitaiApiKeyPromptDialog(
            credential_service=self._credential_service,
            parent=parent,
        )
        try:
            return dialog.request_key()
        finally:
            dialog.deleteLater()


class ModelSuggestionCredentialCoordinator:
    """Authorize protected suggestions through a provider handler registry."""

    def __init__(
        self,
        handlers: Collection[ModelSuggestionCredentialHandler],
    ) -> None:
        """Register uniquely identified provider credential handlers."""

        self._handlers = {handler.provider_id: handler for handler in handlers}
        if len(self._handlers) != len(handlers):
            raise ValueError("Model credential provider identities must be unique.")

    def authorize(self, suggestion: ModelSuggestion, parent: QWidget) -> bool:
        """Authorize public choices or run the selected provider's credential flow."""

        if suggestion.access is ModelSuggestionAccess.PUBLIC:
            return True
        provider_id = suggestion.reference.provider_id
        handler = self._handlers.get(provider_id)
        if handler is None:
            raise RuntimeError(
                f"No credential flow is available for model provider: {provider_id}"
            )
        return handler.has_credential() or handler.request_credential(parent)


__all__ = [
    "CivitaiModelSuggestionCredentialHandler",
    "ModelSuggestionCredentialCoordinator",
    "ModelSuggestionCredentialHandler",
]
