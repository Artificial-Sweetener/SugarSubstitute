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

"""Test onboarding readiness issue presentation."""

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
    ReadinessIssue,
    ReadinessIssueCode,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import OnboardingFlowMode
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.presentation.onboarding.controller.support import (
    FakeFlowService,
    build_context,
)


def test_controller_maps_readiness_issues_to_user_facing_copy(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Readiness issues should be translated into repair copy for normal users."""

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
    owned_controllers.append(controller)

    presentation = controller.present_readiness_issues()[0]

    assert "Runtime Python executable is missing." != presentation.user_message
    assert presentation.user_message == "A required local Python file is missing."
    assert "Missing runtime Python executable." == presentation.technical_detail


def test_controller_maps_endpoint_unreachable_issue_to_user_facing_copy(
    tmp_path: Path,
    owned_controllers: list[OnboardingController],
) -> None:
    """Endpoint reachability issues should use plain-language repair wording."""

    context = build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
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
    owned_controllers.append(controller)

    presentation = controller.present_readiness_issues()[0]

    assert (
        presentation.headline == "Substitute couldn't reach the saved ComfyUI address"
    )
    assert "running at the saved address" in presentation.user_message
    assert presentation.technical_detail == "ComfyUI did not respond at 127.0.0.1:8188."
