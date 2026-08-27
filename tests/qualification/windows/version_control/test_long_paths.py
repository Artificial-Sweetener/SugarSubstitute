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

"""Qualify repository cloning beyond legacy Windows path limits."""

from __future__ import annotations

from pathlib import Path

import pytest
import pygit2

from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
)
from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control.clone_process import Pygit2CloneProcess
from substitute.infrastructure.version_control.pygit2_repository import (
    Pygit2RepositoryService,
)


def test_pygit2_clone_stages_and_promotes_to_long_destination(
    tmp_path: Path,
) -> None:
    """The libgit2 boundary should clone through a short app-controlled staging path."""

    source = tmp_path / "source-repository"
    source.mkdir()
    repository = pygit2.init_repository(source, initial_head="main")
    (source / "proof.txt").write_text("clone proof", encoding="utf-8")
    repository.index.add_all()
    repository.index.write()
    tree = repository.index.write_tree()
    signature = pygit2.Signature("SugarSubstitute Tests", "tests@example.invalid")
    repository.create_commit("HEAD", signature, signature, "proof", tree, [])
    target_root = operational_path(tmp_path / "clone-target")
    target = target_root
    while len(str(target)) < 285:
        target /= "segment-0123456789abcdef"
    target.parent.mkdir(parents=True)

    try:
        Pygit2CloneProcess(timeout_seconds=30).clone(str(source), target)

        assert (target / "proof.txt").read_text(encoding="utf-8") == "clone proof"
        assert (target / ".git").is_dir()
        service = Pygit2RepositoryService()
        assert service.tracked_files(target) == (Path("proof.txt"),)
        assert service.head_commit_id(target) is not None
    finally:
        remove_app_owned_path(target_root)


@pytest.mark.platforms("windows")
def test_pygit2_clone_stages_before_target_reaches_legacy_limit(
    tmp_path: Path,
) -> None:
    """Libgit2 should not inherit a deep managed installation's path budget."""

    source = tmp_path / "source-repository-before-limit"
    source.mkdir()
    repository = pygit2.init_repository(source, initial_head="main")
    (source / "proof.txt").write_text("clone proof", encoding="utf-8")
    repository.index.add_all()
    repository.index.write()
    tree = repository.index.write_tree()
    signature = pygit2.Signature("SugarSubstitute Tests", "tests@example.invalid")
    repository.create_commit("HEAD", signature, signature, "proof", tree, [])
    target_root = operational_path(tmp_path / "managed-install-clone-target")
    managed_root = target_root
    while len(str(managed_root)) < 165:
        managed_root /= "deep-managed-install-segment"
    target = managed_root / "comfyui" / "custom_nodes" / "Substitute-BackEnd"
    assert len(str(target)) < 260
    target.parent.mkdir(parents=True)

    try:
        Pygit2CloneProcess(timeout_seconds=30).clone(str(source), target)

        assert (target / "proof.txt").read_text(encoding="utf-8") == "clone proof"
        assert (target / ".git").is_dir()
    finally:
        remove_app_owned_path(target_root)
