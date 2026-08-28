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

"""Restore historical core-nodepack state for update qualification."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    read_nodepack_project_identity,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_python_dependencies,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    PinnedNodepackSourceInstaller,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError

_SUGARCUBES_VERSION_NAME = "SUGARCUBES_REQUIRED_VERSION"
_SUGARCUBES_RELEASE_ARCHIVE = (
    "https://github.com/Artificial-Sweetener/SugarCubes/archive/refs/tags/"
)


def restore_historical_sugarcubes(
    *,
    install_root: Path,
    workspace: Path,
    python_executable: Path,
    environment: Mapping[str, str],
) -> str:
    """Replace the candidate fixture with the historical app's SugarCubes pin."""

    historical_version = read_historical_sugarcubes_version(install_root)
    current_manifest = next(
        nodepack
        for nodepack in CORE_COMFY_NODEPACKS
        if nodepack.nodepack_id is CoreNodepackId.SUGARCUBES
    )
    historical_manifest = replace(
        current_manifest,
        required_version=historical_version,
        fallback_archive_url=(
            f"{_SUGARCUBES_RELEASE_ARCHIVE}v{historical_version}.zip"
        ),
    )
    target_path = workspace / historical_manifest.expected_folder
    PinnedNodepackSourceInstaller().install_fallback(
        target_path=target_path,
        nodepack=historical_manifest,
        on_log=None,
        env=environment,
    )
    install_nodepack_python_dependencies(
        python_executable=python_executable,
        nodepack_root=target_path,
        display_name=historical_manifest.display_name,
        on_log=None,
        env=environment,
    )
    _, installed_version, _ = read_nodepack_project_identity(
        target_path / "pyproject.toml"
    )
    if installed_version != historical_version:
        raise InstallerLifecycleError(
            "Historical SugarCubes fixture did not match the installed app's pin: "
            f"expected {historical_version}, got {installed_version}."
        )
    return historical_version


def read_historical_sugarcubes_version(install_root: Path) -> str:
    """Read the signed historical app payload's literal SugarCubes requirement."""

    contract_path = (
        install_root / "app" / "substitute" / "domain" / "comfy_nodepacks.py"
    )
    try:
        module = ast.parse(contract_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as error:
        raise InstallerLifecycleError(
            f"Historical nodepack contract is unreadable: {contract_path}."
        ) from error
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == _SUGARCUBES_VERSION_NAME
            for target in targets
        ):
            continue
        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            version = value.value.strip()
            if version:
                return version
        break
    raise InstallerLifecycleError(
        "Historical app payload does not declare a literal SugarCubes requirement."
    )


def historical_sugarcubes_freshness_key(
    freshness_key: Mapping[str, object],
    *,
    historical_version: str,
) -> dict[str, object]:
    """Return setup evidence that truthfully records the historical app pin."""

    historical_key = deepcopy(dict(freshness_key))
    raw_nodepacks = historical_key.get("core_nodepacks")
    if not isinstance(raw_nodepacks, list):
        raise InstallerLifecycleError(
            "Historical managed setup key has no core-nodepack records."
        )
    sugarcubes_records = [
        record
        for record in raw_nodepacks
        if isinstance(record, dict)
        and record.get("id") == CoreNodepackId.SUGARCUBES.value
    ]
    if len(sugarcubes_records) != 1:
        raise InstallerLifecycleError(
            "Historical managed setup key must contain one SugarCubes record."
        )
    sugarcubes_records[0]["required_version"] = historical_version
    sugarcubes_records[0]["fallback_archive"] = (
        f"{_SUGARCUBES_RELEASE_ARCHIVE}v{historical_version}.zip"
    )
    return historical_key


__all__ = [
    "historical_sugarcubes_freshness_key",
    "read_historical_sugarcubes_version",
    "restore_historical_sugarcubes",
]
