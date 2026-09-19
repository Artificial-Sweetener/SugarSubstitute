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

"""Install a confirmed model plan before onboarding validation and commit."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.model_acquisition import CancellationProbe

from substitute.application.execution import CancellationToken
from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)
from substitute.domain.model_recommendations import (
    ModelInstallPlan,
    ModelInstallProgress,
)


class ModelInstallServiceProtocol(Protocol):
    """Acquire every file in one confirmed runnable model plan."""

    def acquire(
        self,
        plan: ModelInstallPlan,
        *,
        cancellation: CancellationProbe | None = None,
        on_progress: Callable[[ModelInstallProgress], None] | None = None,
    ) -> tuple[object, ...]:
        """Download and verify the selected model plan."""


ModelInstallServiceFactory = Callable[[Path, str | None], ModelInstallServiceProtocol]


class OnboardingModelInstaller:
    """Bridge confirmed recipes into verified acquisition and typed progress."""

    def __init__(self, factory: ModelInstallServiceFactory) -> None:
        """Store the model-root-scoped install-service factory."""

        self._factory = factory

    def install(
        self,
        *,
        plan: ModelInstallPlan | None,
        credential_draft: OnboardingCredentialDraft | None,
        cancellation: CancellationToken | None,
        setup_generation: int,
        on_setup_progress: Callable[[SetupProgressEvent], None] | None,
    ) -> None:
        """Acquire selected files, or publish an explicit skipped transition."""

        if plan is None or not plan.files:
            _emit(
                on_setup_progress,
                SetupProgressEvent(
                    setup_generation,
                    SetupTaskId.MODEL_DOWNLOAD,
                    SetupTaskState.SKIPPED,
                    app_text("No model downloads were selected."),
                ),
            )
            return
        _require_current(cancellation)
        _emit(
            on_setup_progress,
            SetupProgressEvent(
                setup_generation,
                SetupTaskId.MODEL_DOWNLOAD,
                SetupTaskState.RUNNING,
                app_text("Downloading the selected model files."),
            ),
        )
        api_key = (
            credential_draft.civitai_api_key.strip()
            if credential_draft is not None and credential_draft.civitai_api_key.strip()
            else None
        )
        probe = _CancellationProbeAdapter(cancellation) if cancellation else None

        def publish(progress: ModelInstallProgress) -> None:
            """Translate exact acquisition bytes into setup progress."""

            _emit(
                on_setup_progress,
                SetupProgressEvent(
                    generation=setup_generation,
                    task_id=SetupTaskId.MODEL_DOWNLOAD,
                    state=SetupTaskState.RUNNING,
                    message=app_text("Downloading %1", progress.file.display_name),
                    unit=SetupProgressUnit.BYTES,
                    completed_units=progress.aggregate_received_bytes,
                    total_units=progress.aggregate_expected_bytes,
                    current_item=progress.file.display_name,
                    current_item_index=min(
                        progress.completed_files + 1,
                        progress.total_files,
                    ),
                    total_items=progress.total_files,
                ),
            )

        self._factory(plan.model_root, api_key).acquire(
            plan,
            cancellation=probe,
            on_progress=publish,
        )
        _emit(
            on_setup_progress,
            SetupProgressEvent(
                generation=setup_generation,
                task_id=SetupTaskId.MODEL_DOWNLOAD,
                state=SetupTaskState.COMPLETED,
                message=app_text("Selected model files are ready."),
                unit=SetupProgressUnit.BYTES,
                completed_units=plan.total_bytes,
                total_units=plan.total_bytes,
            ),
        )


class _CancellationProbeAdapter:
    """Adapt execution's cancellation property to acquisition's probe method."""

    def __init__(self, token: CancellationToken) -> None:
        """Store the current setup cancellation token."""

        self._token = token

    def is_cancelled(self) -> bool:
        """Return whether setup has been cancelled or superseded."""

        return self._token.is_cancelled


def _require_current(cancellation: CancellationToken | None) -> None:
    """Prevent cancelled or superseded setup work from starting acquisition."""

    if cancellation is not None and cancellation.is_cancelled:
        raise RuntimeError("Onboarding setup was cancelled before model download.")


def _emit(
    callback: Callable[[SetupProgressEvent], None] | None,
    event: SetupProgressEvent,
) -> None:
    """Publish one typed transition when an observer is present."""

    if callback is not None:
        callback(event)


__all__ = [
    "ModelInstallServiceFactory",
    "ModelInstallServiceProtocol",
    "OnboardingModelInstaller",
]
