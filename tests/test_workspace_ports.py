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

"""Architecture tests for shell workspace port protocols."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_ports.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_workspace_ports_imports_no_concrete_qt_or_controller_boundaries() -> None:
    """Workspace ports should not import Qt or concrete workspace controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_workspace_composition_consumes_workspace_ports() -> None:
    """Workspace composition should import protocols from the dedicated port owner."""

    controller_source = (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "shell"
        / "workspace_controller.py"
    ).read_text(encoding="utf-8")
    composition_source = (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "shell"
        / "workspace_controller_composition.py"
    ).read_text(encoding="utf-8")

    assert "from substitute.presentation.shell.workspace_ports import" in (
        composition_source
    )
    assert "class InputCanvasPresenterProtocol(Protocol)" not in controller_source
    assert "class WorkspaceGenerationView(Protocol)" not in controller_source
