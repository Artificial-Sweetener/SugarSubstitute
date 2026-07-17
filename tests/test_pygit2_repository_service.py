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

"""Integration tests for the self-contained libgit2 repository backend."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pygit2
import pytest

from substitute.infrastructure.version_control import (
    Pygit2RepositoryService,
    RepositoryOperationError,
)
from substitute.infrastructure.version_control.clone_process import Pygit2CloneProcess


def test_repository_initialization_does_not_require_system_git(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Empty authoring repositories should initialize through libgit2."""

    monkeypatch.setenv("PATH", "")
    repository_path = tmp_path / "local"

    Pygit2RepositoryService().initialize(repository_path)

    repository = pygit2.Repository(repository_path)
    assert repository.head_is_unborn
    assert repository.lookup_reference("HEAD").target == "refs/heads/main"


def test_repository_lifecycle_does_not_require_system_git(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clone, sync, inspect, and checkout should work with an empty PATH."""

    monkeypatch.setenv("PATH", "")
    origin, producer = _create_origin(tmp_path)
    service = Pygit2RepositoryService()
    checkout = tmp_path / "checkout"

    service.clone(str(origin), checkout)
    assert (checkout / "tracked.txt").read_text(encoding="utf-8") == "first"
    assert service.tracked_files(checkout) == (Path("tracked.txt"),)
    assert service.remote_urls(checkout)["origin"] == str(origin)

    assert producer.workdir is not None
    (Path(producer.workdir) / "tracked.txt").write_text("second", encoding="utf-8")
    second_commit = _commit(producer, "second")
    producer.remotes["origin"].push(["refs/heads/main:refs/heads/main"])

    service.sync_fast_forward(checkout)
    assert (checkout / "tracked.txt").read_text(encoding="utf-8") == "second"
    assert service.head_commit_id(checkout) == str(second_commit)

    producer.create_tag(
        "v1.0.0",
        second_commit,
        pygit2.enums.ObjectType.COMMIT,
        _signature(),
        "release",
    )
    producer.remotes["origin"].push(["refs/tags/v1.0.0:refs/tags/v1.0.0"])
    service.fetch_tag(
        checkout,
        repository_url=str(origin),
        tag="v1.0.0",
    )
    service.checkout_revision(checkout, "v1.0.0")
    assert service.head_commit_id(checkout) == str(second_commit)


def test_repository_status_reports_tracked_and_untracked_changes(
    tmp_path: Path,
) -> None:
    """Status diagnostics should expose local work without shelling out."""

    origin, _producer = _create_origin(tmp_path)
    checkout = tmp_path / "checkout"
    service = Pygit2RepositoryService()
    service.clone(str(origin), checkout)
    (checkout / "tracked.txt").write_text("changed", encoding="utf-8")
    (checkout / "untracked.txt").write_text("new", encoding="utf-8")

    status = service.status_excerpt(checkout)

    assert "tracked.txt" in status
    assert "?? untracked.txt" in status


def test_clone_process_removes_partial_checkout_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A stalled clone should fail within its bound and remove partial output."""

    target = tmp_path / "partial-checkout"

    def raise_timeout(*args: object, **kwargs: object) -> None:
        """Materialize partial output before simulating an expired child."""

        del args, kwargs
        target.mkdir()
        (target / ".git").mkdir()
        raise subprocess.TimeoutExpired(("python", "clone"), timeout=1)

    monkeypatch.setattr(
        "substitute.infrastructure.version_control.clone_process.subprocess.run",
        raise_timeout,
    )

    with pytest.raises(RepositoryOperationError, match="timed out"):
        Pygit2CloneProcess(timeout_seconds=1).clone(
            "https://example.invalid/repository.git",
            target,
        )

    assert not target.exists()


def _create_origin(tmp_path: Path) -> tuple[Path, pygit2.Repository]:
    """Create a local producer and bare remote without a Git executable."""

    origin_path = tmp_path / "origin.git"
    pygit2.init_repository(origin_path, bare=True, initial_head="main")
    producer_path = tmp_path / "producer"
    producer = pygit2.init_repository(producer_path, initial_head="main")
    (producer_path / "tracked.txt").write_text("first", encoding="utf-8")
    _commit(producer, "first")
    producer.remotes.create("origin", str(origin_path))
    producer.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
    return origin_path, producer


def _commit(repository: pygit2.Repository, message: str) -> pygit2.Oid:
    """Commit the producer worktree and return the new object identifier."""

    repository.index.add_all()
    repository.index.write()
    tree_id = repository.index.write_tree()
    parents = [] if repository.head_is_unborn else [repository.head.target]
    return repository.create_commit(
        "HEAD",
        _signature(),
        _signature(),
        message,
        tree_id,
        parents,
    )


def _signature() -> pygit2.Signature:
    """Return a deterministic test commit signature."""

    return pygit2.Signature("SugarSubstitute Tests", "tests@example.invalid", 1, 0)
