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

"""Run managed-Comfy subprocess and dependency provisioning operations."""

from __future__ import annotations

from collections.abc import Mapping
import subprocess
import sys
from pathlib import Path
from typing import Callable

from substitute.infrastructure.comfy.managed_install_failures import (
    ManagedInstallStorageError,
    is_storage_exhaustion_message,
    raise_forced_managed_failure,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_python_path,
    workspace_venv_dir,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.managed_install_commands")


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    text: bool = True,
    input_data: str | None = None,
    creationflags: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Run a command and raise when non-zero exit codes are not allowed."""

    log_info(_LOGGER, "Executing command", cmd=cmd, cwd=cwd)
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=text,
        input=input_data,
        stdout=None,
        stderr=None,
        creationflags=creationflags,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(cmd)}"
        )
    return result


def stream_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    on_line: LogCallback | None = None,
    creationflags: int = 0,
) -> int:
    """Run a command and stream merged stdout and stderr line by line."""

    log_info(_LOGGER, "Streaming command", cmd=cmd, cwd=cwd)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        universal_newlines=True,
        creationflags=creationflags,
    )
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                log_debug(_LOGGER, stripped)
                if on_line is not None:
                    on_line(stripped)
        proc.wait()
        return proc.returncode
    finally:
        if proc.stdout is not None:
            proc.stdout.close()


def pip_install(
    python_executable: Path,
    *packages: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install packages into the given Python environment."""

    command = [str(python_executable), "-m", "pip", "install", *packages]
    if on_log is not None:
        output_lines: list[str] = []

        def _record_output(line: str) -> None:
            """Retain streamed pip output while forwarding it to the UI."""

            output_lines.append(line)
            on_log(line)

        exit_code = stream_command(command, on_line=_record_output, env=env)
        if exit_code != 0:
            output = "\n".join(output_lines)
            if is_storage_exhaustion_message(output):
                raise ManagedInstallStorageError(
                    "Managed ComfyUI setup ran out of temporary install space "
                    f"while running pip in {python_executable.parent.parent}: "
                    f"{' '.join(packages)}"
                )
            raise RuntimeError(
                f"Package installation failed in {python_executable.parent.parent}: "
                f"{' '.join(packages)}"
            )
        return
    result = subprocess.run(  # noqa: S603
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        shell=False,
        env=env,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if result.returncode != 0:
        output = result.stdout or ""
        if is_storage_exhaustion_message(output):
            raise ManagedInstallStorageError(
                "Managed ComfyUI setup ran out of temporary install space "
                f"while running pip in {python_executable.parent.parent}: "
                f"{' '.join(packages)}"
            )
        raise RuntimeError(
            f"Package installation failed in {python_executable.parent.parent}: "
            f"{' '.join(packages)}"
        )


def pip_uninstall(
    python_executable: Path,
    *packages: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Uninstall conflicting packages from the given Python environment."""

    if not packages:
        return
    command = [
        str(python_executable),
        "-m",
        "pip",
        "uninstall",
        "--yes",
        *packages,
    ]
    output_lines: list[str] = []

    def _record_output(line: str) -> None:
        """Retain pip diagnostics while forwarding optional setup output."""

        output_lines.append(line)
        if on_log is not None:
            on_log(line)

    exit_code = stream_command(command, on_line=_record_output, env=env)
    if exit_code != 0:
        output = "\n".join(output_lines)
        if is_storage_exhaustion_message(output):
            raise ManagedInstallStorageError(
                "Managed ComfyUI setup ran out of temporary install space while "
                f"removing packages in {python_executable.parent.parent}: "
                f"{' '.join(packages)}"
            )
        raise RuntimeError(
            f"Package removal failed in {python_executable.parent.parent}: "
            f"{' '.join(packages)}"
        )


def ensure_workspace_virtualenv(
    workspace: Path,
    *,
    python_runtime: str | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Create the managed workspace virtualenv and return its Python path."""

    venv_python = workspace_python_path(workspace)
    if venv_python.exists():
        return venv_python
    interpreter = python_runtime or sys.executable
    exit_code = stream_command(
        [interpreter, "-m", "venv", str(workspace_venv_dir(workspace))],
        on_line=on_log,
        env=env,
    )
    if exit_code != 0 or not venv_python.exists():
        raise RuntimeError(
            "Substitute couldn't create the Python environment for this ComfyUI setup."
        )
    return venv_python


def upgrade_workspace_packaging_tools(
    python_executable: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Upgrade pip, setuptools, and wheel inside the workspace venv."""

    pip_install(
        python_executable,
        "--upgrade",
        "pip",
        "setuptools",
        "wheel",
        on_log=on_log,
        env=env,
    )


def install_workspace_comfy_cli(
    python_executable: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install comfy-cli into the managed workspace venv."""

    pip_install(python_executable, "comfy-cli", on_log=on_log, env=env)


def run_workspace_comfy_cli(
    python_executable: Path,
    *args: str,
    on_line: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run comfy-cli through the managed workspace interpreter."""

    return stream_command(
        [str(python_executable), "-m", "comfy_cli", *args],
        on_line=on_line,
        env=env,
    )


def install_selected_torch_backend(
    python_executable: Path,
    *,
    install_arguments: tuple[str, ...],
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install the explicitly selected torch backend into the workspace venv."""

    raise_forced_managed_failure("dependency_install")
    pip_install(
        python_executable,
        "--upgrade",
        "--force-reinstall",
        *install_arguments,
        on_log=on_log,
        env=env,
    )


def install_workspace_requirements(
    python_executable: Path,
    *,
    workspace: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install ComfyUI core requirements into the managed workspace venv."""

    raise_forced_managed_failure("dependency_install")
    pip_install(
        python_executable,
        "-r",
        str(workspace / "requirements.txt"),
        on_log=on_log,
        env=env,
    )


def install_manager_requirements(
    python_executable: Path,
    *,
    workspace: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install manager requirements when the managed workspace ships them."""

    requirements_path = workspace / "manager_requirements.txt"
    if not requirements_path.exists():
        return
    raise_forced_managed_failure("dependency_install")
    pip_install(
        python_executable,
        "-r",
        str(requirements_path),
        on_log=on_log,
        env=env,
    )
