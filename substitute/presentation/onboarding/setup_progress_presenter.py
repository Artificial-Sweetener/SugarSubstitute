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

"""Project typed setup events into the progress-first onboarding page."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.presentation.localization import apply_application_text

from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)
from substitute.presentation.onboarding.onboarding_completion_pages import (
    ProvisioningPage,
)


_VISIBLE_TASKS: tuple[SetupTaskId, ...] = (
    SetupTaskId.CONFIGURATION,
    SetupTaskId.RUNTIME,
    SetupTaskId.COMFY_WORKSPACE,
    SetupTaskId.MODEL_DOWNLOAD,
    SetupTaskId.VALIDATION,
    SetupTaskId.COMMIT,
)
_FINISHED_STATES = {SetupTaskState.COMPLETED, SetupTaskState.SKIPPED}


@dataclass(frozen=True, slots=True)
class SetupProgressSnapshot:
    """Describe exact task completion and optional measured model bytes."""

    completed_tasks: int
    total_tasks: int
    active: bool
    model_completed_bytes: int | None = None
    model_total_bytes: int | None = None
    model_current_item: str | None = None
    model_current_item_index: int | None = None
    model_total_items: int | None = None
    model_complete: bool = False


class SetupProgressPresenter:
    """Own one provisioning generation's progress projection and rendering."""

    def __init__(self, page: ProvisioningPage) -> None:
        """Store the progress page and initialize an empty task projection."""

        self._page = page
        self._generation: int | None = None
        self._states: dict[SetupTaskId, SetupTaskState] = {}
        self._model_measurement: (
            tuple[
                int,
                int,
                str | None,
                int | None,
                int | None,
            ]
            | None
        ) = None

    def begin(self) -> None:
        """Start a new final provisioning projection."""

        self._generation = None
        self._states.clear()
        self._model_measurement = None
        self._page.reset_progress()
        self._page.begin_progress()
        self._render()

    def accept(self, event: object) -> bool:
        """Accept one current typed event and reject malformed or stale events."""

        if not isinstance(event, SetupProgressEvent):
            return False
        if self._generation is None:
            self._generation = event.generation
        elif event.generation < self._generation:
            return False
        elif event.generation > self._generation:
            self._generation = event.generation
            self._states.clear()
            self._model_measurement = None

        if event.task_id in _VISIBLE_TASKS:
            previous_state = self._states.get(event.task_id)
            if (
                previous_state not in _FINISHED_STATES
                or event.state in _FINISHED_STATES
            ):
                self._states[event.task_id] = event.state
        if (
            event.task_id is SetupTaskId.MODEL_DOWNLOAD
            and event.unit is SetupProgressUnit.BYTES
            and event.completed_units is not None
            and event.total_units is not None
        ):
            previous_measurement = self._model_measurement
            if previous_measurement is None or (
                event.total_units == previous_measurement[1]
                and event.completed_units >= previous_measurement[0]
            ):
                self._model_measurement = (
                    event.completed_units,
                    event.total_units,
                    event.current_item,
                    event.current_item_index,
                    event.total_items,
                )
        apply_application_text(self._page.status_label, event.message)
        self._render()
        return True

    def snapshot(self) -> SetupProgressSnapshot:
        """Return the current exact progress projection for tests and adapters."""

        completed = sum(
            self._states.get(task_id) in _FINISHED_STATES for task_id in _VISIBLE_TASKS
        )
        active = any(state is SetupTaskState.RUNNING for state in self._states.values())
        measurement = self._model_measurement
        return SetupProgressSnapshot(
            completed_tasks=completed,
            total_tasks=len(_VISIBLE_TASKS),
            active=active,
            model_completed_bytes=(measurement[0] if measurement else None),
            model_total_bytes=(measurement[1] if measurement else None),
            model_current_item=(measurement[2] if measurement else None),
            model_current_item_index=(measurement[3] if measurement else None),
            model_total_items=(measurement[4] if measurement else None),
            model_complete=(
                self._states.get(SetupTaskId.MODEL_DOWNLOAD) in _FINISHED_STATES
            ),
        )

    def _render(self) -> None:
        """Render the current projection without estimating elapsed-time progress."""

        snapshot = self.snapshot()
        self._page.set_progress(
            completed_tasks=snapshot.completed_tasks,
            total_tasks=snapshot.total_tasks,
            active=snapshot.active,
        )
        if (
            snapshot.model_completed_bytes is not None
            and snapshot.model_total_bytes is not None
        ):
            self._page.set_model_download_progress(
                completed_bytes=snapshot.model_completed_bytes,
                total_bytes=snapshot.model_total_bytes,
                current_item=snapshot.model_current_item,
                current_item_index=snapshot.model_current_item_index,
                total_items=snapshot.model_total_items,
                complete=snapshot.model_complete,
            )


__all__ = ["SetupProgressPresenter", "SetupProgressSnapshot"]
