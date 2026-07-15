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

"""Coordinate persisted Substitute runtime configuration lifecycle work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
from substitute.application.ports.runtime_repository import (
    RuntimeConfigurationRepository,
)
from substitute.domain.onboarding import RuntimeConfiguration
from substitute.domain.onboarding.models import RuntimeBootstrapStatus


@dataclass
class RuntimeService:
    """Load, validate, provision, and launch the visible Substitute runtime."""

    repository: RuntimeConfigurationRepository
    provisioner: RuntimeProvisioner | None = None

    def load_persisted(self) -> RuntimeConfiguration | None:
        """Load persisted runtime configuration when it exists."""

        if not self.repository.exists():
            return None
        return self.repository.load()

    def create_default(self) -> RuntimeConfiguration:
        """Create the default runtime configuration without persisting it."""

        return self.repository.build_default()

    def save(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Persist one runtime configuration after materializing its root."""

        configuration.runtime_root.mkdir(parents=True, exist_ok=True)
        self.repository.save(configuration)
        return configuration

    def validate(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Persist validated runtime configuration state after local normalization."""

        configuration.runtime_root.mkdir(parents=True, exist_ok=True)
        return configuration

    def provision_draft(
        self,
        configuration: RuntimeConfiguration | None = None,
    ) -> RuntimeConfiguration:
        """Provision runtime files and return configuration without active writes."""

        if self.provisioner is None:
            raise RuntimeError("Runtime provisioning requested without a provisioner.")
        draft_configuration = (
            configuration or self.load_persisted() or self.create_default()
        )
        provisioning_configuration = RuntimeConfiguration(
            runtime_root=draft_configuration.runtime_root,
            python_executable=draft_configuration.python_executable,
            bootstrap_status=RuntimeBootstrapStatus.PROVISIONING,
            schema_version=draft_configuration.schema_version,
        )
        return self.provisioner.provision(provisioning_configuration)

    def provision(self) -> RuntimeConfiguration:
        """Provision the visible runtime and persist the updated configuration."""

        if self.provisioner is None:
            raise RuntimeError("Runtime provisioning requested without a provisioner.")
        configuration = self.load_persisted() or self.create_default()
        provisioning_configuration = RuntimeConfiguration(
            runtime_root=configuration.runtime_root,
            python_executable=configuration.python_executable,
            bootstrap_status=RuntimeBootstrapStatus.PROVISIONING,
            schema_version=configuration.schema_version,
        )
        self.save(provisioning_configuration)
        try:
            updated_configuration = self.provisioner.provision(
                provisioning_configuration
            )
        except Exception:
            failed_configuration = RuntimeConfiguration(
                runtime_root=configuration.runtime_root,
                python_executable=configuration.python_executable,
                bootstrap_status=RuntimeBootstrapStatus.FAILED,
                schema_version=configuration.schema_version,
            )
            self.save(failed_configuration)
            raise
        return self.save(updated_configuration)

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Build the authoritative launch command for one runtime configuration."""

        if self.provisioner is None:
            raise RuntimeError(
                "Runtime launch command requested without a provisioner."
            )
        return self.provisioner.build_launch_command(configuration, entrypoint_path)
