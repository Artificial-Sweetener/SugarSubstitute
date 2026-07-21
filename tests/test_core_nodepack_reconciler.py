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

"""Tests for trusted core Comfy nodepack reconciliation."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import cast

import pytest

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy import core_nodepack_reconciler
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    CoreComfyNodepack,
)
from tests.repository_service_test_double import RecordingRepositoryService


def test_missing_core_nodepacks_clone_explicit_trusted_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing core nodepacks should clone without invoking Comfy Manager CLI."""

    python = _prepare_python(tmp_path)
    dependency_installs: list[Path] = []
    repositories = RecordingRepositoryService(
        clone_callback=lambda url, target: _materialize_clone(url, target)
    )
    _patch_dependency_contracts(monkeypatch, dependency_installs)

    ensure_core_comfy_nodepacks(
        tmp_path,
        python_executable=python,
        repositories=repositories,
    )

    assert repositories.calls == [
        ("clone", (nodepack.source_url, tmp_path / nodepack.expected_folder))
        for nodepack in CORE_COMFY_NODEPACKS
    ]
    assert dependency_installs == [
        tmp_path / nodepack.expected_folder for nodepack in CORE_COMFY_NODEPACKS
    ]


def test_targeted_git_refresh_uses_repository_service_only_for_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repair should fast-forward only the selected libgit2-backed nodepack."""

    python = _prepare_python(tmp_path)
    _materialize_installed_nodepacks(tmp_path, git_managed=True)
    dependency_installs: list[Path] = []
    repositories = RecordingRepositoryService()
    _patch_dependency_contracts(monkeypatch, dependency_installs)

    ensure_core_comfy_nodepacks(
        tmp_path,
        python_executable=python,
        refresh_nodepacks=frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
        repositories=repositories,
    )

    backend = _nodepack(CoreNodepackId.SUBSTITUTE_BACKEND)
    assert repositories.calls == [
        ("sync_fast_forward", tmp_path / backend.expected_folder)
    ]
    assert dependency_installs == [tmp_path / backend.expected_folder]


def test_git_refresh_failure_replaces_with_pinned_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unmergeable core checkout should use the existing pinned replacement."""

    python = _prepare_python(tmp_path)
    _materialize_installed_nodepacks(tmp_path, git_managed=True)
    backend = _nodepack(CoreNodepackId.SUBSTITUTE_BACKEND)
    backend_root = tmp_path / backend.expected_folder
    replacements: list[tuple[str, Path]] = []
    dependency_installs: list[Path] = []
    repositories = RecordingRepositoryService(failing_operations={"sync_fast_forward"})

    def replace_source(
        *,
        archive_url: str,
        target_path: Path,
        nodepack: object,
        on_log: object | None,
        env: object | None,
    ) -> None:
        """Materialize a deterministic pinned replacement."""

        _ = on_log, env
        replacements.append((archive_url, target_path))
        shutil.rmtree(target_path)
        _materialize_nodepack(cast(CoreComfyNodepack, nodepack), target_path)

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_replace_with_pinned_source_archive",
        replace_source,
    )
    _patch_dependency_contracts(monkeypatch, dependency_installs)

    ensure_core_comfy_nodepacks(
        tmp_path,
        python_executable=python,
        refresh_nodepacks=frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
        repositories=repositories,
    )

    assert replacements == [(backend.pinned_source_archive_url, backend_root)]
    assert dependency_installs == [backend_root]


def test_existing_nodepack_below_minimum_refreshes_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An installed nodepack below its minimum should refresh before launch."""

    python = _prepare_python(tmp_path)
    _materialize_installed_nodepacks(tmp_path)
    dependency_installs: list[Path] = []
    version_checks = {
        "substitute-backend": [True],
        "SugarCubes": [False, True],
    }

    def version_satisfied(**kwargs: object) -> bool:
        """Return an old SugarCubes version until dependencies are refreshed."""

        name = cast(str, kwargs["distribution_name"])
        return version_checks[name].pop(0)

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_matches_required_version",
        version_satisfied,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )

    ensure_core_comfy_nodepacks(tmp_path, python_executable=python)

    sugarcubes = _nodepack(CoreNodepackId.SUGARCUBES)
    assert dependency_installs == [tmp_path / sugarcubes.expected_folder]


def test_configured_sugarcubes_checkout_can_precede_pinned_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit development checkout should not require an unpublished tag."""

    python = _prepare_python(tmp_path)
    _materialize_installed_nodepacks(tmp_path)
    sugarcubes = _nodepack(CoreNodepackId.SUGARCUBES)
    sugarcubes_root = (tmp_path / sugarcubes.expected_folder).resolve()
    env_var = sugarcubes.local_source_environment_variable
    assert env_var is not None
    dependency_installs: list[Path] = []
    version_checks = {
        "substitute-backend": [True],
        "SugarCubes": [False, False],
    }

    def version_satisfied(**kwargs: object) -> bool:
        """Keep the development checkout below the future release version."""

        name = cast(str, kwargs["distribution_name"])
        return version_checks[name].pop(0)

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_matches_required_version",
        version_satisfied,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_apply_pinned_source_fallback",
        lambda **_kwargs: pytest.fail("local checkout must not use pinned fallback"),
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        python_executable=python,
        env={env_var: str(sugarcubes_root)},
    )

    assert dependency_installs == [sugarcubes_root]


def test_non_git_refresh_uses_pinned_archive_without_manager_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A non-git core nodepack should refresh from its pinned trusted archive."""

    python = _prepare_python(tmp_path)
    _materialize_installed_nodepacks(tmp_path)
    sugarcubes = _nodepack(CoreNodepackId.SUGARCUBES)
    replacements: list[tuple[str, Path]] = []
    dependency_installs: list[Path] = []

    def replace_source(**kwargs: object) -> None:
        """Record the selected pinned archive without changing the fixture."""

        replacements.append(
            (cast(str, kwargs["archive_url"]), cast(Path, kwargs["target_path"]))
        )

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_replace_with_pinned_source_archive",
        replace_source,
    )
    _patch_dependency_contracts(monkeypatch, dependency_installs)

    ensure_core_comfy_nodepacks(
        tmp_path,
        python_executable=python,
        refresh_nodepacks=frozenset({CoreNodepackId.SUGARCUBES}),
    )

    assert replacements == [
        (sugarcubes.pinned_source_archive_url, tmp_path / sugarcubes.expected_folder)
    ]
    assert dependency_installs == [tmp_path / sugarcubes.expected_folder]


def _prepare_python(workspace: Path) -> Path:
    """Create one workspace Python fixture."""

    python = workspace / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python


def _materialize_clone(repository_url: str, target_path: Path) -> None:
    """Create the manifest sentinels associated with a trusted source URL."""

    nodepack = next(
        item for item in CORE_COMFY_NODEPACKS if item.source_url == repository_url
    )
    _materialize_nodepack(nodepack, target_path, git_managed=True)


def _materialize_installed_nodepacks(
    workspace: Path,
    *,
    git_managed: bool = False,
) -> None:
    """Create installed fixtures for every core nodepack."""

    for nodepack in CORE_COMFY_NODEPACKS:
        _materialize_nodepack(
            nodepack,
            workspace / nodepack.expected_folder,
            git_managed=git_managed,
        )


def _materialize_nodepack(
    nodepack: CoreComfyNodepack,
    target_path: Path,
    *,
    git_managed: bool = False,
) -> None:
    """Create one core nodepack's required filesystem contract."""

    if git_managed:
        (target_path / ".git").mkdir(parents=True, exist_ok=True)
    for sentinel in nodepack.sentinel_files:
        sentinel_path = target_path / sentinel
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.write_text("fixture", encoding="utf-8")


def _patch_dependency_contracts(
    monkeypatch: pytest.MonkeyPatch,
    dependency_installs: list[Path],
) -> None:
    """Make dependency validation deterministic while recording refreshes."""

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_matches_required_version",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )


def _nodepack(nodepack_id: CoreNodepackId) -> CoreComfyNodepack:
    """Return one core manifest entry by domain identifier."""

    return next(
        item for item in CORE_COMFY_NODEPACKS if item.nodepack_id is nodepack_id
    )
