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

"""Define typed, honest setup task progress independent of presentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import time

from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.execution import CancellationToken


class SetupTaskId(str, Enum):
    """Identify stable setup phases used across execution and presentation."""

    RUNTIME = "runtime"
    COMFY_WORKSPACE = "comfy_workspace"
    MODEL_SCAN = "model_scan"
    MODEL_DISCOVERY = "model_discovery"
    MODEL_DOWNLOAD = "model_download"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    COMMIT = "commit"


class SetupTaskState(str, Enum):
    """Identify the lifecycle state of one setup task."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class SetupProgressUnit(str, Enum):
    """Identify trustworthy progress units supplied by a task owner."""

    INDETERMINATE = "indeterminate"
    BYTES = "bytes"
    ITEMS = "items"
    PERCENT = "percent"


@dataclass(frozen=True, slots=True)
class SetupProgressEvent:
    """Describe one ordered setup task transition or measured update."""

    generation: int
    task_id: SetupTaskId
    state: SetupTaskState
    message: ApplicationText
    unit: SetupProgressUnit = SetupProgressUnit.INDETERMINATE
    completed_units: int | None = None
    total_units: int | None = None
    current_item: str | None = None
    diagnostic_reference: str | None = None
    monotonic_timestamp: float = 0.0
    current_item_index: int | None = None
    total_items: int | None = None

    def __post_init__(self) -> None:
        """Reject fabricated, negative, or internally inconsistent measurements."""

        if self.generation < 1:
            raise ValueError("Setup progress generation must be positive.")
        if self.unit is SetupProgressUnit.INDETERMINATE:
            if self.completed_units is not None or self.total_units is not None:
                raise ValueError("Indeterminate progress cannot declare units.")
        elif (
            self.completed_units is None
            or self.total_units is None
            or self.completed_units < 0
            or self.total_units <= 0
            or self.completed_units > self.total_units
        ):
            raise ValueError(
                "Measured setup progress requires valid completed/total units."
            )
        if self.monotonic_timestamp == 0.0:
            object.__setattr__(self, "monotonic_timestamp", time.monotonic())
        if (self.current_item_index is None) != (self.total_items is None):
            raise ValueError("Setup progress item position requires both values.")
        if (
            self.current_item_index is not None
            and self.total_items is not None
            and (
                self.current_item_index < 1
                or self.total_items < 1
                or self.current_item_index > self.total_items
            )
        ):
            raise ValueError("Setup progress item position is outside its total.")


class SetupProgressReporter:
    """Publish generation-bound phase transitions without inventing precision."""

    def __init__(
        self,
        generation: int,
        callback: Callable[[SetupProgressEvent], None] | None,
    ) -> None:
        """Store one setup generation and optional observer."""

        self._generation = generation
        self._callback = callback
        self._current_task_id: SetupTaskId | None = None

    @property
    def current_task_id(self) -> SetupTaskId | None:
        """Return the latest task that published a transition."""

        return self._current_task_id

    def transition(
        self,
        task_id: SetupTaskId,
        state: SetupTaskState,
        message: ApplicationText,
    ) -> None:
        """Publish one honest indeterminate task transition."""

        self._current_task_id = task_id
        if self._callback is not None:
            self._callback(
                SetupProgressEvent(self._generation, task_id, state, message)
            )


def require_setup_current(cancellation: CancellationToken | None) -> None:
    """Prevent cancelled or superseded setup work from committing state."""

    if cancellation is not None and cancellation.is_cancelled:
        raise RuntimeError("Onboarding setup was cancelled before commit.")


__all__ = [
    "SetupProgressEvent",
    "SetupProgressReporter",
    "SetupProgressUnit",
    "SetupTaskId",
    "SetupTaskState",
    "require_setup_current",
]
