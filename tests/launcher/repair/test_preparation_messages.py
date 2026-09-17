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

"""Preserve measured preparation progress through bounded process observations."""

import pytest

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    RepairFrameDecoder,
    encode_repair_frame,
)
from launcher.sugarsubstitute_launcher.repair_preparation_messages import (
    preparation_progress_from_message,
    preparation_progress_to_message,
)
from sugarsubstitute_shared.asset_transfer import TransferProgress


@pytest.mark.parametrize("stage", tuple(PreparationStage))
def test_stage_round_trip_retains_estimated_progress(stage: PreparationStage) -> None:
    """Keep stage estimation with its domain owner across real frame encoding."""
    progress = PreparationProgress(stage)
    frames = RepairFrameDecoder().feed(
        encode_repair_frame(preparation_progress_to_message(progress))
    )
    restored = preparation_progress_from_message(frames[0])
    assert restored == progress
    assert restored.completed_fraction == progress.completed_fraction


@pytest.mark.parametrize(
    "stage", [PreparationStage.APPLICATION, PreparationStage.LAUNCHER]
)
@pytest.mark.parametrize(
    "transfer",
    [
        TransferProgress(0, None),
        TransferProgress(12, None),
        TransferProgress(0, 0),
        TransferProgress(4, 10),
        TransferProgress(12, 10),
    ],
)
def test_transfer_round_trip_retains_actual_bytes(
    stage: PreparationStage, transfer: TransferProgress
) -> None:
    """Preserve unknown and exceeded advertised sizes without fabricating completion."""
    progress = PreparationProgress(stage, transfer)
    restored = preparation_progress_from_message(
        preparation_progress_to_message(progress)
    )
    assert restored == progress
    assert restored.completed_fraction < 1


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"kind": "progress", "stage": "unknown", "transfer": None},
        {"kind": "progress", "stage": None, "transfer": None},
        {"kind": "succeeded", "stage": "ready", "transfer": None},
        {"kind": "progress", "stage": "application", "transfer": {}},
        {
            "kind": "progress",
            "stage": "application",
            "transfer": {"completed_bytes": True, "total_bytes": 1},
        },
        {
            "kind": "progress",
            "stage": "application",
            "transfer": {"completed_bytes": -1, "total_bytes": None},
        },
        {
            "kind": "progress",
            "stage": "application",
            "transfer": {"completed_bytes": 1, "total_bytes": False},
        },
        {
            "kind": "progress",
            "stage": "application",
            "transfer": {"completed_bytes": 1, "total_bytes": -2},
        },
        {
            "kind": "progress",
            "stage": "ready",
            "transfer": {"completed_bytes": 1, "total_bytes": 1},
        },
        {"kind": "progress", "stage": "release", "transfer": []},
    ],
)
def test_invalid_observations_cannot_publish_progress(
    message: dict[str, object],
) -> None:
    """Reject malformed domain values before emitting them into the Qt presentation."""
    with pytest.raises(ValueError):
        preparation_progress_from_message(message)
