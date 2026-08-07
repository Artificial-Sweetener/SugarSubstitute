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

"""Migrate persisted core nodepack folders to their Registry-owned paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.nodepack_installation_path_migrator")


def canonicalize_nodepack_root(
    *,
    workspace: Path,
    current_root: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
) -> Path:
    """Atomically rename a managed legacy folder to its Registry path."""

    canonical_root = workspace / nodepack.expected_folder
    if current_root.parent != canonical_root.parent:
        raise RuntimeError(
            f"Nodepack path is outside its canonical parent: {current_root}"
        )
    if current_root.name == canonical_root.name:
        return current_root
    if canonical_root.exists() and not current_root.samefile(canonical_root):
        raise RuntimeError(
            f"Both legacy and canonical nodepack folders exist: {current_root} and "
            f"{canonical_root}"
        )
    temporary_root = current_root.with_name(
        f".{canonical_root.name}.migration-{uuid4().hex}"
    )
    current_root.rename(temporary_root)
    try:
        temporary_root.rename(canonical_root)
    except Exception:
        temporary_root.rename(current_root)
        raise
    message = (
        f"[ComfyNodepacks] Migrated {nodepack.display_name} to its "
        "Comfy Registry folder."
    )
    log_info(
        _LOGGER,
        message,
        nodepack_id=nodepack.nodepack_id.value,
        previous_path=str(current_root),
        canonical_path=str(canonical_root),
    )
    if on_log is not None:
        on_log(message)
    return canonical_root


__all__ = ["canonicalize_nodepack_root"]
