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

"""Provide a deterministic repository-service test double."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from substitute.infrastructure.version_control import RepositoryOperationError
from substitute.infrastructure.version_control.repository import (
    RepositoryProgressCallback,
)


CloneCallback = Callable[[str, Path], None]


@dataclass
class RecordingRepositoryService:
    """Record repository operations and expose configurable deterministic results."""

    clone_callback: CloneCallback | None = None
    failing_operations: set[str] = field(default_factory=set)
    tracked_paths: tuple[Path, ...] = ()
    status: str = "## main"
    remotes: Mapping[str, str] = field(default_factory=dict)
    head: str | None = "0" * 40
    calls: list[tuple[str, object]] = field(default_factory=list)

    def clone(
        self,
        repository_url: str,
        target_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Record a clone and optionally materialize its fixture checkout."""

        self.calls.append(("clone", (repository_url, target_path)))
        self._raise_if_failing("clone")
        if on_progress is not None:
            on_progress(f"Cloning {repository_url}")
        if self.clone_callback is not None:
            self.clone_callback(repository_url, target_path)

    def sync_fast_forward(
        self,
        repository_path: Path,
        *,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Record one fast-forward sync."""

        self.calls.append(("sync_fast_forward", repository_path))
        self._raise_if_failing("sync_fast_forward")
        if on_progress is not None:
            on_progress(f"Fetching {repository_path}")

    def fetch_tag(
        self,
        repository_path: Path,
        *,
        repository_url: str,
        tag: str,
        on_progress: RepositoryProgressCallback | None = None,
    ) -> None:
        """Record one trusted tag fetch."""

        self.calls.append(("fetch_tag", (repository_path, repository_url, tag)))
        self._raise_if_failing("fetch_tag")
        if on_progress is not None:
            on_progress(f"Fetching {tag}")

    def checkout_revision(self, repository_path: Path, revision: str) -> None:
        """Record one revision checkout."""

        self.calls.append(("checkout_revision", (repository_path, revision)))
        self._raise_if_failing("checkout_revision")

    def tracked_files(self, repository_path: Path) -> tuple[Path, ...]:
        """Return configured tracked paths."""

        self.calls.append(("tracked_files", repository_path))
        self._raise_if_failing("tracked_files")
        return self.tracked_paths

    def status_excerpt(self, repository_path: Path) -> str:
        """Return configured status diagnostics."""

        self.calls.append(("status_excerpt", repository_path))
        self._raise_if_failing("status_excerpt")
        return self.status

    def remote_urls(self, repository_path: Path) -> Mapping[str, str]:
        """Return configured remote metadata."""

        self.calls.append(("remote_urls", repository_path))
        self._raise_if_failing("remote_urls")
        return self.remotes

    def head_commit_id(self, repository_path: Path) -> str | None:
        """Return the configured head identifier."""

        self.calls.append(("head_commit_id", repository_path))
        self._raise_if_failing("head_commit_id")
        return self.head

    def _raise_if_failing(self, operation: str) -> None:
        """Raise the backend exception configured for one operation."""

        if operation in self.failing_operations:
            raise RepositoryOperationError(f"Forced {operation} failure")
