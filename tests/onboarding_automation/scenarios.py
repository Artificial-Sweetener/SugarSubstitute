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

"""Define onboarding automation scenarios and deterministic fake flow services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingCredentialDraft,
    OnboardingDraftState,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from tests.onboarding_automation.fixture_paths import ScenarioPaths


@dataclass(frozen=True)
class ScenarioDefinition:
    """Describe one named onboarding automation scenario."""

    name: str
    description: str
    flow_mode: OnboardingFlowMode
    target_mode: OnboardingTargetMode
    install_root: Path
    endpoint_host: str
    endpoint_port: int
    managed_workspace_path: Path
    attached_workspace_path: Path | None
    readiness_assessment: ReadinessAssessment
    execution_mode: ScenarioExecutionMode
    expected_outcome: ScenarioOutcome
    reset_install_state: bool = False
    reset_external_fixture: bool = False
    provision_external_fixture: bool = False
    launch_external_fixture: bool = False
    provisioning_timeout_seconds: float = 300.0
    managed_failure_stage: str | None = None
    prepare_stale_managed_workspace: bool = False
    retry_after_failure: bool = False
    assert_managed_summary: bool = False


class ScenarioExecutionMode(str, Enum):
    """Identify how one onboarding automation scenario should provision work."""

    SYNTHETIC = "synthetic"
    REAL = "real"


class ScenarioOutcome(str, Enum):
    """Identify the expected terminal outcome for one automation scenario."""

    SUCCESS = "success"
    FAILURE = "failure"


class ImmediateSuccessFlowService:
    """Return deterministic onboarding success while exercising the real UI flow."""

    def __init__(self, draft: OnboardingDraftState) -> None:
        """Store the deterministic draft state used by the automation scenario."""

        self._draft = draft

    def load_draft(self, _installation_root: Path) -> OnboardingDraftState:
        """Return the configured onboarding draft."""

        return self._draft

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[str], None],
        on_log: Callable[[str], None],
    ) -> OnboardingCompletionResult:
        """Emit deterministic progress and complete successfully."""

        _ = credential_draft
        on_status("Saving your setup.")
        on_log(f"Automation scenario: {draft.target_mode}")
        target_mode = ComfyTargetMode(draft.target_mode)
        installation = InstallationConfiguration.create_default(draft.installation_root)
        runtime = RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=installation.runtime_dir
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
        workspace_path = (
            draft.managed_workspace_path
            if target_mode is ComfyTargetMode.MANAGED_LOCAL
            else draft.attached_workspace_path
        )
        context = InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=ComfyTargetConfiguration(
                mode=target_mode,
                endpoint=ComfyEndpoint(
                    host=draft.endpoint_host,
                    port=draft.endpoint_port,
                ),
                workspace_path=workspace_path,
                install_owned=target_mode is ComfyTargetMode.MANAGED_LOCAL,
                launch_owned=target_mode is ComfyTargetMode.MANAGED_LOCAL,
            ),
        )
        on_status("Setup is ready.")
        on_log("Automation scenario completed successfully.")
        return OnboardingCompletionResult(
            context=context,
            restart_required=restart_required,
            launch_command=("python", "main.py"),
        )


def build_scenarios(paths: ScenarioPaths) -> dict[str, ScenarioDefinition]:
    """Return the onboarding automation scenarios available to the runner."""

    managed_root = paths.repo_root / "automation_sandboxes" / "managed_smoke"
    attached_root = paths.repo_root / "automation_sandboxes" / "attached_smoke"
    onboarding_readiness = ReadinessAssessment(
        route=BootstrapRoute.ONBOARDING,
        issues=(),
    )
    return {
        "ui_smoke_managed": ScenarioDefinition(
            name="ui_smoke_managed",
            description="Drive the full first-run onboarding UI through the managed-local path with deterministic success.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=managed_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=managed_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.SYNTHETIC,
            expected_outcome=ScenarioOutcome.SUCCESS,
            assert_managed_summary=True,
        ),
        "ui_smoke_attached": ScenarioDefinition(
            name="ui_smoke_attached",
            description="Drive the full first-run onboarding UI through the attached-local path with deterministic success.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
            install_root=attached_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=attached_root / "comfyui",
            attached_workspace_path=paths.external_comfy_root,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.SYNTHETIC,
            expected_outcome=ScenarioOutcome.SUCCESS,
        ),
        "managed_clean_real": ScenarioDefinition(
            name="managed_clean_real",
            description="Run the real first-run managed-local onboarding flow from a clean repo-root reset.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.SUCCESS,
            reset_install_state=True,
            provisioning_timeout_seconds=1800.0,
        ),
        "managed_stale_bootstrap_recovery_real": ScenarioDefinition(
            name="managed_stale_bootstrap_recovery_real",
            description="Run the real managed-local flow with stale bootstrap leftovers and confirm automatic recovery.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.SUCCESS,
            reset_install_state=True,
            prepare_stale_managed_workspace=True,
            provisioning_timeout_seconds=1800.0,
        ),
        "managed_clone_failure_real": ScenarioDefinition(
            name="managed_clone_failure_real",
            description="Run the real managed-local flow with an injected clone failure and confirm the provisioning page leaves the working state.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.FAILURE,
            reset_install_state=True,
            managed_failure_stage="clone",
            provisioning_timeout_seconds=1800.0,
        ),
        "managed_retry_after_clone_failure_real": ScenarioDefinition(
            name="managed_retry_after_clone_failure_real",
            description="Run the real managed-local flow with an injected clone failure, clear the failure, retry, and finish successfully.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.SUCCESS,
            reset_install_state=True,
            managed_failure_stage="clone",
            retry_after_failure=True,
            provisioning_timeout_seconds=1800.0,
        ),
        "managed_dependency_failure_real": ScenarioDefinition(
            name="managed_dependency_failure_real",
            description="Run the real managed-local flow with an injected dependency-install failure and confirm setup exits the working state cleanly.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=None,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.FAILURE,
            reset_install_state=True,
            managed_failure_stage="dependency_install",
            provisioning_timeout_seconds=1800.0,
        ),
        "attached_clean_real": ScenarioDefinition(
            name="attached_clean_real",
            description="Run the real first-run attached-local onboarding flow against the external Comfy fixture.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8190,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=paths.external_comfy_root,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.SUCCESS,
            reset_install_state=True,
            reset_external_fixture=True,
            provision_external_fixture=True,
            launch_external_fixture=True,
            provisioning_timeout_seconds=1800.0,
        ),
        "attached_missing_workspace_real": ScenarioDefinition(
            name="attached_missing_workspace_real",
            description="Run the real attached-local flow with a missing local workspace path and confirm setup fails clearly.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8190,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=paths.external_comfy_root / "missing-workspace",
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.FAILURE,
            reset_install_state=True,
            reset_external_fixture=True,
            provision_external_fixture=True,
            launch_external_fixture=True,
            provisioning_timeout_seconds=1800.0,
        ),
        "attached_unreachable_real": ScenarioDefinition(
            name="attached_unreachable_real",
            description="Run the real attached-local flow without launching the external Comfy fixture and confirm connection failure.",
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
            install_root=paths.repo_root,
            endpoint_host="127.0.0.1",
            endpoint_port=8190,
            managed_workspace_path=paths.repo_root / "comfyui",
            attached_workspace_path=paths.external_comfy_root,
            readiness_assessment=onboarding_readiness,
            execution_mode=ScenarioExecutionMode.REAL,
            expected_outcome=ScenarioOutcome.FAILURE,
            reset_install_state=True,
            reset_external_fixture=True,
            provision_external_fixture=True,
            launch_external_fixture=False,
            provisioning_timeout_seconds=1800.0,
        ),
    }


def build_draft_state(scenario: ScenarioDefinition) -> OnboardingDraftState:
    """Translate one scenario definition into the controller draft state."""

    return OnboardingDraftState(
        installation_root=scenario.install_root,
        target_mode=scenario.target_mode.value,
        endpoint_host=scenario.endpoint_host,
        endpoint_port=scenario.endpoint_port,
        managed_workspace_path=scenario.managed_workspace_path,
        attached_workspace_path=scenario.attached_workspace_path,
        detected_platform="windows",
        detected_accelerator="nvidia",
        selected_install_target="windows_nvidia",
        selected_python_version="3.13",
        selected_comfy_channel="latest",
        selected_backend_policy="cuda_nightly_cu130",
        selected_torch_channel="nightly",
        selected_torch_reason="NVIDIA installs default to nightly torch.",
        selected_stability="experimental",
    )
