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

"""Tests for installed nodepack identity and ownership inspection."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.domain.comfy_nodepacks import NodepackManagementKind
from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    NodepackInstallationInspector,
    repository_urls_match,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from tests.repository_service_test_double import RecordingRepositoryService


@pytest.mark.parametrize(
    ("metadata", "expected"),
    (
        (None, NodepackManagementKind.PLAIN),
        ("git", NodepackManagementKind.GIT),
        ("tracking", NodepackManagementKind.REGISTRY),
    ),
)
def test_inspector_classifies_source_owner_and_exact_project_identity(
    tmp_path: Path,
    metadata: str | None,
    expected: NodepackManagementKind,
) -> None:
    """Use source-folder metadata and pyproject as the installation authority."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    root = tmp_path / nodepack.expected_folder
    _materialize(root, 0)
    if metadata == "git":
        (root / ".git").mkdir()
    elif metadata == "tracking":
        (root / ".tracking").write_text("pyproject.toml", encoding="utf-8")
    repositories = RecordingRepositoryService(
        status="## main\n?? cache/user.json",
        remotes={"origin": nodepack.fallback_repository_url},
    )

    snapshot = NodepackInstallationInspector(repositories).inspect(
        workspace=tmp_path,
        nodepack=nodepack,
    )

    assert snapshot.management is expected
    assert snapshot.matches(nodepack)
    assert snapshot.tracked_worktree_dirty is False
    assert snapshot.official_git_remote is (metadata == "git")


def test_inspector_reports_tracked_git_changes_without_counting_untracked_data(
    tmp_path: Path,
) -> None:
    """Distinguish protected source changes from preserved mutable runtime files."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    root = tmp_path / nodepack.expected_folder
    _materialize(root, 1)
    (root / ".git").mkdir()
    repositories = RecordingRepositoryService(
        status="## main\n M sugarcubes/host_api.py\n?? .sugarcubes/local.cube",
        remotes={"origin": nodepack.fallback_repository_url},
    )

    snapshot = NodepackInstallationInspector(repositories).inspect(
        workspace=tmp_path,
        nodepack=nodepack,
    )

    assert snapshot.tracked_worktree_dirty is True


def test_repository_identity_comparison_handles_git_suffix_and_case() -> None:
    """Recognize the trusted HTTPS remote across harmless spelling differences."""

    assert repository_urls_match(
        ["HTTPS://GITHUB.COM/Artificial-Sweetener/Substitute-BackEnd/"],
        "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git",
    )


def _materialize(root: Path, nodepack_index: int) -> None:
    """Write an exact nodepack source fixture."""

    nodepack = CORE_COMFY_NODEPACKS[nodepack_index]
    for sentinel in nodepack.sentinel_files:
        path = root / sentinel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (
            "[project]\n"
            f'name = "{nodepack.registry_id}"\n'
            f'version = "{nodepack.required_version}"\n'
            "dependencies = []\n"
            "[project.urls]\n"
            f'Repository = "{nodepack.fallback_repository_url}"\n'
        ),
        encoding="utf-8",
    )
