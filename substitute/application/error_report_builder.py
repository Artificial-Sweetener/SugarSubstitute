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

"""Render structured application error reports for display and copy actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor
from sugarsubstitute_shared.localization import (
    ApplicationText,
    app_text,
    render_source_application_text,
)
from substitute.application.diagnostic_json import diagnostic_json_text
from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    ErrorNodeContext,
    PromptValidationReport,
    RuntimeReportContext,
    SubstituteOperationContext,
)

ReportTextRenderer = Callable[[ApplicationText], str]


@dataclass(frozen=True, slots=True)
class ErrorReportBuilder:
    """Build copyable plain-text reports from structured error facts."""

    text_renderer: ReportTextRenderer | None = None

    def render(self, report: ErrorReport) -> str:
        """Return a deterministic plain-text report for one error."""

        if self.text_renderer is None:
            return render_error_report(report)
        return render_error_report(report, self.text_renderer)


def render_error_report(
    report: ErrorReport,
    text_renderer: ReportTextRenderer = render_source_application_text,
) -> str:
    """Render a structured error report as deterministic copyable plain text."""

    sections: list[str] = []
    sections.append(_render_summary(report, text_renderer))
    sections.append(_render_workflow_context(report, text_renderer))
    if report.node is not None:
        sections.append(_render_node_context(report.node, text_renderer))
    if report.prompt_validation is not None:
        sections.append(
            _render_prompt_validation(report.prompt_validation, text_renderer)
        )
    if report.operation_context is not None:
        sections.append(
            _render_substitute_operation_context(
                report.operation_context,
                text_renderer,
            )
        )
    if report.technical_detail and not report.traceback:
        sections.append(_render_technical_detail(report, text_renderer))
    if report.traceback:
        sections.append(
            _render_block(
                text_renderer(app_text("Traceback")),
                "\n".join(report.traceback),
            )
        )
    if report.node is not None and report.node.current_inputs is not None:
        sections.append(
            _render_block(
                text_renderer(app_text("Current inputs")),
                diagnostic_json_text(report.node.current_inputs),
            )
        )
    if report.node is not None and report.node.current_outputs is not None:
        sections.append(
            _render_block(
                text_renderer(app_text("Current outputs")),
                diagnostic_json_text(report.node.current_outputs),
            )
        )
    sections.append(_render_runtime_context(report.runtime, text_renderer))
    if report.runtime.server_logs:
        sections.append(
            _render_block(
                text_renderer(app_text("Comfy startup logs")),
                report.runtime.server_logs,
            )
        )
    if report.runtime.workflow_json:
        sections.append(
            _render_block(
                text_renderer(app_text("Workflow JSON")),
                report.runtime.workflow_json,
            )
        )
    return "\n\n".join(section for section in sections if section.strip())


def _render_summary(
    report: ErrorReport,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render the top-level report summary section."""

    heading = text_renderer(app_text("Error summary"))
    lines = [
        heading,
        "-" * len(heading),
        text_renderer(app_text("Severity: %1", report.severity.value)),
        text_renderer(app_text("Kind: %1", report.kind.value)),
        text_renderer(app_text("Title: %1", report.title)),
        text_renderer(app_text("Message: %1", report.message)),
        text_renderer(app_text("Stage: %1", report.stage)),
    ]
    if report.exception_type:
        lines.append(
            text_renderer(app_text("Exception type: %1", report.exception_type))
        )
    return "\n".join(lines)


def _render_workflow_context(
    report: ErrorReport,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render workflow and prompt identifiers."""

    heading = text_renderer(app_text("Workflow and prompt context"))
    unknown = app_text("unknown")
    lines = [heading, "-" * len(heading)]
    lines.append(
        text_renderer(app_text("Workflow ID: %1", report.workflow_id or unknown))
    )
    lines.append(text_renderer(app_text("Prompt ID: %1", report.prompt_id or unknown)))
    return "\n".join(lines)


def _render_node_context(
    node: ErrorNodeContext,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render node identifiers and execution state."""

    heading = text_renderer(app_text("Node context"))
    unknown = app_text("unknown")
    lines = [
        heading,
        "-" * len(heading),
        text_renderer(app_text("Node ID: %1", node.node_id or unknown)),
        text_renderer(app_text("Node type: %1", node.node_type or unknown)),
        text_renderer(
            app_text(
                "Executed nodes: %1",
                ", ".join(node.executed) if node.executed else app_text("none"),
            )
        ),
    ]
    return "\n".join(lines)


def _render_prompt_validation(
    report: PromptValidationReport,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render prompt validation errors grouped by node."""

    heading = text_renderer(app_text("Prompt validation errors"))
    lines = [heading, "-" * len(heading)]
    if report.status_code is not None:
        lines.append(text_renderer(app_text("HTTP status: %1", report.status_code)))
    if report.top_level_error is not None:
        lines.append(text_renderer(app_text("Top-level error:")))
        lines.append(diagnostic_json_text(report.top_level_error))
    for node_error in report.node_errors:
        lines.append("")
        route = (
            f" [{node_error.cube_alias}.{node_error.node_name}]"
            if node_error.cube_alias and node_error.node_name
            else f" [{node_error.node_title}]"
            if node_error.node_title
            else ""
        )
        node_type = f" - {node_error.class_type}" if node_error.class_type else ""
        lines.append(
            text_renderer(app_text("Node %1%2%3", node_error.node_id, node_type, route))
        )
        for message in node_error.messages:
            prefix = f"  {message.input_name}: " if message.input_name else "  - "
            detail = f": {message.details}" if message.details else ""
            lines.append(f"{prefix}{message.message}{detail}")
    if not report.node_errors:
        lines.append(
            text_renderer(app_text("No node-specific validation errors were reported."))
        )
    if report.raw_response_text:
        lines.append("")
        lines.append(text_renderer(app_text("Raw response text:")))
        lines.append(report.raw_response_text)
    return "\n".join(lines)


def _render_substitute_operation_context(
    context: SubstituteOperationContext,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render Substitute operation context for local application failures."""

    heading = text_renderer(app_text("Substitute operation context"))
    lines = [heading, "-" * len(heading)]
    rows = (
        (app_text("Operation"), context.operation),
        (app_text("Workflow ID"), context.workflow_id),
        (app_text("Workflow name"), context.workflow_name),
        (app_text("Path"), context.path),
        (app_text("Node ID"), context.node_id),
        (app_text("Node name"), context.node_name),
        (app_text("Cube ID"), context.cube_id),
        (app_text("Cube alias"), context.cube_alias),
        (app_text("Package"), context.package_name),
        (app_text("Trace ID"), context.trace_id),
    )
    for label, value in rows:
        if value:
            lines.append(text_renderer(app_text("%1: %2", label, value)))
    for key in sorted(context.values):
        context_value = context.values[key]
        dynamic_label = str(key).replace("_", " ").title()
        lines.append(f"{dynamic_label}: {_context_value_text(context_value)}")
    return "\n".join(lines)


def _render_runtime_context(
    runtime: RuntimeReportContext,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render runtime and system context available at report creation."""

    heading = text_renderer(app_text("Runtime and system information"))
    unknown = app_text("unknown")
    lines = [heading, "-" * len(heading)]
    lines.append(
        text_renderer(app_text("ComfyUI version: %1", runtime.comfy_version or unknown))
    )
    lines.append(
        text_renderer(
            app_text("Substitute version: %1", runtime.substitute_version or unknown)
        )
    )
    lines.append(text_renderer(app_text("OS: %1", runtime.os_name or unknown)))
    lines.append(
        text_renderer(app_text("Python: %1", runtime.python_version or unknown))
    )
    lines.append(
        text_renderer(
            app_text("Embedded Python: %1", runtime.embedded_python or unknown)
        )
    )
    lines.append(
        text_renderer(app_text("PyTorch: %1", runtime.pytorch_version or unknown))
    )
    lines.append(
        text_renderer(
            app_text(
                "Devices: %1",
                ", ".join(runtime.devices) if runtime.devices else unknown,
            )
        )
    )
    lines.append(
        text_renderer(
            app_text(
                "Launch args: %1",
                " ".join(
                    CrashReportRedactor(home=None, install_root=None).arguments(
                        runtime.launch_args
                    )
                ),
            )
        )
    )
    return "\n".join(lines)


def _render_block(title: str, body: str) -> str:
    """Render a titled free-form report block."""

    return f"{title}\n{'-' * len(title)}\n{body}"


def _render_technical_detail(
    report: ErrorReport,
    text_renderer: ReportTextRenderer,
) -> str:
    """Render report-specific technical detail outside the compact summary."""

    title = (
        app_text("Cube Library warnings")
        if report.kind == ErrorReportKind.CUBE_LIBRARY_DRIFT
        else app_text("Technical detail")
    )
    return _render_block(text_renderer(title), report.technical_detail or "")


def _context_value_text(value: object) -> str:
    """Return deterministic display text for one operation context value."""

    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool) or value is None:
        return str(value)
    return diagnostic_json_text(value)


__all__ = ["ErrorReportBuilder", "ReportTextRenderer", "render_error_report"]
