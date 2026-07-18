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

"""Resolve and copy developer-local Comfy nodepack sources."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    source_contains_sentinels,
)


def resolve_local_nodepack_source(nodepack: CoreComfyNodepack) -> Path | None:
    """Return a developer-local source checkout for an unpublished nodepack."""

    if nodepack.local_source_environment_variable is not None:
        configured_source = os.environ.get(nodepack.local_source_environment_variable)
        if configured_source:
            source_path = Path(configured_source).expanduser().resolve()
            if source_contains_sentinels(source_path, nodepack):
                return source_path
            raise RuntimeError(
                f"{nodepack.local_source_environment_variable} does not point to a "
                f"valid {nodepack.display_name} checkout: {source_path}"
            )
    return None


def copy_local_nodepack_source(
    *,
    source_path: Path,
    target_path: Path,
    allow_existing: bool = False,
) -> None:
    """Copy one unpublished local nodepack checkout into a Comfy custom_nodes folder."""

    resolved_source = source_path.resolve()
    resolved_target = target_path.resolve()
    if resolved_target.exists() and not allow_existing:
        raise RuntimeError(f"Custom node target already exists: {resolved_target}")
    shutil.copytree(
        resolved_source,
        resolved_target,
        dirs_exist_ok=allow_existing,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "node_modules",
            "tests",
            ".sugarcubes",
        ),
    )


__all__ = [
    "copy_local_nodepack_source",
    "resolve_local_nodepack_source",
]
