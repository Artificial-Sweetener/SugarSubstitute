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

"""Map Comfy execution_error payloads to listener failure details."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.errors import (
    ErrorReport,
    RuntimeReportContext,
    build_execution_error_report,
)
from substitute.domain.common import WorkflowId


class ExecutionErrorTimingTracker(Protocol):
    """Describe timing operations required for execution_error mapping."""

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record terminal prompt timing."""


@dataclass(frozen=True)
class ExecutionErrorRouteResult:
    """Describe the listener action selected for one execution_error event."""

    handled: bool
    error_message: str | None = None
    error_detail: str | None = None
    error_report: ErrorReport | None = None


def route_execution_error_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    workflow_id: WorkflowId,
    active_prompt_id: str,
    timing_tracker: ExecutionErrorTimingTracker,
    runtime_context_provider: Callable[[], RuntimeReportContext],
) -> ExecutionErrorRouteResult:
    """Build listener failure details for active-prompt execution errors."""

    if message_type != "execution_error":
        return ExecutionErrorRouteResult(handled=False)

    if data.get("prompt_id") != active_prompt_id:
        return ExecutionErrorRouteResult(handled=True)

    timing_tracker.mark_prompt_terminal(_optional_float(data.get("timestamp")))
    error_message, error_detail = format_execution_error(data)
    return ExecutionErrorRouteResult(
        handled=True,
        error_message=error_message,
        error_detail=error_detail,
        error_report=build_execution_error_report(
            data,
            workflow_id=workflow_id,
            runtime=runtime_context_provider(),
        ),
    )


def format_execution_error(data: Mapping[str, object]) -> tuple[str, str | None]:
    """Return compact message and diagnostic detail from Comfy execution errors."""

    exception_type = _string_or_none(data.get("exception_type"))
    exception_message = _string_or_none(data.get("exception_message"))
    if exception_type and exception_message:
        message = f"{exception_type}: {exception_message}"
    elif exception_message:
        message = exception_message
    elif exception_type:
        message = exception_type
    else:
        message = "Comfy execution failed"
    detail = _execution_error_detail(data)
    return message, detail


def _execution_error_detail(data: Mapping[str, object]) -> str | None:
    """Return traceback or payload detail from a Comfy execution error."""

    traceback_value = data.get("traceback")
    if isinstance(traceback_value, list):
        traceback_lines = [
            line for line in traceback_value if isinstance(line, str) and line
        ]
        if traceback_lines:
            return "\n".join(traceback_lines)
    if isinstance(traceback_value, str) and traceback_value:
        return traceback_value
    return json.dumps(data, default=str, sort_keys=True)


def _optional_float(value: object) -> float | None:
    """Return numeric payload fields as floats when present."""

    if isinstance(value, (int, float)):
        return float(value)
    return None


def _string_or_none(value: object) -> str | None:
    """Return a stripped non-empty string or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "ExecutionErrorRouteResult",
    "ExecutionErrorTimingTracker",
    "format_execution_error",
    "route_execution_error_event",
]
