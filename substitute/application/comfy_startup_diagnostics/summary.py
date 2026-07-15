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

from collections.abc import Iterable

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
) -> str:
    """Render startup incidents and transcript as copyable plain text."""

    incident_list = tuple(incidents)
    lines: list[str] = [
        "ComfyUI startup diagnostics",
        "----------------------------",
        f"Incident count: {len(incident_list)}",
    ]
    for index, incident in enumerate(incident_list, start=1):
        lines.extend(
            (
                "",
                f"{index}. {incident.title}",
                f"Severity: {incident.severity.value}",
                f"Kind: {incident.kind.value}",
                f"Source: {incident.source or 'unknown'}",
                f"Message: {incident.message}",
            )
        )
        if incident.impact:
            lines.append(f"Impact: {incident.impact}")
        if incident.cause:
            lines.append(f"Likely cause: {incident.cause}")
        location = _value_as_text(incident.values.get("location"))
        if location:
            lines.append(f"Location: {location}")
        missing_module = _value_as_text(incident.values.get("missing_module"))
        if missing_module:
            lines.append(f"Missing module: {missing_module}")
        extension_version = _value_as_text(incident.values.get("extension_version"))
        if extension_version:
            lines.append(f"Extension version: {extension_version}")
        repository_url = _value_as_text(incident.values.get("repository_url"))
        if repository_url:
            lines.append(f"Repository: {repository_url}")
        issues_url = _value_as_text(incident.values.get("issues_url"))
        if issues_url:
            lines.append(f"Issues: {issues_url}")
        repository_source = _value_as_text(incident.values.get("repository_source"))
        if repository_source:
            lines.append(f"Metadata source: {repository_source}")
        lines.append(f"Fingerprint: {incident.fingerprint}")
        if incident.remediation:
            lines.append(f"Suggested action: {incident.remediation}")
        if incident.traceback:
            lines.extend(("", "Traceback:", *incident.traceback))
        elif incident.log_excerpt:
            lines.extend(("", "Log excerpt:", *incident.log_excerpt))
    if transcript:
        lines.extend(("", "Startup transcript", "------------------", *transcript))
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
