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

"""Describe completed preparation work independently of presentation and elapsed time."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from sugarsubstitute_shared.asset_transfer import TransferProgress


class PreparationStage(str, Enum):
    """Name the ordered immutable operations required before repair can begin."""

    RELEASE = "release"
    APPLICATION = "application"
    LAUNCHER = "launcher"
    VERIFY_APPLICATION = "verify_application"
    VERIFY_LAUNCHER = "verify_launcher"
    HELPER = "helper"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class PreparationProgress:
    """Project completed preparation stages without estimating progress from time."""

    stage: PreparationStage
    transfer: TransferProgress | None = None

    @property
    def completed_fraction(self) -> float:
        """Estimate stages, reserving half of asset staging for verification/extraction.

        Only measured bytes advance the transfer share. Unknown-size transfers
        retain the completed-stage estimate until the stager actually returns.
        Completing a download cannot complete preparation or its staging phase.
        """
        stages = tuple(PreparationStage)
        completed = float(stages.index(self.stage))
        if (
            self.stage in {PreparationStage.APPLICATION, PreparationStage.LAUNCHER}
            and self.transfer is not None
            and self.transfer.total_bytes is not None
            and self.transfer.total_bytes > 0
        ):
            completed += 0.5 * min(
                1.0, max(0.0, self.transfer.completed_bytes / self.transfer.total_bytes)
            )
        return completed / (len(stages) - 1)
