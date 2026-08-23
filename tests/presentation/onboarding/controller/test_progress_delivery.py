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

"""Test onboarding progress publication and cancellation boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import threading

import pytest
from PySide6.QtWidgets import QApplication

from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
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
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingFlowMode,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.support.execution import QueuedTaskSubmitter, RecordingDispatcher
from tests.presentation.onboarding.controller.support import (
    BlockingProgressFlowService,
    FakeFlowService,
    build_context,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.fixture(scope="module", autouse=True)
def progress_qt_application() -> Iterator[QApplication]:
    """Keep one process-local Qt application alive for progress delivery."""

    application = ensure_qt_application()
    yield application


def test_controller_emits_user_facing_progress_status(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Provisioning status updates should be understandable outside developer context."""

    context = build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    statuses: list[str] = []

    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.ONBOARDING,
            issues=(),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    controller.progress_status_changed.connect(statuses.append)

    controller.start_provisioning()
    wait_for_qt_condition(lambda: bool(statuses))

    assert statuses == ["Starting setup."]
    assert "Provisioning Substitute runtime." not in statuses[0]


def test_controller_publishes_provisioning_progress_on_owner_thread(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Provisioning progress should leave task work through owner-thread delivery."""

    main_thread_id = threading.get_ident()
    context = build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    statuses: list[tuple[str, int]] = []
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.ONBOARDING,
            issues=(),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    controller.progress_status_changed.connect(
        lambda status: statuses.append((status, threading.get_ident()))
    )

    controller.start_provisioning()
    wait_for_qt_condition(lambda: bool(statuses))

    assert flow_service.provision_thread_id is not None
    assert flow_service.provision_thread_id != main_thread_id
    assert statuses == [("Starting setup.", main_thread_id)]


def test_controller_streams_progress_before_provisioning_finishes(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Long-running setup should publish status and logs while work is active."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = BlockingProgressFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    statuses: list[str] = []
    logs: list[str] = []
    completions: list[OnboardingCompletion] = []
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.ONBOARDING,
            issues=(),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    owned_controllers.append(controller)
    controller.progress_status_changed.connect(statuses.append)
    controller.progress_log_emitted.connect(logs.append)
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    try:
        wait_for_qt_condition(lambda: bool(statuses) and bool(logs))

        assert statuses == ["Installing ComfyUI."]
        assert logs == ["Cloning the ComfyUI repository."]
        assert completions == []
    finally:
        flow_service.release.set()

    wait_for_qt_condition(lambda: len(completions) == 1)
    controller.shutdown()


def test_controller_shutdown_suppresses_pending_provisioning_signals(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Shutdown should cancel pending provisioning without publishing completion."""

    context = build_context(tmp_path, ComfyTargetMode.REMOTE)
    submitter = QueuedTaskSubmitter()
    flow_service = FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=OnboardingCompletionResult(
            context=context,
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    completions: list[OnboardingCompletion] = []
    failures: list[OnboardingProvisioningFailure] = []
    finished: list[str] = []
    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.ONBOARDING,
            issues=(),
        ),
        flow_service=flow_service,
        submitter=submitter,
        progress_publisher=RecordingDispatcher(),
    )
    owned_controllers.append(controller)
    controller.completion_ready.connect(completions.append)
    controller.failure_reported.connect(failures.append)
    controller.provisioning_finished.connect(lambda: finished.append("finished"))

    controller.start_provisioning()
    controller.shutdown()

    assert len(submitter.handles) == 1
    assert submitter.handles[0].outcome is not None
    assert submitter.handles[0].outcome.cancelled is True
    assert completions == []
    assert failures == []
    assert finished == []
