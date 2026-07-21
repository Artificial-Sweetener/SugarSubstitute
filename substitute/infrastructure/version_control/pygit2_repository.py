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

"""Implement repository operations with bundled libgit2 through pygit2."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pygit2

from substitute.infrastructure.version_control.clone_process import (
    Pygit2CloneProcess,
)
from substitute.infrastructure.version_control.repository import (
    RepositoryOperationError,
    RepositoryProgressCallback,
)
from sugarsubstitute_shared.windows_long_paths import (
    external_long_path_error,
    operational_path,
)


_CHECKOUT_STRATEGY = pygit2.GIT_CHECKOUT_SAFE | pygit2.GIT_CHECKOUT_RECREATE_MISSING


class Pygit2RepositoryService:
    """Perform managed repository work without requiring a system Git binary."""

    def __init__(self, *, clone_process: Pygit2CloneProcess | None = None) -> None:
        """Store the bounded process owner used for network clones."""

        self._clone_process = clone_process or Pygit2CloneProcess()

    def initialize(self, repository_path: Path, *, branch: str = "main") -> None:
        """Initialize an empty repository through libgit2."""

        repository_path = operational_path(repository_path)
        try:
            repository_path.mkdir(parents=True, exist_ok=True)
            pygit2.init_repository(repository_path, initial_head=branch)
        except (OSError, ValueError, pygit2.GitError) as error:
            compatibility_error = external_long_path_error(
                component="pygit2",
                path=repository_path,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise RepositoryOperationError(
                f"Could not initialize repository at {repository_path}."
            ) from error

    def clone(
        self,
        repository_url: str,
        target_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Clone a repository into a new target path."""

        target_path = operational_path(target_path)
        self._emit(on_progress, f"Cloning {repository_url} into {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._clone_process.clone(repository_url, target_path)
        except RepositoryOperationError as error:
            raise RepositoryOperationError(
                f"Could not clone repository {repository_url} into {target_path}: {error}"
            ) from error
        self._emit(on_progress, f"Cloned {repository_url}")

    def sync_fast_forward(
        self,
        repository_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Fetch configured remotes and fast-forward the current branch."""

        repository = self._open(repository_path)
        try:
            for remote in repository.remotes:
                self._emit(on_progress, f"Fetching {remote.name or remote.url}")
                remote.fetch(
                    [
                        *remote.fetch_refspecs,
                        "+refs/tags/*:refs/tags/*",
                    ]
                )
            self._fast_forward_current_branch(repository)
        except (KeyError, ValueError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not fast-forward repository {repository_path}: {error}"
            ) from error

    def fetch_all(
        self,
        repository_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Fetch every configured remote branch and tag through libgit2."""

        repository = self._open(repository_path)
        try:
            for remote in repository.remotes:
                self._emit(on_progress, f"Fetching {remote.name or remote.url}")
                remote.fetch()
        except (KeyError, ValueError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not fetch repository remotes for {repository_path}: {error}"
            ) from error

    def fetch_tag(
        self,
        repository_path: Path,
        *,
        repository_url: str,
        tag: str,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Fetch one tag from a trusted repository URL."""

        repository = self._open(repository_path)
        self._emit(on_progress, f"Fetching tag {tag} from {repository_url}")
        refspec = f"+refs/tags/{tag}:refs/tags/{tag}"
        try:
            repository.remotes.create_anonymous(repository_url).fetch([refspec])
        except (ValueError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not fetch tag {tag} into {repository_path}: {error}"
            ) from error

    def checkout_revision(self, repository_path: Path, revision: str) -> None:
        """Checkout one resolvable revision and detach HEAD at its commit."""

        repository = self._open(repository_path)
        try:
            revision_object = repository.revparse_single(revision)
            commit = revision_object.peel(pygit2.Commit)
            # pygit2's checkout_tree C binding has no callable type signature.
            repository.checkout_tree(  # type: ignore[no-untyped-call]
                commit,
                strategy=_CHECKOUT_STRATEGY,
            )
            repository.set_head(commit.id)
        except (KeyError, ValueError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not checkout revision {revision} in {repository_path}: {error}"
            ) from error

    def tracked_files(self, repository_path: Path) -> tuple[Path, ...]:
        """Return worktree-relative tracked paths from the repository index."""

        repository = self._open(repository_path)
        try:
            repository.index.read()
            return tuple(Path(entry.path) for entry in repository.index)
        except (OSError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not read tracked files in {repository_path}: {error}"
            ) from error

    def status_excerpt(self, repository_path: Path) -> str:
        """Return concise branch and worktree status text for diagnostics."""

        repository = self._open(repository_path)
        try:
            branch = (
                "HEAD detached"
                if repository.head_is_detached
                else repository.head.shorthand
            )
            entries = [f"## {branch}"]
            entries.extend(
                f"{_status_label(flags)} {path}"
                for path, flags in sorted(repository.status().items())
                if flags != pygit2.GIT_STATUS_CURRENT
            )
            return "\n".join(entries)
        except (KeyError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not read repository status in {repository_path}: {error}"
            ) from error

    def remote_urls(self, repository_path: Path) -> Mapping[str, str]:
        """Return configured fetch URLs keyed by remote name."""

        repository = self._open(repository_path)
        return {
            remote.name: remote.url
            for remote in repository.remotes
            if remote.name is not None and remote.url is not None
        }

    def head_commit_id(self, repository_path: Path) -> str | None:
        """Return the current commit identifier when the repository has a head."""

        repository = self._open(repository_path)
        if repository.head_is_unborn:
            return None
        try:
            return str(repository.head.target)
        except (KeyError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                f"Could not resolve repository head in {repository_path}: {error}"
            ) from error

    def _open(self, repository_path: Path) -> pygit2.Repository:
        """Open one worktree repository and normalize backend failures."""

        repository_path = operational_path(repository_path)
        try:
            return pygit2.Repository(repository_path)
        except (OSError, ValueError, pygit2.GitError) as error:
            compatibility_error = external_long_path_error(
                component="pygit2",
                path=repository_path,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise RepositoryOperationError(
                f"Could not open repository {repository_path}: {error}"
            ) from error

    def _fast_forward_current_branch(self, repository: pygit2.Repository) -> None:
        """Advance the current local branch only when its upstream descends from it."""

        if repository.head_is_unborn or repository.head_is_detached:
            raise RepositoryOperationError(
                "Fast-forward sync requires a checked-out local branch."
            )
        local_branch = repository.lookup_branch(repository.head.shorthand)
        if local_branch is None:
            raise RepositoryOperationError(
                "Current local branch could not be resolved."
            )
        try:
            upstream = local_branch.upstream
        except (KeyError, pygit2.GitError) as error:
            raise RepositoryOperationError(
                "Current branch has no configured upstream."
            ) from error
        local_target = local_branch.target
        upstream_target = upstream.target
        if local_target == upstream_target:
            return
        if not repository.descendant_of(upstream_target, local_target):
            raise RepositoryOperationError(
                "Remote history cannot be applied as a fast-forward."
            )
        commit = repository[upstream_target].peel(pygit2.Commit)
        # pygit2's checkout_tree C binding has no callable type signature.
        repository.checkout_tree(  # type: ignore[no-untyped-call]
            commit,
            strategy=_CHECKOUT_STRATEGY,
        )
        local_branch.set_target(upstream_target)
        repository.set_head(local_branch.name)

    @staticmethod
    def _emit(
        callback: RepositoryProgressCallback | None,
        message: str,
    ) -> None:
        """Emit one high-level repository progress message when requested."""

        if callback is not None:
            callback(message)


def _status_label(flags: int) -> str:
    """Render libgit2 status flags as compact diagnostic text."""

    if flags & pygit2.GIT_STATUS_CONFLICTED:
        return "UU"
    if flags & pygit2.GIT_STATUS_WT_NEW:
        return "??"
    index_changed = flags & (
        pygit2.GIT_STATUS_INDEX_NEW
        | pygit2.GIT_STATUS_INDEX_MODIFIED
        | pygit2.GIT_STATUS_INDEX_DELETED
        | pygit2.GIT_STATUS_INDEX_RENAMED
        | pygit2.GIT_STATUS_INDEX_TYPECHANGE
    )
    worktree_changed = flags & (
        pygit2.GIT_STATUS_WT_MODIFIED
        | pygit2.GIT_STATUS_WT_DELETED
        | pygit2.GIT_STATUS_WT_RENAMED
        | pygit2.GIT_STATUS_WT_TYPECHANGE
        | pygit2.GIT_STATUS_WT_UNREADABLE
    )
    return f"{'M' if index_changed else ' '}{'M' if worktree_changed else ' '}"
