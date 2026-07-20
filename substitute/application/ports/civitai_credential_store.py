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

"""Define secure storage contract for CivitAI credentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sugarsubstitute_shared.localization import ApplicationText


@dataclass(frozen=True, slots=True)
class CredentialStoreStatus:
    """Describe secure credential persistence availability and remediation."""

    available: bool
    backend_name: str
    reason: ApplicationText | None = None
    remediation: ApplicationText | None = None


class CredentialStorageUnavailableError(RuntimeError):
    """Raised when secure credential persistence is unavailable."""


@runtime_checkable
class CivitaiCredentialStore(Protocol):
    """Store the CivitAI API key without exposing plaintext persistence."""

    def status(self) -> CredentialStoreStatus:
        """Return secure credential storage availability and remediation."""

    def has_api_key(self) -> bool:
        """Return whether an API key is configured."""

    def load_api_key(self) -> str | None:
        """Return the configured API key when secure storage can decrypt it."""

    def save_api_key(self, api_key: str) -> None:
        """Store one API key through the secure platform store."""

    def clear_api_key(self) -> None:
        """Remove the configured API key."""


__all__ = [
    "CivitaiCredentialStore",
    "CredentialStorageUnavailableError",
    "CredentialStoreStatus",
]
