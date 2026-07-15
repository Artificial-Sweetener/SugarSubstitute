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

"""Tests for Comfy workspace Python runtime resolution."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)

_RESOLVER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "workspace_python_resolver.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_workspace_python_resolver_imports_no_process_archive_or_ui_boundaries() -> (
    None
):
    """Workspace Python resolution must stay free of process and UI imports."""

    source = _RESOLVER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_resolve_workspace_python_prefers_managed_venv(tmp_path: Path) -> None:
    """Managed workspaces should use the canonical `.venv` Python first."""

    managed_python = _write_python(tmp_path / ".venv" / "Scripts" / "python.exe")
    _write_python(tmp_path / "venv" / "Scripts" / "python.exe")

    assert resolve_workspace_python(tmp_path) == managed_python


def test_resolve_workspace_python_supports_existing_comfy_venv(tmp_path: Path) -> None:
    """Adopted Comfy workspaces may use `venv` instead of managed `.venv`."""

    python_path = _write_python(tmp_path / "venv" / "Scripts" / "python.exe")

    assert resolve_workspace_python(tmp_path) == python_path


def test_resolve_workspace_python_supports_embeded_runtime_typo(
    tmp_path: Path,
) -> None:
    """Portable Comfy builds may use the historical `python_embeded` folder."""

    python_path = _write_python(tmp_path / "python_embeded" / "python.exe")

    assert resolve_workspace_python(tmp_path) == python_path


def test_resolve_workspace_python_supports_embedded_runtime_spelling(
    tmp_path: Path,
) -> None:
    """Portable Comfy builds may also use the corrected embedded folder spelling."""

    python_path = _write_python(tmp_path / "python_embedded" / "python.exe")

    assert resolve_workspace_python(tmp_path) == python_path


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX workspace paths are non-Windows only"
)
def test_resolve_workspace_python_supports_posix_venv(tmp_path: Path) -> None:
    """Non-Windows workspaces should accept POSIX virtualenv Python paths."""

    python_path = _write_python(tmp_path / "venv" / "bin" / "python")

    assert resolve_workspace_python(tmp_path) == python_path


def test_resolve_workspace_python_reports_missing_runtime(tmp_path: Path) -> None:
    """Missing workspace runtimes should fail with a setup-facing message."""

    with pytest.raises(RuntimeError, match="Could not find a Python runtime"):
        resolve_workspace_python(tmp_path)


def _write_python(path: Path) -> Path:
    """Create one fake Python executable file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
