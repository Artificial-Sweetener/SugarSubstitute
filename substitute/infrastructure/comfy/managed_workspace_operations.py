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

"""Own managed-Comfy workspace layout and repository operations."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Callable

from substitute.infrastructure.comfy.managed_install_failures import (
    raise_forced_managed_failure,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_nested_main_path,
    workspace_python_dir,
    workspace_venv_dir,
)
from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)

LogCallback = Callable[[str], None]

_COMFY_REPOSITORY_URL = "https://github.com/comfyanonymous/ComfyUI.git"
_OWNED_BOOTSTRAP_WORKSPACE_FILES = frozenset({".substitute", "extra_model_paths.yaml"})


def migrate_nested_workspace_layout(workspace: Path) -> bool:
    """Move a legacy `workspace/ComfyUI` install into the canonical workspace root."""

    nested_repo = workspace / "ComfyUI"
    if (
        not workspace_nested_main_path(workspace).exists()
        or workspace_main_path(workspace).exists()
    ):
        return False

    preserve = {
        workspace_venv_dir(workspace).name,
        workspace_python_dir(workspace).name,
        ".comfy_installed",
    }
    for entry in nested_repo.iterdir():
        if entry.name in preserve:
            continue
        destination = workspace / entry.name
        if destination.exists() or destination.is_symlink():
            remove_app_owned_path(destination)
        shutil.move(str(entry), str(destination))
    remove_app_owned_path(nested_repo)
    return True


def remove_invalid_bootstrap_workspace(workspace: Path) -> bool:
    """Delete a leftover invalid workspace that contains only bootstrap artifacts."""

    if not workspace.exists() or workspace_main_path(workspace).exists():
        return False
    allowed_entries = {
        workspace_venv_dir(workspace).name,
        workspace_python_dir(workspace).name,
        ".comfy_installed",
        *_OWNED_BOOTSTRAP_WORKSPACE_FILES,
    }
    present_entries = {entry.name for entry in workspace.iterdir()}
    if not present_entries:
        workspace.rmdir()
        return True
    if not present_entries.issubset(allowed_entries):
        return False
    remove_app_owned_path(workspace)
    return True


def clone_managed_workspace(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: dict[str, str] | None = None,
    repositories: RepositoryService | None = None,
) -> None:
    """Clone the canonical ComfyUI repository into the managed workspace path."""

    del env
    raise_forced_managed_failure("clone")
    try:
        (repositories or repository_service()).clone(
            _COMFY_REPOSITORY_URL,
            workspace,
            on_progress=on_log,
        )
    except RepositoryOperationError as error:
        raise RuntimeError(
            "Substitute couldn't download ComfyUI into the selected folder."
        ) from error


def sync_managed_workspace_repository(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: dict[str, str] | None = None,
    repositories: RepositoryService | None = None,
) -> None:
    """Clone or update the managed ComfyUI repository in place."""

    if not workspace.exists():
        clone_managed_workspace(
            workspace,
            on_log=on_log,
            env=env,
            repositories=repositories,
        )
        return
    if not (workspace / ".git").exists():
        return
    raise_forced_managed_failure("clone")
    try:
        (repositories or repository_service()).sync_fast_forward(
            workspace,
            on_progress=on_log,
        )
    except RepositoryOperationError as error:
        raise RuntimeError(
            "Substitute couldn't update the managed ComfyUI repository."
        ) from error
