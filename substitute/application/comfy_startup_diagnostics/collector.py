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

"""Collect and classify Comfy startup output into diagnostics incidents."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text, opaque_text

from collections import deque
import re
from typing import Final

from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
    StartupRemediationFacts,
    build_startup_incident_fingerprint,
    build_startup_remediation,
    extract_missing_module_name,
    extract_relevant_traceback_location,
    normalized_startup_incident_source,
)

_DEFAULT_MAX_TRANSCRIPT_RECORDS: Final[int] = 500
_DEFAULT_MAX_EXCERPT_RECORDS: Final[int] = 200
_TRACEBACK_START = "Traceback (most recent call last):"
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_COMFY_LOG_PREFIX_PATTERN = re.compile(
    r"^\[(?P<level>INFO|WARNING|ERROR|DEBUG|CRITICAL)\]\s*(?P<message>.*)$"
)
_CUSTOM_NODE_IMPORT_PATTERN = re.compile(
    r"^Cannot import (?P<source>.+?) module for custom nodes: (?P<reason>.+)$"
)
_CUSTOM_NODE_IMPORT_TIMING_PATTERN = re.compile(
    r"^\s*\d+(?:\.\d+)? seconds \(IMPORT FAILED\): (?P<source>.+)$"
)
_PRESTARTUP_EXCEPTION_PATTERN = re.compile(
    r"^Failed to execute startup-script: (?P<source>.+?) / (?P<reason>.+)$"
)
_PRESTARTUP_TIMING_PATTERN = re.compile(
    r"^\s*\d+(?:\.\d+)? seconds \(PRESTARTUP FAILED\): (?P<source>.+)$"
)
_BUILTIN_IMPORT_HEADER_PATTERN = re.compile(
    r"^WARNING: some (?P<source>comfy_api_nodes/|comfy_extras/) nodes did not import correctly"
)
_BUILTIN_IMPORT_FAILED_PATTERN = re.compile(r"^IMPORT FAILED: (?P<source>.+)$")
_SUGARCUBES_STARTUP_PATTERN = re.compile(
    r"^(?P<level>INFO|WARNING|ERROR): SugarCubes"
    r"(?:\[(?P<code>[A-Za-z0-9_.:-]+)\])?: (?P<message>.+)$"
)


class ComfyStartupDiagnosticsCollector:
    """Collect and classify Comfy startup output until readiness resolves."""

    def __init__(
        self,
        *,
        max_transcript_records: int = _DEFAULT_MAX_TRANSCRIPT_RECORDS,
        max_excerpt_records: int = _DEFAULT_MAX_EXCERPT_RECORDS,
    ) -> None:
        """Initialize bounded startup transcript and incident state."""

        self._transcript: deque[str] = deque(maxlen=max(1, max_transcript_records))
        self._max_excerpt_records = max(1, max_excerpt_records)
        self._incidents_by_fingerprint: dict[str, ComfyStartupIncident] = {}
        self._pending_traceback: list[str] = []
        self._active_builtin_import_source: str | None = None

    def append_output(self, record: str) -> None:
        """Record one Comfy startup output record and classify known incidents."""

        display_line = _normalize_record(record)
        if display_line is None:
            return
        line = _classification_line(display_line)
        self._transcript.append(line)
        if line == _TRACEBACK_START:
            self._pending_traceback = [line]
            return
        if self._pending_traceback:
            self._pending_traceback.append(line)

        if self._classify_custom_node_import(line):
            self._pending_traceback = []
            return
        if self._classify_custom_node_import_timing(line):
            return
        if self._classify_prestartup_exception(line):
            self._pending_traceback = []
            return
        if self._classify_prestartup_timing(line):
            return
        if self._classify_builtin_import_header(line):
            return
        if self._classify_builtin_import_failed(line):
            return
        if self._classify_sugarcubes_startup_diagnostic(line):
            return
        self._classify_generic_warning(line, display_line=display_line)

    def mark_process_exited_before_ready(
        self,
        *,
        pid: int | None,
        exit_code: int | None,
        host: str,
        port: int,
        workspace: str,
    ) -> ComfyStartupIncident:
        """Create and store the fatal incident for a pre-ready process exit."""

        message = app_text("ComfyUI exited before it became ready.")
        values: dict[str, object] = {
            "host": host,
            "port": port,
            "workspace": workspace,
        }
        if pid is not None:
            values["pid"] = pid
        if exit_code is not None:
            values["exit_code"] = exit_code
        return self._add_incident(
            kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
            severity=ComfyStartupIncidentSeverity.FATAL,
            title=app_text("ComfyUI failed to start"),
            message=message,
            source=workspace,
            exception_type=None,
            traceback=tuple(self._pending_traceback),
            log_excerpt=self.transcript(),
            values=values,
        )

    def incidents(self) -> tuple[ComfyStartupIncident, ...]:
        """Return all currently collected incidents."""

        return tuple(self._incidents_by_fingerprint.values())

    def transcript(self) -> tuple[str, ...]:
        """Return bounded startup transcript records."""

        return tuple(self._transcript)

    def _classify_custom_node_import(self, line: str) -> bool:
        """Classify Comfy custom-node import failure summary lines."""

        match = _CUSTOM_NODE_IMPORT_PATTERN.match(line)
        if match is None:
            return False
        source = normalized_startup_incident_source(match.group("source"))
        reason = match.group("reason").strip()
        traceback = tuple(self._pending_traceback)
        exception_type = _exception_type_from_traceback(
            traceback
        ) or _exception_type_from_reason(reason)
        self._add_incident(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            severity=ComfyStartupIncidentSeverity.ERROR,
            title=app_text("Extension failed to load"),
            message=reason,
            source=source,
            exception_type=exception_type,
            traceback=traceback,
            log_excerpt=self._recent_excerpt(),
            values={"source": source or match.group("source")},
        )
        return True

    def _classify_custom_node_import_timing(self, line: str) -> bool:
        """Classify Comfy import timing rows that mark failed custom nodes."""

        match = _CUSTOM_NODE_IMPORT_TIMING_PATTERN.match(line)
        if match is None:
            return False
        source = normalized_startup_incident_source(match.group("source"))
        if self._has_incident_for(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source=source,
        ):
            return True
        self._add_incident(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            severity=ComfyStartupIncidentSeverity.ERROR,
            title=app_text("Extension failed to load"),
            message=app_text("ComfyUI reported this extension as an import failure."),
            source=source,
            exception_type=None,
            traceback=(),
            log_excerpt=(line,),
            values={"source": source or match.group("source")},
        )
        return True

    def _classify_prestartup_exception(self, line: str) -> bool:
        """Classify custom-node prestartup script execution failures."""

        match = _PRESTARTUP_EXCEPTION_PATTERN.match(line)
        if match is None:
            return False
        source = normalized_startup_incident_source(match.group("source"))
        reason = match.group("reason").strip()
        traceback = tuple(self._pending_traceback)
        self._add_incident(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_PRESTARTUP_FAILED,
            severity=ComfyStartupIncidentSeverity.ERROR,
            title=app_text("Extension startup script failed"),
            message=reason,
            source=source,
            exception_type=_exception_type_from_traceback(traceback)
            or _exception_type_from_reason(reason),
            traceback=traceback,
            log_excerpt=self._recent_excerpt(),
            values={"source": source or match.group("source")},
        )
        return True

    def _classify_prestartup_timing(self, line: str) -> bool:
        """Classify prestartup timing rows that mark failed startup scripts."""

        match = _PRESTARTUP_TIMING_PATTERN.match(line)
        if match is None:
            return False
        source = normalized_startup_incident_source(match.group("source"))
        if self._has_incident_for(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_PRESTARTUP_FAILED,
            source=source,
        ):
            return True
        self._add_incident(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_PRESTARTUP_FAILED,
            severity=ComfyStartupIncidentSeverity.ERROR,
            title=app_text("Extension startup script failed"),
            message=app_text(
                "ComfyUI reported this extension prestartup script as failed."
            ),
            source=source,
            exception_type=None,
            traceback=(),
            log_excerpt=(line,),
            values={"source": source or match.group("source")},
        )
        return True

    def _classify_builtin_import_header(self, line: str) -> bool:
        """Classify Comfy builtin/API node import warning headers."""

        match = _BUILTIN_IMPORT_HEADER_PATTERN.match(line)
        if match is None:
            return False
        self._active_builtin_import_source = match.group("source")
        self._add_incident(
            kind=ComfyStartupIncidentKind.BUILTIN_NODE_IMPORT_FAILED,
            severity=ComfyStartupIncidentSeverity.WARNING,
            title=app_text("ComfyUI builtin nodes did not all load"),
            message=line,
            source=self._active_builtin_import_source,
            exception_type=None,
            traceback=(),
            log_excerpt=(line,),
            values={"source": self._active_builtin_import_source},
        )
        return True

    def _classify_builtin_import_failed(self, line: str) -> bool:
        """Classify individual builtin/API node import failure rows."""

        match = _BUILTIN_IMPORT_FAILED_PATTERN.match(line)
        if match is None or self._active_builtin_import_source is None:
            return False
        source = f"{self._active_builtin_import_source}{match.group('source').strip()}"
        self._add_incident(
            kind=ComfyStartupIncidentKind.BUILTIN_NODE_IMPORT_FAILED,
            severity=ComfyStartupIncidentSeverity.WARNING,
            title=app_text("ComfyUI builtin node failed to load"),
            message=line,
            source=source,
            exception_type=None,
            traceback=(),
            log_excerpt=(line,),
            values={"source": source},
        )
        return True

    def _classify_generic_warning(self, line: str, *, display_line: str) -> bool:
        """Classify generic Comfy startup warnings that are not more specific."""

        warning_message = _generic_warning_message(line, display_line=display_line)
        if warning_message is None:
            return False
        self._add_incident(
            kind=ComfyStartupIncidentKind.STARTUP_WARNING,
            severity=ComfyStartupIncidentSeverity.WARNING,
            title=app_text("ComfyUI reported a startup warning"),
            message=warning_message,
            source=None,
            exception_type=None,
            traceback=(),
            log_excerpt=(warning_message,),
            values={},
        )
        return True

    def _classify_sugarcubes_startup_diagnostic(self, line: str) -> bool:
        """Classify SugarCubes maintenance lines emitted before Comfy readiness."""

        match = _SUGARCUBES_STARTUP_PATTERN.match(line)
        if match is None:
            return False
        level = match.group("level")
        if level == "INFO":
            return True
        code = match.group("code") or "sugarcubes_startup"
        title, message = _split_sugarcubes_message(match.group("message"))
        severity = (
            ComfyStartupIncidentSeverity.WARNING
            if level == "WARNING"
            else ComfyStartupIncidentSeverity.ERROR
        )
        kind = (
            ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_WARNING
            if severity is ComfyStartupIncidentSeverity.WARNING
            else ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_FAILED
        )
        self._add_incident(
            kind=kind,
            severity=severity,
            title=title,
            message=message,
            source=f"SugarCubes[{code}]",
            exception_type=None,
            traceback=(),
            log_excerpt=(line,),
            values={"diagnostic_code": code, "source": "SugarCubes"},
        )
        return True

    def _add_incident(
        self,
        *,
        kind: ComfyStartupIncidentKind,
        severity: ComfyStartupIncidentSeverity,
        title: ApplicationText,
        message: ApplicationText,
        source: str | None,
        exception_type: str | None,
        traceback: tuple[str, ...],
        log_excerpt: tuple[str, ...],
        values: dict[str, object],
    ) -> ComfyStartupIncident:
        """Add one deduplicated incident and return the stored instance."""

        normalized_source = normalized_startup_incident_source(source)
        existing = self._incident_for(kind=kind, source=normalized_source)
        if existing is not None:
            return existing
        fingerprint = build_startup_incident_fingerprint(
            kind=kind,
            source=normalized_source,
            exception_type=exception_type,
            message=message,
        )
        incident_values = _incident_values_with_extracted_facts(
            values=values,
            source=normalized_source,
            message=message,
            traceback=traceback,
        )
        location = incident_values.get("location")
        remediation = build_startup_remediation(
            StartupRemediationFacts(
                kind=kind,
                source=normalized_source,
                exception_type=exception_type,
                message=message,
                traceback=traceback,
                location=location if isinstance(location, str) else None,
            )
        )
        incident = ComfyStartupIncident(
            kind=kind,
            severity=severity,
            title=title,
            message=message,
            source=normalized_source,
            exception_type=exception_type,
            fingerprint=fingerprint,
            log_excerpt=log_excerpt[-self._max_excerpt_records :],
            traceback=traceback[-self._max_excerpt_records :],
            impact=remediation.impact,
            cause=remediation.cause,
            remediation=remediation.suggested_action,
            values=incident_values,
        )
        self._incidents_by_fingerprint[fingerprint] = incident
        return incident

    def _has_incident_for(
        self,
        *,
        kind: ComfyStartupIncidentKind,
        source: str | None,
    ) -> bool:
        """Return whether an incident already exists for one kind/source pair."""

        return self._incident_for(kind=kind, source=source) is not None

    def _incident_for(
        self,
        *,
        kind: ComfyStartupIncidentKind,
        source: str | None,
    ) -> ComfyStartupIncident | None:
        """Return an existing incident for one kind/source pair when present."""

        normalized_source = normalized_startup_incident_source(source)
        for incident in self._incidents_by_fingerprint.values():
            if incident.kind is kind and incident.source == normalized_source:
                return incident
        return None

    def _recent_excerpt(self) -> tuple[str, ...]:
        """Return a bounded recent transcript excerpt for a new incident."""

        records = tuple(self._transcript)
        return records[-self._max_excerpt_records :]


def _normalize_record(record: str) -> str | None:
    """Normalize one raw terminal record for startup diagnostics matching."""

    normalized = _ANSI_ESCAPE_PATTERN.sub("", record.rstrip("\r\n"))
    return normalized if normalized.strip() else None


def _classification_line(line: str) -> str:
    """Return the content-bearing portion of a Comfy terminal line."""

    match = _COMFY_LOG_PREFIX_PATTERN.match(line)
    if match is None:
        return line
    return match.group("message")


def _generic_warning_message(line: str, *, display_line: str) -> ApplicationText | None:
    """Return a user-facing warning message for unmatched warning records."""

    if line.startswith("WARNING:"):
        return opaque_text(line)
    match = _COMFY_LOG_PREFIX_PATTERN.match(display_line)
    if match is None or match.group("level") != "WARNING":
        return None
    message = match.group("message").strip()
    return opaque_text(f"WARNING: {message}" if message else "WARNING:")


def _split_sugarcubes_message(
    raw_message: str,
) -> tuple[ApplicationText, ApplicationText]:
    """Split a SugarCubes startup line into title and body text."""

    title, separator, message = raw_message.partition(": ")
    if not separator:
        stripped = raw_message.strip()
        return app_text("SugarCubes startup issue"), opaque_text(stripped)
    return (
        opaque_text(title.strip())
        if title.strip()
        else app_text("SugarCubes startup issue"),
        opaque_text(message.strip()),
    )


def _exception_type_from_reason(reason: str) -> str | None:
    """Return a best-effort exception type from one Comfy error reason."""

    match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\b", reason)
    return match.group(1) if match is not None else None


def _exception_type_from_traceback(traceback: tuple[str, ...]) -> str | None:
    """Return the final Python exception type from traceback lines."""

    for line in reversed(traceback):
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):", line)
        if match is not None:
            return match.group(1)
    return None


def _incident_values_with_extracted_facts(
    *,
    values: dict[str, object],
    source: str | None,
    message: str,
    traceback: tuple[str, ...],
) -> dict[str, object]:
    """Return incident values enriched with parsed traceback and dependency facts."""

    enriched_values = dict(values)
    location = extract_relevant_traceback_location(traceback, source=source)
    if location is not None:
        enriched_values.setdefault("location", location.display)
        enriched_values.setdefault("file", location.file)
        if location.line is not None:
            enriched_values.setdefault("line", location.line)
    missing_module = extract_missing_module_name("\n".join((message, *traceback)))
    if missing_module is not None:
        enriched_values.setdefault("missing_module", missing_module)
    return enriched_values


__all__ = ["ComfyStartupDiagnosticsCollector"]
