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

"""Tests for Registry-first core Comfy nodepack lifecycle orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy import core_nodepack_reconciler
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    CoreNodepackReconciler,
)
from substitute.infrastructure.comfy.legacy_nodepack_distribution import (
    LegacyNodepackDistributionCleaner,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
    RegistryInstallResult,
)
from substitute.infrastructure.comfy.nodepack_registry_update_settler import (
    ComfyNodepackRegistryUpdateSettler,
    RegistryUpdateSettlement,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    PinnedNodepackSourceInstaller,
)
from tests.repository_service_test_double import RecordingRepositoryService


class _RegistryInstaller:
    """Provide deterministic CNR install effects for orchestration tests."""

    def __init__(self, outcome: RegistryInstallOutcome) -> None:
        """Store the requested result and initialize observed calls."""

        self.outcome = outcome
        self.calls: list[tuple[Path, CoreComfyNodepack]] = []

    def install_exact(
        self,
        *,
        manager_runtime: ComfyManagerRuntime,
        nodepack: CoreComfyNodepack,
        on_log: object | None,
        env: object | None,
    ) -> RegistryInstallResult:
        """Materialize exact CNR state only for successful Registry results."""

        workspace = manager_runtime.workspace
        _ = on_log, env
        self.calls.append((workspace, nodepack))
        if self.outcome in {
            RegistryInstallOutcome.INSTALLED,
            RegistryInstallOutcome.ALREADY_INSTALLED,
        }:
            root = _existing_or_canonical_root(workspace, nodepack)
            _materialize_nodepack(root, nodepack, tracking=True)
        return RegistryInstallResult(self.outcome, ())


class _FallbackInstaller:
    """Record pinned fallback while producing Manager-readable ownership."""

    def __init__(self) -> None:
        """Initialize observed fallback requests."""

        self.calls: list[tuple[Path, CoreComfyNodepack]] = []

    def install_fallback(
        self,
        *,
        target_path: Path,
        nodepack: CoreComfyNodepack,
        on_log: object | None,
        env: object | None,
    ) -> None:
        """Install an exact fallback fixture without a network request."""

        _ = on_log, env
        self.calls.append((target_path, nodepack))
        _materialize_nodepack(target_path, nodepack, tracking=True)

    def migrate_clean_git_installation(self, **kwargs: object) -> None:
        """Reject unexpected use of the fake's migration path."""

        _ = kwargs
        raise AssertionError("test should use the real Git migration owner")

    def migrate_plain_installation(self, **kwargs: object) -> None:
        """Reject unexpected use of the fake's plain migration path."""

        _ = kwargs
        raise AssertionError("test should not adopt a plain source")


class _RegistryUpdateSettler:
    """Provide deterministic Manager pre-startup effects for orchestration tests."""

    def __init__(self, *, materialize: bool = True) -> None:
        """Configure whether Manager's queued switch reaches exact disk state."""

        self.materialize = materialize
        self.calls: list[tuple[Path, CoreComfyNodepack]] = []

    def settle(
        self,
        *,
        manager_runtime: ComfyManagerRuntime,
        nodepack: CoreComfyNodepack,
        on_log: object | None,
        env: object | None,
    ) -> RegistryUpdateSettlement:
        """Apply the queued Registry fixture when configured to succeed."""

        workspace = manager_runtime.workspace
        _ = on_log, env
        self.calls.append((workspace, nodepack))
        if self.materialize:
            root = _existing_or_canonical_root(workspace, nodepack)
            _materialize_nodepack(root, nodepack, tracking=True)
        return RegistryUpdateSettlement(self.materialize, ())


class _LegacyCleaner:
    """Record completion-time duplicate cleanup requests."""

    def __init__(self) -> None:
        """Initialize observed cleanup roots."""

        self.roots: list[Path] = []

    def remove_if_owned(self, **kwargs: object) -> bool:
        """Record the installed root and report no duplicate metadata."""

        self.roots.append(cast(Path, kwargs["nodepack_root"]))
        return False


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
        manager_runtime=_runtime(
            tmp_path, tmp_path / ".venv" / "Scripts" / "python.exe"
        ),
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
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
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
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
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
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
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
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        refresh_nodepacks=(),
        on_log=None,
        env=None,
    )

    assert _project_version(root) == "1.9.2"
    assert (root / "cache" / "user.json").read_text(encoding="utf-8") == "keep"
    assert available_registry.calls == [(tmp_path, next_release)]


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
            manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
            refresh_nodepacks=(),
            on_log=None,
            env=None,
        )

    assert (root / ".git").exists()
    assert _project_version(root) == "1.9.0"
    assert registry.calls == []


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
            manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
            refresh_nodepacks=(),
            on_log=None,
            env=None,
        )

    assert _project_version(root) == "1.9.0"
    assert settler.calls == [(tmp_path, nodepack)]


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
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        refresh_nodepacks=(),
        on_log=None,
        env={env_name: str(source)},
    )

    installed = tmp_path / nodepack.expected_folder
    assert registry.calls == []
    assert _project_version(installed) == "0.12.0"
    assert dependencies == [installed]


def _reconciler(
    *,
    registry: _RegistryInstaller,
    fallback: _FallbackInstaller | None = None,
    cleaner: _LegacyCleaner | None = None,
) -> CoreNodepackReconciler:
    """Compose the reconciler with deterministic effect owners."""

    selected_cleaner = cleaner or _LegacyCleaner()
    return CoreNodepackReconciler(
        repositories=RecordingRepositoryService(),
        registry_installer=cast(ComfyNodepackRegistryInstaller, registry),
        fallback_installer=(
            cast(PinnedNodepackSourceInstaller, fallback)
            if fallback is not None
            else None
        ),
        legacy_cleaner=cast(LegacyNodepackDistributionCleaner, selected_cleaner),
    )


def _runtime(workspace: Path, python: Path) -> ComfyManagerRuntime:
    """Build one validated integrated Manager runtime fixture."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=python,
        version="4.1",
    )


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    installs: list[Path],
    *,
    satisfied: bool,
) -> None:
    """Control dependency state while recording dependency-only installs."""

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "nodepack_python_dependencies_satisfied",
        lambda **kwargs: satisfied,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_nodepack_python_dependencies",
        lambda **kwargs: installs.append(cast(Path, kwargs["nodepack_root"])),
    )


def _select_nodepacks(
    monkeypatch: pytest.MonkeyPatch,
    *nodepacks: CoreComfyNodepack,
) -> None:
    """Limit one orchestration scenario to the specified manifest entries."""

    monkeypatch.setattr(core_nodepack_reconciler, "CORE_COMFY_NODEPACKS", nodepacks)


def _existing_or_canonical_root(
    workspace: Path,
    nodepack: CoreComfyNodepack,
) -> Path:
    """Return an existing persisted root before selecting the canonical path."""

    for folder in nodepack.candidate_folders:
        root = workspace / folder
        if root.is_dir():
            return root
    return workspace / nodepack.expected_folder


def _materialize_nodepack(
    root: Path,
    nodepack: CoreComfyNodepack,
    *,
    version: str | None = None,
    tracking: bool = False,
    git: bool = False,
) -> None:
    """Write one nodepack source tree with chosen ownership metadata."""

    for sentinel in nodepack.sentinel_files:
        _write(root / sentinel, "source")
    _write(
        root / "pyproject.toml",
        (
            "[project]\n"
            f'name = "{nodepack.registry_id}"\n'
            f'version = "{version or nodepack.required_version}"\n'
            "dependencies = []\n"
            "[project.urls]\n"
            f'Repository = "{nodepack.fallback_repository_url}"\n'
        ),
    )
    if tracking:
        _write(root / ".tracking", "pyproject.toml")
    if git:
        _write(root / ".git" / "HEAD", "ref: refs/heads/main\n")


def _project_version(root: Path) -> str:
    """Return the fixture project version without duplicating TOML parsing logic."""

    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.partition("=")[2].strip().strip('"')
    raise AssertionError("fixture has no project version")


def _write(path: Path, content: str) -> None:
    """Write a fixture file with its parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
