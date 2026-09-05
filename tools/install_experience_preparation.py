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

"""Simulate staged background ComfyUI preparation for qualification."""

from __future__ import annotations

from collections.abc import Callable
import threading

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.execution import CancellationToken
from substitute.application.onboarding import OnboardingDraftState
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationKey,
    OnboardingPreparationResult,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupTaskId,
    SetupTaskState,
)


class SyntheticBackgroundPreparationService:
    """Expose a controllable preparation barrier without external work."""

    def __init__(self, *, hold_until_released: bool) -> None:
        """Create start/release events for before/after-choice scenarios."""

        self.started = threading.Event()
        self.completed = threading.Event()
        self.release = threading.Event()
        if not hold_until_released:
            self.release.set()

    def prepare(
        self,
        *,
        draft: OnboardingDraftState,
        generation: int,
        on_progress: Callable[[SetupProgressEvent], None],
        on_log: Callable[[ApplicationText], None],
        cancellation: CancellationToken | None = None,
    ) -> OnboardingPreparationResult:
        """Publish typed phases and wait only for the controlled test barrier."""

        self.started.set()
        _publish_phase(
            on_progress,
            generation,
            SetupTaskId.RUNTIME,
            app_text("Preparing the simulated runtime in the background."),
        )
        on_log(app_text("Synthetic background preparation started."))
        while not self.release.wait(timeout=0.02):
            if cancellation is not None and cancellation.is_cancelled:
                raise RuntimeError("Synthetic background preparation was cancelled.")
        _publish_phase(
            on_progress,
            generation,
            SetupTaskId.COMFY_WORKSPACE,
            app_text("Preparing simulated ComfyUI files in the background."),
        )
        for task_id in (SetupTaskId.RUNTIME, SetupTaskId.COMFY_WORKSPACE):
            on_progress(
                SetupProgressEvent(
                    generation,
                    task_id,
                    SetupTaskState.COMPLETED,
                    app_text("Synthetic background preparation is ready."),
                )
            )
        result = OnboardingPreparationResult(
            generation,
            OnboardingPreparationKey.from_draft(draft),
        )
        self.completed.set()
        return result


def _publish_phase(
    callback: Callable[[SetupProgressEvent], None],
    generation: int,
    task_id: SetupTaskId,
    message: ApplicationText,
) -> None:
    """Publish one indeterminate background phase."""

    callback(
        SetupProgressEvent(
            generation,
            task_id,
            SetupTaskState.RUNNING,
            message,
        )
    )


__all__ = ["SyntheticBackgroundPreparationService"]
