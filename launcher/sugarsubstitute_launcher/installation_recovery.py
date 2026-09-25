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

"""Coordinate persisted installation transactions before admitting new work."""

from __future__ import annotations
import logging

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateRecoveryError,
    update_journal_paths,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationOwnership,
    installation_mutation,
)
from sugarsubstitute_shared.repair_recovery.execution import recover_interrupted_repair
from sugarsubstitute_shared.repair_recovery.journal import PENDING_JOURNAL

_LOGGER = logging.getLogger(__name__)


class InstallationRecovery:
    """Restore repair boundaries before resolving their prior payload activation."""

    def __init__(self, layout: InstallLayout) -> None:
        """Bind all recovery participants to one installation identity."""
        self._layout = layout

    @property
    def pending(self) -> bool:
        """Detect journal presence without trusting or interpreting recovery data."""
        return (self._layout.root / PENDING_JOURNAL).exists() or any(
            path.exists() for path in update_journal_paths(self._layout)
        )

    def recover(
        self, *, ownership: InstallationMutationOwnership | None = None
    ) -> bool:
        """Resolve both journal families under one uninterrupted native owner."""
        with installation_mutation(self._layout.root, ownership=ownership) as operation:
            repair_recovered = recover_interrupted_repair(
                self._layout.root, ownership=operation
            )
            update_recovered = recover_interrupted_update(
                self._layout, ownership=operation
            )
            return repair_recovered or update_recovered

    def recover_for_repair(
        self, *, ownership: InstallationMutationOwnership | None = None
    ) -> bool:
        """Recover safe transactions while leaving an unreadable update for quarantine."""

        with installation_mutation(self._layout.root, ownership=ownership) as operation:
            repair_recovered = recover_interrupted_repair(
                self._layout.root, ownership=operation
            )
            try:
                update_recovered = recover_interrupted_update(
                    self._layout, ownership=operation
                )
            except UpdateRecoveryError:
                _LOGGER.warning(
                    "Deferring incompatible update journal to transactional repair",
                    exc_info=True,
                    extra={"install_root": str(self._layout.root)},
                )
                update_recovered = False
            return repair_recovered or update_recovered
