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

"""Project durable crash evidence into the shared QFluent report contract."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.error_report_presentation import (
    ErrorReportPresentation,
)

import logging
from collections.abc import Sequence

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from sugarsubstitute_shared.crash_reporting.model import (
    CrashAttribution,
    CrashIncident,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.diagnostic_context import (
    CrashDiagnosticContext,
    DiagnosticValue,
)
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.error_report_glyph import ReportSeverity
from sugarsubstitute_shared.presentation.localization import render_application_text


_LOGGER = logging.getLogger(__name__)


def build_crash_report_presentation(
    incident: CrashIncident,
    *,
    text_attachments: Sequence[tuple[str, str]] = (),
) -> ErrorReportPresentation:
    """Return the exact shared report surface for one crash incident."""

    title, message = _incident_message(incident)
    rows: list[tuple[ApplicationText, str]] = [
        (app_text("Stage"), incident.boundary.value),
    ]
    if incident.exception_type:
        rows.append((app_text("Exception"), incident.exception_type))
    return ErrorReportPresentation(
        title=title,
        message=message,
        severity=ReportSeverity.ERROR,
        summary_rows=tuple(rows),
        report_text=render_crash_report(
            incident,
            title=title,
            message=message,
            text_attachments=text_attachments,
        ),
        issue_action=_open_issue_tracker,
    )


def render_crash_report(
    incident: CrashIncident,
    *,
    title: ApplicationText,
    message: ApplicationText,
    text_attachments: Sequence[tuple[str, str]] = (),
) -> str:
    """Render one deterministic localized report without app-payload imports."""

    sections = [
        _section(
            app_text("Error summary"),
            (
                app_text("Severity: %1", "error"),
                app_text("Kind: %1", incident.kind.value),
                app_text("Title: %1", title),
                app_text("Message: %1", message),
                app_text("Stage: %1", incident.boundary.value),
                *(
                    (app_text("Exception type: %1", incident.exception_type),)
                    if incident.exception_type
                    else ()
                ),
            ),
        ),
        _section(
            app_text("Substitute operation context"),
            tuple(
                app_text("%1: %2", key, value)
                for key, value in _incident_context_rows(incident)
                if value is not None and value != ""
            ),
        ),
    ]
    if incident.traceback:
        sections.append(_block(app_text("Traceback"), "\n".join(incident.traceback)))
    diagnostic_logs = tuple(
        (filename, content) for filename, content in text_attachments if content.strip()
    )
    if diagnostic_logs:
        sections.append(
            _block(
                app_text("Diagnostic logs"),
                "\n\n".join(
                    f"[{filename}]\n{content}" for filename, content in diagnostic_logs
                ),
            )
        )
    runtime_rows = tuple(
        app_text("%1: %2", key, value) for key, value in _runtime_rows(incident)
    )
    sections.append(_section(app_text("Runtime and system information"), runtime_rows))
    return "\n\n".join(section for section in sections if section.strip())


def _incident_context_rows(
    incident: CrashIncident,
) -> tuple[tuple[str, object | None], ...]:
    """Return complete non-secret crash operation context."""

    return (
        (
            "Operation",
            "application_startup"
            if incident.kind in {CrashKind.STARTUP, CrashKind.STARTUP_READINESS_TIMEOUT}
            else "application_crash",
        ),
        ("Trace ID", incident.incident_id),
        ("run_id", incident.run_id),
        ("occurred_at_utc", incident.occurred_at_utc),
        ("crash_kind", incident.kind.value),
        ("attribution", incident.attribution.value),
        ("summary", incident.summary),
        ("exception_message", incident.exception_message),
        ("process_id", incident.process_id),
        ("exit_code", incident.exit_code),
        ("thread_name", incident.thread_name),
        ("attachments", ", ".join(incident.attachments)),
        *tuple(sorted(incident.metadata.items())),
        ("issues_url", SUGARSUBSTITUTE_ISSUES_URL),
    )


def _incident_message(
    incident: CrashIncident,
) -> tuple[ApplicationText, ApplicationText]:
    """Return truthful user-facing copy for one incident classification."""

    if incident.kind in {CrashKind.STARTUP, CrashKind.STARTUP_READINESS_TIMEOUT}:
        return (
            app_text("SugarSubstitute could not finish starting"),
            app_text(
                "SugarSubstitute encountered a confirmed startup failure. Copy this "
                "report and share it with the maintainers."
            ),
        )
    if incident.attribution is CrashAttribution.CONFIRMED:
        return (
            app_text("SugarSubstitute crashed"),
            app_text(
                "Something unexpected stopped SugarSubstitute. You can copy this "
                "report and share it with the maintainers."
            ),
        )
    return (
        app_text("SugarSubstitute did not close normally"),
        app_text(
            "The previous SugarSubstitute session ended without completing shutdown. "
            "The report below may help determine why."
        ),
    )


def _runtime_rows(incident: CrashIncident) -> tuple[tuple[str, str], ...]:
    """Return every mandatory runtime field without hiding unavailable facts."""

    context = incident.diagnostic_context or _legacy_diagnostic_context(incident)
    return (
        (
            app_text("SugarSubstitute payload version"),
            context.substitute_version.display_value,
        ),
        (
            app_text("SugarSubstitute recorded release version"),
            context.substitute_release_version.display_value,
        ),
        (
            app_text("Supervising launcher version"),
            context.supervising_launcher_version.display_value,
        ),
        (
            app_text("Installed launcher version"),
            context.installed_launcher_version.display_value,
        ),
        (app_text("ComfyUI version"), context.comfyui_version.display_value),
        (app_text("ComfyUI commit"), context.comfyui_commit.display_value),
        (app_text("Operating system"), context.operating_system.display_value),
        (app_text("System architecture"), context.system_architecture.display_value),
        (app_text("Python"), context.python_version.display_value),
        (app_text("Python architecture"), context.python_architecture.display_value),
        (app_text("Processor"), context.processor.display_value),
        (
            app_text("Logical processor count"),
            context.logical_processor_count.display_value,
        ),
        (app_text("Physical memory"), context.physical_memory.display_value),
        (app_text("GPU"), context.gpu.display_value),
        (app_text("Readiness schema"), context.readiness_schema.display_value),
        (
            app_text("Launch arguments"),
            " ".join(incident.launch_arguments)
            if incident.launch_arguments
            else "unavailable (not recorded)",
        ),
    )


def _legacy_diagnostic_context(incident: CrashIncident) -> CrashDiagnosticContext:
    """Project the few legacy runtime values while naming every absent fact."""

    context = CrashDiagnosticContext.unavailable_legacy()
    return CrashDiagnosticContext(
        substitute_version=_legacy_value(
            incident.application_version, source="legacy_incident.application_version"
        ),
        substitute_release_version=context.substitute_release_version,
        supervising_launcher_version=context.supervising_launcher_version,
        installed_launcher_version=context.installed_launcher_version,
        comfyui_version=context.comfyui_version,
        comfyui_commit=context.comfyui_commit,
        operating_system=_legacy_value(
            incident.platform, source="legacy_incident.platform"
        ),
        system_architecture=context.system_architecture,
        python_version=_legacy_value(
            incident.python_version, source="legacy_incident.python_version"
        ),
        python_architecture=context.python_architecture,
        processor=context.processor,
        logical_processor_count=context.logical_processor_count,
        physical_memory=context.physical_memory,
        gpu=context.gpu,
        readiness_schema=context.readiness_schema,
    )


def _legacy_value(value: str | None, *, source: str) -> DiagnosticValue:
    """Preserve a legacy value or identify why it cannot be shown."""

    if value:
        return DiagnosticValue.available(value, source=source)
    return DiagnosticValue.unavailable(
        "not recorded by this incident schema", source=source
    )


def _section(heading: ApplicationText, rows: tuple[ApplicationText, ...]) -> str:
    """Render one heading and localized line sequence."""

    rendered_heading = render_application_text(heading)
    rendered_rows = tuple(render_application_text(row) for row in rows)
    return "\n".join((rendered_heading, "-" * len(rendered_heading), *rendered_rows))


def _block(heading: ApplicationText, content: str) -> str:
    """Render one heading followed by opaque diagnostic content."""

    rendered_heading = render_application_text(heading)
    return "\n".join((rendered_heading, "-" * len(rendered_heading), content))


def _open_issue_tracker() -> None:
    """Open the trusted public issue tracker from the report footer."""

    if not QDesktopServices.openUrl(QUrl(SUGARSUBSTITUTE_ISSUES_URL)):
        _LOGGER.warning("Failed to open crash report issue tracker.")


__all__ = ["build_crash_report_presentation", "render_crash_report"]
