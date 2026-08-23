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

"""Test onboarding navigation and draft projection."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding import OnboardingDraftState
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
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.presentation.onboarding.controller.support import (
    FakeFlowService,
    build_context,
)


def test_controller_advances_to_target_specific_page(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Target selection should map to the dedicated options page."""

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


def test_controller_tracks_attached_workspace_default_model_root(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Changing attached ComfyUI should move its default models folder with it."""

    context = build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    flow_service = FakeFlowService(
        draft=OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=None,
            managed_model_root=context.managed_comfy_dir / "models",
            managed_model_root_uses_default=True,
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
    owned_controllers.append(controller)
    attached_workspace = tmp_path / "ExistingComfyUI"

    controller.update_target_mode(OnboardingTargetMode.ATTACHED_LOCAL)
    controller.update_attached_workspace(attached_workspace)

    assert controller.draft.managed_model_root == attached_workspace / "models"
    assert controller.draft.managed_model_root_uses_default is True
