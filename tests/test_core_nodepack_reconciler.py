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

"""Tests for core Comfy nodepack reconciliation."""

from __future__ import annotations

import ast
from pathlib import Path
import shutil
from typing import cast

import pytest

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy import core_nodepack_reconciler
from substitute.infrastructure.comfy import nodepack_git_maintenance
from substitute.infrastructure.comfy import pinned_nodepack_source
from substitute.infrastructure.comfy.comfy_cli_adapter import ComfyManagerCliAdapter
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
    _install_core_nodepack,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from tests.repository_service_test_double import RecordingRepositoryService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECONCILER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "core_nodepack_reconciler.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_core_nodepack_reconciler_imports_no_ui_or_raw_process_boundaries() -> None:
    """Core reconciliation must stay independent from UI and raw process APIs."""

    imported_modules = _imported_module_names(
        ast.parse(RECONCILER_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_ensure_core_nodepacks_installs_missing_nodepacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing core nodepacks should install through Comfy CLI registry IDs."""

    installed: list[str] = []
    dependency_installs: list[Path] = []
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")

    class FakeAdapter:
        """Record Comfy CLI calls for nodepack reconciliation."""

        def __init__(self, **kwargs: object) -> None:
            """Ignore construction details while keeping the public shape."""

            _ = kwargs

        def ensure_available(self) -> None:
            """Record CLI availability checks."""

        @property
        def workspace(self) -> Path:
            """Return the test workspace."""

            return tmp_path

        def manager_knows_node(self, node_id: str) -> bool:
            """Pretend the Comfy Manager registry knows every core nodepack."""

            _ = node_id
            return True

        def install_node(self, node_id: str) -> None:
            """Record one requested Registry node install."""

            installed.append(node_id)
            for nodepack in CORE_COMFY_NODEPACKS:
                if nodepack.registry_id == node_id or nodepack.source_url == node_id:
                    root = tmp_path / nodepack.expected_folder
                    root.mkdir(parents=True, exist_ok=True)
                    for sentinel in nodepack.sentinel_files:
                        (root / sentinel).parent.mkdir(parents=True, exist_ok=True)
                        (root / sentinel).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: True,
    )

    ensure_core_comfy_nodepacks(tmp_path)

    assert installed == ["substitute-backend", "SugarCubes"]
    assert dependency_installs == [
        tmp_path / "custom_nodes" / "Substitute-BackEnd",
        tmp_path / "custom_nodes" / "SugarCubes",
    ]


def test_ensure_core_nodepacks_uses_github_when_manager_id_is_unpublished(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Published nodepacks should use GitHub fallback when Registry lookup misses."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    dependency_installs: list[Path] = []
    installed: list[str] = []

    class FakeAdapter:
        """Force the installer down the GitHub fallback branch."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Pretend Comfy Manager cannot resolve the package id."""

            _ = node_id
            return False

        def install_node(self, node_id: str) -> None:
            """Record one GitHub install and materialize the expected sentinels."""

            installed.append(node_id)
            for nodepack in CORE_COMFY_NODEPACKS:
                if nodepack.source_url == node_id:
                    root = tmp_path / nodepack.expected_folder
                    root.mkdir(parents=True, exist_ok=True)
                    for sentinel in nodepack.sentinel_files:
                        (root / sentinel).parent.mkdir(parents=True, exist_ok=True)
                        (root / sentinel).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: True,
    )

    ensure_core_comfy_nodepacks(tmp_path)

    for nodepack in CORE_COMFY_NODEPACKS:
        assert (tmp_path / nodepack.expected_folder).is_dir()
        for sentinel in nodepack.sentinel_files:
            assert (tmp_path / nodepack.expected_folder / sentinel).is_file()
    assert installed == [
        "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git",
        "https://github.com/Artificial-Sweetener/SugarCubes.git",
    ]
    assert dependency_installs == [
        tmp_path / "custom_nodes" / "Substitute-BackEnd",
        tmp_path / "custom_nodes" / "SugarCubes",
    ]


def test_ensure_core_nodepacks_refreshes_only_targeted_existing_git_nodepacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed repair should fast-forward only targeted git-backed nodepacks."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        (target_root / ".git").mkdir(parents=True)
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("", encoding="utf-8")

    dependency_installs: list[Path] = []
    repositories = RecordingRepositoryService()
    monkeypatch.setattr(
        nodepack_git_maintenance,
        "repository_service",
        lambda: repositories,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )

    class FakeAdapter:
        """Expose only the adapter surface needed by git refresh."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Fail if git refresh falls through to registry inspection."""

            raise AssertionError(f"Unexpected manager lookup: {node_id}")

        def install_node(self, node_id: str) -> None:
            """Fail if git refresh falls through to registry install."""

            raise AssertionError(f"Unexpected registry install: {node_id}")

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        refresh_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    backend_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    assert repositories.calls == [("sync_fast_forward", backend_root)]
    assert dependency_installs == [backend_root]


def test_backend_refresh_overlays_pinned_archive_when_registry_version_is_too_old(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """BackEnd repair should fall back to the pinned tag when Registry lags."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    backend_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    sugarcubes_root = tmp_path / "custom_nodes" / "SugarCubes"
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("old", encoding="utf-8")
    (backend_root / "pyproject.toml").write_text(
        '[project]\nname = "substitute-backend"\nversion = "1.5.0"\n',
        encoding="utf-8",
    )
    (backend_root / ".tracking").write_text(
        "__init__.py\npyproject.toml\nsubstitute_backend/__init__.py",
        encoding="utf-8",
    )

    installed: list[str] = []
    dependency_installs: list[Path] = []
    overlays: list[tuple[str, Path, bool]] = []
    backend_version_checks = [False, True]

    class FakeAdapter:
        """Expose registry refresh behavior for the lagging-version fallback."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Pretend Comfy Manager can resolve registry node ids."""

            _ = node_id
            return True

        def install_node(self, node_id: str) -> None:
            """Record registry installs without changing the installed version."""

            installed.append(node_id)

    def fake_overlay(
        *,
        archive_url: str,
        target_path: Path,
        nodepack: object,
        write_registry_tracking: bool,
        on_log: object | None,
        temp_dir: Path | None = None,
    ) -> None:
        """Record one pinned source overlay."""

        _ = nodepack, on_log, temp_dir
        overlays.append((archive_url, target_path, write_registry_tracking))
        (target_path / "fallback.txt").write_text("fallback", encoding="utf-8")

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: (
            backend_version_checks.pop(0)
            if kwargs["distribution_name"] == "substitute-backend"
            else True
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "resolve_local_nodepack_source",
        lambda nodepack: None,
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "overlay_pinned_source_archive",
        fake_overlay,
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        refresh_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert installed == ["substitute-backend"]
    assert dependency_installs == [backend_root, backend_root]
    assert overlays == [
        (
            "https://github.com/Artificial-Sweetener/Substitute-BackEnd/archive/refs/tags/"
            "v1.7.0.zip",
            backend_root,
            True,
        )
    ]
    assert (backend_root / "fallback.txt").read_text(encoding="utf-8") == "fallback"
    assert not (sugarcubes_root / "fallback.txt").exists()


def test_existing_sugarcubes_below_minimum_refreshes_before_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing SugarCubes folders should not skip the required version check."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    sugarcubes_root = tmp_path / "custom_nodes" / "SugarCubes"
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("old", encoding="utf-8")
    dependency_installs: list[Path] = []
    checked_distributions: list[str | None] = []
    version_checks = {
        "substitute-backend": [True],
        "SugarCubes": [False, True],
    }

    class FakeAdapter:
        """Fail if an installed nodepack falls back to Comfy Manager installation."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Fail if setup treats installed nodepacks as missing."""

            raise AssertionError(f"Unexpected manager lookup: {node_id}")

        def install_node(self, node_id: str) -> None:
            """Fail if setup treats installed nodepacks as missing."""

            raise AssertionError(f"Unexpected manager install: {node_id}")

    def fake_version_check(**kwargs: object) -> bool:
        """Return an old SugarCubes version until dependency refresh runs."""

        distribution_name = cast(str, kwargs["distribution_name"])
        checked_distributions.append(distribution_name)
        return version_checks[distribution_name].pop(0)

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        fake_version_check,
    )

    ensure_core_comfy_nodepacks(tmp_path)

    assert checked_distributions == ["substitute-backend", "SugarCubes", "SugarCubes"]
    assert dependency_installs == [sugarcubes_root]


def test_sugarcubes_refresh_removes_noncanonical_distribution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SugarCubes refresh should keep only canonical local package metadata."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    sugarcubes_nodepack = next(
        nodepack
        for nodepack in CORE_COMFY_NODEPACKS
        if nodepack.nodepack_id is CoreNodepackId.SUGARCUBES
    )
    sugarcubes_root = tmp_path / sugarcubes_nodepack.expected_folder
    for sentinel in sugarcubes_nodepack.sentinel_files:
        (sugarcubes_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
        (sugarcubes_root / sentinel).write_text("old", encoding="utf-8")
    stale_metadata = sugarcubes_root / "obsolete_sugarcubes.egg-info"
    stale_metadata.mkdir()
    (stale_metadata / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: ObsoleteSugarCubes\nVersion: 0.9.0\n",
        encoding="utf-8",
    )
    dependency_installs: list[Path] = []
    primary_checks = [True]

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: (
            primary_checks.pop(0)
            if kwargs["distribution_name"] == "SugarCubes"
            else True
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    core_nodepack_reconciler._refresh_nodepack_python_dependencies(
        python_executable=python_path,
        workspace=tmp_path,
        nodepack=sugarcubes_nodepack,
        on_log=None,
        env=None,
    )

    assert dependency_installs == [sugarcubes_root]
    assert not stale_metadata.exists()
    assert primary_checks == []


def test_backend_git_fallback_checks_out_pinned_tag_without_registry_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Git-managed BackEnd repair should keep the folder git-managed."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    backend_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    sugarcubes_root = tmp_path / "custom_nodes" / "SugarCubes"
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("old", encoding="utf-8")
    (backend_root / ".git").mkdir(parents=True)

    dependency_installs: list[Path] = []
    backend_version_checks = [False, True]
    overlays: list[str] = []

    repositories = RecordingRepositoryService()

    class FakeAdapter:
        """Expose only the adapter surface needed by git refresh."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Fail if git refresh falls through to registry inspection."""

            raise AssertionError(f"Unexpected manager lookup: {node_id}")

        def install_node(self, node_id: str) -> None:
            """Fail if git refresh falls through to registry install."""

            raise AssertionError(f"Unexpected registry install: {node_id}")

    monkeypatch.setattr(
        nodepack_git_maintenance,
        "repository_service",
        lambda: repositories,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: (
            backend_version_checks.pop(0)
            if kwargs["distribution_name"] == "substitute-backend"
            else True
        ),
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "overlay_pinned_source_archive",
        lambda **kwargs: overlays.append("overlay"),
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        refresh_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert repositories.calls == [
        ("sync_fast_forward", backend_root),
        (
            "fetch_tag",
            (
                backend_root,
                "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git",
                "v1.7.0",
            ),
        ),
        ("checkout_revision", (backend_root, "v1.7.0")),
    ]
    assert dependency_installs == [backend_root, backend_root]
    assert overlays == []
    assert not (backend_root / ".tracking").exists()
    assert not (sugarcubes_root / ".tracking").exists()


def test_backend_git_refresh_failure_replaces_pinned_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unmergeable managed BackEnd checkouts should be replaced during repair."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    backend_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("old", encoding="utf-8")
    (backend_root / ".git").mkdir(parents=True)
    replacements: list[tuple[str, Path]] = []
    dependency_installs: list[Path] = []

    repositories = RecordingRepositoryService(failing_operations={"sync_fast_forward"})

    class FakeAdapter:
        """Expose only the adapter surface needed by git repair."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Fail if unmergeable git repair falls through to Registry lookup."""

            raise AssertionError(f"Unexpected manager lookup: {node_id}")

        def install_node(self, node_id: str) -> None:
            """Fail if unmergeable git repair falls through to Manager install."""

            raise AssertionError(f"Unexpected manager install: {node_id}")

    def fake_replace(
        *,
        archive_url: str,
        target_path: Path,
        nodepack: object,
        on_log: object | None,
        env: object | None,
    ) -> None:
        """Record managed replacement and materialize replacement sentinels."""

        _ = nodepack, on_log, env
        replacements.append((archive_url, target_path))
        shutil.rmtree(target_path)
        for sentinel in next(
            item
            for item in CORE_COMFY_NODEPACKS
            if item.nodepack_id is CoreNodepackId.SUBSTITUTE_BACKEND
        ).sentinel_files:
            (target_path / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_path / sentinel).write_text("new", encoding="utf-8")

    monkeypatch.setattr(
        nodepack_git_maintenance,
        "repository_service",
        lambda: repositories,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_replace_with_pinned_source_archive",
        fake_replace,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_backend_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: True,
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        refresh_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert repositories.calls == [("sync_fast_forward", backend_root)]
    assert replacements == [
        (
            "https://github.com/Artificial-Sweetener/Substitute-BackEnd/archive/refs/tags/"
            "v1.7.0.zip",
            backend_root,
        )
    ]
    assert dependency_installs == [backend_root]
    assert not (backend_root / ".git").exists()


def test_ensure_core_nodepacks_refresh_uses_github_fallback_for_sugarcubes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SugarCubes repair should use GitHub fallback after Registry lookup misses."""

    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        for sentinel in nodepack.sentinel_files:
            (target_root / sentinel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / sentinel).write_text("old", encoding="utf-8")
        (target_root / "user-extra.txt").write_text("keep", encoding="utf-8")
    installed: list[str] = []
    dependency_installs: list[Path] = []

    class FakeAdapter:
        """Force refresh to use GitHub fallback."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the workspace used by the reconciliation service."""

            self.workspace = kwargs["workspace"]

        def ensure_available(self) -> None:
            """Keep the fake CLI available."""

        def manager_knows_node(self, node_id: str) -> bool:
            """Pretend Registry lookup cannot find the nodepack."""

            _ = node_id
            return False

        def install_node(self, node_id: str) -> None:
            """Record GitHub fallback install and update SugarCubes sentinels."""

            installed.append(node_id)
            assert node_id == "https://github.com/Artificial-Sweetener/SugarCubes.git"
            sugarcubes = next(
                item
                for item in CORE_COMFY_NODEPACKS
                if item.nodepack_id is CoreNodepackId.SUGARCUBES
            )
            target_root = tmp_path / sugarcubes.expected_folder
            for sentinel in sugarcubes.sentinel_files:
                (target_root / sentinel).write_text("updated", encoding="utf-8")

    monkeypatch.setattr(
        core_nodepack_reconciler,
        "ComfyManagerCliAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "install_sugarcubes_python_dependencies",
        lambda *, python_executable, nodepack_root, on_log=None, env=None: (
            dependency_installs.append(nodepack_root)
        ),
    )
    monkeypatch.setattr(
        core_nodepack_reconciler,
        "_python_distribution_satisfies_minimum",
        lambda **kwargs: True,
    )

    ensure_core_comfy_nodepacks(
        tmp_path,
        refresh_nodepacks={CoreNodepackId.SUGARCUBES},
    )

    assert installed == ["https://github.com/Artificial-Sweetener/SugarCubes.git"]
    assert dependency_installs == [tmp_path / "custom_nodes" / "SugarCubes"]
    for nodepack in CORE_COMFY_NODEPACKS:
        target_root = tmp_path / nodepack.expected_folder
        assert (target_root / "user-extra.txt").read_text(encoding="utf-8") == "keep"
        for sentinel in nodepack.sentinel_files:
            expected = (
                "updated"
                if nodepack.nodepack_id is CoreNodepackId.SUGARCUBES
                else "old"
            )
            assert (target_root / sentinel).read_text(encoding="utf-8") == expected


def test_install_core_nodepack_prefers_registry_install(tmp_path: Path) -> None:
    """Registry-known nodepacks should install by registry ID before fallbacks."""

    adapter = _RecordingAdapter(tmp_path, manager_knows=True)
    nodepack = CORE_COMFY_NODEPACKS[0]

    _install_core_nodepack(adapter, nodepack, on_log=None)

    assert adapter.installed == [nodepack.registry_id]


def test_install_core_nodepack_uses_source_url_when_registry_misses(
    tmp_path: Path,
) -> None:
    """Registry misses should use the trusted source URL fallback."""

    adapter = _RecordingAdapter(tmp_path, manager_knows=False)
    nodepack = CORE_COMFY_NODEPACKS[0]

    _install_core_nodepack(adapter, nodepack, on_log=None)

    assert adapter.installed == [nodepack.source_url]


class _RecordingAdapter(ComfyManagerCliAdapter):
    """Record core nodepack install attempts without running Comfy CLI."""

    def __init__(self, workspace: Path, *, manager_knows: bool) -> None:
        """Store fake registry knowledge and install history."""

        self._workspace = workspace
        self._manager_knows = manager_knows
        self.installed: list[str | None] = []

    @property
    def workspace(self) -> Path:
        """Return the fake workspace."""

        return self._workspace

    def manager_knows_node(self, node_id: str) -> bool:
        """Return the configured registry lookup result."""

        _ = node_id
        return self._manager_knows

    def install_node(self, node_id: str) -> None:
        """Record one requested install ID."""

        self.installed.append(node_id)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
