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

"""Restore and validate exact SugarSubstitute-owned Comfy nodepacks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    refresh_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    NodepackInstallationInspector,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.version_control import repository_service


class OwnedNodeMaintenanceError(RuntimeError):
    """Report owned nodepacks that cannot be restored or proven exact."""


NodepackRefresher = Callable[..., None]


class OwnedNodeMaintenanceService:
    """Compose existing nodepack policy for a repair-specific headless use case."""

    def __init__(self, *, refresher: NodepackRefresher = refresh_core_comfy_nodepacks):
        """Store the production nodepack reconciliation boundary."""

        self._refresher = refresher

    def repair(self, workspace: Path) -> None:
        """Install every exact owned nodepack into an existing Comfy runtime."""

        resolved = _require_workspace(workspace)
        self._refresher(
            resolved,
            nodepacks=frozenset(CoreNodepackId),
        )

    def validate(self, workspace: Path) -> None:
        """Raise unless identity, version, and sentinels match every exact pin."""

        resolved = _require_workspace(workspace)
        inspector = NodepackInstallationInspector(repository_service())
        mismatches = tuple(
            f"{nodepack.registry_id}@{nodepack.required_version}"
            for nodepack in CORE_COMFY_NODEPACKS
            if not inspector.inspect(workspace=resolved, nodepack=nodepack).matches(
                nodepack
            )
        )
        if mismatches:
            raise OwnedNodeMaintenanceError(
                "Managed Comfy nodepack validation failed: " + ", ".join(mismatches)
            )


def _require_workspace(workspace: Path) -> Path:
    """Return one existing non-link workspace directory."""

    resolved = workspace.resolve()
    if workspace.is_symlink() or not resolved.is_dir():
        raise OwnedNodeMaintenanceError(
            f"Managed Comfy workspace is unavailable or unsafe: {workspace}"
        )
    return resolved


__all__ = ["OwnedNodeMaintenanceError", "OwnedNodeMaintenanceService"]
