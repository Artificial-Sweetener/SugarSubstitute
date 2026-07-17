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

"""Install and inspect Python distributions for Comfy nodepacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import shutil

from substitute.infrastructure.comfy.nodepack_manifest import (
    CLI_INSTALL_TIMEOUT_SECONDS,
    CoreComfyNodepack,
)
from substitute.infrastructure.process.hidden_process_runner import (
    run_command,
    stream_command,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger(__name__)


def install_backend_python_dependencies(
    *,
    python_executable: Path,
    nodepack_root: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install BackEnd runtime dependencies from the custom node folder."""

    install_nodepack_python_project(
        python_executable=python_executable,
        nodepack_root=nodepack_root,
        display_name="Substitute BackEnd",
        on_log=on_log,
        env=env,
    )


def install_sugarcubes_python_dependencies(
    *,
    python_executable: Path,
    nodepack_root: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install SugarCubes runtime dependencies from the custom node folder."""

    install_nodepack_python_project(
        python_executable=python_executable,
        nodepack_root=nodepack_root,
        display_name="SugarCubes",
        on_log=on_log,
        env=env,
    )


def install_nodepack_python_project(
    *,
    python_executable: Path,
    nodepack_root: Path,
    display_name: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install one pyproject-backed nodepack into the workspace runtime."""

    _emit_log(
        on_log,
        f"[ComfyNodepacks] Updating {display_name} Python dependencies.",
    )
    command = [str(python_executable), "-m", "pip", "install", str(nodepack_root)]
    exit_code = stream_command(
        command,
        cwd=nodepack_root,
        on_line=on_log,
        timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
        env=env,
    )
    if exit_code != 0:
        raise RuntimeError(f"Could not update {display_name} Python dependencies.")


def install_nodepack_requirements(
    *,
    python_executable: Path,
    nodepack_root: Path,
    display_name: str,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install a trusted nodepack's conventional requirements file when present."""

    requirements_path = nodepack_root / "requirements.txt"
    if not requirements_path.is_file():
        return
    _emit_log(on_log, f"[ComfyNodepacks] Installing {display_name} dependencies.")
    exit_code = stream_command(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
        ],
        cwd=nodepack_root,
        on_line=on_log,
        timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
        env=env,
    )
    if exit_code != 0:
        raise RuntimeError(f"Could not install {display_name} dependencies.")


def nodepack_python_distributions_satisfy_minimum(
    *,
    python_executable: Path,
    cwd: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether the canonical Python distribution satisfies the nodepack contract."""

    return python_distribution_satisfies_minimum(
        python_executable=python_executable,
        cwd=cwd,
        distribution_name=nodepack.python_distribution_name,
        minimum_version=nodepack.minimum_python_distribution_version,
        on_log=on_log,
        env=env,
    )


def remove_noncanonical_python_distribution_metadata(
    *,
    nodepack_root: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
) -> None:
    """Remove local egg-info metadata that does not match the canonical package name."""

    if nodepack.python_distribution_name is None:
        return
    canonical_name = normalized_distribution_name(nodepack.python_distribution_name)
    for metadata_dir in nodepack_root.glob("*.egg-info"):
        metadata_name = egg_info_distribution_name(metadata_dir)
        if metadata_name is None:
            continue
        if normalized_distribution_name(metadata_name) == canonical_name:
            continue
        shutil.rmtree(metadata_dir, onexc=_clear_readonly_and_retry)
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Removed non-canonical {metadata_name} "
                f"metadata from {metadata_dir}."
            ),
        )


def egg_info_distribution_name(metadata_dir: Path) -> str | None:
    """Return the distribution name recorded by one local egg-info directory."""

    package_info_path = metadata_dir / "PKG-INFO"
    if not package_info_path.exists():
        return None
    for line in package_info_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        if line.lower().startswith("name:"):
            return line.partition(":")[2].strip()
    return None


def normalized_distribution_name(distribution_name: str) -> str:
    """Return the package-name normalization used by Python metadata."""

    return distribution_name.replace("_", "-").lower()


def python_distribution_satisfies_minimum(
    *,
    python_executable: Path,
    cwd: Path,
    distribution_name: str | None,
    minimum_version: str | None,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether the workspace Python sees the required distribution version."""

    if distribution_name is None or minimum_version is None:
        return True
    installed_version = installed_python_distribution_version(
        python_executable=python_executable,
        cwd=cwd,
        distribution_name=distribution_name,
        on_log=on_log,
        env=env,
    )
    if installed_version is None:
        return False
    return version_at_least(installed_version, minimum_version)


def installed_python_distribution_version(
    *,
    python_executable: Path,
    cwd: Path,
    distribution_name: str,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> str | None:
    """Read one installed Python distribution version from the workspace runtime."""

    script = (
        "from importlib import metadata\n"
        f"print(metadata.version({distribution_name!r}))\n"
    )
    result = run_command(
        [str(python_executable), "-c", script],
        cwd=cwd,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Could not read installed {distribution_name} "
                "version from Comfy Python."
            ),
        )
        return None
    return result.stdout.strip()


def version_at_least(installed_version: str, minimum_version: str) -> bool:
    """Return whether a simple semver-ish version is at least the minimum."""

    return version_key(installed_version) >= version_key(minimum_version)


def version_key(version: str) -> tuple[int, int, int, str]:
    """Return a comparable key for release and prerelease version strings."""

    release, _, suffix = version.partition("-")
    parts = release.split(".")
    numeric_parts: list[int] = []
    for part in parts[:3]:
        try:
            numeric_parts.append(int(part))
        except ValueError:
            numeric_parts.append(0)
    while len(numeric_parts) < 3:
        numeric_parts.append(0)
    return numeric_parts[0], numeric_parts[1], numeric_parts[2], suffix


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one nodepack dependency line to logs and optional setup output."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def _clear_readonly_and_retry(
    function: Callable[[str], object],
    path: str,
    excinfo: BaseException,
) -> None:
    """Clear a readonly bit and retry rmtree cleanup on Windows."""

    _ = excinfo
    os.chmod(path, 0o700)
    function(path)


__all__ = [
    "LogCallback",
    "egg_info_distribution_name",
    "install_backend_python_dependencies",
    "install_nodepack_python_project",
    "install_nodepack_requirements",
    "install_sugarcubes_python_dependencies",
    "installed_python_distribution_version",
    "nodepack_python_distributions_satisfy_minimum",
    "normalized_distribution_name",
    "python_distribution_satisfies_minimum",
    "remove_noncanonical_python_distribution_metadata",
    "version_at_least",
    "version_key",
]
