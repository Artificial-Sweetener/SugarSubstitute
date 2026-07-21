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

"""Persist Substitute runtime configuration inside the visible install root."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from substitute.application.ports.runtime_repository import (
    RuntimeConfigurationRepository,
)
from substitute.domain.onboarding import (
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from sugarsubstitute_shared.windows_long_paths import operational_path


@dataclass
class FileRuntimeConfigurationRepository(RuntimeConfigurationRepository):
    """Load and save runtime configuration under `user/settings/runtime.json`."""

    installation_configuration: InstallationConfiguration

    def exists(self) -> bool:
        """Return whether persisted runtime configuration exists."""

        return self._path().exists() or self._legacy_path().exists()

    def build_default(self) -> RuntimeConfiguration:
        """Build the default runtime configuration for this installation."""

        return RuntimeConfiguration.create_default(self.installation_configuration)

    def load(self) -> RuntimeConfiguration:
        """Load runtime configuration or synthesize defaults from installation paths."""

        path = self._path() if self._path().exists() else self._legacy_path()
        if not path.exists():
            return self.build_default()
        payload = json.loads(path.read_text(encoding="utf-8"))
        python_executable = payload.get("python_executable")
        return RuntimeConfiguration(
            runtime_root=operational_path(payload["runtime_root"]),
            python_executable=operational_path(python_executable)
            if isinstance(python_executable, str)
            else None,
            bootstrap_status=RuntimeBootstrapStatus(payload["bootstrap_status"]),
            schema_version=str(payload.get("schema_version", "1")),
        )

    def save(self, configuration: RuntimeConfiguration) -> None:
        """Persist runtime configuration to the visible config directory."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "runtime_root": str(configuration.runtime_root),
                    "python_executable": (
                        str(configuration.python_executable)
                        if configuration.python_executable is not None
                        else None
                    ),
                    "bootstrap_status": configuration.bootstrap_status.value,
                    "schema_version": configuration.schema_version,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _path(self) -> Path:
        """Return the persisted runtime config path."""

        return self.installation_configuration.user_settings_dir / "runtime.json"

    def _legacy_path(self) -> Path:
        """Return the legacy persisted runtime config path."""

        return (
            self.installation_configuration.installation_root
            / "config"
            / "runtime.json"
        )
