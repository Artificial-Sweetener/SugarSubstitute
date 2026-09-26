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

"""Tests for approved arbitrary workflow nodepack installation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackSourceKind,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem
from substitute.infrastructure.comfy.comfy_registry_release_client import (
    ComfyRegistryRelease,
    ComfyRegistryReleaseClient,
    RegistryReleaseUnavailableError,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    TrustedNodepackArchiveInstaller,
)
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
    WorkflowNodepackInstallStatus,
)

_GIT_REVISION = "3740add9dbdc9f254a2befda30e95ba95e3b115d"


class _ReleaseClient:
    """Return exact descriptors or configured failures by Registry identity."""

    def __init__(self, failures: set[str] | None = None) -> None:
        """Store Registry ids that should report a missing version."""

        self.failures = failures or set()
        self.calls: list[tuple[str, str]] = []

    def resolve_exact(
        self,
        *,
        registry_id: str,
        version: str,
    ) -> ComfyRegistryRelease:
        """Return one deterministic trusted archive descriptor."""

        self.calls.append((registry_id, version))
        if registry_id in self.failures:
            raise RegistryReleaseUnavailableError("missing")
        return ComfyRegistryRelease(
            node_id=registry_id,
            version=version,
            archive_url=f"https://cdn.comfy.org/publisher/{registry_id}/node.zip",
        )


class _ArchiveInstaller:
    """Record exact workflow archive installation requests."""

    def __init__(self, *, include_requirements: bool = True) -> None:
        """Initialize recorded calls and dependency-manifest shape."""

        self.calls: list[dict[str, object]] = []
        self.include_requirements = include_requirements

    def install_workflow_registry_release(self, **kwargs: object) -> None:
        """Record the transaction and materialize a minimal package."""

        self.calls.append(kwargs)
        target = cast(Path, kwargs["target_path"])
        target.mkdir(parents=True)
        if self.include_requirements:
            (target / "requirements.txt").write_text("dependency\n", encoding="utf-8")
        (target / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='1'\ndependencies=[]\n",
            encoding="utf-8",
        )


def _candidate(
    registry_id: str,
    *,
    source_kind: WorkflowNodepackSourceKind = WorkflowNodepackSourceKind.REGISTRY,
    repository_url: str | None = None,
) -> WorkflowNodepackInstallCandidate:
    """Build one concise approved install candidate."""

    return WorkflowNodepackInstallCandidate(
        nodepack=ResolvedWorkflowNodepack(
            identifier=registry_id,
            display_name=registry_id,
            source_kind=source_kind,
            repository_url=repository_url,
            version=(
                "2.0.0"
                if source_kind is WorkflowNodepackSourceKind.REGISTRY
                else _GIT_REVISION
            ),
        ),
        nodes=(
            WorkflowNodeInventoryItem(
                node_id="1",
                class_type=f"{registry_id}Node",
                title=registry_id,
                cube_alias=None,
                nodepack_hint=None,
            ),
        ),
        persisted_versions=(),
    )


def test_installs_exact_release_with_requirements_manifest_precedence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An approved package should use its exact latest release and Comfy Python."""

    release_client = _ReleaseClient()
    archive_installer = _ArchiveInstaller()
    dependency_calls: list[tuple[str, Path, Path]] = []
    module = "substitute.infrastructure.comfy.workflow_nodepack_installer"
    monkeypatch.setattr(
        f"{module}.install_nodepack_requirements",
        lambda **kwargs: dependency_calls.append(
            (
                "requirements",
                cast(Path, kwargs["python_executable"]),
                cast(Path, kwargs["nodepack_root"]),
            )
        ),
    )
    monkeypatch.setattr(
        f"{module}.install_nodepack_python_dependencies",
        lambda **kwargs: dependency_calls.append(
            (
                "pyproject",
                cast(Path, kwargs["python_executable"]),
                cast(Path, kwargs["nodepack_root"]),
            )
        ),
    )

    result = WorkflowNodepackInstaller(
        release_client=cast(ComfyRegistryReleaseClient, release_client),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install(
        (_candidate("comfyui-impact-pack"),),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    target = tmp_path / "custom_nodes" / "comfyui-impact-pack"
    assert result.installed_package_ids == ("comfyui-impact-pack",)
    assert release_client.calls == [("comfyui-impact-pack", "2.0.0")]
    staged = cast(Path, archive_installer.calls[0]["target_path"])
    assert staged.name == target.name
    assert staged.parent.name.startswith(".substitute-workflow-nodepack-")
    assert dependency_calls == [
        ("requirements", tmp_path / "python.exe", staged),
    ]
    assert target.is_dir()
    assert not any(target.parent.glob(".substitute-workflow-nodepack-*"))


def test_uses_pyproject_dependencies_when_requirements_are_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A Registry package with only project metadata should install its dependencies."""

    archive_installer = _ArchiveInstaller(include_requirements=False)
    dependency_calls: list[str] = []
    module = "substitute.infrastructure.comfy.workflow_nodepack_installer"
    monkeypatch.setattr(
        f"{module}.install_nodepack_requirements",
        lambda **_kwargs: dependency_calls.append("requirements"),
    )
    monkeypatch.setattr(
        f"{module}.install_nodepack_python_dependencies",
        lambda **_kwargs: dependency_calls.append("pyproject"),
    )

    result = WorkflowNodepackInstaller(
        release_client=cast(ComfyRegistryReleaseClient, _ReleaseClient()),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install(
        (_candidate("project-only-pack"),),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    assert result.installed_package_ids == ("project-only-pack",)
    assert dependency_calls == ["pyproject"]


def test_retains_partial_results_and_rejects_unsafe_target_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One bad package should not erase independent successful acquisitions."""

    release_client = _ReleaseClient(failures={"missing-pack"})
    archive_installer = _ArchiveInstaller()
    module = "substitute.infrastructure.comfy.workflow_nodepack_installer"
    monkeypatch.setattr(
        f"{module}.install_nodepack_requirements", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        f"{module}.install_nodepack_python_dependencies", lambda **_kwargs: None
    )

    result = WorkflowNodepackInstaller(
        release_client=cast(ComfyRegistryReleaseClient, release_client),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install(
        (
            _candidate("healthy-pack"),
            _candidate("missing-pack"),
            _candidate("../escape"),
        ),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    assert [item.status for item in result.items] == [
        WorkflowNodepackInstallStatus.INSTALLED,
        WorkflowNodepackInstallStatus.VERSION_UNAVAILABLE,
        WorkflowNodepackInstallStatus.FAILED,
    ]
    assert result.installed_package_ids == ("healthy-pack",)
    assert result.failed
    assert not (tmp_path / "escape").exists()


def test_installs_confirmed_git_repository_and_commits_only_after_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A legacy repository should remain staged until dependency setup succeeds."""

    repository = "https://github.com/blue-pen5805/ComfyUI-krea2-negpip"
    clone_calls: list[tuple[str, str, Path]] = []
    dependency_roots: list[Path] = []
    module = "substitute.infrastructure.comfy.workflow_nodepack_installer"

    def fake_clone(**kwargs: object) -> None:
        target = cast(Path, kwargs["target_path"])
        clone_calls.append(
            (
                cast(str, kwargs["repository_url"]),
                cast(str, kwargs["revision"]),
                target,
            )
        )
        target.mkdir(parents=True)
        (target / "requirements.txt").write_text("dependency\n", encoding="utf-8")

    monkeypatch.setattr(f"{module}.install_trusted_nodepack_repository", fake_clone)
    monkeypatch.setattr(
        f"{module}.install_nodepack_requirements",
        lambda **kwargs: dependency_roots.append(cast(Path, kwargs["nodepack_root"])),
    )

    result = WorkflowNodepackInstaller().install(
        (
            _candidate(
                repository,
                source_kind=WorkflowNodepackSourceKind.GIT_REPOSITORY,
                repository_url=repository,
            ),
        ),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    target = tmp_path / "custom_nodes" / "ComfyUI-krea2-negpip"
    assert result.installed_package_ids == (repository,)
    assert clone_calls[0][0] == repository
    assert clone_calls[0][1] == _GIT_REVISION
    assert clone_calls[0][2] == dependency_roots[0]
    assert clone_calls[0][2] != target
    assert target.is_dir()


def test_dependency_failure_removes_staged_source_and_preserves_target_absence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed dependency install must not expose a partially installed nodepack."""

    archive_installer = _ArchiveInstaller()
    module = "substitute.infrastructure.comfy.workflow_nodepack_installer"
    monkeypatch.setattr(
        f"{module}.install_nodepack_requirements",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("dependency failed")),
    )

    result = WorkflowNodepackInstaller(
        release_client=cast(ComfyRegistryReleaseClient, _ReleaseClient()),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install(
        (_candidate("broken-pack"),),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    custom_nodes = tmp_path / "custom_nodes"
    assert result.items[0].status is WorkflowNodepackInstallStatus.FAILED
    assert not (custom_nodes / "broken-pack").exists()
    assert not any(custom_nodes.glob(".substitute-workflow-nodepack-*"))
