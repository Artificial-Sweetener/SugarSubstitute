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

"""Detect, provision, and validate ComfyUI Manager runtimes."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from substitute.domain.comfy_manager import (
    ComfyManagerCapabilities,
    ComfyManagerKind,
    ComfyManagerProvisioningAction,
    ComfyManagerRuntime,
    select_attached_manager_action,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.manager_provisioner")
DEFAULT_MANAGER_REPOSITORY_URL = "https://github.com/ltdrdata/ComfyUI-Manager.git"
_INTEGRATED_IMPORT_SCRIPT = (
    "import importlib.metadata; import comfyui_manager; import cm_cli.__main__; "
    "print(importlib.metadata.version('comfyui-manager'))"
)


def workspace_manager_directory(workspace: Path) -> Path:
    """Return the legacy ComfyUI-Manager custom-node directory."""

    return workspace / "custom_nodes" / "ComfyUI-Manager"


def workspace_manager_cli_path(workspace: Path) -> Path:
    """Return the legacy Manager CLI script path."""

    return workspace_manager_directory(workspace) / "cm-cli.py"


def workspace_manager_requirements_path(workspace: Path) -> Path:
    """Return the integrated Manager requirements file shipped by ComfyUI."""

    return workspace / "manager_requirements.txt"


def workspace_supports_integrated_manager(workspace: Path) -> bool:
    """Return whether ComfyUI declares its integrated Manager launch contract."""

    requirements_path = workspace_manager_requirements_path(workspace)
    cli_args_path = workspace / "comfy" / "cli_args.py"
    if not requirements_path.is_file() or not cli_args_path.is_file():
        return False
    try:
        return "--enable-manager" in cli_args_path.read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return False


def ensure_managed_workspace_manager(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyManagerRuntime:
    """Ensure an app-owned current ComfyUI uses integrated Manager only."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    if not workspace_supports_integrated_manager(workspace):
        raise RuntimeError(
            "Managed ComfyUI does not expose the required integrated Manager contract "
            "(--enable-manager and manager_requirements.txt)."
        )
    runtime, failure = _probe_integrated_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if runtime is None:
        _emit_log(on_log, "[Manager] Installing ComfyUI's integrated Manager package.")
        _install_requirements(
            workspace=workspace,
            python_executable=resolved_python,
            requirements_path=workspace_manager_requirements_path(workspace),
            on_log=on_log,
            env=env,
        )
        runtime, failure = _probe_integrated_runtime(
            workspace=workspace,
            python_executable=resolved_python,
            env=env,
        )
    if runtime is None:
        raise RuntimeError(_validation_failure_message("integrated", failure))
    legacy_directory = workspace_manager_directory(workspace)
    if legacy_directory.exists():
        _emit_log(
            on_log,
            f"[Manager] Removing app-owned legacy Manager checkout: {legacy_directory}",
        )
        _remove_path(legacy_directory)
    return runtime


def ensure_attached_workspace_manager(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    repository_url: str = DEFAULT_MANAGER_REPOSITORY_URL,
    repositories: RepositoryService | None = None,
) -> ComfyManagerRuntime:
    """Select or install Manager without replacing user-owned attached checkouts."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    integrated, integrated_failure = _probe_integrated_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    legacy, legacy_failure = _probe_legacy_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    action = select_attached_manager_action(
        ComfyManagerCapabilities(
            supports_integrated=workspace_supports_integrated_manager(workspace),
            integrated_healthy=integrated is not None,
            legacy_healthy=legacy is not None,
        )
    )
    if action is ComfyManagerProvisioningAction.USE_INTEGRATED:
        _emit_log(on_log, "[Manager] Using ComfyUI's integrated Manager package.")
        assert integrated is not None
        return integrated
    if action is ComfyManagerProvisioningAction.USE_LEGACY:
        _emit_log(on_log, "[Manager] Using the attached legacy Manager custom node.")
        assert legacy is not None
        return legacy
    if action is ComfyManagerProvisioningAction.INSTALL_INTEGRATED:
        _emit_log(on_log, "[Manager] Installing ComfyUI's integrated Manager package.")
        _install_requirements(
            workspace=workspace,
            python_executable=resolved_python,
            requirements_path=workspace_manager_requirements_path(workspace),
            on_log=on_log,
            env=env,
        )
        integrated, integrated_failure = _probe_integrated_runtime(
            workspace=workspace,
            python_executable=resolved_python,
            env=env,
        )
        if integrated is None:
            raise RuntimeError(
                _validation_failure_message("integrated", integrated_failure)
            )
        return integrated

    legacy_directory = workspace_manager_directory(workspace)
    if legacy_directory.exists():
        raise RuntimeError(
            _validation_failure_message("legacy custom-node", legacy_failure)
            + " The existing user-owned Manager directory was left unchanged."
        )
    legacy_directory.parent.mkdir(parents=True, exist_ok=True)
    _emit_log(on_log, f"[Manager] Installing legacy Manager into {legacy_directory}.")
    try:
        (repositories or repository_service()).clone(
            repository_url,
            legacy_directory,
            on_progress=on_log,
        )
    except RepositoryOperationError as error:
        raise RuntimeError(
            "Substitute could not install the required legacy ComfyUI-Manager custom node."
        ) from error
    requirements_path = legacy_directory / "requirements.txt"
    if requirements_path.is_file():
        _install_requirements(
            workspace=workspace,
            python_executable=resolved_python,
            requirements_path=requirements_path,
            on_log=on_log,
            env=env,
        )
    legacy, legacy_failure = _probe_legacy_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if legacy is None:
        raise RuntimeError(_validation_failure_message("legacy", legacy_failure))
    return legacy


def detect_workspace_manager_runtime(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyManagerRuntime:
    """Return the preferred validated Manager runtime without changing the workspace."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    integrated, integrated_failure = _probe_integrated_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if integrated is not None:
        return integrated
    legacy, legacy_failure = _probe_legacy_runtime(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if legacy is not None:
        return legacy
    details = integrated_failure or legacy_failure
    raise RuntimeError(_validation_failure_message("workspace", details))


def _probe_integrated_runtime(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> tuple[ComfyManagerRuntime | None, str]:
    """Probe the integrated Manager package and retain diagnostic output."""

    if not workspace_supports_integrated_manager(workspace):
        return None, "ComfyUI does not declare integrated Manager support."
    result = _run_probe(
        [str(python_executable), "-c", _INTEGRATED_IMPORT_SCRIPT],
        workspace=workspace,
        env=env,
    )
    if result.returncode != 0:
        return None, _command_output(result)
    version = next(
        (line.strip() for line in (result.stdout or "").splitlines() if line.strip()),
        None,
    )
    return (
        ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python_executable,
            version=version,
        ),
        "",
    )


def _probe_legacy_runtime(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> tuple[ComfyManagerRuntime | None, str]:
    """Probe the legacy Manager script and retain diagnostic output."""

    cli_path = workspace_manager_cli_path(workspace)
    if not cli_path.is_file():
        return None, f"Legacy Manager CLI is missing: {cli_path}"
    result = _run_probe(
        [str(python_executable), str(cli_path), "--help"],
        workspace=workspace,
        env=env,
    )
    if result.returncode != 0:
        return None, _command_output(result)
    return (
        ComfyManagerRuntime(
            kind=ComfyManagerKind.LEGACY_CUSTOM_NODE,
            workspace=workspace,
            python_executable=python_executable,
            legacy_cli_path=cli_path,
        ),
        "",
    )


def _run_probe(
    command: list[str],
    *,
    workspace: Path,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded Manager health probe with its required environment."""

    command_env = dict(os.environ if env is None else env)
    command_env["COMFYUI_PATH"] = str(workspace)
    command_env.setdefault("PYTHONUTF8", "1")
    command_env.setdefault("PYTHONIOENCODING", "utf-8:replace")
    return subprocess.run(
        command,
        cwd=str(workspace),
        env=command_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )


def _install_requirements(
    *,
    workspace: Path,
    python_executable: Path,
    requirements_path: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> None:
    """Install one authoritative Manager requirements file and expose failures."""

    result = subprocess.run(
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
        timeout=1_800,
        check=False,
    )
    _log_command_output(result, on_log)
    if result.returncode != 0:
        raise RuntimeError(
            "Substitute could not install ComfyUI Manager requirements. "
            + _command_output(result)
        )


def _validation_failure_message(kind: str, detail: str) -> str:
    """Build an actionable Manager validation failure message."""

    excerpt = detail.strip() or "The validation command returned no diagnostic output."
    return f"ComfyUI Manager {kind} validation failed. {excerpt}"


def _command_output(result: subprocess.CompletedProcess[str]) -> str:
    """Return a bounded combined stdout/stderr diagnostic excerpt."""

    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    return " ".join(lines[-20:])[-4_000:]


def _log_command_output(
    result: subprocess.CompletedProcess[str], callback: LogCallback | None
) -> None:
    """Emit non-empty stdout and stderr from one package installation."""

    for line in _command_output(result).splitlines():
        _emit_log(callback, line)


def _remove_path(path: Path) -> None:
    """Remove one app-owned legacy Manager path after integrated validation."""

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one Manager provisioning line to structured and setup logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "DEFAULT_MANAGER_REPOSITORY_URL",
    "detect_workspace_manager_runtime",
    "ensure_attached_workspace_manager",
    "ensure_managed_workspace_manager",
    "workspace_manager_cli_path",
    "workspace_manager_directory",
    "workspace_manager_requirements_path",
    "workspace_supports_integrated_manager",
]
