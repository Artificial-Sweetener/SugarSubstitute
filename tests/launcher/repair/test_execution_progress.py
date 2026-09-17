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

"""Validate execution-domain observations independently of byte framing."""

import pytest
from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgress,
    RepairStage,
)
from launcher.sugarsubstitute_launcher.repair_execution_progress import (
    repair_progress_from_message,
    repair_progress_to_message,
)


@pytest.mark.parametrize(
    "message",
    [
        {"stage": "validate_input", "completed": True, "total": 1},
        {"stage": "validate_input", "completed": 0, "total": 0},
        {"stage": "validate_input", "completed": 2, "total": 1},
        {"stage": "unknown", "completed": 0, "total": 1},
        {"stage": None, "completed": 0, "total": 1},
        {"stage": "validate_input", "completed": 1, "total": 1},
    ],
)
def test_progress_rejects_invalid_domain_observations(
    message: dict[str, object],
) -> None:
    """Keep malformed process data from fabricating progress or completion."""
    with pytest.raises(ValueError):
        repair_progress_from_message(message)


def test_progress_accepts_committed_completion() -> None:
    """Retain the executor's final completed stage count without inventing a stage."""
    progress = repair_progress_from_message({"stage": None, "completed": 3, "total": 3})
    assert progress.stage is None
    assert progress.completed == progress.total == 3


def test_execution_progress_round_trip_retains_authoritative_counts() -> None:
    """Preserve stage identity and measured completion across producer and consumer."""
    progress = RepairProgress(RepairStage.VALIDATE_INPUT, 0, 5)
    message = repair_progress_to_message(progress)
    assert message["kind"] == "progress"
    assert repair_progress_from_message(message) == progress
