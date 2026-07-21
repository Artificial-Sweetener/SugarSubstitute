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

"""Install trusted custom nodes reported by SugarCubes dependency readiness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    current_dependency_readiness,
    mapping_items,
    repair_result_node_ids,
    string_sequence,
    string_value,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SUGARCUBES_COMPANION_NODEPACKS,
)
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_requirements,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log,
)
from substitute.infrastructure.comfy.trusted_nodepack_installer import (
    install_trusted_nodepack_repository,
)
from substitute.infrastructure.version_control import RepositoryService


def install_sugarcubes_reported_nodepacks(
    workspace: Path,
    result: SugarCubesMaintenanceResult,
    *,
    python_executable: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None,
) -> bool:
    """Install known Base-Cubes nodepacks from the readiness plan."""

    node_ids = sugarcubes_installable_missing_node_ids(result.payload)
    requested_node_ids = _node_ids_with_companions(node_ids)
    known_node_ids = tuple(
        node_id
        for node_id in requested_node_ids
        if node_id in SUGARCUBES_BASE_NODEPACK_INSTALLS
    )
    if not known_node_ids:
        return False
    unknown_node_ids = tuple(
        node_id for node_id in requested_node_ids if node_id not in known_node_ids
    )
    if unknown_node_ids:
        raise RuntimeError(
            "SugarCubes reported required Base-Cubes nodepacks without an installer "
            f"mapping: {', '.join(unknown_node_ids)}."
        )
    emit_log(
        on_log,
        (
            "[SugarCubes] Installing required trusted Base-Cubes nodepacks: "
            f"{', '.join(known_node_ids)}."
        ),
        operation="sugarcubes_nodepack_install",
    )
    for node_id in known_node_ids:
        _install_nodepack_candidate(
            workspace,
            node_id,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
            repositories=repositories,
        )
    return True


def sugarcubes_installable_missing_node_ids(
    payload: Mapping[str, object],
) -> tuple[str, ...]:
    """Return installable node IDs SugarCubes still reports as missing."""

    readiness = current_dependency_readiness(payload)
    if readiness is None:
        return ()
    missing = set(string_sequence(readiness.get("missingCustomNodes")))
    node_ids: list[str] = []
    for item in mapping_items(readiness.get("installPlan")):
        node_id = string_value(item.get("nodeId"))
        if not node_id:
            continue
        if item.get("installed") is True:
            continue
        if item.get("installable") is False:
            continue
        if missing and node_id not in missing:
            continue
        node_ids.append(node_id)
    if node_ids:
        return tuple(dict.fromkeys(node_ids))
    return tuple(
        node_id
        for node_id in repair_result_node_ids(payload, "failedNodes")
        if not missing or node_id in missing
    )


def _node_ids_with_companions(node_ids: Sequence[str]) -> tuple[str, ...]:
    """Return SugarCubes node IDs plus required companion nodepacks."""

    expanded: list[str] = []
    for node_id in node_ids:
        expanded.append(node_id)
        expanded.extend(SUGARCUBES_COMPANION_NODEPACKS.get(node_id, ()))
    return tuple(dict.fromkeys(expanded))


def _install_nodepack_candidate(
    workspace: Path,
    node_id: str,
    *,
    python_executable: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None,
) -> None:
    """Install one SugarCubes nodepack from its trusted repository."""

    failures: list[str] = []
    for candidate in SUGARCUBES_BASE_NODEPACK_INSTALLS[node_id]:
        try:
            target_path = workspace / "custom_nodes" / candidate.target_folder_name
            install_trusted_nodepack_repository(
                repository_url=candidate.source_url,
                target_path=target_path,
                display_name=node_id,
                on_log=on_log,
                repositories=repositories,
            )
            install_nodepack_requirements(
                python_executable=python_executable,
                nodepack_root=target_path,
                display_name=node_id,
                on_log=on_log,
                env=env,
            )
            return
        except RuntimeError as exc:
            failures.append(str(exc))
    details = " ".join(failures[-2:])
    raise RuntimeError(
        f"Substitute could not install SugarCubes nodepack '{node_id}'. {details}"
    )
