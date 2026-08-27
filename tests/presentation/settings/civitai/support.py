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

"""Provide in-memory CivitAI boundary fakes for Settings tests."""

from __future__ import annotations

from substitute.application.ports.civitai_cache_repository import CivitaiCacheSummary
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
    CredentialStoreStatus,
)


class MemoryCivitaiCredentialStore:
    """Keep CivitAI credentials in process memory."""

    def __init__(self, *, status: CredentialStoreStatus | None = None) -> None:
        """Initialize with no saved API key."""

        self.saved_key: str | None = None
        self._status = status or CredentialStoreStatus(
            available=True,
            backend_name="Test secure store",
        )

    def status(self) -> CredentialStoreStatus:
        """Return configured storage availability."""

        return self._status

    def has_api_key(self) -> bool:
        """Return whether an API key is saved."""

        return self.saved_key is not None

    def load_api_key(self) -> str | None:
        """Return the saved API key."""

        return self.saved_key

    def save_api_key(self, api_key: str) -> None:
        """Save an API key when secure storage is available."""

        if not self._status.available:
            raise CredentialStorageUnavailableError(
                "Secure credential storage is unavailable."
            )
        self.saved_key = api_key

    def clear_api_key(self) -> None:
        """Clear the saved API key."""

        self.saved_key = None


class RecordingCivitaiCacheRepository:
    """Return a stable summary while recording cache mutations."""

    def __init__(self) -> None:
        """Initialize an empty action log."""

        self.actions: list[str] = []

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return a deterministic cache summary."""

        return CivitaiCacheSummary(
            provider_record_count=1,
            thumbnail_source_count=2,
            thumbnail_variant_count=3,
            thumbnail_bytes=4,
        )

    def clear_civitai_thumbnails(self) -> None:
        """Record thumbnail clearing."""

        self.actions.append("clear-thumbnails")

    def clear_civitai_metadata(self) -> None:
        """Record metadata clearing."""

        self.actions.append("clear-metadata")
