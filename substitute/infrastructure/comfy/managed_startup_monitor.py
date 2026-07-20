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

"""Monitor managed Comfy startup readiness together with process liveness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time

from sugarsubstitute_shared.localization import app_text

from substitute.application.execution import CancellationToken
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
    build_startup_incident_fingerprint,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_readiness import probe_http_ready

StatusCallback = Callable[[str], None]
ReadinessProbe = Callable[..., bool]

_POLL_DELAY_SECONDS = 0.25
_STATUS_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class ManagedStartupReadinessResult:
    """Describe managed Comfy readiness resolution."""

    ready: bool
    fatal_incident: ComfyStartupIncident | None = None
    timed_out: bool = False
    canceled: bool = False


def wait_for_managed_startup_ready(
    *,
    host: str,
    port: int,
    process: ManagedProcessHandle,
    workspace: Path,
    timeout: float = 300.0,
    on_status: StatusCallback | None = None,
    cancellation: CancellationToken | None = None,
    diagnostics: ComfyStartupDiagnosticsCollector | None = None,
    probe_ready: ReadinessProbe = probe_http_ready,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> ManagedStartupReadinessResult:
    """Poll readiness while treating pre-ready process exit as fatal."""

    started_at = monotonic()
    next_status_at = started_at + _STATUS_INTERVAL_SECONDS
    while monotonic() - started_at < timeout:
        if cancellation is not None and cancellation.is_cancelled:
            return ManagedStartupReadinessResult(ready=False, canceled=True)
        exit_code = process.poll()
        if exit_code is not None:
            return ManagedStartupReadinessResult(
                ready=False,
                fatal_incident=_process_exit_incident(
                    diagnostics=diagnostics,
                    process=process,
                    exit_code=exit_code,
                    host=host,
                    port=port,
                    workspace=workspace,
                ),
            )
        if probe_ready(host=host, port=port):
            return ManagedStartupReadinessResult(ready=True)
        sleep(_POLL_DELAY_SECONDS)
        current_time = monotonic()
        if on_status is not None and current_time >= next_status_at:
            on_status(app_text("Waiting for ComfyUI to become ready..."))
            while next_status_at <= current_time:
                next_status_at += _STATUS_INTERVAL_SECONDS
    return ManagedStartupReadinessResult(
        ready=False,
        fatal_incident=_timeout_incident(
            diagnostics=diagnostics,
            process=process,
            host=host,
            port=port,
            workspace=workspace,
        ),
        timed_out=True,
    )


def _process_exit_incident(
    *,
    diagnostics: ComfyStartupDiagnosticsCollector | None,
    process: ManagedProcessHandle,
    exit_code: int,
    host: str,
    port: int,
    workspace: Path,
) -> ComfyStartupIncident:
    """Return a fatal incident for managed process exit before readiness."""

    if diagnostics is not None:
        return diagnostics.mark_process_exited_before_ready(
            pid=process.pid,
            exit_code=exit_code,
            host=host,
            port=port,
            workspace=str(workspace),
        )
    message = app_text("ComfyUI exited before it became ready.")
    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title=app_text("ComfyUI failed to start"),
        message=message,
        source=str(workspace),
        fingerprint=build_startup_incident_fingerprint(
            kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
            source=str(workspace),
            exception_type=None,
            message=message,
        ),
        remediation=app_text(
            "Review the startup log and fix the last reported ComfyUI error."
        ),
        values={
            "pid": process.pid,
            "exit_code": exit_code,
            "host": host,
            "port": port,
            "workspace": str(workspace),
        },
    )


def _timeout_incident(
    *,
    diagnostics: ComfyStartupDiagnosticsCollector | None,
    process: ManagedProcessHandle,
    host: str,
    port: int,
    workspace: Path,
) -> ComfyStartupIncident:
    """Return a fatal incident for managed startup readiness timeout."""

    transcript = diagnostics.transcript() if diagnostics is not None else ()
    message = app_text("ComfyUI did not become ready before the startup timeout.")
    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.READINESS_TIMEOUT,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title=app_text("ComfyUI failed to start"),
        message=message,
        source=str(workspace),
        fingerprint=build_startup_incident_fingerprint(
            kind=ComfyStartupIncidentKind.READINESS_TIMEOUT,
            source=str(workspace),
            exception_type=None,
            message=message,
        ),
        log_excerpt=transcript,
        remediation=app_text(
            "Review the startup log, then update or disable the last component "
            "that was loading before the timeout."
        ),
        values={
            "pid": process.pid,
            "host": host,
            "port": port,
            "workspace": str(workspace),
        },
    )


__all__ = ["ManagedStartupReadinessResult", "wait_for_managed_startup_ready"]
