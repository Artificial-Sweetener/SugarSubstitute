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

"""Install explicitly trusted custom-node repositories with libgit2."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)
from substitute.infrastructure.filesystem import remove_app_owned_path

from substitute.infrastructure.comfy.nodepack_reconciliation_logger import LogCallback


def install_trusted_nodepack_repository(
    *,
    repository_url: str,
    revision: str,
    target_path: Path,
    display_name: str,
    on_log: LogCallback | None = None,
    repositories: RepositoryService | None = None,
) -> None:
    """Clone one application-owned trusted nodepack at an exact revision."""

    if target_path.exists():
        raise RuntimeError(
            f"Could not install {display_name}: target already exists at {target_path}."
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        repository_operations = repositories or repository_service()
        repository_operations.clone(
            repository_url,
            target_path,
            on_progress=on_log,
        )
        repository_operations.checkout_revision(target_path, revision)
        if repository_operations.head_commit_id(target_path) != revision.casefold():
            raise RepositoryOperationError(
                "Repository checkout did not reach the approved revision."
            )
    except RepositoryOperationError as error:
        _remove_partial_clone(target_path)
        raise RuntimeError(
            f"Could not clone the trusted {display_name} repository."
        ) from error


def _remove_partial_clone(target_path: Path) -> None:
    """Remove a partially materialized clone after the repository backend fails."""

    remove_app_owned_path(target_path)


__all__ = ["install_trusted_nodepack_repository"]
