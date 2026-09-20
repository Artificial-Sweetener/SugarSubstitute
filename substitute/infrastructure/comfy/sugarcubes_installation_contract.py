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

"""Own SugarCubes' installed layout and public maintenance command contract."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

SUGARCUBES_MAINTENANCE_MODULE = "sugarcubes.maintenance"
SUGARCUBES_MAINTENANCE_RELATIVE_PATH = Path("sugarcubes") / "maintenance.py"


def sugarcubes_root(workspace: Path) -> Path:
    """Return the canonical SugarCubes custom-node directory."""

    return workspace / "custom_nodes" / "SugarCubes"


def sugarcubes_maintenance_path(workspace: Path) -> Path:
    """Return the public SugarCubes maintenance entrypoint path."""

    return sugarcubes_maintenance_path_for_root(sugarcubes_root(workspace))


def sugarcubes_maintenance_path_for_root(installed_root: Path) -> Path:
    """Return the public entrypoint beneath an explicitly selected checkout."""

    return installed_root / SUGARCUBES_MAINTENANCE_RELATIVE_PATH


def build_sugarcubes_maintenance_command(
    *,
    python_executable: Path,
    workspace: Path,
    baseline_only: bool,
) -> tuple[str, ...]:
    """Build a read-only SugarCubes check that includes required versions."""

    if baseline_only:
        raise ValueError("Version-aware dependency checks cannot perform repairs.")

    command: tuple[str, ...] = (
        str(python_executable),
        "-m",
        SUGARCUBES_MAINTENANCE_MODULE,
        "cube-deps",
        "sync-and-check",
        "--workspace",
        str(workspace),
    )
    return command


def build_sugarcubes_dependency_repair_command(
    *,
    python_executable: Path,
    workspace: Path,
    approved_node_ids: Sequence[str],
) -> tuple[str, ...]:
    """Build a repair command for every preflight-selected node pack."""

    command: tuple[str, ...] = (
        str(python_executable),
        "-m",
        SUGARCUBES_MAINTENANCE_MODULE,
        "cube-deps",
        "repair",
        "--workspace",
        str(workspace),
    )
    for node_id in approved_node_ids:
        command = (*command, "--approve", node_id)
    return command
