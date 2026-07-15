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

"""Persist the selected Comfy target inside the visible install root."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from substitute.application.ports.comfy_target_repository import (
    ComfyTargetConfigurationRepository,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
)


@dataclass
class FileComfyTargetConfigurationRepository(ComfyTargetConfigurationRepository):
    """Load and save the active Comfy target under user settings."""

    installation_configuration: InstallationConfiguration

    def exists(self) -> bool:
        """Return whether persisted target configuration exists."""

        return self._path().exists() or self._legacy_path().exists()

    def build_default(self) -> ComfyTargetConfiguration:
        """Build the default target configuration for this installation."""

        return ComfyTargetConfiguration.create_default(self.installation_configuration)

    def load(self) -> ComfyTargetConfiguration:
        """Load target configuration or synthesize default managed-local settings."""

        path = self._path() if self._path().exists() else self._legacy_path()
        if not path.exists():
            return self.build_default()
        payload = json.loads(path.read_text(encoding="utf-8"))
        workspace_path = payload.get("workspace_path")
        return ComfyTargetConfiguration(
            mode=ComfyTargetMode(payload["mode"]),
            endpoint=ComfyEndpoint(
                host=str(payload["endpoint"]["host"]),
                port=int(payload["endpoint"]["port"]),
            ),
            workspace_path=Path(workspace_path)
            if isinstance(workspace_path, str)
            else None,
            install_owned=bool(payload.get("install_owned", False)),
            launch_owned=bool(payload.get("launch_owned", False)),
        )

    def save(self, configuration: ComfyTargetConfiguration) -> None:
        """Persist target configuration to the visible config directory."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "mode": configuration.mode.value,
                    "endpoint": {
                        "host": configuration.endpoint.host,
                        "port": configuration.endpoint.port,
                    },
                    "workspace_path": (
                        str(configuration.workspace_path)
                        if configuration.workspace_path is not None
                        else None
                    ),
                    "install_owned": configuration.install_owned,
                    "launch_owned": configuration.launch_owned,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _path(self) -> Path:
        """Return the persisted Comfy target config path."""

        return self.installation_configuration.user_settings_dir / "comfy_target.json"

    def _legacy_path(self) -> Path:
        """Return the legacy persisted Comfy target config path."""

        return (
            self.installation_configuration.installation_root
            / "config"
            / "comfy_target.json"
        )
