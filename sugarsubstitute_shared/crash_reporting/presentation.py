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

import logging

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from sugarsubstitute_shared.crash_reporting.model import (
    CrashAttribution,
    CrashIncident,
)
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.error_report_dialog import (
    ErrorReportPresentation,
)
from sugarsubstitute_shared.presentation.error_report_glyph import ReportSeverity
from sugarsubstitute_shared.presentation.localization import render_application_text


_LOGGER = logging.getLogger(__name__)


def build_crash_report_presentation(
    incident: CrashIncident,
) -> ErrorReportPresentation:
    """Return the exact shared report surface for one crash incident."""

    confirmed = incident.attribution is CrashAttribution.CONFIRMED
    title = (
        app_text("SugarSubstitute crashed")
        if confirmed
        else app_text("SugarSubstitute did not close normally")
    )
    message = (
        app_text(
            "Something unexpected stopped SugarSubstitute. You can copy this report "
            "and share it with the maintainers."
        )
        if confirmed
        else app_text(
            "The previous SugarSubstitute session ended without completing shutdown. "
            "The report below may help determine why."
        )
    )
    rows: list[tuple[ApplicationText, str]] = [
        (app_text("Stage"), incident.boundary.value),
        (app_text("Workflow"), render_application_text(app_text("unknown"))),
    ]
    if incident.exception_type:
        rows.append((app_text("Exception"), incident.exception_type))
    return ErrorReportPresentation(
        title=title,
        message=message,
        severity=ReportSeverity.ERROR,
        summary_rows=tuple(rows),
        report_text=render_crash_report(incident, title=title, message=message),
        issue_action=_open_issue_tracker,
    )


def render_crash_report(
    incident: CrashIncident,
    *,
    title: ApplicationText,
    message: ApplicationText,
) -> str:
    """Render one deterministic localized report without app-payload imports."""

    sections = [
        _section(
            app_text("Error summary"),
            (
                app_text("Severity: %1", "error"),
                app_text("Kind: %1", "substitute_internal"),
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
    sections.append(
        _section(
            app_text("Runtime context"),
            tuple(
                app_text("%1: %2", key, value)
                for key, value in _runtime_rows(incident)
                if value
            ),
        )
    )
    return "\n\n".join(section for section in sections if section.strip())


def _incident_context_rows(
    incident: CrashIncident,
) -> tuple[tuple[str, object | None], ...]:
    """Return complete non-secret crash operation context."""

    return (
        ("Operation", "application_crash"),
        ("Trace ID", incident.incident_id),
        ("run_id", incident.run_id),
        ("crash_kind", incident.kind.value),
        ("attribution", incident.attribution.value),
        ("process_id", incident.process_id),
        ("exit_code", incident.exit_code),
        ("thread_name", incident.thread_name),
        ("attachments", ", ".join(incident.attachments)),
        ("issues_url", SUGARSUBSTITUTE_ISSUES_URL),
    )


def _runtime_rows(incident: CrashIncident) -> tuple[tuple[str, str | None], ...]:
    """Return the runtime fields carried by one incident."""

    return (
        ("SugarSubstitute version", incident.application_version),
        ("Operating system", incident.platform),
        ("Python", incident.python_version),
        ("Launch arguments", " ".join(incident.launch_arguments)),
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
