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

"""Build structured startup failure reports without presentation dependencies."""

from __future__ import annotations

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    RuntimeReportContext,
    SubstituteOperationContext,
)
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
    build_startup_incident_fingerprint,
)
from substitute.domain.onboarding import InstallationContext


def build_startup_failure_report(
    *,
    installation_context: InstallationContext,
    incident: ComfyStartupIncident,
    transcript: tuple[str, ...],
) -> ErrorReport:
    """Build a structured fatal startup failure report."""

    target = installation_context.comfy_target
    workspace = target.workspace_path or installation_context.managed_comfy_dir
    technical_lines = incident.traceback or incident.log_excerpt or transcript
    return ErrorReport(
        kind=ErrorReportKind.COMFY_CONNECTION,
        title=incident.title,
        message=incident.message,
        stage="managed_startup",
        exception_type=incident.exception_type,
        technical_detail="\n".join(technical_lines) if technical_lines else None,
        traceback=incident.traceback,
        operation_context=SubstituteOperationContext(
            operation="managed_comfy_startup",
            path=str(workspace),
            values={
                "target_mode": target.mode.value,
                "host": target.endpoint.host,
                "port": target.endpoint.port,
                "workspace": str(workspace),
                "readiness_path": "/system_stats",
                **incident.values,
            },
        ),
        runtime=RuntimeReportContext(
            server_logs=_bounded_report_text(transcript),
        ),
    )


def build_startup_readiness_timeout_incident(
    *,
    installation_context: InstallationContext,
    transcript: tuple[str, ...],
) -> ComfyStartupIncident:
    """Build a fatal incident for startup HTTP readiness timeout."""

    target = installation_context.comfy_target
    workspace = target.workspace_path or installation_context.managed_comfy_dir
    message = "ComfyUI did not become ready before the startup timeout."
    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.READINESS_TIMEOUT,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message=message,
        source=str(workspace),
        fingerprint=build_startup_incident_fingerprint(
            kind=ComfyStartupIncidentKind.READINESS_TIMEOUT,
            source=str(workspace),
            exception_type=None,
            message=message,
        ),
        log_excerpt=transcript,
        remediation=(
            "Review the startup log, then update or disable the last component "
            "that was loading before the timeout."
        ),
        values={
            "host": target.endpoint.host,
            "port": target.endpoint.port,
            "workspace": str(workspace),
            "readiness_path": "/system_stats",
        },
    )


def build_startup_runtime_compatibility_incident(
    *,
    installation_context: InstallationContext,
    compatibility: BackendCompatibilityResult,
    transcript: tuple[str, ...],
    recovery_attempted: bool,
    error: Exception | None = None,
) -> ComfyStartupIncident:
    """Build a fatal startup incident for incompatible BackEnd/SugarCubes."""

    target = installation_context.comfy_target
    workspace = target.workspace_path or installation_context.managed_comfy_dir
    message_parts = [compatibility.summary]
    if compatibility.required_backend_version:
        message_parts.append(
            f"Required BackEnd: {compatibility.required_backend_version}."
        )
    if compatibility.required_sugarcubes_version:
        message_parts.append(
            f"Required SugarCubes: {compatibility.required_sugarcubes_version}."
        )
    if error is not None:
        message_parts.append(str(error).strip() or type(error).__name__)
    message = " ".join(part for part in message_parts if part)
    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="Comfy runtime is incompatible",
        message=message,
        source=str(workspace),
        exception_type=type(error).__name__ if error is not None else None,
        fingerprint=build_startup_incident_fingerprint(
            kind=ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED,
            source=str(workspace),
            exception_type=type(error).__name__ if error is not None else None,
            message=message,
        ),
        log_excerpt=transcript,
        remediation=(
            "Automatic managed core update was attempted, but the runtime is still "
            "incompatible. Repair the managed Comfy installation or update Substitute."
            if recovery_attempted
            else "Repair the Comfy target so Substitute BackEnd and SugarCubes satisfy "
            "this Substitute build."
        ),
        values={
            "compatibility_status": compatibility.status.value,
            "installed_backend_version": compatibility.installed_backend_version,
            "required_backend_version": compatibility.required_backend_version,
            "installed_sugarcubes_version": compatibility.installed_sugarcubes_version,
            "required_sugarcubes_version": compatibility.required_sugarcubes_version,
            "recovery_attempted": recovery_attempted,
            "host": target.endpoint.host,
            "port": target.endpoint.port,
            "workspace": str(workspace),
        },
    )


def _bounded_report_text(records: tuple[str, ...], *, limit: int = 65536) -> str | None:
    """Return a bounded report text block from startup transcript records."""

    text = "\n".join(records).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[-limit:]


__all__ = [
    "build_startup_failure_report",
    "build_startup_readiness_timeout_incident",
    "build_startup_runtime_compatibility_incident",
]
