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

"""Tests for nodepack dependency-only Python reconciliation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_python_dependencies,
    nodepack_python_dependencies_satisfied,
    read_nodepack_python_dependencies,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from sugarsubstitute_shared.startup_remote_access import StartupConnectivityError

_MODULE = (
    Path(__file__).resolve().parents[4]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "nodepack_python_dependencies.py"
)


def test_dependency_owner_imports_no_nodepack_acquisition_or_ui_boundaries() -> None:
    """Keep dependency reconciliation separate from archives, Registry, and UI."""

    imported = _imported_module_names(ast.parse(_MODULE.read_text(encoding="utf-8")))

    assert not {
        name
        for name in imported
        if name.startswith(("PySide6", "substitute.presentation", "urllib", "zipfile"))
    }


def test_install_uses_only_declared_dependencies_not_nodepack_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never create a second importable nodepack copy in site-packages."""

    nodepack_root = tmp_path / "custom_nodes" / "substitute-backend"
    _write_pyproject(
        nodepack_root,
        dependencies=("aiohttp>=3", "sugar-dsl==1.2.0"),
    )
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    observed: dict[str, object] = {}

    def fake_stream(command: list[str], **kwargs: Any) -> tuple[int, tuple[str, ...]]:
        """Capture the dependency-only pip invocation."""

        observed["command"] = command
        observed.update(kwargs)
        return 0, ()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.stream_command_collecting_output",
        fake_stream,
    )

    install_nodepack_python_dependencies(
        python_executable=python,
        nodepack_root=nodepack_root,
        display_name="Substitute BackEnd",
        env={"EXAMPLE": "1"},
    )

    assert observed["command"] == [
        subprocess_path(python),
        "-m",
        "pip",
        "install",
        "aiohttp>=3",
        "sugar-dsl==1.2.0",
    ]
    assert subprocess_path(nodepack_root) not in observed["command"]
    assert observed["cwd"] == nodepack_root
    assert observed["env"] == {"EXAMPLE": "1"}


def test_empty_dependency_list_performs_no_pip_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Avoid unnecessary process work for dependency-free nodepacks."""

    _write_pyproject(tmp_path, dependencies=())
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.stream_command_collecting_output",
        lambda *args, **kwargs: pytest.fail("pip must not run"),
    )

    install_nodepack_python_dependencies(
        python_executable=tmp_path / "python.exe",
        nodepack_root=tmp_path,
        display_name="Example",
    )


def test_dependency_install_promotes_connectivity_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nodepack pip transport evidence must activate startup degradation."""

    _write_pyproject(tmp_path, dependencies=("example",))
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.stream_command_collecting_output",
        lambda *args, **kwargs: (
            1,
            ("NewConnectionError: network is unreachable",),
        ),
    )

    with pytest.raises(StartupConnectivityError):
        install_nodepack_python_dependencies(
            python_executable=tmp_path / "python.exe",
            nodepack_root=tmp_path,
            display_name="Example",
        )


def test_dependency_manifest_rejects_invalid_values(tmp_path: Path) -> None:
    """Fail closed when a nodepack project manifest is structurally invalid."""

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\ndependencies = "requests"\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid project dependencies"):
        read_nodepack_python_dependencies(tmp_path / "pyproject.toml")


def test_dependency_probe_uses_selected_python_and_honors_markers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Evaluate exact requirements inside Comfy's selected interpreter."""

    _write_pyproject(
        tmp_path,
        dependencies=("pip>=1", "missing-package; python_version < '2'"),
    )
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: Any) -> object:
        """Capture the isolated dependency probe."""

        observed["command"] = command
        observed.update(kwargs)
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.run_command",
        fake_run,
    )

    assert nodepack_python_dependencies_satisfied(
        python_executable=tmp_path / "python.exe",
        nodepack_root=tmp_path,
        env=None,
    )
    command = observed["command"]
    assert isinstance(command, list)
    assert "requirement.marker.evaluate()" in command[2]


def _write_pyproject(root: Path, *, dependencies: tuple[str, ...]) -> None:
    """Write one dependency manifest fixture."""

    root.mkdir(parents=True, exist_ok=True)
    rendered = ", ".join(repr(value) for value in dependencies)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "example"\nversion = "1.0.0"\ndependencies = [{rendered}]\n',
        encoding="utf-8",
    )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
