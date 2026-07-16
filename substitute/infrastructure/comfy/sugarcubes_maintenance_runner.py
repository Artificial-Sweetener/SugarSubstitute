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

"""Run SugarCubes baseline maintenance for managed Comfy workspaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    current_dependency_readiness as _current_dependency_readiness,
    mapping_items as _mapping_items,
    repair_result_node_ids as _repair_result_node_ids,
    string_sequence as _string_sequence,
    string_value as _string_value,
    sugarcubes_maintenance_result as _sugarcubes_maintenance_result,
    sugarcubes_required_dependency_failure_message as _sugarcubes_required_dependency_failure_message,
)
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.comfy_cli_adapter import ComfyManagerCliAdapter
from substitute.infrastructure.comfy.nodepack_manifest import (
    SUGARCUBES_BASE_NODEPACK_INSTALLS as _SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SUGARCUBES_COMPANION_NODEPACKS as _SUGARCUBES_COMPANION_NODEPACKS,
    SugarCubesNodepackInstallCandidate,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log as _emit_log,
    emit_sugarcubes_diagnostics as _emit_sugarcubes_diagnostics,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.infrastructure.process.hidden_process_runner import (
    stream_command_collecting_output as _stream_command_collecting_output,
)


def run_sugarcubes_baseline_maintenance(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
    manager_runtime: ComfyManagerRuntime | None = None,
) -> SugarCubesMaintenanceResult:
    """Run SugarCubes offline sync/check maintenance before Comfy starts."""

    if python_executable is None:
        python_executable = resolve_workspace_python(workspace)
    sugarcubes_root = workspace / "custom_nodes" / "SugarCubes"
    if not (sugarcubes_root / "backend" / "maintenance.py").exists():
        raise RuntimeError("SugarCubes offline maintenance entrypoint is missing.")
    command = [
        str(python_executable),
        "-m",
        "backend.maintenance",
        "cube-deps",
        "sync-and-check",
        "--workspace",
        str(workspace),
        "--baseline-only",
        "--sync-enabled-repos",
    ]
    exit_code, output_lines = _stream_command_collecting_output(
        command,
        cwd=sugarcubes_root,
        on_line=None,
        env=env,
    )
    result = _sugarcubes_maintenance_result(exit_code, output_lines)
    _emit_sugarcubes_diagnostics(result, on_log=on_log)
    if result.exit_code == 0:
        if not result.diagnostics:
            _emit_log(
                on_log,
                "[SugarCubes] Base-Cubes sync and dependencies are ready.",
                operation="sugarcubes_maintenance",
            )
        return result
    if result.exit_code == 2:
        if _install_sugarcubes_reported_nodepacks(
            workspace,
            result,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
            manager_runtime=manager_runtime,
        ):
            exit_code, output_lines = _stream_command_collecting_output(
                command,
                cwd=sugarcubes_root,
                on_line=None,
                env=env,
            )
            verification_result = _sugarcubes_maintenance_result(
                exit_code, output_lines
            )
            _emit_sugarcubes_diagnostics(verification_result, on_log=on_log)
            if verification_result.exit_code == 0:
                if not verification_result.diagnostics:
                    _emit_log(
                        on_log,
                        "[SugarCubes] Base-Cubes sync and dependencies are ready.",
                        operation="sugarcubes_maintenance",
                    )
                return verification_result
            raise RuntimeError(
                _sugarcubes_required_dependency_failure_message(verification_result)
            )
        raise RuntimeError(_sugarcubes_required_dependency_failure_message(result))
    _emit_log(
        on_log,
        "[SugarCubes] Dependency maintenance failed.",
        operation="sugarcubes_maintenance",
    )
    raise RuntimeError(_sugarcubes_required_dependency_failure_message(result))


def _install_sugarcubes_reported_nodepacks(
    workspace: Path,
    result: SugarCubesMaintenanceResult,
    *,
    python_executable: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    manager_runtime: ComfyManagerRuntime | None,
) -> bool:
    """Install known Base-Cubes nodepacks from the SugarCubes readiness plan."""

    node_ids = _sugarcubes_installable_missing_node_ids(result.payload)
    requested_node_ids = _sugarcubes_node_ids_with_companions(node_ids)
    known_node_ids = tuple(
        node_id
        for node_id in requested_node_ids
        if node_id in _SUGARCUBES_BASE_NODEPACK_INSTALLS
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
    _emit_log(
        on_log,
        (
            "[SugarCubes] Installing required Base-Cubes nodepacks through Comfy "
            f"Manager: {', '.join(known_node_ids)}."
        ),
        operation="sugarcubes_nodepack_install",
    )
    adapter = ComfyManagerCliAdapter(
        workspace=workspace,
        python_executable=python_executable,
        on_log=on_log,
        env=env,
        manager_runtime=manager_runtime,
    )
    for node_id in known_node_ids:
        _install_sugarcubes_nodepack_candidate(adapter, workspace, node_id)
    adapter.restore_dependencies()
    adapter.clear_startup_actions()
    return True


def _sugarcubes_node_ids_with_companions(node_ids: Sequence[str]) -> tuple[str, ...]:
    """Return SugarCubes node IDs plus required companion nodepacks."""

    expanded: list[str] = []
    for node_id in node_ids:
        expanded.append(node_id)
        expanded.extend(_SUGARCUBES_COMPANION_NODEPACKS.get(node_id, ()))
    return tuple(dict.fromkeys(expanded))


def _install_sugarcubes_nodepack_candidate(
    adapter: ComfyManagerCliAdapter,
    workspace: Path,
    node_id: str,
) -> None:
    """Install one SugarCubes nodepack using its known Manager/source fallbacks."""

    failures: list[str] = []
    for candidate in _SUGARCUBES_BASE_NODEPACK_INSTALLS[node_id]:
        try:
            adapter.install_node(candidate.install_id)
            _normalize_sugarcubes_nodepack_folder(workspace, candidate)
            return
        except RuntimeError as exc:
            failures.append(str(exc))
    details = " ".join(failures[-2:])
    raise RuntimeError(
        f"Comfy Manager could not install SugarCubes nodepack '{node_id}'. {details}"
    )


def _normalize_sugarcubes_nodepack_folder(
    workspace: Path,
    candidate: SugarCubesNodepackInstallCandidate,
) -> None:
    """Rename known Manager clone folders to the names SugarCubes requires."""

    if not candidate.cloned_folder_name or not candidate.expected_folder_name:
        return
    custom_nodes_root = workspace / "custom_nodes"
    cloned_folder = custom_nodes_root / candidate.cloned_folder_name
    expected_folder = custom_nodes_root / candidate.expected_folder_name
    if expected_folder.exists() or not cloned_folder.exists():
        return
    cloned_folder.rename(expected_folder)


def _sugarcubes_installable_missing_node_ids(
    payload: Mapping[str, object],
) -> tuple[str, ...]:
    """Return installable node IDs SugarCubes still reports as missing."""

    readiness = _current_dependency_readiness(payload)
    if readiness is None:
        return ()
    missing = set(_string_sequence(readiness.get("missingCustomNodes")))
    node_ids: list[str] = []
    for item in _mapping_items(readiness.get("installPlan")):
        node_id = _string_value(item.get("nodeId"))
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
        for node_id in _repair_result_node_ids(payload, "failedNodes")
        if not missing or node_id in missing
    )


__all__ = [
    "run_sugarcubes_baseline_maintenance",
]
