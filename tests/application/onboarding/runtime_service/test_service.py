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

"""Tests for final runtime validation and provisioning status transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.domain.onboarding import (
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)


@dataclass
class _FakeRuntimeRepository:
    """Persist runtime configuration snapshots in memory for assertions."""

    configuration: RuntimeConfiguration
    saved: list[RuntimeConfiguration] = field(default_factory=list)

    def exists(self) -> bool:
        """Report that persisted runtime configuration already exists."""

        return True

    def build_default(self) -> RuntimeConfiguration:
        """Return the current default runtime configuration."""

        return self.configuration

    def load(self) -> RuntimeConfiguration:
        """Return the current runtime configuration."""

        return self.configuration

    def save(self, configuration: RuntimeConfiguration) -> None:
        """Record one persisted runtime configuration snapshot."""

        self.configuration = configuration
        self.saved.append(configuration)


class _ReadyProvisioner:
    """Return a ready runtime configuration without invoking subprocesses."""

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Return the supplied configuration marked ready."""

        return RuntimeConfiguration(
            runtime_root=configuration.runtime_root,
            python_executable=configuration.runtime_root
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version=configuration.schema_version,
        )

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return the final runtime launch command."""

        return [str(configuration.python_executable), str(entrypoint_path)]


class _FailingProvisioner(_ReadyProvisioner):
    """Raise during runtime provisioning to test failure persistence."""

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Raise after provisioning begins."""

        _ = configuration
        raise RuntimeError("boom")


def test_runtime_service_persists_provisioning_then_ready(tmp_path: Path) -> None:
    """Runtime provisioning should persist explicit provisioning and ready states."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = _FakeRuntimeRepository(
        RuntimeConfiguration.create_default(installation)
    )
    service = RuntimeService(repository=repository, provisioner=_ReadyProvisioner())

    configuration = service.provision()

    assert configuration.bootstrap_status is RuntimeBootstrapStatus.READY
    assert [saved.bootstrap_status for saved in repository.saved] == [
        RuntimeBootstrapStatus.PROVISIONING,
        RuntimeBootstrapStatus.READY,
    ]


def test_runtime_service_persists_failed_state_when_provisioning_raises(
    tmp_path: Path,
) -> None:
    """Runtime provisioning failures should persist a failed runtime state."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = _FakeRuntimeRepository(
        RuntimeConfiguration.create_default(installation)
    )
    service = RuntimeService(repository=repository, provisioner=_FailingProvisioner())

    with pytest.raises(RuntimeError, match="boom"):
        service.provision()

    assert [saved.bootstrap_status for saved in repository.saved] == [
        RuntimeBootstrapStatus.PROVISIONING,
        RuntimeBootstrapStatus.FAILED,
    ]
