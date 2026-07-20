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

"""Prepare recoverable Comfy startup diagnostics for user presentation."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from sugarsubstitute_shared.localization import (
    ApplicationText,
    app_text,
    render_source_application_text,
)

from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentSeverity,
)


def recoverable_unignored_incidents(
    incidents: Iterable[ComfyStartupIncident],
    ignored_fingerprints: frozenset[str],
) -> tuple[ComfyStartupIncident, ...]:
    """Return recoverable incidents not hidden by the user's ignore choices."""

    return tuple(
        incident
        for incident in incidents
        if incident.severity is not ComfyStartupIncidentSeverity.FATAL
        and incident.fingerprint not in ignored_fingerprints
    )


def render_startup_diagnostics_report(
    incidents: Iterable[ComfyStartupIncident],
    *,
    transcript: tuple[str, ...] = (),
    text_renderer: Callable[[ApplicationText], str] | None = None,
) -> str:
    """Render startup incidents and transcript as copyable plain text."""

    incident_list = tuple(incidents)
    render = text_renderer or render_source_application_text
    heading = render(app_text("ComfyUI startup diagnostics"))
    lines: list[str] = [
        heading,
        "-" * len(heading),
        render(app_text("Incident count: %1", len(incident_list))),
    ]
    for index, incident in enumerate(incident_list, start=1):
        lines.extend(
            (
                "",
                render(app_text("%1. %2", index, incident.title)),
                render(app_text("Severity: %1", incident.severity.value)),
                render(app_text("Kind: %1", incident.kind.value)),
                render(
                    app_text(
                        "Source: %1",
                        incident.source or app_text("unknown"),
                    )
                ),
                render(app_text("Message: %1", incident.message)),
            )
        )
        if incident.impact:
            lines.append(render(app_text("Impact: %1", incident.impact)))
        if incident.cause:
            lines.append(render(app_text("Likely cause: %1", incident.cause)))
        location = _value_as_text(incident.values.get("location"))
        if location:
            lines.append(render(app_text("Location: %1", location)))
        missing_module = _value_as_text(incident.values.get("missing_module"))
        if missing_module:
            lines.append(render(app_text("Missing module: %1", missing_module)))
        extension_version = _value_as_text(incident.values.get("extension_version"))
        if extension_version:
            lines.append(render(app_text("Extension version: %1", extension_version)))
        repository_url = _value_as_text(incident.values.get("repository_url"))
        if repository_url:
            lines.append(render(app_text("Repository: %1", repository_url)))
        issues_url = _value_as_text(incident.values.get("issues_url"))
        if issues_url:
            lines.append(render(app_text("Issues: %1", issues_url)))
        repository_source = _value_as_text(incident.values.get("repository_source"))
        if repository_source:
            lines.append(render(app_text("Metadata source: %1", repository_source)))
        lines.append(render(app_text("Fingerprint: %1", incident.fingerprint)))
        if incident.remediation:
            lines.append(render(app_text("Suggested action: %1", incident.remediation)))
        if incident.traceback:
            lines.extend(("", render(app_text("Traceback:")), *incident.traceback))
        elif incident.log_excerpt:
            lines.extend(("", render(app_text("Log excerpt:")), *incident.log_excerpt))
    if transcript:
        transcript_heading = render(app_text("Startup transcript"))
        lines.extend(
            ("", transcript_heading, "-" * len(transcript_heading), *transcript)
        )
    return "\n".join(lines).strip()


def _value_as_text(value: object) -> str | None:
    """Return a report-safe string for optional incident value metadata."""

    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, int):
        return str(value)
    return None


__all__ = [
    "recoverable_unignored_incidents",
    "render_startup_diagnostics_report",
]
