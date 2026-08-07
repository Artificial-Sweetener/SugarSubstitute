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

"""Install only the declared Python dependencies of trusted nodepacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import tomllib

from substitute.infrastructure.comfy.nodepack_manifest import (
    CLI_INSTALL_TIMEOUT_SECONDS,
)
from substitute.infrastructure.process.hidden_process_runner import (
    run_command,
    stream_command_collecting_output,
)
from substitute.infrastructure.process.pip_failure import (
    raise_pip_path_compatibility_error,
)
from substitute.shared.logging.logger import get_logger, log_info
from sugarsubstitute_shared.windows_long_paths import subprocess_path

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.nodepack_python_dependencies")


def install_nodepack_python_dependencies(
    *,
    python_executable: Path,
    nodepack_root: Path,
    display_name: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install `[project].dependencies` without installing the nodepack itself."""

    dependencies = read_nodepack_python_dependencies(nodepack_root / "pyproject.toml")
    if not dependencies:
        return
    _emit_log(
        on_log,
        f"[ComfyNodepacks] Installing {display_name} Python dependencies.",
    )
    command = [
        subprocess_path(python_executable),
        "-m",
        "pip",
        "install",
        *dependencies,
    ]
    exit_code, output_lines = stream_command_collecting_output(
        command,
        cwd=nodepack_root,
        on_line=on_log,
        timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
        env=env,
    )
    if exit_code == 0:
        return
    raise_pip_path_compatibility_error(
        fallback_path=nodepack_root,
        output="\n".join(output_lines),
    )
    raise RuntimeError(f"Could not install {display_name} Python dependencies.")


def install_nodepack_requirements(
    *,
    python_executable: Path,
    nodepack_root: Path,
    display_name: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install a trusted companion nodepack's conventional requirements file."""

    requirements_path = nodepack_root / "requirements.txt"
    if not requirements_path.is_file():
        return
    _emit_log(
        on_log,
        f"[ComfyNodepacks] Installing {display_name} Python dependencies.",
    )
    exit_code, output_lines = stream_command_collecting_output(
        [
            subprocess_path(python_executable),
            "-m",
            "pip",
            "install",
            "-r",
            subprocess_path(requirements_path),
        ],
        cwd=nodepack_root,
        on_line=on_log,
        timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
        env=env,
    )
    if exit_code == 0:
        return
    raise_pip_path_compatibility_error(
        fallback_path=nodepack_root,
        output="\n".join(output_lines),
    )
    raise RuntimeError(f"Could not install {display_name} Python dependencies.")


def read_nodepack_python_dependencies(pyproject_path: Path) -> tuple[str, ...]:
    """Return validated dependency strings from one nodepack project manifest."""

    try:
        with pyproject_path.open("rb") as pyproject_file:
            payload = tomllib.load(pyproject_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(
            f"Could not read nodepack dependency manifest: {pyproject_path}"
        ) from error
    project = payload.get("project")
    if not isinstance(project, dict):
        raise RuntimeError(f"Nodepack manifest has no project table: {pyproject_path}")
    raw_dependencies = project.get("dependencies", [])
    if not isinstance(raw_dependencies, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_dependencies
    ):
        raise RuntimeError(
            f"Nodepack manifest has invalid project dependencies: {pyproject_path}"
        )
    return tuple(item.strip() for item in raw_dependencies)


def nodepack_python_dependencies_satisfied(
    *,
    python_executable: Path,
    nodepack_root: Path,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether Comfy Python satisfies every declared project dependency."""

    dependencies = read_nodepack_python_dependencies(nodepack_root / "pyproject.toml")
    script = (
        "from importlib.metadata import PackageNotFoundError, version\n"
        "from packaging.requirements import Requirement\n"
        f"requirements = {dependencies!r}\n"
        "for raw in requirements:\n"
        "    requirement = Requirement(raw)\n"
        "    if requirement.marker and not requirement.marker.evaluate():\n"
        "        continue\n"
        "    try:\n"
        "        installed = version(requirement.name)\n"
        "    except PackageNotFoundError:\n"
        "        raise SystemExit(2)\n"
        "    if requirement.specifier and installed not in requirement.specifier:\n"
        "        raise SystemExit(2)\n"
    )
    result = run_command(
        [subprocess_path(python_executable), "-c", script],
        cwd=nodepack_root,
        check=False,
        env=env,
    )
    return result.returncode == 0


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit dependency activity to structured and setup logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "install_nodepack_python_dependencies",
    "install_nodepack_requirements",
    "nodepack_python_dependencies_satisfied",
    "read_nodepack_python_dependencies",
]
