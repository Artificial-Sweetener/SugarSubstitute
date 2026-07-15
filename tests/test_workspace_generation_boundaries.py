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

"""Architecture boundaries for extracted workspace generation modules."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATHS = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py",
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py",
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_scene_generation_controller.py",
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_action_adapter.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.canvas",
    "substitute.presentation.editor",
    "substitute.presentation.shell.app_orb",
    "substitute.presentation.shell.comfy_output_panel",
    "substitute.presentation.shell.main_window",
    "substitute.presentation.shell.search_view",
    "substitute.presentation.shell.settings_",
    "substitute.presentation.shell.shell_layout_controller",
    "substitute.presentation.shell.workspace_controller",
)
FORBIDDEN_SOURCE_TOKENS = (
    "QFileDialog",
    "QMessageBox",
    "QWidget",
    "qfluentwidgets",
    "qframelesswindow",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names in one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_workspace_generation_owners_import_no_concrete_ui_boundaries() -> None:
    """Extracted generation owners must not import Qt or concrete UI widgets."""

    violations: dict[str, tuple[str, ...]] = {}
    for source_path in MODULE_PATHS:
        forbidden_imports = tuple(
            sorted(
                imported_module
                for imported_module in _imported_module_names(source_path)
                if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
            )
        )
        if forbidden_imports:
            violations[str(source_path.relative_to(PROJECT_ROOT))] = forbidden_imports

    assert violations == {}


def test_workspace_generation_owners_reference_no_concrete_ui_tokens() -> None:
    """Extracted generation owners must not reference concrete UI symbols."""

    violations: dict[str, tuple[str, ...]] = {}
    for source_path in MODULE_PATHS:
        source = source_path.read_text(encoding="utf-8")
        forbidden_tokens = tuple(
            token for token in FORBIDDEN_SOURCE_TOKENS if token in source
        )
        if forbidden_tokens:
            violations[str(source_path.relative_to(PROJECT_ROOT))] = forbidden_tokens

    assert violations == {}
