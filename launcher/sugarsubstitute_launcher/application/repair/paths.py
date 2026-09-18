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

"""Own current and persisted legacy repair preparation namespaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sugarsubstitute_shared.launcher_version import safe_launcher_version
from sugarsubstitute_shared.windows_long_paths import operational_path


@dataclass(frozen=True, slots=True)
class RepairPreparationPaths:
    """Bind a repair attempt's staged inputs and canonical request location."""

    install_root: Path
    version: str
    preparation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate path components before any repair storage is accessed."""
        safe_launcher_version(self.version)
        if (
            self.preparation_id is not None
            and UUID(self.preparation_id).hex != self.preparation_id
        ):
            raise ValueError("Repair preparation identity must be canonical UUID hex.")

    @property
    def staging_root(self) -> Path:
        """Return the attempt namespace, retaining legacy version-bound requests."""
        root = (
            operational_path(self.install_root).resolve()
            / ".repair"
            / "staging"
            / self.version
        )
        return root / self.preparation_id if self.preparation_id is not None else root

    @property
    def request_path(self) -> Path:
        """Return the sole request location owned by this prepared attempt."""
        if self.preparation_id is None:
            return (
                operational_path(self.install_root).resolve()
                / ".repair"
                / "prepared.json"
            )
        return self.staging_root / "request.json"

    @staticmethod
    def accepts_request(install_root: Path, request_path: Path) -> bool:
        """Recognize producer-owned invocation paths even after request retirement."""
        root = operational_path(install_root).resolve()
        request = operational_path(request_path).resolve()
        if request == root / ".repair" / "prepared.json":
            return True
        try:
            parts = request.relative_to(root).parts
            if (
                len(parts) != 5
                or parts[:2] != (".repair", "staging")
                or parts[4] != "request.json"
            ):
                return False
            return (
                RepairPreparationPaths(root, parts[2], parts[3]).request_path == request
            )
        except (ValueError, OSError):
            return False
