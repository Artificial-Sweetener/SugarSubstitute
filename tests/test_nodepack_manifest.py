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

"""Tests for trusted Comfy nodepack manifest definitions."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.nodepack_manifest import (
    ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS,
    CLI_INSTALL_TIMEOUT_SECONDS,
    CORE_COMFY_NODEPACKS,
    NODEPACK_BACKUP_KEEP_COUNT,
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SUGARCUBES_COMPANION_NODEPACKS,
)

_MANIFEST_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "nodepack_manifest.py"
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


def test_nodepack_manifest_imports_no_process_archive_or_ui_boundaries() -> None:
    """The manifest owner must stay pure trusted install metadata."""

    source = _MANIFEST_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_core_nodepack_manifest_contains_expected_install_identities() -> None:
    """Core nodepack definitions should keep install identities centralized."""

    by_project = {nodepack.project_name: nodepack for nodepack in CORE_COMFY_NODEPACKS}

    assert (
        by_project["substitute-backend"].nodepack_id
        is CoreNodepackId.SUBSTITUTE_BACKEND
    )
    assert by_project["substitute-backend"].registry_id == "substitute-backend"
    assert by_project["substitute-backend"].source_url == (
        "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git"
    )
    assert by_project["substitute-backend"].minimum_python_distribution_version == (
        "1.7.0"
    )
    assert by_project["substitute-backend"].pinned_source_archive_url == (
        "https://github.com/Artificial-Sweetener/Substitute-BackEnd/archive/refs/tags/"
        "v1.7.0.zip"
    )
    assert by_project["substitute-backend"].expected_folder == (
        Path("custom_nodes") / "Substitute-BackEnd"
    )
    assert by_project["SugarCubes"].nodepack_id is CoreNodepackId.SUGARCUBES
    assert by_project["SugarCubes"].registry_id == "SugarCubes"
    assert by_project["SugarCubes"].source_url == (
        "https://github.com/Artificial-Sweetener/SugarCubes.git"
    )
    assert by_project["SugarCubes"].minimum_python_distribution_version == "0.10.0"
    assert by_project["SugarCubes"].pinned_source_archive_url == (
        "https://github.com/Artificial-Sweetener/SugarCubes/archive/refs/tags/"
        "v0.10.0.zip"
    )
    assert by_project["SugarCubes"].expected_folder == (
        Path("custom_nodes") / "SugarCubes"
    )


def test_sugarcubes_nodepack_manifest_contains_trusted_install_fallbacks() -> None:
    """SugarCubes companion nodepacks should stay in the manifest owner."""

    assert (
        SUGARCUBES_BASE_NODEPACK_INSTALLS["comfyui-vectorscope-cc"][0].install_id
        == "vectorscope"
    )
    assert (
        SUGARCUBES_BASE_NODEPACK_INSTALLS["seedvr2_videoupscaler"][
            0
        ].expected_folder_name
        == "seedvr2_videoupscaler"
    )
    assert SUGARCUBES_COMPANION_NODEPACKS == {
        "SimpleSyrup": ("comfyui-prompt-control",),
    }


def test_nodepack_manifest_centralizes_timeout_and_retention_policy() -> None:
    """Nodepack timeout and backup retention policy should be manifest-owned."""

    assert CLI_INSTALL_TIMEOUT_SECONDS == 900
    assert ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS == 120
    assert NODEPACK_BACKUP_KEEP_COUNT == 5


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
