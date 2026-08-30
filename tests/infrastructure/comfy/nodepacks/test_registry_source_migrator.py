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

"""Tests for transferring recognized nodepack source to Registry ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_registry_source_migrator import (
    NodepackRegistrySourceMigrator,
)
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)


def test_clean_official_git_installation_migrates_without_touching_untracked_data(
    tmp_path: Path,
) -> None:
    """Convert an existing managed checkout into Manager-readable CNR ownership."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    target = tmp_path / nodepack.expected_folder
    _materialize_release(target, nodepack_index=1)
    _write(target / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write(target / ".sugarcubes" / "Base-Cubes" / "local.cube", "user")
    tracked = (Path("__init__.py"), Path("pyproject.toml"))
    repositories = RecordingRepositoryService(
        tracked_paths=tracked,
        status="## main",
        remotes={"origin": nodepack.fallback_repository_url},
    )

    NodepackRegistrySourceMigrator(repositories).migrate_clean_git_installation(
        target_path=target,
        nodepack=nodepack,
        on_log=None,
    )

    assert not (target / ".git").exists()
    assert (target / ".tracking").read_text(encoding="utf-8") == (
        "__init__.py\npyproject.toml"
    )
    assert (target / ".sugarcubes" / "Base-Cubes" / "local.cube").is_file()


@pytest.mark.parametrize(
    ("status", "remote", "message"),
    (
        ("## main\n M pyproject.toml", None, "changed Git checkout"),
        ("## main", "https://example.invalid/fork.git", "unrecognized Git checkout"),
    ),
)
def test_git_migration_refuses_dirty_or_unrecognized_checkouts(
    tmp_path: Path,
    status: str,
    remote: str | None,
    message: str,
) -> None:
    """Preserve development work that is not proven safe for ownership conversion."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    target = tmp_path / nodepack.expected_folder
    _materialize_release(target, nodepack_index=0)
    _write(target / ".git" / "HEAD", "ref: refs/heads/main\n")
    repositories = RecordingRepositoryService(
        tracked_paths=(Path("pyproject.toml"),),
        status=status,
        remotes={"origin": remote or nodepack.fallback_repository_url},
    )

    with pytest.raises(RuntimeError, match=message):
        NodepackRegistrySourceMigrator(repositories).migrate_clean_git_installation(
            target_path=target,
            nodepack=nodepack,
            on_log=None,
        )

    assert (target / ".git").exists()
    assert not (target / ".tracking").exists()


def _materialize_release(root: Path, *, nodepack_index: int) -> None:
    """Create one trusted source fixture for migration tests."""

    nodepack = CORE_COMFY_NODEPACKS[nodepack_index]
    for sentinel in nodepack.sentinel_files:
        _write(root / sentinel, "source")
    _write(
        root / "pyproject.toml",
        (
            "[project]\n"
            f'name = "{nodepack.registry_id}"\n'
            f'version = "{nodepack.required_version}"\n'
            "dependencies = []\n"
            "[project.urls]\n"
            f'Repository = "{nodepack.fallback_repository_url.removesuffix(".git")}"\n'
        ),
    )


def _write(path: Path, content: str) -> None:
    """Write one fixture file and its parents."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
