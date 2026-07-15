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

"""Define managed Comfy runtime state shared across readiness, install, and repair."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path


class ManagedRuntimeStability(str, Enum):
    """Describe whether the selected managed runtime path is stable or experimental."""

    STABLE = "stable"
    EXPERIMENTAL = "experimental"


class ManagedRuntimeValidationStatus(str, Enum):
    """Describe the latest managed runtime validation outcome."""

    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID_BACKEND = "invalid_backend"
    INSTALL_FAILED = "install_failed"


class ManagedRuntimeLaunchStatus(str, Enum):
    """Describe the latest managed runtime launch or listener ownership outcome."""

    UNKNOWN = "unknown"
    READY = "ready"
    REUSED_OWNED = "reused_owned"
    STALE_REAPED = "stale_reaped"
    FOREIGN_LISTENER_BLOCKED = "foreign_listener_blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ManagedRuntimeConfiguration:
    """Capture the selected managed runtime policy and its latest health state."""

    workspace_path: str | None = None
    detected_platform: str | None = None
    detected_accelerator: str | None = None
    detected_adapter_name: str | None = None
    install_target: str | None = None
    python_version: str | None = None
    python_fallback_used: bool = False
    comfy_channel: str | None = None
    backend_policy: str | None = None
    torch_release_channel: str | None = None
    torch_selection_reason: str | None = None
    torch_fallback_used: bool = False
    stability: ManagedRuntimeStability = ManagedRuntimeStability.STABLE
    prefer_edge_torch: bool = False
    prefer_edge_comfy_channel: bool = False
    force_cpu_mode: bool = False
    validation_status: ManagedRuntimeValidationStatus = (
        ManagedRuntimeValidationStatus.UNKNOWN
    )
    validation_detail: str | None = None
    last_validation_at: str | None = None
    launch_status: ManagedRuntimeLaunchStatus = ManagedRuntimeLaunchStatus.UNKNOWN
    launch_detail: str | None = None
    last_launch_at: str | None = None

    def for_workspace(
        self, workspace: Path | str | None
    ) -> ManagedRuntimeConfiguration:
        """Return a copy claiming ownership of one managed workspace path."""

        if workspace is None:
            return replace(self, workspace_path=None)
        return replace(self, workspace_path=str(Path(workspace).resolve()))


__all__ = [
    "ManagedRuntimeConfiguration",
    "ManagedRuntimeLaunchStatus",
    "ManagedRuntimeStability",
    "ManagedRuntimeValidationStatus",
]
