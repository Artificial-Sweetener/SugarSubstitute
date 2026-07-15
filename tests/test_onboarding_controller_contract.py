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

"""Tests for the final onboarding controller contract."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from tests.execution_testing import QueuedTaskSubmitter, RecordingDispatcher
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_provisioning_submitter_factory,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from tests.execution_test_helpers import ExecutionRuntimeStub


class _FakeFlowService:
    """Return fixed onboarding draft and provisioning results for tests."""

    def __init__(
        self,
        *,
        draft: OnboardingDraftState,
        provision_result: OnboardingCompletionResult | None,
        provision_error: Exception | None = None,
    ) -> None:
        """Store the deterministic onboarding draft and completion result."""

        self._draft = draft
        self._provision_result = provision_result
        self._provision_error = provision_error
        self.provision_kwargs: dict[str, object] = {}
        self.provision_thread_id: int | None = None

    def load_draft(self, _installation_root: Path) -> OnboardingDraftState:
        """Return the configured onboarding draft."""

        return self._draft

    def provision(self, **_kwargs: object) -> OnboardingCompletionResult:
        """Return the configured onboarding completion result."""

        self.provision_thread_id = threading.get_ident()
        self.provision_kwargs = dict(_kwargs)
        on_status = _kwargs.get("on_status")
        if callable(on_status):
            on_status("Starting setup.")
        if self._provision_error is not None:
            raise self._provision_error
        assert self._provision_result is not None
        return self._provision_result


class _BlockingProgressFlowService(_FakeFlowService):
    """Hold provisioning open after publishing deterministic live progress."""

    def __init__(
        self,
        *,
        draft: OnboardingDraftState,
        provision_result: OnboardingCompletionResult,
    ) -> None:
        """Store the completion and expose a release gate for the worker."""

        super().__init__(draft=draft, provision_result=provision_result)
        self.release = threading.Event()

    def provision(self, **kwargs: object) -> OnboardingCompletionResult:
        """Publish progress, then wait so tests can observe it before completion."""

        self.provision_thread_id = threading.get_ident()
        self.provision_kwargs = dict(kwargs)
        on_status = kwargs.get("on_status")
        on_log = kwargs.get("on_log")
        assert callable(on_status)
        assert callable(on_log)
        on_status("Installing ComfyUI.")
        on_log("Cloning the ComfyUI repository.")
        if not self.release.wait(timeout=5.0):
            raise TimeoutError("Test did not release blocked onboarding provisioning.")
        assert self._provision_result is not None
        return self._provision_result


def _build_context(tmp_path: Path, mode: ComfyTargetMode) -> InstallationContext:
    """Build a deterministic onboarding context for controller tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir
        if mode is ComfyTargetMode.MANAGED_LOCAL
        else None,
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def test_controller_advances_to_target_specific_page(tmp_path: Path) -> None:
    """Target selection should map to the dedicated options page."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = _FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=None,
    )

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

    controller.update_target_mode(OnboardingTargetMode.REMOTE)

    assert controller.next_page(OnboardingPageId.TARGET_MODE) is OnboardingPageId.REMOTE
    assert controller.next_page(OnboardingPageId.REMOTE) is OnboardingPageId.FOLDERS
    assert (
        controller.next_page(OnboardingPageId.FOLDERS) is OnboardingPageId.INTEGRATIONS
    )
    assert (
        controller.next_page(OnboardingPageId.INTEGRATIONS)
        is OnboardingPageId.PROVISIONING
    )
    assert (
        controller.previous_page(OnboardingPageId.PROVISIONING)
        is OnboardingPageId.INTEGRATIONS
    )


def test_controller_emits_completion_for_remote_provisioning(tmp_path: Path) -> None:
    """Successful remote onboarding should emit completion with launch command."""

    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = _FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=OnboardingCompletionResult(
            context=InstallationContext(
                installation=context.installation,
                runtime=context.runtime,
                comfy_target=ComfyTargetConfiguration(
                    mode=ComfyTargetMode.REMOTE,
                    endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
                    workspace_path=None,
                    install_owned=False,
                    launch_owned=False,
                ),
            ),
            restart_required=False,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
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
    controller.update_target_mode(OnboardingTargetMode.REMOTE)
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    _process_events_until(lambda: len(completions) == 1)

    assert len(completions) == 1
    completion = completions[0]
    assert completion.restart_required is False
    assert isinstance(completion.context, InstallationContext)
    assert completion.context.comfy_target.mode is ComfyTargetMode.REMOTE


def test_controller_passes_short_lived_civitai_api_key_to_provisioning(
    tmp_path: Path,
) -> None:
    """The optional CivitAI API key should not become part of the main draft."""

    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = _FakeFlowService(
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

    controller.update_integration_preferences(
        danbooru_tag_help_enabled=True,
        danbooru_safe_previews_enabled=True,
        danbooru_image_rating_policy="safe_and_questionable",
        civitai_model_help_enabled=True,
        civitai_downloads_enabled=True,
        civitai_safe_thumbnails_enabled=True,
        civitai_thumbnail_safety_policy="allow_soft",
        civitai_api_key="civitai-secret",
    )
    controller.start_provisioning()
    _process_events_until(lambda: bool(flow_service.provision_kwargs))

    credential_draft = flow_service.provision_kwargs["credential_draft"]
    assert credential_draft == OnboardingCredentialDraft("civitai-secret")
    assert not hasattr(controller.draft, "civitai_api_key")


def test_controller_marks_reconfigure_completion_as_restart_required(
    tmp_path: Path,
) -> None:
    """Reconfigure flow should require restart on successful completion."""

    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = _FakeFlowService(
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
            restart_required=True,
            launch_command=("python", str(tmp_path / "main.py")),
        ),
    )
    completions: list[OnboardingCompletion] = []

    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.RECONFIGURE,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.READY,
            issues=(),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    _process_events_until(lambda: len(completions) == 1)

    assert len(completions) == 1
    assert completions[0].restart_required is True


def test_controller_maps_readiness_issues_to_user_facing_copy(tmp_path: Path) -> None:
    """Readiness issues should be translated into repair copy for normal users."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = _FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=None,
    )

    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.REPAIR,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.REPAIR,
            issues=(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_PYTHON_MISSING,
                    summary="Runtime Python executable is missing.",
                    detail="Repair the visible runtime before normal launch.",
                ),
            ),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )

    presentation = controller.present_readiness_issues()[0]

    assert "Runtime Python executable is missing." != presentation.user_message
    assert presentation.user_message == "A required local Python file is missing."
    assert "Missing runtime Python executable." == presentation.technical_detail


def test_controller_emits_user_facing_progress_status(tmp_path: Path) -> None:
    """Provisioning status updates should be understandable outside developer context."""

    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = _FakeFlowService(
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
    controller.progress_status_changed.connect(statuses.append)

    controller.start_provisioning()
    _process_events_until(lambda: bool(statuses))

    assert statuses == ["Starting setup."]
    assert "Provisioning Substitute runtime." not in statuses[0]


def test_controller_publishes_provisioning_progress_on_owner_thread(
    tmp_path: Path,
) -> None:
    """Provisioning progress should leave task work through owner-thread delivery."""

    main_thread_id = threading.get_ident()
    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    flow_service = _FakeFlowService(
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
    controller.progress_status_changed.connect(
        lambda status: statuses.append((status, threading.get_ident()))
    )

    controller.start_provisioning()
    _process_events_until(lambda: bool(statuses))

    assert flow_service.provision_thread_id is not None
    assert flow_service.provision_thread_id != main_thread_id
    assert statuses == [("Starting setup.", main_thread_id)]


def test_controller_streams_progress_before_provisioning_finishes(
    tmp_path: Path,
) -> None:
    """Long-running setup should publish status and logs while work is active."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = _BlockingProgressFlowService(
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
    controller.progress_status_changed.connect(statuses.append)
    controller.progress_log_emitted.connect(logs.append)
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    try:
        _process_events_until(lambda: bool(statuses) and bool(logs))

        assert statuses == ["Installing ComfyUI."]
        assert logs == ["Cloning the ComfyUI repository."]
        assert completions == []
    finally:
        flow_service.release.set()

    _process_events_until(lambda: len(completions) == 1)
    controller.shutdown()


def test_controller_shutdown_suppresses_pending_provisioning_signals(
    tmp_path: Path,
) -> None:
    """Shutdown should cancel pending provisioning without publishing completion."""

    context = _build_context(tmp_path, ComfyTargetMode.REMOTE)
    submitter = QueuedTaskSubmitter()
    flow_service = _FakeFlowService(
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


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="onboarding provisioning failure signal test aborts Windows xdist workers",
)
def test_controller_emits_structured_failure_for_actionable_provisioning_errors(
    tmp_path: Path,
) -> None:
    """Provisioning failures should preserve guided remediation details."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = _FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=None,
        provision_error=OnboardingProvisioningFailure(
            headline="The ComfyUI folder needs to be cleared before setup can continue",
            user_message="Substitute found leftover files in the selected ComfyUI folder.",
            technical_detail="invalid ComfyUI repository",
            remediation_steps=(
                f"Delete the incomplete folder at {context.managed_comfy_dir}.",
                "Then run setup again.",
            ),
        ),
    )
    failures: list[OnboardingProvisioningFailure] = []

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
    controller.failure_reported.connect(failures.append)

    controller.start_provisioning()
    _process_events_until(lambda: len(failures) == 1)

    assert len(failures) == 1
    assert failures[0].headline.startswith("The ComfyUI folder needs to be cleared")
    assert "Delete the incomplete folder" in failures[0].remediation_steps[0]


def test_controller_maps_endpoint_unreachable_issue_to_user_facing_copy(
    tmp_path: Path,
) -> None:
    """Endpoint reachability issues should use plain-language repair wording."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    flow_service = _FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        provision_result=None,
    )

    controller = OnboardingController(
        initial_install_root=tmp_path,
        flow_mode=OnboardingFlowMode.REPAIR,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.REPAIR,
            issues=(
                ReadinessIssue(
                    code=ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE,
                    summary="Substitute could not reach the saved ComfyUI address.",
                    detail="ComfyUI did not respond at 127.0.0.1:8188.",
                ),
            ),
        ),
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            ExecutionRuntimeStub()
        ),
    )

    presentation = controller.present_readiness_issues()[0]

    assert (
        presentation.headline == "Substitute couldn't reach the saved ComfyUI address"
    )
    assert "running at the saved address" in presentation.user_message
    assert presentation.technical_detail == "ComfyUI did not respond at 127.0.0.1:8188."


def _process_events_until(
    condition: Callable[[], bool],
    *,
    timeout_ms: int = 1000,
) -> None:
    """Process Qt events until one asynchronous controller condition is true."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(10)
    app.processEvents()
    assert condition()
