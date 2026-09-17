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

"""Describe structured user-visible errors and interpret failure payloads."""

from __future__ import annotations

from sugarsubstitute_shared.localization import (
    ApplicationText,
    app_text,
)

import platform
import sys
import traceback as traceback_module
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from substitute.application.diagnostic_json import diagnostic_json_text
from substitute.domain.common import WorkflowId


class ErrorReportKind(Enum):
    """Classify the user-facing error surface for presentation routing."""

    EXECUTION = "execution"
    PROMPT_VALIDATION = "prompt_validation"
    MISSING_MODELS = "missing_models"
    MISSING_NODES = "missing_nodes"
    CUBE_LIBRARY_DRIFT = "cube_library_drift"
    SUBSTITUTE_INTERNAL = "substitute_internal"
    COMFY_CONNECTION = "comfy_connection"


class DiagnosticSeverity(Enum):
    """Classify how a diagnostic report should be presented to the user."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ErrorNodeContext:
    """Identify the ComfyUI node and node-local payload involved in a failure."""

    node_id: str | None = None
    node_type: str | None = None
    executed: tuple[str, ...] = ()
    current_inputs: object | None = None
    current_outputs: object | None = None


@dataclass(frozen=True)
class PromptValidationMessage:
    """Describe one ComfyUI prompt validation message."""

    message: str
    details: str | None = None
    input_name: str | None = None
    error_type: str | None = None
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptNodeError:
    """Describe all prompt validation errors reported for one node."""

    node_id: str
    class_type: str | None = None
    node_title: str | None = None
    cube_alias: str | None = None
    node_name: str | None = None
    messages: tuple[PromptValidationMessage, ...] = ()
    dependent_outputs: tuple[object, ...] = ()


@dataclass(frozen=True)
class PromptValidationReport:
    """Describe ComfyUI prompt validation failures by node."""

    top_level_error: object | None = None
    node_errors: tuple[PromptNodeError, ...] = ()
    status_code: int | None = None
    raw_response_text: str | None = None


@dataclass(frozen=True)
class RuntimeReportContext:
    """Capture runtime context available for a Comfy-style error report."""

    comfy_version: str | None = None
    substitute_version: str | None = None
    os_name: str | None = field(default_factory=platform.platform)
    python_version: str | None = field(default_factory=lambda: sys.version)
    embedded_python: str | None = None
    pytorch_version: str | None = None
    devices: tuple[str, ...] = ()
    launch_args: tuple[str, ...] = field(default_factory=lambda: tuple(sys.argv))
    server_logs: str | None = None
    workflow_json: str | None = None


@dataclass(frozen=True)
class SubstituteOperationContext:
    """Describe one Substitute operation involved in a user-visible failure."""

    operation: str
    workflow_id: WorkflowId | None = None
    workflow_name: str | None = None
    path: str | None = None
    node_id: str | None = None
    node_name: str | None = None
    cube_id: str | None = None
    cube_alias: str | None = None
    package_name: str | None = None
    trace_id: str | None = None
    values: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ErrorReport:
    """Describe a user-visible failure and its diagnostic report data."""

    kind: ErrorReportKind
    title: ApplicationText
    message: ApplicationText
    stage: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    workflow_id: WorkflowId | None = None
    prompt_id: str | None = None
    exception_type: str | None = None
    technical_detail: str | None = None
    traceback: tuple[str, ...] = ()
    node: ErrorNodeContext | None = None
    prompt_validation: PromptValidationReport | None = None
    operation_context: SubstituteOperationContext | None = None
    runtime: RuntimeReportContext = field(default_factory=RuntimeReportContext)


def build_execution_error_report(
    data: Mapping[str, object],
    *,
    workflow_id: WorkflowId | None = None,
    runtime: RuntimeReportContext | None = None,
    stage: str = "listen",
) -> ErrorReport:
    """Build an execution error report from a Comfy `execution_error` payload."""

    exception_type = _string_or_none(data.get("exception_type"))
    exception_message = _string_or_none(data.get("exception_message"))
    node_type = _string_or_none(data.get("node_type"))
    title = (
        app_text("%1 failed", node_type)
        if node_type
        else exception_type or app_text("Comfy failed")
    )
    message = exception_message or exception_type or "Comfy execution failed"
    traceback_lines = _traceback_lines(data.get("traceback"))
    technical_detail = "\n".join(traceback_lines) if traceback_lines else None
    if technical_detail is None:
        technical_detail = diagnostic_json_text(data)
    return ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        severity=DiagnosticSeverity.ERROR,
        title=title,
        message=message,
        stage=stage,
        workflow_id=workflow_id,
        prompt_id=_string_or_none(data.get("prompt_id")),
        exception_type=exception_type,
        technical_detail=technical_detail,
        traceback=traceback_lines,
        runtime=runtime or RuntimeReportContext(),
        node=ErrorNodeContext(
            node_id=_string_or_none(data.get("node_id")),
            node_type=node_type,
            executed=_string_tuple(data.get("executed")),
            current_inputs=data.get("current_inputs"),
            current_outputs=data.get("current_outputs"),
        ),
    )


def build_prompt_validation_error_report(
    response_payload: object,
    *,
    workflow_id: WorkflowId | None = None,
    runtime: RuntimeReportContext | None = None,
    status_code: int | None = None,
    raw_response_text: str | None = None,
    prompt_nodes: Mapping[str, object] | None = None,
) -> ErrorReport:
    """Build a prompt validation report from a Comfy `/prompt` error response."""

    response_mapping = response_payload if isinstance(response_payload, Mapping) else {}
    top_level_error = response_mapping.get("error")
    validation_report = PromptValidationReport(
        top_level_error=top_level_error,
        node_errors=_prompt_node_errors(
            response_mapping.get("node_errors"),
            prompt_nodes=prompt_nodes,
        ),
        status_code=status_code,
        raw_response_text=raw_response_text,
    )
    message = _prompt_validation_message(top_level_error)
    return ErrorReport(
        kind=ErrorReportKind.PROMPT_VALIDATION,
        severity=DiagnosticSeverity.ERROR,
        title=app_text("Prompt validation failed"),
        message=message,
        stage="queue",
        workflow_id=workflow_id,
        technical_detail=diagnostic_json_text(response_payload),
        prompt_validation=validation_report,
        runtime=runtime or RuntimeReportContext(),
    )


def build_substitute_exception_report(
    *,
    title: ApplicationText,
    message: ApplicationText,
    stage: str,
    error: BaseException,
    context: SubstituteOperationContext,
    runtime: RuntimeReportContext | None = None,
) -> ErrorReport:
    """Build a report for an exception raised by Substitute code."""

    traceback_lines = _exception_traceback_lines(error)
    technical_detail = "\n".join(traceback_lines) if traceback_lines else repr(error)
    return ErrorReport(
        kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
        severity=DiagnosticSeverity.ERROR,
        title=title,
        message=message,
        stage=stage,
        workflow_id=context.workflow_id,
        exception_type=type(error).__name__,
        technical_detail=technical_detail,
        traceback=traceback_lines,
        operation_context=context,
        runtime=runtime or RuntimeReportContext(),
    )


def build_comfy_connection_error_report(
    *,
    title: ApplicationText,
    message: ApplicationText,
    stage: str,
    context: SubstituteOperationContext,
    error: BaseException | None = None,
    runtime: RuntimeReportContext | None = None,
) -> ErrorReport:
    """Build a report for Substitute-side connection or startup failures around Comfy."""

    traceback_lines = _exception_traceback_lines(error) if error is not None else ()
    technical_detail = (
        "\n".join(traceback_lines)
        if traceback_lines
        else repr(error)
        if error is not None
        else str(message)
    )
    return ErrorReport(
        kind=ErrorReportKind.COMFY_CONNECTION,
        severity=DiagnosticSeverity.ERROR,
        title=title,
        message=message,
        stage=stage,
        workflow_id=context.workflow_id,
        exception_type=type(error).__name__ if error is not None else None,
        technical_detail=technical_detail,
        traceback=traceback_lines,
        operation_context=context,
        runtime=runtime or RuntimeReportContext(),
    )


def build_cube_library_drift_report(
    messages: tuple[str, ...],
    *,
    context: SubstituteOperationContext,
    runtime: RuntimeReportContext | None = None,
) -> ErrorReport:
    """Build a report for recipe cubes that do not match the local library state."""

    return ErrorReport(
        kind=ErrorReportKind.CUBE_LIBRARY_DRIFT,
        severity=DiagnosticSeverity.WARNING,
        title=app_text("Cube Library Notice"),
        message=app_text("The recipe loaded with Cube Library warnings."),
        stage="load_recipe",
        workflow_id=context.workflow_id,
        technical_detail="\n".join(messages),
        operation_context=context,
        runtime=runtime or RuntimeReportContext(),
    )


def _prompt_node_errors(
    value: object,
    *,
    prompt_nodes: Mapping[str, object] | None = None,
) -> tuple[PromptNodeError, ...]:
    """Return prompt node errors from Comfy's `node_errors` mapping."""

    if not isinstance(value, Mapping):
        return ()
    errors: list[PromptNodeError] = []
    for node_id, node_error in value.items():
        if not isinstance(node_error, Mapping):
            continue
        node_context = _prompt_node_context(str(node_id), prompt_nodes)
        errors.append(
            PromptNodeError(
                node_id=str(node_id),
                class_type=_string_or_none(node_error.get("class_type")),
                node_title=node_context[0],
                cube_alias=node_context[1],
                node_name=node_context[2],
                messages=_prompt_validation_messages(node_error.get("errors")),
                dependent_outputs=tuple(
                    node_error.get("dependent_outputs", ())
                    if isinstance(node_error.get("dependent_outputs"), list)
                    else ()
                ),
            )
        )
    return tuple(errors)


def _prompt_node_context(
    node_id: str,
    prompt_nodes: Mapping[str, object] | None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve compiled node title and cube identity for validation diagnostics."""

    if prompt_nodes is None:
        return None, None, None
    node = prompt_nodes.get(node_id)
    if not isinstance(node, Mapping):
        return None, None, None
    metadata = node.get("_meta")
    if not isinstance(metadata, Mapping):
        return None, None, None
    substitute = metadata.get("substitute")
    cube_alias = None
    node_name = None
    if isinstance(substitute, Mapping):
        cube_alias = _string_or_none(substitute.get("cube_alias"))
        node_name = _string_or_none(substitute.get("node_name"))
    return _string_or_none(metadata.get("title")), cube_alias, node_name


def _prompt_validation_messages(value: object) -> tuple[PromptValidationMessage, ...]:
    """Return normalized prompt validation messages from Comfy error entries."""

    if not isinstance(value, list):
        return ()
    messages: list[PromptValidationMessage] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        extra_info = entry.get("extra_info")
        input_name = (
            _string_or_none(extra_info.get("input_name"))
            if isinstance(extra_info, Mapping)
            else None
        )
        messages.append(
            PromptValidationMessage(
                message=_string_or_none(entry.get("message")) or "Validation error",
                details=_string_or_none(entry.get("details")),
                input_name=input_name,
                error_type=_string_or_none(entry.get("type")),
                raw={str(key): value for key, value in entry.items()},
            )
        )
    return tuple(messages)


def _prompt_validation_message(top_level_error: object) -> ApplicationText:
    """Return the primary human-readable prompt validation message."""

    if isinstance(top_level_error, str) and top_level_error:
        return top_level_error
    if isinstance(top_level_error, Mapping):
        message = _string_or_none(top_level_error.get("message"))
        details = _string_or_none(top_level_error.get("details"))
        if message and details:
            return f"{message}: {details}"
        return message or details or app_text("The workflow could not be queued.")
    return app_text(
        "The workflow could not be queued because Comfy rejected the prompt."
    )


def _traceback_lines(value: object) -> tuple[str, ...]:
    """Return traceback lines from Comfy's traceback field."""

    if isinstance(value, list):
        return tuple(line for line in value if isinstance(line, str) and line)
    if isinstance(value, str) and value:
        return tuple(value.splitlines())
    return ()


def _string_tuple(value: object) -> tuple[str, ...]:
    """Return a tuple of stringified values for list-like fields."""

    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _string_or_none(value: object) -> str | None:
    """Return a non-empty string value or None."""

    if isinstance(value, str) and value:
        return value
    return None


def _exception_traceback_lines(error: BaseException) -> tuple[str, ...]:
    """Return formatted traceback lines for a caught exception."""

    return tuple(
        line.rstrip("\n")
        for line in traceback_module.format_exception(
            type(error),
            error,
            error.__traceback__,
        )
        if line
    )


__all__ = [
    "DiagnosticSeverity",
    "ErrorNodeContext",
    "ErrorReport",
    "ErrorReportKind",
    "PromptNodeError",
    "PromptValidationMessage",
    "PromptValidationReport",
    "RuntimeReportContext",
    "SubstituteOperationContext",
    "build_comfy_connection_error_report",
    "build_cube_library_drift_report",
    "build_execution_error_report",
    "build_prompt_validation_error_report",
    "build_substitute_exception_report",
]
