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

"""SugarCubes maintenance fixtures."""

from __future__ import annotations

import ast
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "sugarcubes_maintenance_runner.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def _write_maintenance_fixture(workspace: Path) -> Path:
    """Create the minimum workspace files required by maintenance startup."""

    python_path = _workspace_python_path(workspace)
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    maintenance_path = (
        workspace / "custom_nodes" / "SugarCubes" / "sugarcubes" / "maintenance.py"
    )
    maintenance_path.parent.mkdir(parents=True)
    maintenance_path.write_text("", encoding="utf-8")
    return python_path


def _workspace_python_path(workspace: Path) -> Path:
    """Return the host-native managed Python path for a Comfy workspace."""

    relative_path = (
        Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    )
    return workspace / ".venv" / relative_path


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
