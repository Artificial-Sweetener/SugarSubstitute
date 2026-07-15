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

"""Define the repository-operation boundary used by infrastructure workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol


RepositoryProgressCallback = Callable[[str], None]


class RepositoryOperationError(RuntimeError):
    """Report a repository operation that could not complete safely."""


class RepositoryService(Protocol):
    """Provide the repository behavior required by managed Comfy workflows."""

    def clone(
        self,
        repository_url: str,
        target_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Clone a repository into a new target path."""

    def sync_fast_forward(
        self,
        repository_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Fetch configured remotes and fast-forward the current branch."""

    def fetch_tag(
        self,
        repository_path: Path,
        *,
        repository_url: str,
        tag: str,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Fetch one tag from a trusted repository URL."""

    def checkout_revision(self, repository_path: Path, revision: str) -> None:
        """Checkout one resolvable revision without invoking a system executable."""

    def tracked_files(self, repository_path: Path) -> tuple[Path, ...]:
        """Return worktree-relative tracked file paths."""

    def status_excerpt(self, repository_path: Path) -> str:
        """Return concise branch and worktree status text for diagnostics."""

    def remote_urls(self, repository_path: Path) -> Mapping[str, str]:
        """Return configured fetch URLs keyed by remote name."""

    def head_commit_id(self, repository_path: Path) -> str | None:
        """Return the current commit identifier when the repository has a head."""
