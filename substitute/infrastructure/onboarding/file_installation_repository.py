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

"""Persist installation configuration inside the visible install root."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from substitute.application.ports.installation_repository import (
    InstallationConfigurationRepository,
)
from substitute.domain.onboarding import InstallationConfiguration
from sugarsubstitute_shared.windows_long_paths import operational_path


@dataclass
class FileInstallationConfigurationRepository(InstallationConfigurationRepository):
    """Load and save installation configuration under `user/settings`."""

    installation_root: Path

    def exists(self) -> bool:
        """Return whether persisted installation configuration exists."""

        return self._path().exists() or self._legacy_path().exists()

    def build_default(self) -> InstallationConfiguration:
        """Build the default installation configuration for this root."""

        return InstallationConfiguration.create_default(self.installation_root)

    def load(self) -> InstallationConfiguration:
        """Load installation configuration or synthesize default install-root paths."""

        path = self._path() if self._path().exists() else self._legacy_path()
        if not path.exists():
            return self.build_default()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return self.build_default()
        return self._configuration_from_payload(payload)

    def _configuration_from_payload(
        self,
        payload: dict[str, object],
    ) -> InstallationConfiguration:
        """Return normalized installation paths from current or legacy JSON."""

        default_configuration = self.build_default()
        installation_root = operational_path(
            str(
                payload.get(
                    "installation_root", default_configuration.installation_root
                )
            )
        )
        default_for_root = InstallationConfiguration.create_default(installation_root)
        legacy_payload = any(
            key in payload
            for key in (
                "config_dir",
                "state_dir",
                "cubes_dir",
                "workspace_custom_nodes_dir",
            )
        )

        def appdata_path(key: str, default_path: Path) -> Path:
            """Return app-data owned paths normalized away from legacy locations."""

            if legacy_payload:
                return default_path
            return operational_path(str(payload.get(key, default_path)))

        projects_dir = operational_path(
            str(payload.get("projects_dir", default_for_root.projects_dir))
        )
        return InstallationConfiguration(
            installation_root=installation_root,
            user_dir=operational_path(
                str(payload.get("user_dir", default_for_root.user_dir))
            ),
            user_settings_dir=operational_path(
                str(
                    payload.get(
                        "user_settings_dir",
                        default_for_root.user_settings_dir,
                    )
                )
            ),
            projects_dir=projects_dir,
            outputs_dir=operational_path(
                str(payload.get("outputs_dir", default_for_root.outputs_dir))
            ),
            sugar_scripts_dir=projects_dir,
            wildcards_dir=operational_path(
                str(payload.get("wildcards_dir", default_for_root.wildcards_dir))
            ),
            appdata_dir=operational_path(
                str(payload.get("appdata_dir", default_for_root.appdata_dir))
            ),
            session_dir=appdata_path("session_dir", default_for_root.session_dir),
            cache_dir=appdata_path("cache_dir", default_for_root.cache_dir),
            diagnostics_dir=appdata_path(
                "diagnostics_dir", default_for_root.diagnostics_dir
            ),
            logs_dir=appdata_path("logs_dir", default_for_root.logs_dir),
            runtime_state_dir=appdata_path(
                "runtime_state_dir", default_for_root.runtime_state_dir
            ),
            model_metadata_dir=appdata_path(
                "model_metadata_dir", default_for_root.model_metadata_dir
            ),
            runtime_dir=operational_path(
                str(payload.get("runtime_dir", default_for_root.runtime_dir))
            ),
            default_managed_comfy_dir=operational_path(
                str(
                    payload.get(
                        "default_managed_comfy_dir",
                        default_for_root.default_managed_comfy_dir,
                    )
                )
            ),
        )

    def save(self, configuration: InstallationConfiguration) -> None:
        """Persist installation configuration to the visible config directory."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "installation_root": str(configuration.installation_root),
                    "user_dir": str(configuration.user_dir),
                    "user_settings_dir": str(configuration.user_settings_dir),
                    "projects_dir": str(configuration.projects_dir),
                    "outputs_dir": str(configuration.outputs_dir),
                    "sugar_scripts_dir": str(configuration.projects_dir),
                    "wildcards_dir": str(configuration.wildcards_dir),
                    "appdata_dir": str(configuration.appdata_dir),
                    "session_dir": str(configuration.session_dir),
                    "cache_dir": str(configuration.cache_dir),
                    "diagnostics_dir": str(configuration.diagnostics_dir),
                    "logs_dir": str(configuration.logs_dir),
                    "runtime_state_dir": str(configuration.runtime_state_dir),
                    "model_metadata_dir": str(configuration.model_metadata_dir),
                    "runtime_dir": str(configuration.runtime_dir),
                    "default_managed_comfy_dir": str(
                        configuration.default_managed_comfy_dir
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _path(self) -> Path:
        """Return the persisted installation config path."""

        return self.installation_root / "user" / "settings" / "installation.json"

    def _legacy_path(self) -> Path:
        """Return the legacy persisted installation config path."""

        return self.installation_root / "config" / "installation.json"
