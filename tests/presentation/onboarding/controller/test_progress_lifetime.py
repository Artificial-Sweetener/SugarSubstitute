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

"""Keep terminal setup outcomes authoritative over delayed active feedback."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
import pytest
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationKey,
    OnboardingPreparationResult,
)
from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingDraftState,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupTaskId,
    SetupTaskState,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyTargetMode,
    ReadinessAssessment,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import OnboardingFlowMode
from sugarsubstitute_shared.localization import ApplicationText
from tests.presentation.onboarding.controller.support import (
    FakeFlowService,
    build_context,
)
from tests.support.execution import ImmediateTaskSubmitter, RecordingDispatcher
from tests.support.qt.lifecycle import ensure_qt_application


class _ProgressFlow(FakeFlowService):
    """Publish real executor callbacks before the configured terminal outcome."""

    def provision(self, **kwargs: object) -> OnboardingCompletionResult:
        """Queue typed progress and diagnostic output through the production boundary."""
        progress = cast(
            Callable[[SetupProgressEvent], None], kwargs["on_setup_progress"]
        )
        progress(
            SetupProgressEvent(
                cast(int, kwargs["setup_generation"]),
                SetupTaskId.RUNTIME,
                SetupTaskState.RUNNING,
                "Preparing runtime",
            )
        )
        log = cast(Callable[[ApplicationText], None], kwargs["on_log"])
        log("Diagnostic output")
        return super().provision(**kwargs)


@pytest.mark.parametrize("fails", [False, True])
def test_finished_setup_rejects_delayed_active_feedback_but_retains_diagnostics(
    tmp_path: Path, owned_controllers: list[OnboardingController], fails: bool
) -> None:
    """Drain delayed owner-thread publications after success or failure settles."""
    ensure_qt_application()
    context = build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow = _ProgressFlow(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=None,
        ),
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", "main.py"),
        ),
        provision_error=RuntimeError("Synthetic setup failure") if fails else None,
    )
    dispatcher = RecordingDispatcher()
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(BootstrapRoute.ONBOARDING, ()),
        flow_service=flow,
        submitter=ImmediateTaskSubmitter(),
        progress_publisher=dispatcher,
    )
    owned_controllers.append(controller)
    events: list[str] = []
    controller.failure_reported.connect(lambda _failure: events.append("failure"))
    controller.completion_ready.connect(lambda _completion: events.append("complete"))
    controller.provisioning_finished.connect(lambda: events.append("finished"))
    controller.progress_status_changed.connect(lambda _message: events.append("status"))
    controller.setup_progress_changed.connect(lambda _event: events.append("progress"))
    controller.progress_log_emitted.connect(
        lambda _message: events.append("diagnostic")
    )
    controller.start_provisioning()
    terminal = ["failure" if fails else "complete", "finished"]
    assert events == terminal
    dispatcher.run_all()
    assert events == [*terminal, "diagnostic"]


class _Preparation:
    """Delay progress and logs from successive preparation operations."""

    def prepare(self, **kwargs: object) -> OnboardingPreparationResult:
        """Publish through supplied production ports before synchronous completion."""
        generation = cast(int, kwargs["generation"])
        progress = cast(Callable[[SetupProgressEvent], None], kwargs["on_progress"])
        progress(
            SetupProgressEvent(
                generation,
                SetupTaskId.RUNTIME,
                SetupTaskState.RUNNING,
                "Preparing runtime",
            )
        )
        log = cast(Callable[[ApplicationText], None], kwargs["on_log"])
        log(f"Preparation {generation}")
        return OnboardingPreparationResult(
            generation,
            OnboardingPreparationKey.from_draft(
                cast(OnboardingDraftState, kwargs["draft"])
            ),
        )


def test_superseded_preparation_cannot_publish_into_the_current_transcript(
    tmp_path: Path, owned_controllers: list[OnboardingController]
) -> None:
    """Drop old preparation publications while retaining settled current diagnostics."""
    ensure_qt_application()
    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow = FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=None,
        ),
        provision_result=None,
    )
    dispatcher = RecordingDispatcher()
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(BootstrapRoute.ONBOARDING, ()),
        flow_service=flow,
        preparation_service=_Preparation(),
        submitter=ImmediateTaskSubmitter(),
        progress_publisher=dispatcher,
    )
    owned_controllers.append(controller)
    logs: list[ApplicationText] = []
    progress: list[object] = []
    controller.progress_log_emitted.connect(logs.append)
    controller.setup_progress_changed.connect(progress.append)
    assert controller.start_background_preparation()
    assert controller.start_background_preparation()
    dispatcher.run_all()
    assert logs == ["Preparation 2"]
    assert progress == []
