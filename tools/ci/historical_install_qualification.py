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
import time

from tools.ci.historical_managed_configuration import (
    materialize_historical_managed_configuration,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.owned_process_runner import run_owned_process


def prepare_portable_historical_install(
    *,
    repository_root: Path,
    installer_path: Path,
    install_root: Path,
    manifest_url: str,
    historical_version: str,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    source_repository: Path,
    timeout_seconds: float,
    environment: dict[str, str] | None = None,
) -> None:
    """Complete the native historical installer contract without launching it."""

    deadline = time.monotonic() + timeout_seconds
    command = [
        str(installer_path.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
        f"--manifest-url={manifest_url}",
    ]
    result = run_owned_process(
        command,
        cwd=installer_path.resolve().parent,
        environment=dict(os.environ if environment is None else environment),
        timeout_seconds=_remaining_timeout(deadline, phase="historical installer"),
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Historical installer exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    materialize_historical_managed_configuration(
        repository_root=repository_root,
        install_root=install_root,
        endpoint_port=endpoint_port,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
        source_repository=source_repository,
        timeout_seconds=_remaining_timeout(
            deadline,
            phase="historical managed configuration",
        ),
    )
    print(
        f"HISTORICAL_INSTALLER_COMPLETED version={historical_version}",
        flush=True,
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


def _remaining_timeout(deadline: float, *, phase: str) -> float:
    """Return the positive budget remaining for one historical install phase."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InstallerLifecycleError(
            f"Historical installation exhausted its timeout before {phase}."
        )
    return remaining


__all__ = [
    "assert_historical_user_configuration_preserved",
    "prepare_portable_historical_install",
    "seed_historical_user_configuration",
]
