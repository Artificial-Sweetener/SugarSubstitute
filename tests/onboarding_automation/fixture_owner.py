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

"""Own filesystem, process, environment, and service fixtures for one scenario."""

from __future__ import annotations

import pytest

from substitute.application.onboarding import OnboardingFlowService
from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonGateway,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.infrastructure.comfy.attached_install import (
    prepare_verified_attached_comfy_setup,
)
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_shutdown import kill_managed_comfy
from substitute.infrastructure.comfy.workspace_python_discovery import (
    WorkspacePythonGateway,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingFlowServiceLike,
)
from tests.onboarding_automation.external_comfy_fixture import (
    ExternalComfyFixture,
    launch_external_comfy_fixture,
    provision_external_comfy_workspace,
    reset_external_comfy_root,
)
from tests.onboarding_automation.environment_fixture import (
    StaticPythonGateway,
    synthetic_python_binding,
)
from tests.onboarding_automation.install_state import reset_install_state
from tests.onboarding_automation.scenarios import (
    ImmediateSuccessFlowService,
    ScenarioDefinition,
    ScenarioExecutionMode,
    build_draft_state,
)


_FORCED_MANAGED_FAILURE_STAGE_ENV = "SUGARSUB_FORCE_MANAGED_FAILURE_STAGE"


class OnboardingScenarioFixtureOwner:
    """Prepare and release every non-UI resource used by one scenario."""

    def __init__(self, scenario: ScenarioDefinition) -> None:
        """Capture scenario state and own its reversible environment changes."""

        self._scenario = scenario
        self._external_process: ManagedProcessHandle | None = None
        self._environment = pytest.MonkeyPatch()

    def prepare(self) -> None:
        """Reset and provision the exact resources requested by the scenario."""

        self.clear_forced_failure_stage()
        if self._scenario.reset_install_state:
            reset_install_state(self._scenario.install_root)
        if self._scenario.reset_external_fixture:
            reset_external_comfy_root(self._external_fixture())
        if self._scenario.provision_external_fixture:
            provision_external_comfy_workspace(self._external_fixture())
        if self._scenario.launch_external_fixture:
            self._external_process = launch_external_comfy_fixture(
                self._external_fixture()
            )
        if self._scenario.prepare_stale_managed_workspace:
            stale_python = (
                self._scenario.managed_workspace_path
                / ".venv"
                / "Scripts"
                / "python.exe"
            )
            stale_python.parent.mkdir(parents=True, exist_ok=True)
            stale_python.write_text("", encoding="utf-8")
        if self._scenario.managed_failure_stage is not None:
            self._environment.setenv(
                _FORCED_MANAGED_FAILURE_STAGE_ENV, self._scenario.managed_failure_stage
            )

    def build_flow_service(self) -> OnboardingFlowServiceLike:
        """Build the real or synthetic application service for the scenario."""

        if self._scenario.execution_mode is ScenarioExecutionMode.SYNTHETIC:
            return ImmediateSuccessFlowService(build_draft_state(self._scenario))
        return OnboardingFlowService(
            service_bundle_factory=build_onboarding_service_bundle,
            managed_workspace_provisioner=ensure_managed_comfy_setup,
            entrypoint_path=resolve_app_layout(
                self._scenario.install_root
            ).entrypoint_path,
            attached_workspace_provisioner=prepare_verified_attached_comfy_setup,
        )

    def build_python_gateway(self) -> AttachedPythonGateway:
        """Build the real or deterministic Python discovery boundary."""

        if self._scenario.execution_mode is ScenarioExecutionMode.REAL:
            return WorkspacePythonGateway()
        executable = (
            self._scenario.attached_python_executable
            or self._scenario.install_root / ".venv" / "Scripts" / "python.exe"
        )
        return StaticPythonGateway(synthetic_python_binding(executable))

    def clear_forced_failure_stage(self) -> None:
        """Remove the scenario-owned managed-install failure injection."""

        self._environment.delenv(_FORCED_MANAGED_FAILURE_STAGE_ENV, raising=False)

    def _external_fixture(self) -> ExternalComfyFixture:
        """Return the configured fixture for a scenario that requests one."""

        fixture = self._scenario.external_fixture
        if fixture is None:
            raise RuntimeError(
                "An onboarding scenario requested an external Comfy lifecycle without "
                "an external fixture."
            )
        return fixture

    def close(self) -> None:
        """Release the external process and restore caller environment state."""

        self._environment.undo()
        if self._external_process is not None:
            kill_managed_comfy(self._external_process)
            self._external_process = None


__all__ = ["OnboardingScenarioFixtureOwner"]
