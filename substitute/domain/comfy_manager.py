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

"""Define ComfyUI Manager runtime identity and attached-workspace policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ComfyManagerKind(str, Enum):
    """Identify the supported ComfyUI Manager integration mechanisms."""

    INTEGRATED = "integrated"
    LEGACY_CUSTOM_NODE = "legacy_custom_node"


class ComfyManagerProvisioningAction(str, Enum):
    """Describe the action required to produce a healthy Manager runtime."""

    USE_INTEGRATED = "use_integrated"
    USE_LEGACY = "use_legacy"
    INSTALL_INTEGRATED = "install_integrated"
    INSTALL_LEGACY = "install_legacy"


@dataclass(frozen=True, slots=True)
class ComfyManagerCapabilities:
    """Capture Manager capabilities observed in one attached workspace."""

    supports_integrated: bool
    integrated_healthy: bool
    legacy_healthy: bool


@dataclass(frozen=True, slots=True)
class ComfyManagerRuntime:
    """Describe one validated Manager runtime used for launch and CLI commands."""

    kind: ComfyManagerKind
    workspace: Path
    python_executable: Path
    version: str | None = None
    legacy_cli_path: Path | None = None
    supports_pygit2: bool = False
    uses_pygit2: bool = False

    @property
    def launch_arguments(self) -> tuple[str, ...]:
        """Return the Comfy launch arguments required by this runtime."""

        if self.kind is ComfyManagerKind.INTEGRATED:
            return ("--enable-manager",)
        return ()


def select_attached_manager_action(
    capabilities: ComfyManagerCapabilities,
) -> ComfyManagerProvisioningAction:
    """Select the least-invasive healthy Manager route for attached ComfyUI."""

    if capabilities.integrated_healthy:
        return ComfyManagerProvisioningAction.USE_INTEGRATED
    if capabilities.legacy_healthy:
        return ComfyManagerProvisioningAction.USE_LEGACY
    if capabilities.supports_integrated:
        return ComfyManagerProvisioningAction.INSTALL_INTEGRATED
    return ComfyManagerProvisioningAction.INSTALL_LEGACY


__all__ = [
    "ComfyManagerCapabilities",
    "ComfyManagerKind",
    "ComfyManagerProvisioningAction",
    "ComfyManagerRuntime",
    "select_attached_manager_action",
]
