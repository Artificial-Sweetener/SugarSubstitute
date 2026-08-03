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

"""Open and initialize pygit2 repositories through path-safe workspaces."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pygit2

from substitute.infrastructure.version_control.repository import (
    RepositoryOperationError,
)
from substitute.infrastructure.version_control.repository_path_workspace import (
    RepositoryPathWorkspace,
)
from sugarsubstitute_shared.external_path_failure import external_long_path_error
from sugarsubstitute_shared.windows_long_paths import operational_path


def initialize_pygit2_repository(repository_path: Path, *, branch: str) -> None:
    """Initialize one repository without exposing its final path to libgit2."""

    workspace: RepositoryPathWorkspace | None = None
    try:
        workspace = RepositoryPathWorkspace.reserve(
            repository_path,
            create_target=True,
        )
        pygit2.init_repository(workspace.access_path, initial_head=branch)
    except (OSError, ValueError, pygit2.GitError) as error:
        compatibility_error = external_long_path_error(
            component="pygit2",
            path=operational_path(repository_path),
            detail=error,
        )
        if compatibility_error is not None:
            raise compatibility_error from error
        raise RepositoryOperationError(
            f"Could not initialize repository at {operational_path(repository_path)}."
        ) from error
    finally:
        if workspace is not None:
            workspace.cleanup()


@contextmanager
def open_pygit2_repository(repository_path: Path) -> Iterator[pygit2.Repository]:
    """Yield one repository opened through a short component-safe path."""

    workspace: RepositoryPathWorkspace | None = None
    try:
        try:
            workspace = RepositoryPathWorkspace.reserve(repository_path)
            repository = pygit2.Repository(workspace.access_path)
        except (OSError, ValueError, pygit2.GitError) as error:
            compatibility_error = external_long_path_error(
                component="pygit2",
                path=operational_path(repository_path),
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise RepositoryOperationError(
                f"Could not open repository {operational_path(repository_path)}: {error}"
            ) from error
        yield repository
    finally:
        if workspace is not None:
            workspace.cleanup()


__all__ = ["initialize_pygit2_repository", "open_pygit2_repository"]
