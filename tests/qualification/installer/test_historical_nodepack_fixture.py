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

"""Verify historical SugarCubes qualification fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci.historical_nodepack_fixture import (
    historical_sugarcubes_freshness_key,
    historical_sugarcubes_has_maintenance,
    read_historical_sugarcubes_version,
    restore_historical_sugarcubes,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_historical_pin_is_read_from_the_installed_app_payload(tmp_path: Path) -> None:
    """Qualification should derive history from the installed signed payload."""

    contract = tmp_path / "app" / "substitute" / "domain" / "comfy_nodepacks.py"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        'SUBSTITUTE_BACKEND_REQUIRED_VERSION = "1.8.0"\n'
        'SUGARCUBES_REQUIRED_VERSION = "0.11.0"\n',
        encoding="utf-8",
    )

    assert read_historical_sugarcubes_version(tmp_path) == "0.11.0"


def test_legacy_minimum_is_read_from_the_installed_app_payload(tmp_path: Path) -> None:
    """Qualification should reconstruct releases predating exact nodepack pins."""

    contract = tmp_path / "app" / "substitute" / "domain" / "comfy_nodepacks.py"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        'SUGARCUBES_REQUIRED_MINIMUM_VERSION = "0.10.0"\n',
        encoding="utf-8",
    )

    assert read_historical_sugarcubes_version(tmp_path) == "0.10.0"


def test_dynamic_historical_pin_is_rejected(tmp_path: Path) -> None:
    """Qualification must not execute historical source to discover its pin."""

    contract = tmp_path / "app" / "substitute" / "domain" / "comfy_nodepacks.py"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        "SUGARCUBES_REQUIRED_VERSION = load_version()\n",
        encoding="utf-8",
    )

    with pytest.raises(InstallerLifecycleError, match="literal SugarCubes"):
        read_historical_sugarcubes_version(tmp_path)


def test_legacy_release_without_maintenance_remains_valid_input(tmp_path: Path) -> None:
    """Qualification should recognize releases predating offline maintenance."""

    workspace = tmp_path / "comfyui"
    assert historical_sugarcubes_has_maintenance(workspace) is False

    maintenance = (
        workspace / "custom_nodes" / "SugarCubes" / "sugarcubes" / "maintenance.py"
    )
    maintenance.parent.mkdir(parents=True)
    maintenance.touch()

    assert historical_sugarcubes_has_maintenance(workspace) is True


def test_restore_uses_historical_release_and_requires_installed_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixture should replace candidate SugarCubes with exact old source."""

    contract = tmp_path / "install" / "app" / "substitute" / "domain"
    contract.mkdir(parents=True)
    (contract / "comfy_nodepacks.py").write_text(
        'SUGARCUBES_REQUIRED_VERSION = "0.11.0"\n',
        encoding="utf-8",
    )
    workspace = tmp_path / "comfyui"
    installed_manifest: list[object] = []
    dependency_roots: list[Path] = []

    def _install(self: object, **arguments: object) -> None:
        """Record the historical manifest and materialize its inspected identity."""

        del self
        manifest = arguments["nodepack"]
        installed_manifest.append(manifest)
        target_path = arguments["target_path"]
        assert isinstance(target_path, Path)
        target_path.mkdir(parents=True)
        (target_path / "pyproject.toml").write_text(
            '[project]\nname = "SugarCubes"\nversion = "0.11.0"\n',
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "tools.ci.historical_nodepack_fixture."
        "PinnedNodepackSourceInstaller.install_fallback",
        _install,
    )
    monkeypatch.setattr(
        "tools.ci.historical_nodepack_fixture.install_nodepack_python_dependencies",
        lambda **arguments: dependency_roots.append(arguments["nodepack_root"]),
    )

    restored = restore_historical_sugarcubes(
        install_root=tmp_path / "install",
        workspace=workspace,
        python_executable=workspace / "python.exe",
        environment={},
    )

    assert restored == "0.11.0"
    manifest = installed_manifest[0]
    assert getattr(manifest, "required_version") == "0.11.0"
    assert getattr(manifest, "fallback_archive_url").endswith("/v0.11.0.zip")
    assert dependency_roots == [workspace / "custom_nodes" / "SugarCubes"]


def test_freshness_evidence_records_the_historical_pin() -> None:
    """Candidate startup must observe a version-policy change in saved evidence."""

    candidate_key: dict[str, object] = {
        "schema_version": 5,
        "core_nodepacks": [
            {
                "id": "substitute-backend",
                "required_version": "1.9.1",
            },
            {
                "id": "SugarCubes",
                "required_version": "0.12.0",
                "fallback_archive": "https://example.test/v0.12.0.zip",
            },
        ],
    }

    historical_key = historical_sugarcubes_freshness_key(
        candidate_key,
        historical_version="0.11.0",
    )

    historical_nodepacks = historical_key["core_nodepacks"]
    assert isinstance(historical_nodepacks, list)
    historical_sugarcubes = next(
        item
        for item in historical_nodepacks
        if isinstance(item, dict) and item.get("id") == "SugarCubes"
    )
    assert historical_sugarcubes["required_version"] == "0.11.0"
    assert historical_sugarcubes["fallback_archive"].endswith("/v0.11.0.zip")
    assert candidate_key["core_nodepacks"] != historical_key["core_nodepacks"]
