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

"""Provide deterministic adapters for connection-settings service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.onboarding import (
    ComfyConnectionSettingsService,
    ComfyTargetService,
)
from substitute.application.restart_requirements import RestartRequirementService
from substitute.domain.comfy_environment import (
    ComfyEnvironmentCapabilities,
    ComfyModelRootStatus,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    InstallationConfiguration,
)


class TargetRepository:
    """Persist target settings in memory for service tests."""

    def __init__(self, installation: InstallationConfiguration) -> None:
        """Store the installation used for default target construction."""

        self.installation = installation
        self.saved: ComfyTargetConfiguration | None = None

    def exists(self) -> bool:
        """Return whether a target has been saved."""

        return self.saved is not None

    def build_default(self) -> ComfyTargetConfiguration:
        """Return the default managed-local target."""

        return ComfyTargetConfiguration.create_default(self.installation)

    def load(self) -> ComfyTargetConfiguration:
        """Return the saved target or default target."""

        return self.saved or self.build_default()

    def save(self, configuration: ComfyTargetConfiguration) -> None:
        """Record one saved target."""

        self.saved = configuration


class ConnectionChecks:
    """Expose controllable readiness checks for service tests."""

    def __init__(self) -> None:
        """Initialize checks with permissive endpoint defaults."""

        self.existing_workspaces: set[Path] = set()
        self.endpoint_reachable = True
        self.endpoint_probe_count = 0

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return whether the workspace is listed as existing."""

        return workspace in self.existing_workspaces

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Record endpoint probes and return the configured result."""

        _ = configuration
        self.endpoint_probe_count += 1
        return self.endpoint_reachable


class EnvironmentClient:
    """Provide controllable BackEnd model-root state for settings tests."""

    def __init__(self, status: ComfyModelRootStatus) -> None:
        """Initialize the reported host state."""

        self.status = status
        self.last_update_path: str | None = None

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities:
        """Advertise model-root management support."""

        return ComfyEnvironmentCapabilities(
            schema_version=1,
            supported_features=("model-root-management",),
            restart_supported=True,
            package_mutation_supported=False,
            operation_planning_supported=True,
            model_root_management_supported=True,
        )

    def get_model_root(self) -> ComfyModelRootStatus:
        """Return current fake host state."""

        return self.status

    def update_model_root(
        self,
        *,
        use_default: bool,
        path: str | None = None,
    ) -> ComfyModelRootStatus:
        """Persist a fake selection while leaving active process state unchanged."""

        self.last_update_path = path
        configured = None if use_default else path
        desired = configured or self.status.default_model_root
        self.status = ComfyModelRootStatus(
            schema_version=1,
            default_model_root=self.status.default_model_root,
            configured_model_root=configured,
            active_model_root=self.status.active_model_root,
            uses_default=use_default,
            restart_required=desired != self.status.active_model_root,
        )
        return self.status


@dataclass(frozen=True)
class EnvironmentClientFactory:
    """Return one fake client for every endpoint in a settings test."""

    client: EnvironmentClient

    def __call__(self, _endpoint: ComfyEndpoint) -> EnvironmentClient:
        """Return the configured fake client."""

        return self.client


def environment_client(service: ComfyConnectionSettingsService) -> EnvironmentClient:
    """Return the fake client composed into a model-root test service."""

    factory = service.environment_client_factory
    assert isinstance(factory, EnvironmentClientFactory)
    return factory.client


def build_service(
    tmp_path: Path,
    *,
    with_model_root: bool = False,
    restart_requirements: RestartRequirementService | None = None,
) -> tuple[ComfyConnectionSettingsService, TargetRepository, ConnectionChecks]:
    """Create a service and deterministic adapters rooted under the temp directory."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = TargetRepository(installation)
    checks = ConnectionChecks()
    default_workspace = installation.default_managed_comfy_dir
    environment_client_factory = (
        EnvironmentClientFactory(
            EnvironmentClient(
                model_root_status(
                    workspace=default_workspace,
                    configured=None,
                    active=default_workspace / "models",
                )
            )
        )
        if with_model_root
        else None
    )
    service = ComfyConnectionSettingsService(
        target_service=ComfyTargetService(repository),
        checks=checks,
        environment_client_factory=environment_client_factory,
        restart_requirements=restart_requirements,
        attached_python_resolver=lambda workspace, **_kwargs: ComfyPythonBinding(
            executable=workspace / ".venv" / "Scripts" / "python.exe",
            version="3.13",
            architecture="AMD64",
            prefix=workspace / ".venv",
            base_prefix=workspace / ".venv",
            source=ComfyPythonSelectionSource.DISCOVERED,
        ),
    )
    return service, repository, checks


def model_root_status(
    *,
    workspace: Path,
    configured: Path | None,
    active: Path,
) -> ComfyModelRootStatus:
    """Build one normalized fake BackEnd model-root response."""

    default_root = (workspace / "models").resolve()
    configured_root = configured.resolve() if configured is not None else None
    active_root = active.resolve()
    return ComfyModelRootStatus(
        schema_version=1,
        default_model_root=str(default_root),
        configured_model_root=(
            str(configured_root) if configured_root is not None else None
        ),
        active_model_root=str(active_root),
        uses_default=configured_root is None,
        restart_required=(configured_root or default_root) != active_root,
    )
