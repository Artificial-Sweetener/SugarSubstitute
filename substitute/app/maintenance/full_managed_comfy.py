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

"""Stage and validate a fresh managed Comfy candidate for installer repair."""

from __future__ import annotations

import logging
from pathlib import Path

from substitute.app.maintenance.owned_nodes import OwnedNodeMaintenanceService
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)

_LOGGER = logging.getLogger(__name__)


class FullManagedComfyMaintenanceError(RuntimeError):
    """Report an unsafe candidate path or incomplete managed workspace."""


class FullManagedComfyMaintenanceService:
    """Build a verified fresh workspace without touching the active Comfy tree."""

    def stage(self, *, install_root: Path, destination: Path) -> None:
        """Provision a fresh pinned workspace inside repair-owned staging."""

        candidate = _require_staging_destination(install_root, destination)
        if candidate.exists() and any(candidate.iterdir()):
            raise FullManagedComfyMaintenanceError(
                f"Full Comfy staging destination is not empty: {candidate}"
            )
        candidate.mkdir(parents=True, exist_ok=True)
        ensure_managed_comfy_setup(
            workspace=candidate,
            force_cpu_mode=False,
            prefer_edge_torch=False,
            prefer_edge_comfy_channel=False,
            on_status=lambda message: _LOGGER.info(
                "Full managed Comfy staging status | message=%s", message
            ),
            on_log=lambda message: _LOGGER.info(
                "Full managed Comfy staging output | message=%s", message
            ),
        )
        self.validate(candidate)

    def validate(self, workspace: Path) -> None:
        """Require core, runtime, and both exact app-owned nodepacks."""

        resolved = workspace.resolve()
        if workspace.is_symlink() or not resolved.is_dir():
            raise FullManagedComfyMaintenanceError(
                f"Managed Comfy workspace is unavailable or unsafe: {workspace}"
            )
        missing = tuple(
            path
            for path in (workspace_main_path(resolved), workspace_python_path(resolved))
            if not path.is_file()
        )
        if missing:
            raise FullManagedComfyMaintenanceError(
                "Managed Comfy workspace is incomplete: "
                + ", ".join(str(path) for path in missing)
            )
        OwnedNodeMaintenanceService().validate(resolved)


def _require_staging_destination(install_root: Path, destination: Path) -> Path:
    """Accept only a non-link descendant of this install's repair staging tree."""

    root = install_root.resolve()
    candidate = destination.resolve()
    staging_root = root / ".repair" / "staging"
    if (
        destination.is_symlink()
        or candidate == staging_root
        or not candidate.is_relative_to(staging_root)
    ):
        raise FullManagedComfyMaintenanceError(
            f"Full Comfy staging destination is unsafe: {destination}"
        )
    return candidate


__all__ = [
    "FullManagedComfyMaintenanceError",
    "FullManagedComfyMaintenanceService",
]
