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

"""Verify core nodepack reconciliation safety behavior."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    CoreNodepackReconciler,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
)
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
)
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)
from tests.infrastructure.comfy.nodepacks.reconciler_support import (
    _RegistryInstaller,
    _materialize_nodepack,
    _patch_dependencies,
    _project_version,
    _reconciler,
    _select_nodepacks,
)


def test_dirty_outdated_git_checkout_is_preserved_and_blocks_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never erase tracked development work to satisfy managed version policy."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, nodepack)
    root = tmp_path / nodepack.legacy_folders[0]
    _materialize_nodepack(root, nodepack, version="1.9.0", git=True)
    repositories = RecordingRepositoryService(
        status="## main\n M pyproject.toml",
        remotes={"origin": nodepack.fallback_repository_url},
    )
    registry = _RegistryInstaller(RegistryInstallOutcome.INSTALLED)
    _patch_dependencies(monkeypatch, [], satisfied=True)

    with pytest.raises(RuntimeError, match="tracked local changes"):
        CoreNodepackReconciler(
            repositories=repositories,
            registry_installer=cast(ComfyNodepackRegistryInstaller, registry),
        ).ensure(
            tmp_path,
            python_executable=tmp_path / "python.exe",
            refresh_nodepacks=(),
            on_log=None,
            env=None,
        )

    assert (root / ".git").exists()
    assert _project_version(root) == "1.9.0"
    assert registry.calls == []


def test_explicit_local_source_bypasses_registry_acquisition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Retain the declared developer-source override as an explicit escape hatch."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    _select_nodepacks(monkeypatch, nodepack)
    source = tmp_path / "development" / "SugarCubes"
    _materialize_nodepack(source, nodepack, version="0.12.0")
    registry = _RegistryInstaller(RegistryInstallOutcome.INSTALLED)
    dependencies: list[Path] = []
    _patch_dependencies(monkeypatch, dependencies, satisfied=False)
    env_name = nodepack.local_source_environment_variable
    assert env_name is not None

    _reconciler(registry=registry).ensure(
        tmp_path,
        python_executable=tmp_path / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env={env_name: str(source)},
    )

    installed = tmp_path / nodepack.expected_folder
    assert registry.calls == []
    assert _project_version(installed) == "0.12.0"
    assert dependencies == [installed]
