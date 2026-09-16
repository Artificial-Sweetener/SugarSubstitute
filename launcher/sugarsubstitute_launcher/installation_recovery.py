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
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    update_journal_path,
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


class InstallationRecovery:
    """Restore repair boundaries before resolving their prior payload activation."""

    def __init__(self, layout: InstallLayout) -> None:
        """Bind all recovery participants to one installation identity."""
        self._layout = layout

    @property
    def pending(self) -> bool:
        """Detect journal presence without trusting or interpreting recovery data."""
        return (self._layout.root / PENDING_JOURNAL).exists() or update_journal_path(
            self._layout
        ).exists()

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
