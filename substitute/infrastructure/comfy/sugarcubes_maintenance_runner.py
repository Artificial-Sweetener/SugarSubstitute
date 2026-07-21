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

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    sugarcubes_maintenance_result as _sugarcubes_maintenance_result,
    sugarcubes_required_dependency_failure_message as _sugarcubes_required_dependency_failure_message,
)
from substitute.infrastructure.comfy.sugarcubes_dependency_installer import (
    install_sugarcubes_reported_nodepacks,
)
from substitute.infrastructure.comfy.sugarcubes_installation_contract import (
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
from substitute.infrastructure.comfy.sugarcubes_version_repair import (
    repair_sugarcubes_git_versions,
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
    """Read SugarCubes readiness and repair trusted dependencies with libgit2."""

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
            baseline_only=True,
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
        if repair_sugarcubes_git_versions(
            result.payload,
            workspace=workspace,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
            repositories=repositories,
        ):
            exit_code, output_lines = _stream_command_collecting_output(
                command,
                cwd=installed_sugarcubes_root,
                on_line=None,
                env=env,
            )
            result = _sugarcubes_maintenance_result(exit_code, output_lines)
            _emit_sugarcubes_diagnostics(result, on_log=on_log)
        if not result.diagnostics:
            _emit_log(
                on_log,
                "[SugarCubes] Base-Cubes sync and dependencies are ready.",
                operation="sugarcubes_maintenance",
            )
        return result
    if result.exit_code == 2:
        if install_sugarcubes_reported_nodepacks(
            workspace,
            result,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
            repositories=repositories,
        ):
            exit_code, output_lines = _stream_command_collecting_output(
                command,
                cwd=installed_sugarcubes_root,
                on_line=None,
                env=env,
            )
            verification_result = _sugarcubes_maintenance_result(
                exit_code, output_lines
            )
            _emit_sugarcubes_diagnostics(verification_result, on_log=on_log)
            if repair_sugarcubes_git_versions(
                verification_result.payload,
                workspace=workspace,
                python_executable=python_executable,
                on_log=on_log,
                env=env,
                repositories=repositories,
            ):
                exit_code, output_lines = _stream_command_collecting_output(
                    command,
                    cwd=installed_sugarcubes_root,
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


__all__ = [
    "run_sugarcubes_baseline_maintenance",
]
