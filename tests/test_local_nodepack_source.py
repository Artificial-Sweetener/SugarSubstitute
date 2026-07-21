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

"""Tests for developer-local Comfy nodepack source handling."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.local_nodepack_source import (
    copy_local_nodepack_source,
    resolve_local_nodepack_source,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS

_LOCAL_SOURCE_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "local_nodepack_source.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.app",
    "subprocess",
    "urllib",
    "zipfile",
)


def test_local_nodepack_source_imports_no_ui_network_archive_or_process_boundaries() -> (
    None
):
    """Local source handling must stay GUI-free and avoid network/archive/process work."""

    source = _LOCAL_SOURCE_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_local_nodepack_copy_excludes_development_artifacts(tmp_path: Path) -> None:
    """Local-source installs should not copy caches, git metadata, or node_modules."""

    source = tmp_path / "source"
    _write_file(source / "__init__.py", "")
    _write_file(source / "backend" / "__init__.py", "")
    _write_file(source / "nodes.py", "")
    _write_file(source / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write_file(source / ".sugarcubes" / "tracked_repos.json", "{}")
    _write_file(
        source / ".sugarcubes" / "Artificial-Sweetener" / "Base-Cubes" / "README.md",
        "",
    )
    _write_file(
        source
        / ".sugarcubes"
        / "Artificial-Sweetener"
        / "Base-Cubes"
        / ".git"
        / "HEAD",
        "ref: refs/heads/main\n",
    )
    _write_file(source / "node_modules" / "package" / "index.js", "")
    _write_file(source / "__pycache__" / "nodes.pyc", "")
    target = tmp_path / "custom_nodes" / "SugarCubes"

    copy_local_nodepack_source(source_path=source, target_path=target)

    assert (target / "__init__.py").is_file()
    assert (target / "backend" / "__init__.py").is_file()
    assert not (target / ".git").exists()
    assert not (target / ".sugarcubes").exists()
    assert not (target / "node_modules").exists()
    assert not (target / "__pycache__").exists()


def test_local_nodepack_copy_rejects_existing_target(tmp_path: Path) -> None:
    """Local-source installs should not overwrite a target unless allowed."""

    source = tmp_path / "source"
    target = tmp_path / "target"
    _write_file(source / "__init__.py", "")
    target.mkdir()

    with pytest.raises(RuntimeError, match="Custom node target already exists"):
        copy_local_nodepack_source(source_path=source, target_path=target)


def test_local_nodepack_copy_allows_existing_target_overlay(tmp_path: Path) -> None:
    """Pinned-source overlays should be able to merge local source files."""

    source = tmp_path / "source"
    target = tmp_path / "target"
    _write_file(source / "new.txt", "new")
    _write_file(target / "existing.txt", "existing")

    copy_local_nodepack_source(
        source_path=source,
        target_path=target,
        allow_existing=True,
    )

    assert (target / "existing.txt").read_text(encoding="utf-8") == "existing"
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"


def test_resolve_local_nodepack_source_uses_valid_configured_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A configured local source should win when it contains sentinel files."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    env_var = nodepack.local_source_environment_variable
    assert env_var is not None
    for sentinel in nodepack.sentinel_layouts[0]:
        _write_file(tmp_path / "source" / sentinel, "")
    monkeypatch.setenv(env_var, str(tmp_path / "source"))

    assert resolve_local_nodepack_source(nodepack) == (tmp_path / "source").resolve()


def test_resolve_local_nodepack_source_rejects_invalid_configured_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A configured local source must contain the nodepack sentinel files."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    env_var = nodepack.local_source_environment_variable
    assert env_var is not None
    monkeypatch.setenv(env_var, str(tmp_path / "missing"))

    with pytest.raises(RuntimeError, match=env_var):
        resolve_local_nodepack_source(nodepack)


def _write_file(path: Path, content: str) -> None:
    """Write one test file and create its parents."""

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
