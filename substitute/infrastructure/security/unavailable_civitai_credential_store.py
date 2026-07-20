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

"""Fail-closed CivitAI credential store for unavailable secure storage."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.localization import (
    ApplicationText,
    render_source_application_text,
)

from substitute.application.ports.civitai_credential_store import (
    CivitaiCredentialStore,
    CredentialStorageUnavailableError,
    CredentialStoreStatus,
)


@dataclass(frozen=True, slots=True)
class UnavailableCivitaiCredentialStore(CivitaiCredentialStore):
    """Report unavailable secure storage without persisting plaintext secrets."""

    backend_name: str
    reason: ApplicationText
    remediation: ApplicationText

    def status(self) -> CredentialStoreStatus:
        """Return the configured unavailable storage status."""

        return CredentialStoreStatus(
            available=False,
            backend_name=self.backend_name,
            reason=self.reason,
            remediation=self.remediation,
        )

    def has_api_key(self) -> bool:
        """Return false because unavailable storage cannot expose credentials."""

        return False

    def load_api_key(self) -> str | None:
        """Return no credential when secure storage is unavailable."""

        return None

    def save_api_key(self, _api_key: str) -> None:
        """Reject persistence because no secure store is available."""

        raise CredentialStorageUnavailableError(_status_message(self.status()))

    def clear_api_key(self) -> None:
        """Treat clearing unavailable secure storage as an idempotent no-op."""


def _status_message(status: CredentialStoreStatus) -> str:
    """Return a user-safe unavailable storage message."""

    parts = ["Secure credential storage is unavailable."]
    if status.reason:
        parts.append(render_source_application_text(status.reason))
    if status.remediation:
        parts.append(render_source_application_text(status.remediation))
    return " ".join(parts)


__all__ = ["UnavailableCivitaiCredentialStore"]
