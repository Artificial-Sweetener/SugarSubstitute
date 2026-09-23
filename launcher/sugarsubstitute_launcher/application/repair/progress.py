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

"""Describe completed repair stages independently of presentation and elapsed time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging


_LOGGER = logging.getLogger(__name__)


class RepairStage(str, Enum):
    """Identify work whose completion advances the repair progress contract."""

    VALIDATE_INPUT = "validate_input"
    RESTORE_APPLICATION = "restore_application"
    PREPARE_RUNTIME = "prepare_runtime"
    RESTORE_NODES = "restore_nodes"
    SAVE_STATE = "save_state"
    VALIDATE_APPLICATION = "validate_application"
    PREPARE_COMFY = "prepare_comfy"
    RESTORE_COMFY = "restore_comfy"
    VALIDATE_COMFY = "validate_comfy"


@dataclass(frozen=True, slots=True)
class RepairProgress:
    """Report completed steps and the next active stage, or committed completion."""

    stage: RepairStage | None
    completed: int
    total: int
    activity: bool = False


RepairProgressObserver = Callable[[RepairProgress], None]


class RepairProgressTracker:
    """Advance one planned execution only at its authoritative work boundaries."""

    def __init__(
        self,
        *,
        repair_nodes: bool,
        full_comfy: bool,
        observer: RepairProgressObserver | None,
    ) -> None:
        """Build the exact stage inventory for the verified repair scope."""
        stages = [
            RepairStage.VALIDATE_INPUT,
            RepairStage.RESTORE_APPLICATION,
            RepairStage.PREPARE_RUNTIME,
        ]
        if repair_nodes:
            stages.append(RepairStage.RESTORE_NODES)
        stages.extend((RepairStage.SAVE_STATE, RepairStage.VALIDATE_APPLICATION))
        if full_comfy:
            stages.extend(
                (
                    RepairStage.PREPARE_COMFY,
                    RepairStage.RESTORE_COMFY,
                    RepairStage.VALIDATE_COMFY,
                )
            )
        self._stages = tuple(stages)
        self._position = -1
        self._observer = observer

    def begin(self, stage: RepairStage) -> None:
        """Publish the next stage only after all preceding work has returned."""
        position = self._position + 1
        if position >= len(self._stages) or self._stages[position] is not stage:
            raise ValueError("Repair progress must follow its planned stage order.")
        self._position = position
        self._publish(stage, position)

    def complete(self) -> None:
        """Publish terminal progress only after the final transaction commits."""
        if self._position != len(self._stages) - 1:
            raise ValueError("Repair cannot complete before all planned work.")
        self._position += 1
        self._publish(None, len(self._stages))

    def record_activity(self) -> None:
        """Republish the active boundary when its owner completes an inner work unit."""

        if self._position < 0 or self._position >= len(self._stages):
            raise ValueError("Repair activity requires an active planned stage.")
        self._publish(self._stages[self._position], self._position, activity=True)

    def _publish(
        self,
        stage: RepairStage | None,
        completed: int,
        *,
        activity: bool = False,
    ) -> None:
        """Notify presentation without adding a second progress state owner."""
        if self._observer is not None:
            try:
                self._observer(
                    RepairProgress(stage, completed, len(self._stages), activity)
                )
            except Exception:
                _LOGGER.exception(
                    "Repair progress observer failed; continuing the transaction.",
                    extra={"repair_stage": stage, "completed_steps": completed},
                )
                self._observer = None
