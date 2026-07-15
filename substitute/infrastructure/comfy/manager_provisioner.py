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

"""Provision the workspace-local ComfyUI-Manager custom node for managed installs."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from collections.abc import Mapping
from typing import Callable

from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.manager_provisioner")
DEFAULT_MANAGER_REPOSITORY_URL = "https://github.com/ltdrdata/ComfyUI-Manager.git"
_MANAGER_ENTRYPOINT_REQUIREMENTS = ("aiohttp>=3.11.8",)


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one manager-provisioning log line through logger and optional callback."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def workspace_manager_directory(workspace: Path) -> Path:
    """Return the managed workspace directory reserved for ComfyUI-Manager."""

    return workspace / "custom_nodes" / "ComfyUI-Manager"


def workspace_manager_cli_path(workspace: Path) -> Path:
    """Return the `cm-cli.py` path expected by comfy-cli in the workspace."""

    return workspace_manager_directory(workspace) / "cm-cli.py"


def workspace_manager_requirements_path(workspace: Path) -> Path:
    """Return the ComfyUI manager requirements file for the workspace."""

    return workspace / "manager_requirements.txt"


def ensure_workspace_manager_custom_node(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    repository_url: str = DEFAULT_MANAGER_REPOSITORY_URL,
    revision: str | None = None,
    repositories: RepositoryService | None = None,
) -> Path:
    """Ensure the managed workspace contains a usable ComfyUI-Manager checkout.

    Args:
        workspace: Managed ComfyUI workspace root.
        on_log: Optional callback for streaming user-visible log lines.
        repository_url: Git repository used to populate the manager checkout.
        revision: Optional git revision to checkout after clone.

    Returns:
        The resolved workspace-local `cm-cli.py` path.

    Raises:
        RuntimeError: If the manager checkout cannot be provisioned or validated.
    """

    manager_directory = workspace_manager_directory(workspace)
    manager_cli_path = workspace_manager_cli_path(workspace)
    if not manager_cli_path.exists():
        custom_nodes_root = manager_directory.parent
        custom_nodes_root.mkdir(parents=True, exist_ok=True)

        if manager_directory.exists():
            _emit_log(
                on_log,
                f"[Manager] Recreating invalid workspace manager directory: {manager_directory}",
            )
            if manager_directory.is_dir():
                shutil.rmtree(manager_directory, ignore_errors=True)
            else:
                manager_directory.unlink(missing_ok=True)

        _emit_log(on_log, f"[Manager] Cloning ComfyUI-Manager into {manager_directory}")
        try:
            (repositories or repository_service()).clone(
                repository_url,
                manager_directory,
                on_progress=on_log,
            )
        except RepositoryOperationError as error:
            raise RuntimeError(
                "Substitute couldn't provision ComfyUI-Manager into the managed workspace."
            ) from error

    if revision:
        _emit_log(on_log, f"[Manager] Checking out ComfyUI-Manager revision {revision}")
        try:
            (repositories or repository_service()).checkout_revision(
                manager_directory,
                revision,
            )
        except RepositoryOperationError as error:
            raise RuntimeError(
                "Substitute couldn't pin ComfyUI-Manager to the configured revision."
            ) from error

    if not manager_cli_path.exists():
        raise RuntimeError(
            "Substitute provisioned ComfyUI-Manager, but cm-cli.py is still missing."
        )

    ensure_workspace_manager_python_package(workspace, on_log=on_log, env=env)
    return manager_cli_path


def ensure_workspace_manager_python_package(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Ensure comfy-cli can import the workspace manager CLI module."""

    python_executable = _resolve_workspace_python(workspace)
    if not _workspace_cm_cli_importable(
        workspace=workspace,
        python_executable=python_executable,
        env=env,
    ):
        requirements_path = workspace_manager_requirements_path(workspace)
        if not requirements_path.is_file():
            raise RuntimeError(
                "Substitute provisioned ComfyUI-Manager, but the workspace is missing "
                "manager_requirements.txt."
            )
        _emit_log(
            on_log,
            "[Manager] Installing ComfyUI-Manager Python package into ComfyUI.",
        )
        install_result = subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_path),
            ],
            cwd=str(workspace),
            env=dict(env) if env is not None else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        _log_command_output(install_result, on_log)
        if install_result.returncode != 0:
            raise RuntimeError(
                "Substitute couldn't install ComfyUI-Manager's Python package."
            )
        if not _workspace_cm_cli_importable(
            workspace=workspace,
            python_executable=python_executable,
            env=env,
        ):
            raise RuntimeError(
                "Substitute installed ComfyUI-Manager, but comfy-cli still cannot import cm_cli."
            )
    if _workspace_cm_cli_entrypoint_importable(
        workspace=workspace,
        python_executable=python_executable,
        env=env,
    ):
        return
    _emit_log(
        on_log,
        "[Manager] Installing ComfyUI-Manager runtime dependencies.",
    )
    requirements_result = subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            *_MANAGER_ENTRYPOINT_REQUIREMENTS,
        ],
        cwd=str(workspace),
        env=dict(env) if env is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    _log_command_output(requirements_result, on_log)
    if requirements_result.returncode != 0:
        raise RuntimeError(
            "Substitute couldn't install ComfyUI-Manager runtime dependencies."
        )
    if not _workspace_cm_cli_entrypoint_importable(
        workspace=workspace,
        python_executable=python_executable,
        env=env,
    ):
        raise RuntimeError(
            "Substitute installed ComfyUI requirements, but ComfyUI-Manager still cannot start."
        )


def _workspace_cm_cli_importable(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether the workspace Python can import Manager's cm_cli module."""

    result = subprocess.run(
        [str(python_executable), "-c", "import cm_cli"],
        cwd=str(workspace),
        env=dict(env) if env is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return result.returncode == 0


def _workspace_cm_cli_entrypoint_importable(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether Manager's CLI entrypoint can import its runtime dependencies."""

    command_env = dict(os.environ if env is None else env)
    command_env["COMFYUI_PATH"] = str(workspace)
    result = subprocess.run(
        [str(python_executable), "-c", "import cm_cli.__main__"],
        cwd=str(workspace),
        env=command_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return result.returncode == 0


def _resolve_workspace_python(workspace: Path) -> Path:
    """Return the Python executable used by this Comfy workspace."""

    candidates = (
        workspace_python_path(workspace),
        workspace / "venv" / "Scripts" / "python.exe",
        workspace / "python_embeded" / "python.exe",
        workspace / "python_embedded" / "python.exe",
        workspace / ".venv" / "bin" / "python",
        workspace / "venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Substitute couldn't find the Python environment for ComfyUI-Manager."
    )


def _log_command_output(
    result: subprocess.CompletedProcess[str],
    callback: LogCallback | None,
) -> None:
    """Emit non-empty stdout and stderr lines from one subprocess result."""

    combined_output = (result.stdout or "") + (
        "\n" + result.stderr if result.stderr else ""
    )
    for line in combined_output.splitlines():
        stripped_line = line.strip()
        if stripped_line:
            _emit_log(callback, stripped_line)


__all__ = [
    "DEFAULT_MANAGER_REPOSITORY_URL",
    "ensure_workspace_manager_custom_node",
    "ensure_workspace_manager_python_package",
    "workspace_manager_cli_path",
    "workspace_manager_directory",
    "workspace_manager_requirements_path",
]
