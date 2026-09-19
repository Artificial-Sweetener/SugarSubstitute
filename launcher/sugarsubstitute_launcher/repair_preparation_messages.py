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

"""Map preparation observations without duplicating stage estimation policy."""

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from sugarsubstitute_shared.asset_transfer import TransferProgress


def preparation_progress_to_message(progress: PreparationProgress) -> dict[str, object]:
    """Publish stage identity and measured bytes independently of presentation."""
    transfer = progress.transfer
    return {
        "kind": "progress",
        "stage": progress.stage.value,
        "transfer": None
        if transfer is None
        else {
            "completed_bytes": transfer.completed_bytes,
            "total_bytes": transfer.total_bytes,
        },
    }


def preparation_progress_from_message(
    message: dict[str, object],
) -> PreparationProgress:
    """Validate worker observations before the UI derives its estimated progress."""
    stage_value = message.get("stage")
    if (
        set(message) != {"kind", "stage", "transfer"}
        or message.get("kind") != "progress"
        or not isinstance(stage_value, str)
    ):
        raise ValueError("Repair preparation progress is malformed.")
    stage = PreparationStage(stage_value)
    transfer_value = message["transfer"]
    if transfer_value is None:
        return PreparationProgress(stage)
    if (
        stage not in {PreparationStage.APPLICATION, PreparationStage.LAUNCHER}
        or not isinstance(transfer_value, dict)
        or set(transfer_value) != {"completed_bytes", "total_bytes"}
    ):
        raise ValueError("Repair preparation transfer is malformed.")
    completed, total = transfer_value["completed_bytes"], transfer_value["total_bytes"]
    if type(completed) is not int or completed < 0:
        raise ValueError("Repair preparation byte count is malformed.")
    if total is not None and (type(total) is not int or total < 0):
        raise ValueError("Repair preparation byte total is malformed.")
    return PreparationProgress(stage, TransferProgress(completed, total))
