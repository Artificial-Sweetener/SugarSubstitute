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

"""Prepare real historical installations and verify state survives updates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.onboarding.file_comfy_target_repository import (
    FileComfyTargetConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_installation_repository import (
    FileInstallationConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_runtime_repository import (
    FileRuntimeConfigurationRepository,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def prepare_portable_historical_install(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str,
    historical_version: str,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    timeout_seconds: float,
) -> None:
    """Complete the native historical installer contract on Linux and macOS."""

    command = [
        str(installer_path.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
        f"--manifest-url={manifest_url}",
    ]
    result = subprocess.run(
        command,
        cwd=installer_path.resolve().parent,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Historical installer exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    materialize_historical_managed_configuration(
        install_root=install_root,
        endpoint_port=endpoint_port,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
    )
    print(
        f"HISTORICAL_INSTALLER_COMPLETED version={historical_version}",
        flush=True,
    )


def materialize_historical_managed_configuration(
    *,
    install_root: Path,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
) -> None:
    """Prepare a real managed target representing an established user install."""

    installation = InstallationConfiguration.create_default(install_root)
    for required_path in (
        installation.user_settings_dir,
        installation.projects_dir,
        installation.outputs_dir,
        installation.wildcards_dir,
        installation.runtime_state_dir,
        managed_model_root,
    ):
        required_path.mkdir(parents=True, exist_ok=True)
    FileInstallationConfigurationRepository(install_root).save(installation)
    layout = InstallLayout.from_root(install_root)
    FileRuntimeConfigurationRepository(installation).save(
        RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=layout.runtime_python,
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
    )
    FileComfyTargetConfigurationRepository(installation).save(
        ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=endpoint_port),
            workspace_path=managed_workspace,
            install_owned=True,
            launch_owned=True,
        )
    )
    ensure_managed_comfy_setup(
        workspace=managed_workspace,
        managed_model_root=managed_model_root,
        configure_model_root=True,
        force_cpu_mode=True,
    )


def seed_historical_user_configuration(
    *,
    install_root: Path,
    historical_version: str,
    managed_workspace: Path,
    managed_model_root: Path,
) -> Path:
    """Add authoritative user state whose exact survival is required after update."""

    marker = install_root / "user" / "settings" / "qualification-preservation.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "historical_version": historical_version,
                "managed_workspace": str(managed_workspace.resolve()),
                "managed_model_root": str(managed_model_root.resolve()),
                "user_value": "preserve-exactly",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return marker


def assert_historical_user_configuration_preserved(
    *,
    preservation_marker: Path,
    historical_version: str,
    managed_workspace: Path,
    managed_model_root: Path,
) -> None:
    """Require update activation to retain user state and selected target paths."""

    expected = {
        "historical_version": historical_version,
        "managed_workspace": str(managed_workspace.resolve()),
        "managed_model_root": str(managed_model_root.resolve()),
        "user_value": "preserve-exactly",
    }
    if _read_json(preservation_marker) != expected:
        raise InstallerLifecycleError(
            "Candidate update changed authoritative historical user configuration."
        )
    target = _read_json(preservation_marker.parent / "comfy_target.json")
    if target.get("mode") != "managed_local":
        raise InstallerLifecycleError(
            "Candidate update changed the historical target mode."
        )
    if target.get("workspace_path") != str(managed_workspace.resolve()):
        raise InstallerLifecycleError(
            "Candidate update changed the historical managed workspace."
        )


def _read_json(path: Path) -> dict[str, object]:
    """Load one required authoritative-state JSON object."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            f"Historical user configuration is invalid: {path}."
        ) from error
    if not isinstance(payload, dict):
        raise InstallerLifecycleError(
            f"Historical user configuration is not an object: {path}."
        )
    return payload


__all__ = [
    "assert_historical_user_configuration_preserved",
    "materialize_historical_managed_configuration",
    "prepare_portable_historical_install",
    "seed_historical_user_configuration",
]
