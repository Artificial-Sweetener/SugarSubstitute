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

"""Provide core nodepack reconciler fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.infrastructure.comfy import core_nodepack_reconciler
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    CoreNodepackReconciler,
)
from substitute.infrastructure.comfy.legacy_nodepack_distribution import (
    LegacyNodepackDistributionCleaner,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
    RegistryInstallResult,
)
from substitute.infrastructure.comfy.nodepack_registry_update_settler import (
    RegistryUpdateSettlement,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    PinnedNodepackSourceInstaller,
)
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)


class _RegistryInstaller:
    """Provide deterministic CNR install effects for orchestration tests."""

    def __init__(self, outcome: RegistryInstallOutcome) -> None:
        """Store the requested result and initialize observed calls."""

        self.outcome = outcome
        self.calls: list[tuple[Path, CoreComfyNodepack]] = []

    def install_exact(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        nodepack: CoreComfyNodepack,
        on_log: object | None,
        env: object | None,
    ) -> RegistryInstallResult:
        """Materialize exact CNR state only for successful Registry results."""

        _ = python_executable, on_log, env
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
        workspace: Path,
        python_executable: Path,
        nodepack: CoreComfyNodepack,
        on_log: object | None,
        env: object | None,
    ) -> RegistryUpdateSettlement:
        """Apply the queued Registry fixture when configured to succeed."""

        _ = python_executable, on_log, env
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
