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

"""Load optional onboarding draft inputs without aborting the setup surface."""

from __future__ import annotations

from typing import Protocol

from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepositoryError,
)
from substitute.domain.onboarding import SetupTransaction
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.onboarding.draft_load_support")


class PendingTransactionLoader(Protocol):
    """Load the current pending setup transaction."""

    def load(self) -> SetupTransaction | None:
        """Return pending state when present."""


class CredentialPresenceReader(Protocol):
    """Report secure CivitAI credential presence."""

    def has_api_key(self) -> bool:
        """Return whether an API key exists without exposing it."""


def load_pending_transaction_safely(
    service: PendingTransactionLoader,
) -> SetupTransaction | None:
    """Ignore corrupt pending state while preserving diagnostics."""

    try:
        return service.load()
    except SetupTransactionRepositoryError as error:
        log_warning(
            _LOGGER,
            "Pending setup transaction could not be loaded for draft prefill.",
            error=error,
        )
        return None


def credential_is_configured(service: CredentialPresenceReader) -> bool:
    """Return secure credential presence without exposing the stored key."""

    try:
        return service.has_api_key()
    except Exception as error:
        log_warning(
            _LOGGER,
            "CivitAI API key status could not be loaded for onboarding.",
            error=error,
        )
        return False


__all__ = [
    "CredentialPresenceReader",
    "PendingTransactionLoader",
    "credential_is_configured",
    "load_pending_transaction_safely",
]
