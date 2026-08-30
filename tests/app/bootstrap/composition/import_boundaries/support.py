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

"""Provide isolated-process support for bootstrap import-boundary tests."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
COMPOSITION_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "composition.py"
)
_IMPORT_PROBE_TIMEOUT_SECONDS = 30


def run_isolated_import_probe(code: str) -> subprocess.CompletedProcess[str]:
    """Run one import probe from the repository with bounded diagnostics."""

    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=_IMPORT_PROBE_TIMEOUT_SECONDS,
    )


def top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at top level by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
