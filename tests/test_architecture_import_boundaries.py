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

"""Static architecture guards for pure domain and application layers."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PURE_LAYER_ROOTS = (
    PROJECT_ROOT / "substitute" / "domain",
    PROJECT_ROOT / "substitute" / "application",
)
APPLICATION_WORKFLOW_ROOT = PROJECT_ROOT / "substitute" / "application" / "workflows"
OUTPUT_CANVAS_APPLICATION_MODULES = (
    APPLICATION_WORKFLOW_ROOT / "output_canvas_route_scope.py",
    APPLICATION_WORKFLOW_ROOT / "output_preview_lifecycle_service.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qpane",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
)


def _python_files(root: Path) -> tuple[Path, ...]:
    """Return Python source files below one architecture layer root."""

    return tuple(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_domain_and_application_layers_do_not_import_presentation_or_qt() -> None:
    """Keep pure layers independent from Qt widgets and presentation adapters."""

    violations: dict[str, tuple[str, ...]] = {}
    for layer_root in PURE_LAYER_ROOTS:
        for source_path in _python_files(layer_root):
            forbidden_imports = tuple(
                sorted(
                    imported_module
                    for imported_module in _imported_module_names(source_path)
                    if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
                )
            )
            if forbidden_imports:
                violations[str(source_path.relative_to(PROJECT_ROOT))] = (
                    forbidden_imports
                )

    assert violations == {}


def test_application_workflow_modules_do_not_import_presentation_or_qt() -> None:
    """Keep workflow policies portable across PySide, PyQt, and non-Qt runtimes."""

    missing_modules = tuple(
        source_path
        for source_path in OUTPUT_CANVAS_APPLICATION_MODULES
        if not source_path.exists()
    )
    assert missing_modules == ()

    violations: dict[str, tuple[str, ...]] = {}
    for source_path in _python_files(APPLICATION_WORKFLOW_ROOT):
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
