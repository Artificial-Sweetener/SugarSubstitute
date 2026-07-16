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

"""Tests for git-backed Comfy nodepack maintenance."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy import nodepack_git_maintenance
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    CoreComfyNodepack,
)
from tests.repository_service_test_double import RecordingRepositoryService


def test_refresh_git_nodepack_fast_forwards_checkout(
    tmp_path: Path,
) -> None:
    """Git refresh should delegate one self-contained fast-forward operation."""

    target_path = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    (target_path / ".git").mkdir(parents=True)
    repositories = RecordingRepositoryService()

    refreshed = nodepack_git_maintenance.refresh_git_nodepack(
        target_path,
        on_log=None,
        env=None,
        repositories=repositories,
    )

    assert refreshed is True
    assert repositories.calls == [("sync_fast_forward", target_path)]


def test_refresh_git_nodepack_skips_plain_folders(tmp_path: Path) -> None:
    """Git refresh should reject non-git folders without running git."""

    assert (
        nodepack_git_maintenance.refresh_git_nodepack(
            tmp_path / "custom_nodes" / "Substitute-BackEnd",
            on_log=None,
            env=None,
        )
        is False
    )


def test_refresh_git_nodepack_returns_false_when_fast_forward_fails(
    tmp_path: Path,
) -> None:
    """Git refresh should fall back cleanly when fast-forward pull fails."""

    target_path = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    (target_path / ".git").mkdir(parents=True)
    logs: list[str] = []
    repositories = RecordingRepositoryService(failing_operations={"sync_fast_forward"})

    refreshed = nodepack_git_maintenance.refresh_git_nodepack(
        target_path,
        on_log=logs.append,
        env=None,
        repositories=repositories,
    )

    assert refreshed is False
    assert logs == [
        (
            f"[ComfyNodepacks] Git fast-forward failed for {target_path}; "
            "using managed replacement fallback."
        )
    ]


def test_checkout_pinned_git_tag_fetches_and_checks_out_tag(
    tmp_path: Path,
) -> None:
    """Pinned git fallback should fetch the trusted source tag and check it out."""

    nodepack = _backend_nodepack()
    target_path = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    target_path.mkdir(parents=True)
    repositories = RecordingRepositoryService()

    nodepack_git_maintenance.checkout_pinned_git_tag(
        target_path=target_path,
        nodepack=nodepack,
        on_log=None,
        env=None,
        repositories=repositories,
    )

    assert repositories.calls == [
        (
            "fetch_tag",
            (
                target_path,
                "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git",
                "v1.7.0",
            ),
        ),
        ("checkout_revision", (target_path, "v1.7.0")),
    ]


def test_checkout_pinned_git_tag_raises_when_checkout_fails(
    tmp_path: Path,
) -> None:
    """Pinned git fallback should surface failed checkout commands."""

    nodepack = _backend_nodepack()
    target_path = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    target_path.mkdir(parents=True)

    repositories = RecordingRepositoryService(failing_operations={"checkout_revision"})

    with pytest.raises(RuntimeError, match="Could not check out"):
        nodepack_git_maintenance.checkout_pinned_git_tag(
            target_path=target_path,
            nodepack=nodepack,
            on_log=None,
            env=None,
            repositories=repositories,
        )


def test_git_nodepack_backup_excludes_untracked_files(
    tmp_path: Path,
) -> None:
    """Managed replacement backups should preserve tracked state only."""

    backend_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    (backend_root / ".git").mkdir(parents=True)
    (backend_root / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n",
        encoding="utf-8",
    )
    (backend_root / "tracked.py").write_text("tracked", encoding="utf-8")
    (backend_root / "nested").mkdir()
    (backend_root / "nested" / "tracked.txt").write_text("nested", encoding="utf-8")
    (backend_root / "untracked.py").write_text("untracked", encoding="utf-8")

    repositories = RecordingRepositoryService(
        tracked_paths=(Path("tracked.py"), Path("nested") / "tracked.txt"),
        status=" M tracked.py\n?? untracked.py",
    )

    backup_path = nodepack_git_maintenance.backup_git_nodepack_before_replacement(
        target_path=backend_root,
        nodepack=_backend_nodepack(),
        reason="git_fast_forward_failed",
        env=None,
        repositories=repositories,
    )

    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
    assert "Substitute-BackEnd/.git/HEAD" in names
    assert "Substitute-BackEnd/tracked.py" in names
    assert "Substitute-BackEnd/nested/tracked.txt" in names
    assert "Substitute-BackEnd/untracked.py" not in names
    metadata = json.loads(backup_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["untrackedFilesIncluded"] is False
    assert metadata["trackedFileCount"] == 2


def _backend_nodepack() -> CoreComfyNodepack:
    """Return the Substitute BackEnd nodepack manifest."""

    return next(
        nodepack
        for nodepack in CORE_COMFY_NODEPACKS
        if nodepack.nodepack_id is CoreNodepackId.SUBSTITUTE_BACKEND
    )
