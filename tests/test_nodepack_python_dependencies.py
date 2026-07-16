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

"""Tests for Comfy nodepack Python dependency management."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
from typing import Any, cast

import pytest

from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    egg_info_distribution_name,
    install_editable_nodepack_python_dependencies,
    installed_python_distribution_version,
    nodepack_python_distributions_satisfy_minimum,
    normalized_distribution_name,
    remove_noncanonical_python_distribution_metadata,
    version_at_least,
    version_key,
)

_DEPENDENCIES_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "nodepack_python_dependencies.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.app",
    "urllib",
    "zipfile",
)


def test_nodepack_python_dependencies_imports_no_ui_or_archive_boundaries() -> None:
    """Dependency management must stay GUI-free and avoid archive/network work."""

    source = _DEPENDENCIES_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_install_editable_nodepack_python_dependencies_uses_pip_editable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Editable nodepack installs should run pip in the nodepack root."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    nodepack_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    emitted: list[str] = []
    observed: dict[str, object] = {}

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        timeout_seconds: int | None = None,
        env: object | None = None,
    ) -> int:
        observed["command"] = command
        observed["cwd"] = cwd
        observed["on_line"] = on_line
        observed["timeout_seconds"] = timeout_seconds
        observed["env"] = env
        return 0

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.stream_command",
        fake_stream,
    )

    install_editable_nodepack_python_dependencies(
        python_executable=python_path,
        nodepack_root=nodepack_root,
        display_name="Substitute BackEnd",
        on_log=emitted.append,
        env={"EXAMPLE": "1"},
    )

    assert observed["command"] == [
        str(python_path),
        "-m",
        "pip",
        "install",
        "-e",
        str(nodepack_root),
    ]
    assert observed["cwd"] == nodepack_root
    assert observed["on_line"] == emitted.append
    assert observed["env"] == {"EXAMPLE": "1"}
    assert emitted == [
        "[ComfyNodepacks] Updating Substitute BackEnd Python dependencies."
    ]


def test_install_editable_nodepack_python_dependencies_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Failed editable pip installs should raise an actionable setup error."""

    def fake_stream(
        command: list[str],
        **kwargs: object,
    ) -> int:
        _ = command, kwargs
        return 9

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.stream_command",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="Could not update SugarCubes"):
        install_editable_nodepack_python_dependencies(
            python_executable=tmp_path / "python.exe",
            nodepack_root=tmp_path,
            display_name="SugarCubes",
        )


def test_installed_python_distribution_version_reads_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Installed distribution probes should execute importlib metadata in workspace Python."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    observed: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="1.6.0\n", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.run_command",
        fake_run,
    )

    assert (
        installed_python_distribution_version(
            python_executable=python_path,
            cwd=tmp_path,
            distribution_name="substitute-backend",
            on_log=None,
            env={"EXAMPLE": "1"},
        )
        == "1.6.0"
    )
    command = cast(list[str], observed["command"])
    assert command[0] == str(python_path)
    assert command[1] == "-c"
    assert "metadata.version('substitute-backend')" in command[2]
    assert observed["cwd"] == tmp_path
    assert observed["env"] == {"EXAMPLE": "1"}


def test_installed_python_distribution_version_logs_probe_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing distribution metadata should return None and emit context."""

    def fake_run(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="missing")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.run_command",
        fake_run,
    )
    emitted: list[str] = []

    assert (
        installed_python_distribution_version(
            python_executable=tmp_path / "python.exe",
            cwd=tmp_path,
            distribution_name="SugarCubes",
            on_log=emitted.append,
            env=None,
        )
        is None
    )
    assert emitted == [
        "[ComfyNodepacks] Could not read installed SugarCubes version from Comfy Python."
    ]


def test_nodepack_python_distributions_satisfy_minimum_uses_manifest_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nodepack version checks should derive distribution policy from the manifest."""

    backend_nodepack = next(
        nodepack
        for nodepack in CORE_COMFY_NODEPACKS
        if nodepack.project_name == "substitute-backend"
    )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.nodepack_python_dependencies.installed_python_distribution_version",
        lambda **kwargs: "1.7.0",
    )

    assert nodepack_python_distributions_satisfy_minimum(
        python_executable=tmp_path / "python.exe",
        cwd=tmp_path,
        nodepack=backend_nodepack,
        on_log=None,
        env=None,
    )


def test_remove_noncanonical_python_distribution_metadata_keeps_canonical(
    tmp_path: Path,
) -> None:
    """Metadata cleanup should delete stale egg-info while preserving canonical names."""

    sugarcubes_nodepack = next(
        nodepack
        for nodepack in CORE_COMFY_NODEPACKS
        if nodepack.project_name == "SugarCubes"
    )
    canonical_metadata = tmp_path / "SugarCubes.egg-info"
    stale_metadata = tmp_path / "obsolete_sugarcubes.egg-info"
    missing_name_metadata = tmp_path / "unknown.egg-info"
    canonical_metadata.mkdir()
    stale_metadata.mkdir()
    missing_name_metadata.mkdir()
    (canonical_metadata / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: SugarCubes\nVersion: 0.9.1\n",
        encoding="utf-8",
    )
    (stale_metadata / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: ObsoleteSugarCubes\nVersion: 0.9.0\n",
        encoding="utf-8",
    )
    (missing_name_metadata / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nVersion: 0.9.0\n",
        encoding="utf-8",
    )
    emitted: list[str] = []

    remove_noncanonical_python_distribution_metadata(
        nodepack_root=tmp_path,
        nodepack=sugarcubes_nodepack,
        on_log=emitted.append,
    )

    assert canonical_metadata.exists()
    assert missing_name_metadata.exists()
    assert not stale_metadata.exists()
    assert len(emitted) == 1
    assert "Removed non-canonical ObsoleteSugarCubes metadata" in emitted[0]


def test_egg_info_distribution_name_reads_pkg_info(tmp_path: Path) -> None:
    """Egg-info package metadata should expose the declared distribution name."""

    metadata = tmp_path / "example.egg-info"
    metadata.mkdir()
    (metadata / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: Example_Package\n",
        encoding="utf-8",
    )

    assert egg_info_distribution_name(metadata) == "Example_Package"
    assert normalized_distribution_name("Example_Package") == "example-package"


@pytest.mark.parametrize(
    ("installed", "minimum", "expected"),
    [
        ("1.6.0", "1.6.0", True),
        ("1.6.1", "1.6.0", True),
        ("1.5.9", "1.6.0", False),
        ("1.6.0-beta", "1.6.0", True),
        ("bad", "1.0.0", False),
    ],
)
def test_version_at_least_compares_semver_like_versions(
    installed: str,
    minimum: str,
    expected: bool,
) -> None:
    """Version comparison should preserve the existing semver-ish ordering."""

    assert version_at_least(installed, minimum) is expected


def test_version_key_pads_missing_numeric_parts() -> None:
    """Short versions should compare as zero-padded release tuples."""

    assert version_key("1.2") == (1, 2, 0, "")


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
