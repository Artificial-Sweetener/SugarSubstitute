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

"""Verify background setup preparation and its final-provisioning barrier."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
from typing import cast

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.execution import CancellationToken
from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingDraftState,
)
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationKey,
    OnboardingPreparationResult,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupTaskId,
    SetupTaskState,
)
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_provisioning_submitter_factory,
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
from tests.presentation.onboarding.controller.support import (
    FakeFlowService,
    build_context,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _BlockingPreparationService:
    """Hold choice-independent work until the test releases its barrier."""

    def __init__(self) -> None:
        """Create observable start and release barriers."""

        self.started = threading.Event()
        self.release = threading.Event()

    def prepare(
        self,
        *,
        draft: OnboardingDraftState,
        generation: int,
        on_progress: Callable[[SetupProgressEvent], None],
        on_log: Callable[[ApplicationText], None],
        cancellation: CancellationToken | None = None,
    ) -> OnboardingPreparationResult:
        """Emit typed progress, wait, and return the exact preparation identity."""

        _ = on_log, cancellation
        on_progress(
            SetupProgressEvent(
                generation,
                SetupTaskId.COMFY_WORKSPACE,
                SetupTaskState.RUNNING,
                app_text("Preparing ComfyUI in the background."),
            )
        )
        self.started.set()
        assert self.release.wait(timeout=5)
        return OnboardingPreparationResult(
            generation,
            OnboardingPreparationKey.from_draft(draft),
        )


class _ReplacingPreparationService:
    """Observe cancellation of superseded background preparation."""

    def __init__(self) -> None:
        """Create invocation and cancellation evidence."""

        self.invocations = 0
        self.first_started = threading.Event()
        self.first_cancelled = threading.Event()
        self.second_finished = threading.Event()

    def prepare(
        self,
        *,
        draft: OnboardingDraftState,
        generation: int,
        on_progress: Callable[[SetupProgressEvent], None],
        on_log: Callable[[ApplicationText], None],
        cancellation: CancellationToken | None = None,
    ) -> OnboardingPreparationResult:
        """Wait for cancellation on generation one and finish generation two."""

        _ = on_progress, on_log
        self.invocations += 1
        if generation == 1:
            self.first_started.set()
            for _attempt in range(1000):
                if cancellation is None or cancellation.is_cancelled:
                    break
                threading.Event().wait(timeout=0.005)
            else:
                raise TimeoutError("Superseded preparation was not cancelled.")
            self.first_cancelled.set()
            raise RuntimeError("Superseded preparation stopped.")
        self.second_finished.set()
        return OnboardingPreparationResult(
            generation,
            OnboardingPreparationKey.from_draft(draft),
        )


class _CancellationAwareFlowService(FakeFlowService):
    """Hold final setup until controller shutdown cancels its owned token."""

    def __init__(self, *, draft: OnboardingDraftState) -> None:
        """Create start and cancellation observations without a commit path."""

        super().__init__(draft=draft, provision_result=None)
        self.started = threading.Event()
        self.cancellation_seen = threading.Event()
        self.commit_reached = False

    def provision(self, **kwargs: object) -> OnboardingCompletionResult:
        """Wait for cancellation and fail before the synthetic commit boundary."""

        cancellation = kwargs.get("cancellation")
        assert cancellation is not None
        token = cast(CancellationToken, cancellation)
        self.started.set()
        for _attempt in range(1000):
            if token.is_cancelled:
                break
            threading.Event().wait(timeout=0.005)
        else:
            raise TimeoutError("Provisioning cancellation was not delivered.")
        self.cancellation_seen.set()
        raise RuntimeError("Cancelled setup stopped before commit.")


def test_preparation_runs_while_later_choices_remain_editable_and_blocks_commit(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Background work must not freeze choices or let final setup pass its barrier."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    draft = OnboardingDraftState(
        installation_root=context.install_root,
        target_mode=context.comfy_target.mode.value,
        endpoint_host=context.comfy_target.endpoint.host,
        endpoint_port=context.comfy_target.endpoint.port,
        managed_workspace_path=context.managed_comfy_dir,
        attached_workspace_path=None,
    )
    flow = FakeFlowService(
        draft=draft,
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    preparation = _BlockingPreparationService()
    progress: list[SetupProgressEvent] = []
    completions: list[object] = []
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(BootstrapRoute.ONBOARDING, ()),
        flow_service=flow,
        preparation_service=preparation,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    controller.setup_progress_changed.connect(progress.append)
    controller.completion_ready.connect(completions.append)

    assert controller.start_background_preparation()
    assert preparation.started.wait(timeout=5)
    controller.update_integration_preferences(
        danbooru_tag_help_enabled=False,
        danbooru_safe_previews_enabled=True,
        danbooru_image_rating_policy="safe_only",
        civitai_model_help_enabled=True,
        civitai_downloads_enabled=True,
        civitai_safe_thumbnails_enabled=True,
        civitai_thumbnail_safety_policy="sfw_only",
    )
    controller.start_provisioning()
    assert flow.provision_kwargs == {}
    assert controller.draft.danbooru_tag_help_enabled is False

    preparation.release.set()
    wait_for_qt_condition(lambda: bool(completions), timeout_ms=5000)

    assert progress[0].task_id is SetupTaskId.COMFY_WORKSPACE
    assert flow.provision_kwargs


def test_changed_inputs_cancel_superseded_background_preparation(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Replan a changed workspace without letting stale work publish completion."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    draft = OnboardingDraftState(
        installation_root=context.install_root,
        target_mode=context.comfy_target.mode.value,
        endpoint_host=context.comfy_target.endpoint.host,
        endpoint_port=context.comfy_target.endpoint.port,
        managed_workspace_path=context.managed_comfy_dir,
        attached_workspace_path=None,
    )
    preparation = _ReplacingPreparationService()
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(BootstrapRoute.ONBOARDING, ()),
        flow_service=FakeFlowService(draft=draft, provision_result=None),
        preparation_service=preparation,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    finished: list[object] = []
    controller.background_preparation_finished.connect(finished.append)

    assert controller.start_background_preparation()
    assert preparation.first_started.wait(timeout=5)
    controller.update_managed_workspace(tmp_path / "changed-comfyui")
    assert controller.start_background_preparation()
    assert preparation.first_cancelled.wait(timeout=5)
    assert preparation.second_finished.wait(timeout=5)
    wait_for_qt_condition(lambda: bool(finished), timeout_ms=5000)

    assert preparation.invocations == 2
    assert len(finished) == 1
    result = finished[0]
    assert isinstance(result, OnboardingPreparationResult)
    assert result.key.workspace_path == tmp_path / "changed-comfyui"


def test_closing_onboarding_cancels_final_setup_before_commit(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Closing setup must cancel owned work without publishing stale completion."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    draft = OnboardingDraftState(
        installation_root=context.install_root,
        target_mode=context.comfy_target.mode.value,
        endpoint_host=context.comfy_target.endpoint.host,
        endpoint_port=context.comfy_target.endpoint.port,
        managed_workspace_path=context.managed_comfy_dir,
        attached_workspace_path=None,
    )
    flow = _CancellationAwareFlowService(draft=draft)
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(BootstrapRoute.ONBOARDING, ()),
        flow_service=flow,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    completions: list[object] = []
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    assert flow.started.wait(timeout=5)
    controller.shutdown()
    assert flow.cancellation_seen.wait(timeout=5)

    assert not completions
    assert not flow.commit_reached
