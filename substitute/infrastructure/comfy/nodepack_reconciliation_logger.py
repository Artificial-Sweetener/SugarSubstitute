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

"""Emit bounded Comfy nodepack reconciliation setup logs."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    diagnostic_detail_summary,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger(__name__)


def emit_sugarcubes_diagnostics(
    result: SugarCubesMaintenanceResult,
    *,
    on_log: LogCallback | None,
) -> None:
    """Emit parsed SugarCubes diagnostics as bounded startup log lines."""

    for diagnostic in result.diagnostics:
        if diagnostic.severity == "info":
            level = "INFO"
        elif diagnostic.severity == "warning":
            level = "WARNING"
        else:
            level = "ERROR"
        detail_summary = diagnostic_detail_summary(diagnostic.details)
        suffix = f" ({detail_summary})" if detail_summary else ""
        message = (
            f"{level}: SugarCubes[{diagnostic.code}]: "
            f"{diagnostic.title}: {diagnostic.message}{suffix}"
        )
        emit_log(
            on_log,
            message,
            operation="sugarcubes_maintenance_diagnostic",
            diagnostic_code=diagnostic.code,
            diagnostic_severity=diagnostic.severity,
        )


def emit_log(
    callback: LogCallback | None,
    message: str,
    **context: object,
) -> None:
    """Emit one nodepack reconciliation line to logs and optional setup output."""

    log_info(_LOGGER, message, **context)
    if callback is not None:
        callback(message)


__all__ = [
    "LogCallback",
    "emit_log",
    "emit_sugarcubes_diagnostics",
]
