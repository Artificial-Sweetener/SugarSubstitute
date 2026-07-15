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

"""Persist the managed Comfy runtime configuration under the install state root."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from substitute.application.ports.managed_runtime_repository import (
    ManagedRuntimeConfigurationRepository,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)


@dataclass
class FileManagedRuntimeConfigurationRepository(ManagedRuntimeConfigurationRepository):
    """Load and save managed runtime state under app runtime state storage."""

    runtime_state_dir: Path

    def exists(self) -> bool:
        """Return whether persisted managed runtime configuration exists."""

        return self._path().exists()

    def build_default(self) -> ManagedRuntimeConfiguration:
        """Build the default managed runtime configuration for this installation."""

        return ManagedRuntimeConfiguration()

    def load(self) -> ManagedRuntimeConfiguration:
        """Load managed runtime configuration or synthesize the default state."""

        path = self._path()
        if not path.exists():
            return self.build_default()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ManagedRuntimeConfiguration(
            workspace_path=_optional_string(payload.get("workspace_path")),
            detected_platform=_optional_string(payload.get("detected_platform")),
            detected_accelerator=_optional_string(payload.get("detected_accelerator")),
            detected_adapter_name=_optional_string(
                payload.get("detected_adapter_name")
            ),
            install_target=_optional_string(payload.get("install_target")),
            python_version=_optional_string(payload.get("python_version")),
            python_fallback_used=bool(payload.get("python_fallback_used", False)),
            comfy_channel=_optional_string(payload.get("comfy_channel")),
            backend_policy=_optional_string(payload.get("backend_policy")),
            torch_release_channel=_optional_string(
                payload.get("torch_release_channel")
            ),
            torch_selection_reason=_optional_string(
                payload.get("torch_selection_reason")
            ),
            torch_fallback_used=bool(payload.get("torch_fallback_used", False)),
            stability=ManagedRuntimeStability(payload.get("stability", "stable")),
            prefer_edge_torch=bool(payload.get("prefer_edge_torch", False)),
            prefer_edge_comfy_channel=bool(
                payload.get("prefer_edge_comfy_channel", False)
            ),
            force_cpu_mode=bool(payload.get("force_cpu_mode", False)),
            validation_status=ManagedRuntimeValidationStatus(
                payload.get("validation_status", "unknown")
            ),
            validation_detail=_optional_string(payload.get("validation_detail")),
            last_validation_at=_optional_string(payload.get("last_validation_at")),
            launch_status=ManagedRuntimeLaunchStatus(
                payload.get("launch_status", "unknown")
            ),
            launch_detail=_optional_string(payload.get("launch_detail")),
            last_launch_at=_optional_string(payload.get("last_launch_at")),
        )

    def save(self, configuration: ManagedRuntimeConfiguration) -> None:
        """Persist managed runtime configuration to the install state directory."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "workspace_path": configuration.workspace_path,
                    "detected_platform": configuration.detected_platform,
                    "detected_accelerator": configuration.detected_accelerator,
                    "detected_adapter_name": configuration.detected_adapter_name,
                    "install_target": configuration.install_target,
                    "python_version": configuration.python_version,
                    "python_fallback_used": configuration.python_fallback_used,
                    "comfy_channel": configuration.comfy_channel,
                    "backend_policy": configuration.backend_policy,
                    "torch_release_channel": configuration.torch_release_channel,
                    "torch_selection_reason": configuration.torch_selection_reason,
                    "torch_fallback_used": configuration.torch_fallback_used,
                    "stability": configuration.stability.value,
                    "prefer_edge_torch": configuration.prefer_edge_torch,
                    "prefer_edge_comfy_channel": configuration.prefer_edge_comfy_channel,
                    "force_cpu_mode": configuration.force_cpu_mode,
                    "validation_status": configuration.validation_status.value,
                    "validation_detail": configuration.validation_detail,
                    "last_validation_at": configuration.last_validation_at,
                    "launch_status": configuration.launch_status.value,
                    "launch_detail": configuration.launch_detail,
                    "last_launch_at": configuration.last_launch_at,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _path(self) -> Path:
        """Return the persisted managed runtime configuration path."""

        return self.runtime_state_dir / "managed_runtime.json"


def _optional_string(value: object) -> str | None:
    """Normalize one optional string payload value."""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


__all__ = ["FileManagedRuntimeConfigurationRepository"]
