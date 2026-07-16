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

"""Provide filesystem-backed readiness checks used by bootstrap composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import socket

from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
    probe_managed_listener,
)
from substitute.infrastructure.comfy.nodepack_reconciliation import (
    CORE_COMFY_NODEPACKS,
    core_nodepack_installed,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.domain.onboarding.runtime_layout import runtime_layout_for_root


@dataclass(frozen=True)
class ConfigurationFileSet:
    """Describe persisted onboarding configuration file locations for one install root."""

    installation_path: Path
    runtime_path: Path
    target_path: Path


@dataclass(frozen=True)
class FileSystemReadinessChecks:
    """Implement readiness checks against visible install-root filesystem state."""

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return the canonical persisted configuration files for one install root."""

        settings_dir = installation_root / "user" / "settings"
        return ConfigurationFileSet(
            installation_path=settings_dir / "installation.json",
            runtime_path=settings_dir / "runtime.json",
            target_path=settings_dir / "comfy_target.json",
        )

    def is_installation_configuration_valid(
        self,
        configuration: InstallationConfiguration,
    ) -> bool:
        """Return whether installation configuration paths remain rooted correctly."""

        install_root = configuration.installation_root.resolve()
        expected = InstallationConfiguration.create_default(install_root)
        return (
            configuration.user_dir.resolve() == expected.user_dir
            and configuration.user_settings_dir.resolve() == expected.user_settings_dir
            and configuration.projects_dir.resolve() == expected.projects_dir
            and configuration.outputs_dir.resolve() == expected.outputs_dir
            and configuration.sugar_scripts_dir.resolve() == expected.sugar_scripts_dir
            and configuration.wildcards_dir.resolve() == expected.wildcards_dir
            and configuration.appdata_dir.resolve() == expected.appdata_dir
            and configuration.session_dir.resolve() == expected.session_dir
            and configuration.cache_dir.resolve() == expected.cache_dir
            and configuration.diagnostics_dir.resolve() == expected.diagnostics_dir
            and configuration.logs_dir.resolve() == expected.logs_dir
            and configuration.runtime_state_dir.resolve() == expected.runtime_state_dir
            and configuration.model_metadata_dir.resolve()
            == expected.model_metadata_dir
            and configuration.runtime_dir.resolve() == expected.runtime_dir
            and configuration.default_managed_comfy_dir.resolve()
            == expected.default_managed_comfy_dir
        )

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return whether the configured runtime Python executable exists on disk."""

        python_executable = configuration.python_executable
        return python_executable is not None and python_executable.exists()

    def is_runtime_configuration_valid(
        self, configuration: RuntimeConfiguration
    ) -> bool:
        """Return whether runtime configuration points at the visible runtime layout."""

        expected_python = runtime_layout_for_root(
            configuration.runtime_root.resolve()
        ).python_executable
        python_executable = configuration.python_executable
        if python_executable is None:
            return configuration.bootstrap_status is not RuntimeBootstrapStatus.READY
        return python_executable.resolve() == expected_python.resolve()

    def is_target_configuration_valid(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the persisted target configuration is internally coherent."""

        endpoint = configuration.endpoint
        if not endpoint.host.strip():
            return False
        if endpoint.port <= 0 or endpoint.port > 65535:
            return False
        if configuration.mode is ComfyTargetMode.MANAGED_LOCAL:
            return configuration.workspace_path is not None
        if configuration.mode is ComfyTargetMode.ATTACHED_LOCAL:
            binding = configuration.python_binding
            return (
                configuration.workspace_path is not None
                and binding is not None
                and binding.executable.is_file()
            )
        return True

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return whether the supplied attached-local workspace path exists."""

        return workspace.exists()

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the configured target endpoint accepts TCP connections."""

        endpoint = configuration.endpoint
        try:
            with socket.create_connection(
                (endpoint.host, endpoint.port),
                timeout=0.35,
            ):
                return True
        except OSError:
            return False

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Return whether the managed workspace shows the expected install artifacts."""

        return (
            self.managed_workspace_python_path(workspace).exists()
            and self.managed_workspace_main_path(workspace).exists()
        )

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return whether the managed workspace can be launched."""

        return (
            self.managed_workspace_python_path(workspace).exists()
            and self.managed_workspace_main_path(workspace).exists()
        )

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Return whether Substitute's required Comfy nodepacks are present."""

        return all(
            core_nodepack_installed(workspace, nodepack)
            for nodepack in CORE_COMFY_NODEPACKS
        )

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> ManagedListenerProbeResult:
        """Return the listener ownership probe result for one managed-local target."""

        if not configuration.launch_owned:
            return ManagedListenerProbeResult(
                status=ManagedListenerStatus.ABSENT,
                reason="Managed listener probing is only valid for launch-owned local targets.",
            )
        workspace = configuration.workspace_path
        if workspace is None:
            return ManagedListenerProbeResult(
                status=ManagedListenerStatus.ABSENT,
                reason="Managed-local target does not have a configured workspace path.",
            )
        registry = ManagedProcessRegistry(installation.runtime_state_dir)
        return probe_managed_listener(
            host=configuration.endpoint.host,
            port=configuration.endpoint.port,
            workspace=workspace,
            metadata=registry.load(),
        )

    @staticmethod
    def managed_workspace_python_path(workspace: Path) -> Path:
        """Return the canonical managed-workspace Python path."""

        return workspace / ".venv" / "Scripts" / "python.exe"

    @staticmethod
    def managed_workspace_main_path(workspace: Path) -> Path:
        """Return the canonical managed-workspace entrypoint path."""

        return workspace / "main.py"
