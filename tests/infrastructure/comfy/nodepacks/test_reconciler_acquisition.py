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

"""Verify core nodepack acquisition and update behavior."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    CoreNodepackReconciler,
)
from substitute.infrastructure.comfy.legacy_nodepack_distribution import (
    LegacyNodepackDistributionCleaner,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
)
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
)
from substitute.infrastructure.comfy.nodepack_registry_update_settler import (
    ComfyNodepackRegistryUpdateSettler,
)
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)
from tests.infrastructure.comfy.nodepacks.reconciler_support import (
    _FallbackInstaller,
    _LegacyCleaner,
    _RegistryInstaller,
    _RegistryUpdateSettler,
    _materialize_nodepack,
    _patch_dependencies,
    _project_version,
    _reconciler,
    _select_nodepacks,
    _write,
)


def test_missing_nodepack_installs_through_registry_and_only_then_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Use Comfy Registry as source authority for a new installation."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, nodepack)
    registry = _RegistryInstaller(RegistryInstallOutcome.INSTALLED)
    cleaner = _LegacyCleaner()
    dependency_installs: list[Path] = []
    _patch_dependencies(monkeypatch, dependency_installs, satisfied=True)

    _reconciler(registry=registry, cleaner=cleaner).ensure(
        tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    root = tmp_path / nodepack.expected_folder
    assert registry.calls == [(tmp_path, nodepack)]
    assert (root / ".tracking").is_file()
    assert dependency_installs == [root]
    assert cleaner.roots == [root]


def test_exact_registry_installation_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Perform no acquisition or dependency process work on a settled startup."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, nodepack)
    root = tmp_path / nodepack.expected_folder
    _materialize_nodepack(root, nodepack, tracking=True)
    registry = _RegistryInstaller(RegistryInstallOutcome.FAILED)
    dependency_installs: list[Path] = []
    _patch_dependencies(monkeypatch, dependency_installs, satisfied=True)

    _reconciler(registry=registry).ensure(
        tmp_path,
        python_executable=tmp_path / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    assert registry.calls == []
    assert dependency_installs == []


def test_existing_clean_official_git_install_migrates_then_registry_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Move existing users to CNR ownership without losing mutable nodepack data."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, nodepack)
    root = tmp_path / nodepack.legacy_folders[0]
    _materialize_nodepack(root, nodepack, version="1.9.0", git=True)
    _write(root / "cache" / "user.json", "keep")
    tracked = tuple(
        path.relative_to(root) for path in root.rglob("*") if path.is_file()
    )
    repositories = RecordingRepositoryService(
        tracked_paths=tracked,
        status="## main\n?? cache/user.json",
        remotes={"origin": nodepack.fallback_repository_url},
    )
    registry = _RegistryInstaller(RegistryInstallOutcome.PENDING_STARTUP)
    settler = _RegistryUpdateSettler()
    dependency_installs: list[Path] = []
    _patch_dependencies(monkeypatch, dependency_installs, satisfied=True)

    CoreNodepackReconciler(
        repositories=repositories,
        registry_installer=cast(ComfyNodepackRegistryInstaller, registry),
        registry_update_settler=cast(
            ComfyNodepackRegistryUpdateSettler,
            settler,
        ),
        legacy_cleaner=cast(LegacyNodepackDistributionCleaner, _LegacyCleaner()),
    ).ensure(
        tmp_path,
        python_executable=tmp_path / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    canonical_root = tmp_path / nodepack.expected_folder
    assert not (canonical_root / ".git").exists()
    assert (canonical_root / ".tracking").is_file()
    assert (canonical_root / "cache" / "user.json").read_text(
        encoding="utf-8"
    ) == "keep"
    assert _project_version(canonical_root) == nodepack.required_version
    assert registry.calls == [(tmp_path, nodepack)]
    assert settler.calls == [(tmp_path, nodepack)]
    assert nodepack.expected_folder.name in {
        child.name for child in canonical_root.parent.iterdir()
    }


def test_fallback_install_is_later_adopted_by_exact_registry_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Make an unavailable release updateable by Manager on a later app release."""

    first_release = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, first_release)
    unavailable_registry = _RegistryInstaller(
        RegistryInstallOutcome.VERSION_UNAVAILABLE
    )
    fallback = _FallbackInstaller()
    _patch_dependencies(monkeypatch, [], satisfied=True)

    _reconciler(registry=unavailable_registry, fallback=fallback).ensure(
        tmp_path,
        python_executable=tmp_path / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    root = tmp_path / first_release.expected_folder
    _write(root / "cache" / "user.json", "keep")
    assert (root / ".tracking").is_file()
    assert fallback.calls == [(root, first_release)]

    next_release = replace(first_release, required_version="1.9.2")
    _select_nodepacks(monkeypatch, next_release)
    available_registry = _RegistryInstaller(RegistryInstallOutcome.INSTALLED)
    _reconciler(registry=available_registry).ensure(
        tmp_path,
        python_executable=tmp_path / "python.exe",
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    assert _project_version(root) == "1.9.2"
    assert (root / "cache" / "user.json").read_text(encoding="utf-8") == "keep"
    assert available_registry.calls == [(tmp_path, next_release)]


def test_queued_registry_update_must_reach_exact_disk_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reject a nominal Manager settlement that leaves stale nodepack source."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    _select_nodepacks(monkeypatch, nodepack)
    root = tmp_path / nodepack.expected_folder
    _materialize_nodepack(root, nodepack, version="1.9.0", tracking=True)
    registry = _RegistryInstaller(RegistryInstallOutcome.PENDING_STARTUP)
    settler = _RegistryUpdateSettler(materialize=False)
    _patch_dependencies(monkeypatch, [], satisfied=True)

    with pytest.raises(RuntimeError, match="Could not install"):
        CoreNodepackReconciler(
            repositories=RecordingRepositoryService(),
            registry_installer=cast(ComfyNodepackRegistryInstaller, registry),
            registry_update_settler=cast(
                ComfyNodepackRegistryUpdateSettler,
                settler,
            ),
        ).ensure(
            tmp_path,
            python_executable=tmp_path / "python.exe",
            refresh_nodepacks=(),
            on_log=None,
            env=None,
        )

    assert _project_version(root) == "1.9.0"
    assert settler.calls == [(tmp_path, nodepack)]
