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

"""Provide deterministic collaborators for onboarding readiness contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.readiness_service import (
    BootstrapReadinessService,
)
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from substitute.infrastructure.onboarding.readiness_checks import ConfigurationFileSet


@dataclass(frozen=True)
class StaticInstallationService:
    """Return one persisted installation configuration."""

    configuration: InstallationConfiguration | None

    def load_persisted(self) -> InstallationConfiguration | None:
        """Return the persisted installation configuration."""

        return self.configuration


@dataclass(frozen=True)
class StaticRuntimeService:
    """Return one persisted runtime configuration."""

    configuration: RuntimeConfiguration | None

    def load_persisted(self) -> RuntimeConfiguration | None:
        """Return the persisted runtime configuration."""

        return self.configuration


@dataclass(frozen=True)
class StaticTargetService:
    """Return one persisted Comfy target configuration."""

    configuration: ComfyTargetConfiguration | None

    def load_persisted(self) -> ComfyTargetConfiguration | None:
        """Return the persisted target configuration."""

        return self.configuration


@dataclass(frozen=True)
class StaticManagedRuntimeService:
    """Return one persisted managed-runtime configuration."""

    configuration: ManagedRuntimeConfiguration | None = None

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Return the persisted managed-runtime configuration."""

        return self.configuration


@dataclass(frozen=True)
class FakeReadinessChecks:
    """Provide deterministic readiness outcomes for one scenario."""

    files: ConfigurationFileSet
    installation_valid: bool = True
    runtime_valid: bool = True
    runtime_python_present: bool = True
    target_valid: bool = True
    managed_workspace_installed: bool = True
    managed_workspace_launchable: bool = True
    managed_nodepacks_present: bool = True
    attached_workspace_present: bool = True
    endpoint_reachable: bool = True
    managed_listener_status: ManagedListenerStatus = ManagedListenerStatus.ABSENT
    endpoint_reachability_calls: list[ComfyTargetConfiguration] | None = None

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return the configured file set."""

        _ = installation_root
        return self.files

    def is_installation_configuration_valid(
        self, configuration: InstallationConfiguration
    ) -> bool:
        """Return the configured installation validation result."""

        _ = configuration
        return self.installation_valid

    def is_runtime_configuration_valid(
        self, configuration: RuntimeConfiguration
    ) -> bool:
        """Return the configured runtime validation result."""

        _ = configuration
        return self.runtime_valid

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return the configured runtime-python existence result."""

        _ = configuration
        return self.runtime_python_present

    def is_target_configuration_valid(
        self, configuration: ComfyTargetConfiguration
    ) -> bool:
        """Return the configured target validation result."""

        _ = configuration
        return self.target_valid

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return the configured attached-workspace result."""

        _ = workspace
        return self.attached_workspace_present

    def is_target_endpoint_reachable(
        self, configuration: ComfyTargetConfiguration
    ) -> bool:
        """Record and return the configured endpoint reachability result."""

        if self.endpoint_reachability_calls is not None:
            self.endpoint_reachability_calls.append(configuration)
        return self.endpoint_reachable

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Return the configured managed-install result."""

        _ = workspace
        return self.managed_workspace_installed

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return the configured managed-launchability result."""

        _ = workspace
        return self.managed_workspace_launchable

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Return the configured managed-nodepack result."""

        _ = workspace
        return self.managed_nodepacks_present

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> ManagedListenerProbeResult:
        """Return the configured managed-listener state."""

        _ = installation, configuration
        return ManagedListenerProbeResult(
            status=self.managed_listener_status,
            reason=f"Managed listener status: {self.managed_listener_status.value}.",
        )


@dataclass
class FakeBackendCompatibility:
    """Return one configured backend-compatibility assessment."""

    result: BackendCompatibilityResult
    assessed_targets: list[ComfyTargetConfiguration]

    def assess_target(
        self, target: ComfyTargetConfiguration
    ) -> BackendCompatibilityResult:
        """Record the target and return the configured result."""

        self.assessed_targets.append(target)
        return self.result


def ready_runtime(installation: InstallationConfiguration) -> RuntimeConfiguration:
    """Build a ready runtime configuration for one installation."""

    return RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )


def present_files(installation: InstallationConfiguration) -> ConfigurationFileSet:
    """Create the persisted configuration files required by readiness."""

    installation.user_settings_dir.mkdir(parents=True, exist_ok=True)
    files = ConfigurationFileSet(
        installation_path=installation.user_settings_dir / "installation.json",
        runtime_path=installation.user_settings_dir / "runtime.json",
        target_path=installation.user_settings_dir / "comfy_target.json",
    )
    for path in (files.installation_path, files.runtime_path, files.target_path):
        path.write_text("{}", encoding="utf-8")
    return files


def readiness_service(
    installation: InstallationConfiguration,
    target: ComfyTargetConfiguration,
    checks: FakeReadinessChecks,
    *,
    managed_runtime: ManagedRuntimeConfiguration | None = None,
    backend_compatibility: FakeBackendCompatibility | None = None,
) -> BootstrapReadinessService:
    """Build the real readiness service with deterministic boundary collaborators."""

    return BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService, StaticInstallationService(installation)
        ),
        runtime_service=cast(
            RuntimeService, StaticRuntimeService(ready_runtime(installation))
        ),
        comfy_target_service=cast(ComfyTargetService, StaticTargetService(target)),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            StaticManagedRuntimeService(managed_runtime),
        ),
        checks=checks,
        backend_compatibility=backend_compatibility,
    )
