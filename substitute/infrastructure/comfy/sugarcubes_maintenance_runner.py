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

from collections.abc import Mapping
from pathlib import Path

from substitute.application.comfy_nodepacks.sugarcubes_dependency_repair_plan import (
    dependency_repair_node_ids,
)
from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    current_dependency_readiness,
    sugarcubes_maintenance_result as _sugarcubes_maintenance_result,
    sugarcubes_required_dependency_failure_message as _sugarcubes_required_dependency_failure_message,
)
from substitute.infrastructure.comfy.sugarcubes_installation_contract import (
    build_sugarcubes_dependency_repair_command,
    build_sugarcubes_maintenance_command,
    sugarcubes_maintenance_path,
    sugarcubes_root,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log as _emit_log,
    emit_sugarcubes_diagnostics as _emit_sugarcubes_diagnostics,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.infrastructure.comfy.sugarcubes_repository_bootstrapper import (
    prepare_sugarcubes_repositories,
)
from substitute.infrastructure.version_control import RepositoryService
from substitute.infrastructure.process.hidden_process_runner import (
    stream_command_collecting_output as _stream_command_collecting_output,
)


def run_sugarcubes_baseline_maintenance(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
    repositories: RepositoryService | None = None,
) -> SugarCubesMaintenanceResult:
    """Preflight SugarCubes dependencies and repair only reported deficiencies."""

    if python_executable is None:
        python_executable = resolve_workspace_python(workspace)
    installed_sugarcubes_root = sugarcubes_root(workspace)
    if not sugarcubes_maintenance_path(workspace).exists():
        raise RuntimeError("SugarCubes offline maintenance entrypoint is missing.")
    prepare_sugarcubes_repositories(
        installed_sugarcubes_root,
        on_log=on_log,
        repositories=repositories,
    )
    command = list(
        build_sugarcubes_maintenance_command(
            python_executable=python_executable,
            workspace=workspace,
            baseline_only=False,
        )
    )
    exit_code, output_lines = _stream_command_collecting_output(
        command,
        cwd=installed_sugarcubes_root,
        on_line=None,
        env=env,
    )
    result = _sugarcubes_maintenance_result(exit_code, output_lines)
    _emit_sugarcubes_diagnostics(result, on_log=on_log)
    if result.exit_code == 0:
        if not result.diagnostics:
            _emit_log(
                on_log,
                "[SugarCubes] Cube-required node packs are ready.",
                operation="sugarcubes_maintenance",
            )
        return result
    if result.exit_code == 2:
        if _uses_preserved_local_base_cubes(result):
            return result
        node_ids = dependency_repair_node_ids(result.payload)
        if not node_ids:
            raise RuntimeError(_sugarcubes_required_dependency_failure_message(result))
        _emit_log(
            on_log,
            (
                "[SugarCubes] Reconciling cube-required node packs: "
                f"{', '.join(node_ids)}."
            ),
            operation="sugarcubes_dependency_repair",
        )
        repair_result = _run_sugarcubes_command(
            list(
                build_sugarcubes_dependency_repair_command(
                    python_executable=python_executable,
                    workspace=workspace,
                    approved_node_ids=node_ids,
                )
            ),
            sugarcubes_root=installed_sugarcubes_root,
            on_log=on_log,
            env=env,
        )
        if repair_result.exit_code not in {0, 2}:
            raise RuntimeError(
                _sugarcubes_required_dependency_failure_message(repair_result)
            )
        verification_result = _run_sugarcubes_command(
            command,
            sugarcubes_root=installed_sugarcubes_root,
            on_log=on_log,
            env=env,
        )
        if verification_result.exit_code != 0:
            raise RuntimeError(
                _sugarcubes_required_dependency_failure_message(verification_result)
            )
        if not verification_result.diagnostics:
            _emit_log(
                on_log,
                "[SugarCubes] Cube-required node packs are ready.",
                operation="sugarcubes_maintenance",
            )
        return verification_result
    _emit_log(
        on_log,
        "[SugarCubes] Dependency maintenance failed.",
        operation="sugarcubes_maintenance",
    )
    raise RuntimeError(_sugarcubes_required_dependency_failure_message(result))


def _run_sugarcubes_command(
    command: list[str],
    *,
    sugarcubes_root: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> SugarCubesMaintenanceResult:
    """Run and parse one SugarCubes maintenance command."""

    exit_code, output_lines = _stream_command_collecting_output(
        command,
        cwd=sugarcubes_root,
        on_line=None,
        env=env,
    )
    result = _sugarcubes_maintenance_result(exit_code, output_lines)
    _emit_sugarcubes_diagnostics(result, on_log=on_log)
    return result


def _uses_preserved_local_base_cubes(result: SugarCubesMaintenanceResult) -> bool:
    """Accept the explicit recoverable diagnostic for an existing local checkout."""

    readiness = current_dependency_readiness(result.payload)
    return (
        readiness is None
        and bool(result.diagnostics)
        and all(
            diagnostic.code == "base_cubes_sync_failed"
            and diagnostic.severity in {"info", "warning"}
            for diagnostic in result.diagnostics
        )
    )


__all__ = [
    "run_sugarcubes_baseline_maintenance",
]
