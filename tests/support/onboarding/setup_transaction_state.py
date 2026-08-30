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

"""Regression tests for interruption-safe setup transaction state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast


from substitute.application.onboarding import (
    BootstrapReadinessService,
    ComfyTargetService,
    InstallationService,
    ManagedRuntimeService,
    RuntimeService,
)
from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionPolicy,
    ManagedRuntimeSelectionUnavailableError,
)
from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from substitute.infrastructure.onboarding import (
    FileSetupTransactionRepository,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    ConfigurationFileSet,
)


@dataclass(frozen=True)
class _StaticInstallationService:
    """Return one optional persisted installation configuration."""

    configuration: InstallationConfiguration | None

    def load_persisted(self) -> InstallationConfiguration | None:
        """Return the configured installation value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticRuntimeService:
    """Return one optional persisted runtime configuration."""

    configuration: RuntimeConfiguration | None

    def load_persisted(self) -> RuntimeConfiguration | None:
        """Return the configured runtime value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticTargetService:
    """Return one optional persisted target configuration."""

    configuration: ComfyTargetConfiguration | None

    def load_persisted(self) -> ComfyTargetConfiguration | None:
        """Return the configured target value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticManagedRuntimeService:
    """Return one optional persisted managed runtime configuration."""

    configuration: ManagedRuntimeConfiguration | None

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Return the configured managed runtime value."""

        return self.configuration


@dataclass(frozen=True)
class _FakeReadinessChecks:
    """Provide deterministic readiness outcomes for pending-state tests."""

    files: ConfigurationFileSet
    endpoint_reachable: bool = True
    runtime_python_present: bool = True

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return the configured file set."""

        _ = installation_root
        return self.files

    def is_installation_configuration_valid(
        self,
        configuration: InstallationConfiguration,
    ) -> bool:
        """Treat all supplied installation configurations as valid."""

        _ = configuration
        return True

    def is_runtime_configuration_valid(
        self,
        configuration: RuntimeConfiguration,
    ) -> bool:
        """Treat all supplied runtime configurations as valid."""

        _ = configuration
        return True

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return the configured runtime-python presence."""

        _ = configuration
        return self.runtime_python_present

    def is_target_configuration_valid(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Treat all supplied target configurations as valid."""

        _ = configuration
        return True

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Treat attached workspaces as present."""

        _ = workspace
        return True

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return the configured endpoint reachability."""

        _ = configuration
        return self.endpoint_reachable

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Treat managed workspace files as installed."""

        _ = workspace
        return True

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Treat managed workspace files as launchable."""

        _ = workspace
        return True

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Treat required managed custom nodes as present."""

        _ = workspace
        return True

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> ManagedListenerProbeResult:
        """Return no active managed listener."""

        _ = installation, configuration
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="No listener in this test.",
        )


@dataclass(frozen=True)
class _LegacyRecoveryChecks:
    """Provide deterministic checks for legacy attached-target recovery."""

    endpoint_reachable: bool = False
    managed_launchable: bool = True

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the stale attached target is reachable."""

        _ = configuration
        return self.endpoint_reachable

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return whether the local workspace can be launched as managed Comfy."""

        _ = workspace
        return self.managed_launchable


@dataclass
class _RecordingManagedRuntimeRepository:
    """Record managed runtime saves while satisfying the repository protocol."""

    saved: ManagedRuntimeConfiguration | None = None

    def exists(self) -> bool:
        """Return whether a configuration has been saved."""

        return self.saved is not None

    def build_default(self) -> ManagedRuntimeConfiguration:
        """Return the default managed runtime configuration."""

        return ManagedRuntimeConfiguration()

    def load(self) -> ManagedRuntimeConfiguration:
        """Return the saved configuration or default."""

        return self.saved or self.build_default()

    def save(self, configuration: ManagedRuntimeConfiguration) -> None:
        """Record one saved configuration."""

        self.saved = configuration


@dataclass(frozen=True)
class _StaticSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Return a deterministic managed runtime selection."""

    configuration: ManagedRuntimeConfiguration

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the configured managed runtime."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        return self.configuration


@dataclass(frozen=True)
class _UnavailableSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Report that managed Comfy is unsupported on the detected machine."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Raise the expected capability error for every selection attempt."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        raise ManagedRuntimeSelectionUnavailableError("No Linux accelerator detected.")


@dataclass(frozen=True)
class _ReadyRuntimeProvisioner(RuntimeProvisioner):
    """Return ready runtime configuration without installing dependencies."""

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Return the supplied configuration as ready."""

        return RuntimeConfiguration(
            runtime_root=configuration.runtime_root,
            python_executable=configuration.python_executable,
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version=configuration.schema_version,
        )

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return a deterministic launch command."""

        _ = configuration
        return ["python", str(entrypoint_path)]


def _build_readiness_service(
    *,
    installation: InstallationConfiguration,
    runtime: RuntimeConfiguration | None,
    target: ComfyTargetConfiguration | None,
    managed_runtime: ManagedRuntimeConfiguration | None,
    repository: FileSetupTransactionRepository,
    files_present: bool,
) -> BootstrapReadinessService:
    """Build one readiness service for pending-state tests."""

    file_set = ConfigurationFileSet(
        installation_path=installation.user_settings_dir / "installation.json",
        runtime_path=installation.user_settings_dir / "runtime.json",
        target_path=installation.user_settings_dir / "comfy_target.json",
    )
    if files_present:
        installation.user_settings_dir.mkdir(parents=True, exist_ok=True)
        file_set.installation_path.write_text("{}", encoding="utf-8")
        file_set.runtime_path.write_text("{}", encoding="utf-8")
        file_set.target_path.write_text("{}", encoding="utf-8")
    return BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation if files_present else None),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(ComfyTargetService, _StaticTargetService(target)),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeReadinessChecks(files=file_set),
        setup_transaction_repository=repository,
    )


def _ready_runtime(
    installation: InstallationConfiguration,
) -> RuntimeConfiguration:
    """Build a ready runtime configuration for tests."""

    return RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )


def _managed_target(
    installation: InstallationConfiguration,
) -> ComfyTargetConfiguration:
    """Build a managed-local target configuration for tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )


def _valid_managed_runtime() -> ManagedRuntimeConfiguration:
    """Build a valid managed runtime configuration for tests."""

    return ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
