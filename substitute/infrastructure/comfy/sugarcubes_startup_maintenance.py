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

"""Adapt strict SugarCubes maintenance into degradative startup preparation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log,
)
from substitute.infrastructure.comfy.sugarcubes_maintenance_runner import (
    run_sugarcubes_baseline_maintenance,
)
from substitute.infrastructure.version_control import RepositoryService
from substitute.shared.logging.logger import get_logger, log_warning_exception

_LOGGER = get_logger(__name__)


def attempt_sugarcubes_startup_maintenance(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
    repositories: RepositoryService | None = None,
) -> SugarCubesMaintenanceResult | None:
    """Prepare SugarCubes when possible without making startup depend on it."""

    try:
        return run_sugarcubes_baseline_maintenance(
            workspace,
            on_log=on_log,
            env=env,
            python_executable=python_executable,
            repositories=repositories,
        )
    except Exception as error:  # noqa: BLE001 - startup must survive this optional phase.
        log_warning_exception(
            _LOGGER,
            "SugarCubes startup maintenance degraded without blocking launch",
            error=error,
            workspace=workspace,
        )
        detail = " ".join(str(error).split()) or type(error).__name__
        emit_log(
            on_log,
            "ERROR: SugarCubes[sugarcubes_maintenance_failed]: "
            f"SugarCubes startup maintenance failed: {detail} "
            "ComfyUI will continue starting.",
            operation="sugarcubes_startup_maintenance",
            outcome="degraded",
        )
        return None


__all__ = ["attempt_sugarcubes_startup_maintenance"]
