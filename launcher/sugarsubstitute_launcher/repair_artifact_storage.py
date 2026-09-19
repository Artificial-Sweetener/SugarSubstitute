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

"""Allocate unique repair artifacts beneath verified installation-owned storage."""

from __future__ import annotations

from pathlib import Path
import tempfile

from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    RepairArtifactIntegrityError,
)
from sugarsubstitute_shared.windows_long_paths import operational_path
from sugarsubstitute_shared.launcher_version import safe_launcher_version

REPAIR_SESSION_PREFIX = "session-"


def repair_bundle_for_executable(
    *, install_root: Path, executable: Path, executable_relative_path: Path
) -> Path | None:
    """Recognize the repair-owned executable namespace without requiring retained state."""
    helper_root = install_root.resolve() / ".repair" / "helper"
    image = executable.resolve()
    try:
        relative = image.relative_to(helper_root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) != 3 + len(executable_relative_path.parts):
        return None
    if (
        not parts[1].startswith(REPAIR_SESSION_PREFIX)
        or parts[1] == REPAIR_SESSION_PREFIX
        or parts[2] != "bundle"
    ):
        return None
    try:
        safe_launcher_version(parts[0])
    except ValueError:
        return None
    bundle = helper_root / parts[0] / parts[1] / "bundle"
    return bundle if (bundle / executable_relative_path).resolve() == image else None


def create_repair_artifact_directory(
    *,
    install_root: Path,
    parent: Path,
    prefix: str,
) -> Path:
    """Reject redirected ancestors before allocating an independently owned directory."""
    root = operational_path(install_root).absolute()
    parent = operational_path(parent).absolute()
    if not parent.is_relative_to(root / ".repair"):
        raise RepairArtifactIntegrityError("Repair artifact storage escapes its owner.")
    for path in (parent, *parent.parents):
        if path.is_symlink() or path.is_junction():
            raise RepairArtifactIntegrityError(
                f"Repair artifact storage is redirected: {path}"
            )
        if path == root:
            break
    parent.mkdir(parents=True, exist_ok=True)
    return operational_path(tempfile.mkdtemp(prefix=prefix, dir=parent))
