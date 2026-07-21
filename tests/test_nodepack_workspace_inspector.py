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

"""Tests for Comfy nodepack workspace inspection helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    core_nodepack_installed,
    nodepack_has_git_metadata,
    nodepack_has_registry_metadata,
    path_is_relative_to,
    source_contains_sentinels,
    tracked_source_files,
)

_INSPECTOR_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "nodepack_workspace_inspector.py"
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


def test_nodepack_workspace_inspector_imports_no_mutating_boundaries() -> None:
    """Workspace inspection must stay free of process, archive, and UI imports."""

    source = _INSPECTOR_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_core_nodepack_installed_requires_all_sentinels(tmp_path: Path) -> None:
    """Installed checks should require the expected folder and every sentinel."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    root = tmp_path / nodepack.expected_folder
    for sentinel in nodepack.sentinel_files[:-1]:
        _write_file(root / sentinel, "")

    assert core_nodepack_installed(tmp_path, nodepack) is False

    _write_file(root / nodepack.sentinel_files[-1], "")

    assert core_nodepack_installed(tmp_path, nodepack) is True


def test_old_sugarcubes_layout_is_recognized_for_version_reconciliation(
    tmp_path: Path,
) -> None:
    """Layout migration should classify an old checkout as installed, not absent."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    root = tmp_path / nodepack.expected_folder
    _write_file(root / "__init__.py", "")
    _write_file(root / "pyproject.toml", "[project]\nname='SugarCubes'\n")
    _write_file(root / "nodes.py", "")
    _write_file(root / "backend" / "__init__.py", "")

    assert core_nodepack_installed(tmp_path, nodepack) is True


def test_source_contains_sentinels_checks_checkout_root(tmp_path: Path) -> None:
    """Local source checks should validate sentinel files under the source root."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    for sentinel in nodepack.sentinel_files:
        _write_file(tmp_path / "source" / sentinel, "")

    assert source_contains_sentinels(tmp_path / "source", nodepack) is True
    assert source_contains_sentinels(tmp_path / "missing", nodepack) is False


def test_nodepack_metadata_detection(tmp_path: Path) -> None:
    """Metadata checks should distinguish git and Comfy Registry folders."""

    target = tmp_path / "nodepack"
    (target / ".git").mkdir(parents=True)
    _write_file(target / "pyproject.toml", "[project]\nname='nodepack'\n")

    assert nodepack_has_git_metadata(target) is True
    assert nodepack_has_registry_metadata(target) is False

    _write_file(target / ".tracking", "pyproject.toml\n")

    assert nodepack_has_registry_metadata(target) is True


def test_tracked_source_files_filters_generated_and_untrusted_metadata(
    tmp_path: Path,
) -> None:
    """Registry tracking should include source files and skip generated folders."""

    source = tmp_path / "source"
    _write_file(source / "__init__.py", "")
    _write_file(source / "nested" / "node.py", "")
    _write_file(source / ".tracking", "")
    _write_file(source / ".git" / "HEAD", "")
    _write_file(source / "tests" / "test_node.py", "")
    _write_file(source / "node_modules" / "package" / "index.js", "")
    _write_file(source / "__pycache__" / "node.pyc", "")

    assert tracked_source_files(source) == (
        Path("__init__.py"),
        Path("nested") / "node.py",
    )


def test_path_is_relative_to_uses_path_parts_not_string_prefix() -> None:
    """Relative checks should not accept sibling paths with matching prefixes."""

    parent = Path("custom_nodes") / "SugarCubes"

    assert path_is_relative_to(parent / "backend" / "__init__.py", parent) is True
    assert path_is_relative_to(Path("custom_nodes") / "SugarCubes2", parent) is False


def _write_file(path: Path, content: str) -> None:
    """Write one test file and create parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
