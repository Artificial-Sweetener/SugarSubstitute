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

"""Exercise native short aliases for Windows repository operations."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control.pygit2_repository import (
    Pygit2RepositoryService,
)
from substitute.infrastructure.version_control.repository_path_workspace import (
    REPOSITORY_DESCENDANT_BUDGET,
    RepositoryPathWorkspace,
)
from sugarsubstitute_shared.windows_long_paths import (
    WINDOWS_LEGACY_PATH_LIMIT,
    operational_path,
)


@pytest.mark.platforms("windows")
def test_workspace_alias_writes_to_target_and_cleans_only_alias(tmp_path: Path) -> None:
    """A transient junction should preserve the repository it exposes."""

    cleanup_root, repository_path = _deep_repository_path(tmp_path)
    workspace = RepositoryPathWorkspace.reserve(repository_path, create_target=True)
    try:
        assert os.path.isjunction(workspace.access_path)
        assert (
            len(str(workspace.access_path)) + REPOSITORY_DESCENDANT_BUDGET
            < WINDOWS_LEGACY_PATH_LIMIT
        )
        (workspace.access_path / "proof.txt").write_text("proof", encoding="utf-8")
    finally:
        workspace.cleanup()

    try:
        assert (repository_path / "proof.txt").read_text(encoding="utf-8") == "proof"
        assert not workspace.access_path.exists()
    finally:
        remove_app_owned_path(cleanup_root)


@pytest.mark.platforms("windows")
def test_repository_service_initializes_and_reopens_deep_repository(
    tmp_path: Path,
) -> None:
    """Initialization and later access should share the native alias boundary."""

    cleanup_root, repository_path = _deep_repository_path(tmp_path)
    service = Pygit2RepositoryService()
    try:
        service.initialize(repository_path)

        assert (repository_path / ".git").is_dir()
        assert service.head_commit_id(repository_path) is None
        assert service.remote_urls(repository_path) == {}
    finally:
        remove_app_owned_path(cleanup_root)


def _deep_repository_path(tmp_path: Path) -> tuple[Path, Path]:
    """Return a managed-workspace-shaped path that triggers libgit2's limit."""

    cleanup_root = operational_path(tmp_path / "repository-alias-target")
    managed_root = cleanup_root
    while len(str(managed_root)) < 165:
        managed_root /= "deep-managed-install-segment"
    repository_path = (
        managed_root
        / "comfyui"
        / "custom_nodes"
        / "SugarCubes"
        / ".sugarcubes"
        / "local"
    )
    assert len(str(repository_path)) < 260
    return cleanup_root, repository_path
