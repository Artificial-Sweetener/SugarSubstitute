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

"""Verify preparation estimates remain bounded by completed authoritative work."""

import pytest

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from sugarsubstitute_shared.asset_transfer import TransferProgress


@pytest.mark.parametrize("total", [None, 0])
def test_unknown_transfer_total_does_not_invent_stage_completion(
    total: int | None,
) -> None:
    """Retain the completed-stage estimate when no usable transfer denominator exists."""
    before = PreparationProgress(PreparationStage.APPLICATION)
    observed = PreparationProgress(
        PreparationStage.APPLICATION, TransferProgress(512, total)
    )
    assert observed.completed_fraction == before.completed_fraction


@pytest.mark.parametrize("completed", [100, 101, 1000])
def test_download_completion_cannot_complete_staging_or_preparation(
    completed: int,
) -> None:
    """Reserve verification and extraction even for excess bytes in an invalid asset."""
    baseline = PreparationProgress(PreparationStage.APPLICATION)
    observed = PreparationProgress(
        PreparationStage.APPLICATION, TransferProgress(completed, 100)
    )
    staged = PreparationProgress(PreparationStage.LAUNCHER)
    assert (
        baseline.completed_fraction
        < observed.completed_fraction
        < staged.completed_fraction
        < 1
    )
