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

"""Test onboarding provisioning inputs, completion, and failure routing."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_provisioning_submitter_factory,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationContext,
    ReadinessAssessment,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.presentation.onboarding.controller.support import (
    FakeFlowService,
    build_context,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.fixture(scope="module", autouse=True)
def provisioning_qt_application() -> Iterator[QApplication]:
    """Keep one process-local Qt application alive for provisioning delivery."""

    application = ensure_qt_application()
    yield application


def test_controller_emits_completion_for_remote_provisioning(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Successful remote onboarding should emit completion with launch command."""

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
    owned_controllers.append(controller)
    controller.update_target_mode(OnboardingTargetMode.REMOTE)
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    wait_for_qt_condition(lambda: len(completions) == 1)

    assert len(completions) == 1
    completion = completions[0]
    assert completion.restart_required is False
    assert isinstance(completion.context, InstallationContext)
    assert completion.context.comfy_target.mode is ComfyTargetMode.REMOTE


def test_controller_passes_short_lived_civitai_api_key_to_provisioning(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """The optional CivitAI API key should not become part of the main draft."""

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
    wait_for_qt_condition(lambda: bool(flow_service.provision_kwargs))

    credential_draft = flow_service.provision_kwargs["credential_draft"]
    assert credential_draft == OnboardingCredentialDraft("civitai-secret")
    assert not hasattr(controller.draft, "civitai_api_key")


def test_controller_marks_reconfigure_completion_as_restart_required(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Reconfigure flow should require restart on successful completion."""

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
    owned_controllers.append(controller)
    controller.completion_ready.connect(completions.append)

    controller.start_provisioning()
    wait_for_qt_condition(lambda: len(completions) == 1)

    assert len(completions) == 1
    assert completions[0].restart_required is True


def test_controller_emits_structured_failure_for_actionable_provisioning_errors(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Provisioning failures should preserve guided remediation details."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = FakeFlowService(
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
    owned_controllers.append(controller)
    controller.failure_reported.connect(failures.append)

    controller.start_provisioning()
    wait_for_qt_condition(lambda: len(failures) == 1)

    assert len(failures) == 1
    assert failures[0].headline.startswith("The ComfyUI folder needs to be cleared")
    assert "Delete the incomplete folder" in failures[0].remediation_steps[0]
