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

"""Coordinate CivitAI API key storage and validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.model_metadata.ports import CivitaiMetadataGateway
from substitute.application.ports.civitai_credential_store import (
    CivitaiCredentialStore,
    CredentialStoreStatus,
)
from substitute.domain.model_metadata import CivitaiLookupStatus

_CIVITAI_TEST_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


@dataclass(frozen=True, slots=True)
class CivitaiApiKeyTestResult:
    """Describe the result of testing stored CivitAI credentials."""

    succeeded: bool
    message: str


class CivitaiCredentialService:
    """Own CivitAI API key use cases without exposing persisted plaintext."""

    def __init__(
        self,
        store: CivitaiCredentialStore,
        *,
        validation_client_factory: (
            Callable[[str], CivitaiMetadataGateway] | None
        ) = None,
    ) -> None:
        """Store credential collaborators.

        Args:
            store: Secure credential storage adapter.
            validation_client_factory: Optional factory used by tests and bootstrap to
                create an authenticated CivitAI client.
        """

        self._store = store
        self._validation_client_factory = validation_client_factory

    def has_api_key(self) -> bool:
        """Return whether a CivitAI API key is configured."""

        return self._store.has_api_key()

    def load_api_key(self) -> str | None:
        """Return the configured CivitAI API key when available."""

        return self._store.load_api_key()

    def storage_status(self) -> CredentialStoreStatus:
        """Return secure credential storage availability and remediation."""

        return self._store.status()

    def save_api_key(self, api_key: str) -> None:
        """Persist a non-empty CivitAI API key."""

        stripped_key = api_key.strip()
        if not stripped_key:
            raise ValueError("CivitAI API key cannot be empty.")
        self._store.save_api_key(stripped_key)

    def clear_api_key(self) -> None:
        """Remove the configured CivitAI API key."""

        self._store.clear_api_key()

    def test_api_key(self, api_key: str | None = None) -> CivitaiApiKeyTestResult:
        """Validate one API key with a lightweight CivitAI request."""

        candidate_key = (api_key or self._store.load_api_key() or "").strip()
        if not candidate_key:
            return CivitaiApiKeyTestResult(
                succeeded=False,
                message="No CivitAI API key is configured.",
            )
        if self._validation_client_factory is None:
            return CivitaiApiKeyTestResult(
                succeeded=True,
                message="CivitAI API key is stored.",
            )
        result = self._validation_client_factory(
            candidate_key
        ).lookup_model_version_by_hash(_CIVITAI_TEST_HASH)
        if result.status in {
            CivitaiLookupStatus.NOT_FOUND,
            CivitaiLookupStatus.FOUND,
        }:
            return CivitaiApiKeyTestResult(
                succeeded=True,
                message="CivitAI API key works.",
            )
        return CivitaiApiKeyTestResult(
            succeeded=False,
            message=result.error or "CivitAI API key test failed.",
        )


__all__ = ["CivitaiApiKeyTestResult", "CivitaiCredentialService"]
