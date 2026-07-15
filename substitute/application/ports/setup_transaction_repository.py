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

"""Define persistence for pending setup transactions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.onboarding.setup_transaction_models import SetupTransaction


class SetupTransactionRepositoryError(RuntimeError):
    """Report unreadable or invalid pending setup transaction state."""


@runtime_checkable
class SetupTransactionRepository(Protocol):
    """Load and save pending setup state outside active configuration files."""

    def exists(self) -> bool:
        """Return whether a pending setup transaction exists."""

    def load(self) -> SetupTransaction | None:
        """Load the pending setup transaction when one exists."""

    def save(self, transaction: SetupTransaction) -> None:
        """Persist one pending setup transaction."""

    def delete(self) -> None:
        """Remove pending setup transaction state."""


__all__ = ["SetupTransactionRepository", "SetupTransactionRepositoryError"]
