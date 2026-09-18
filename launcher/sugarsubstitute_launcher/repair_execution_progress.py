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

"""Map execution-owned progress to and from inert repair worker observations."""

from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgress,
    RepairStage,
)


def repair_progress_from_message(message: dict[str, object]) -> RepairProgress:
    """Validate the executor's domain progress at the process boundary."""
    stage, completed, total = (
        message.get("stage"),
        message.get("completed"),
        message.get("total"),
    )
    if (
        type(completed) is not int
        or type(total) is not int
        or not 0 <= completed <= total
        or total <= 0
    ):
        raise ValueError("Repair worker progress counts are malformed.")
    if stage is not None and not isinstance(stage, str):
        raise ValueError("Repair worker progress stage is malformed.")
    if (stage is None) != (completed == total):
        raise ValueError("Repair worker progress completion is inconsistent.")
    return RepairProgress(
        RepairStage(stage) if stage is not None else None, completed, total
    )


def repair_progress_to_message(progress: RepairProgress) -> dict[str, object]:
    """Project authoritative execution progress at its process boundary."""
    return {
        "kind": "progress",
        "stage": progress.stage.value if progress.stage is not None else None,
        "completed": progress.completed,
        "total": progress.total,
    }
