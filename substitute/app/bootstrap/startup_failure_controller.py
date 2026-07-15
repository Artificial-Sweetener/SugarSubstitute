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

"""Coordinate fail-closed startup cleanup paths."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.shared.logging.logger import (
    get_logger,
    log_error,
    log_exception,
    log_info,
)

_LOGGER = get_logger("app.bootstrap.startup_failure_controller")


class StartupTimerProtocol(Protocol):
    """Stop one startup timer."""

    def stop(self) -> None:
        """Stop the timer."""


class RuntimeCompatibilityProbeProtocol(Protocol):
    """Cancel one in-flight runtime compatibility probe."""

    def cancel_current(self) -> None:
        """Cancel the active probe request."""


class ManagedComfyStopStateProtocol(Protocol):
    """Expose managed Comfy cancellation for fail-closed stop."""

    def request_stop(self, *, reason: str) -> None:
        """Request managed Comfy startup shutdown."""


class SplashCloseProtocol(Protocol):
    """Close the active startup splash window."""

    def close(self) -> None:
        """Close the splash window."""


@dataclass(frozen=True)
class StartupFailClosedCleanupPorts:
    """Ports required to shut down startup after cancellation or failure."""

    readiness_timers: Sequence[StartupTimerProtocol]
    runtime_compatibility_probes: Sequence[RuntimeCompatibilityProbeProtocol]
    stop_managed_comfy: Callable[[], None]
    close_splash: Callable[[], None]
    cleanup: Callable[[], object]
    quit_app: Callable[[], None]
    cancel_gui_queue: Callable[[], None] | None = None


class StartupCleanupPortsFactory(Protocol):
    """Build cleanup ports for one fail-closed startup path."""

    def __call__(
        self,
        *,
        cancel_gui_queue: bool,
        quit_app: Callable[[], None] | None = None,
    ) -> StartupFailClosedCleanupPorts:
        """Return cleanup ports configured for one failure path."""


class StartupFailClosedCleanupPortFactory:
    """Adapt live startup state into fail-closed cleanup ports."""

    def __init__(
        self,
        *,
        readiness_timers: Callable[[], Sequence[StartupTimerProtocol]],
        runtime_compatibility_probes: Callable[
            [], Sequence[RuntimeCompatibilityProbeProtocol]
        ],
        managed_comfy_state: Callable[[], object | None],
        splash: Callable[[], SplashCloseProtocol | None],
        cleanup: Callable[[], object],
        quit_app: Callable[[], None],
        cancel_gui_queue: Callable[[], None],
    ) -> None:
        """Store live startup state accessors for cleanup-port construction."""

        self._readiness_timers = readiness_timers
        self._runtime_compatibility_probes = runtime_compatibility_probes
        self._managed_comfy_state = managed_comfy_state
        self._splash = splash
        self._cleanup = cleanup
        self._quit_app = quit_app
        self._cancel_gui_queue = cancel_gui_queue

    def __call__(
        self,
        *,
        cancel_gui_queue: bool,
        quit_app: Callable[[], None] | None = None,
    ) -> StartupFailClosedCleanupPorts:
        """Build cleanup ports from the current startup state."""

        return create_startup_fail_closed_cleanup_ports(
            readiness_timers=self._readiness_timers(),
            runtime_compatibility_probes=self._runtime_compatibility_probes(),
            managed_comfy_state=self._managed_comfy_state(),
            splash=self._splash(),
            cleanup=self._cleanup,
            quit_app=self._quit_app if quit_app is None else quit_app,
            cancel_gui_queue=self._cancel_gui_queue if cancel_gui_queue else None,
        )


class StartupManagedFailureReportAdapter:
    """Adapt live startup diagnostics into managed failure report construction."""

    def __init__(
        self,
        *,
        installation_context: object,
        transcript: Callable[[], tuple[str, ...]],
        build_report: Callable[..., Any],
    ) -> None:
        """Store collaborators needed to build a managed failure report."""

        self._installation_context = installation_context
        self._transcript = transcript
        self._build_report = build_report

    def build(self, incident: ComfyStartupIncident) -> Any:
        """Build a managed startup failure report with current transcript lines."""

        return self._build_report(
            installation_context=self._installation_context,
            incident=incident,
            transcript=self._transcript(),
        )


def create_startup_managed_failure_report_adapter(
    *,
    installation_context: object,
    transcript: Callable[[], tuple[str, ...]],
    build_report: Callable[..., Any],
) -> StartupManagedFailureReportAdapter:
    """Create the adapter for managed startup failure report construction."""

    return StartupManagedFailureReportAdapter(
        installation_context=installation_context,
        transcript=transcript,
        build_report=build_report,
    )


def create_startup_fail_closed_cleanup_ports(
    *,
    readiness_timers: Sequence[StartupTimerProtocol],
    runtime_compatibility_probes: Sequence[RuntimeCompatibilityProbeProtocol],
    managed_comfy_state: object | None,
    splash: SplashCloseProtocol | None,
    cleanup: Callable[[], object],
    quit_app: Callable[[], None],
    cancel_gui_queue: Callable[[], None] | None = None,
) -> StartupFailClosedCleanupPorts:
    """Adapt current startup state into fail-closed cleanup ports."""

    def stop_managed_comfy() -> None:
        """Request managed Comfy shutdown when a process is active."""

        if managed_comfy_state is not None:
            cast(
                ManagedComfyStopStateProtocol,
                managed_comfy_state,
            ).request_stop(reason="startup_fail_closed_cleanup")

    def close_current_splash() -> None:
        """Close the current splash window when present."""

        if splash is not None:
            splash.close()

    return StartupFailClosedCleanupPorts(
        readiness_timers=tuple(readiness_timers),
        runtime_compatibility_probes=tuple(runtime_compatibility_probes),
        stop_managed_comfy=stop_managed_comfy,
        close_splash=close_current_splash,
        cleanup=cleanup,
        quit_app=quit_app,
        cancel_gui_queue=cancel_gui_queue,
    )


class StartupFailureController:
    """Own startup cancellation and fail-closed failure entry points."""

    def __init__(
        self,
        *,
        is_startup_cancelled: Callable[[], bool],
        mark_startup_cancelled: Callable[[], None],
        cleanup_ports: StartupCleanupPortsFactory,
        trace_fields: Callable[[], dict[str, object]],
        managed_failure_report_factory: Callable[[ComfyStartupIncident], Any],
        present_startup_failure_report: Callable[[Any], None],
        quit_app: Callable[[], None],
    ) -> None:
        """Store fail-closed ports and startup cancellation state callbacks."""

        self._is_startup_cancelled = is_startup_cancelled
        self._mark_startup_cancelled = mark_startup_cancelled
        self._cleanup_ports = cleanup_ports
        self._trace_fields = trace_fields
        self._managed_failure_report_factory = managed_failure_report_factory
        self._present_startup_failure_report = present_startup_failure_report
        self._quit_app = quit_app

    def request_startup_cancel(self) -> None:
        """Cancel ready-shell startup and run the normal managed cleanup path."""

        trace_mark("startup.cancel.requested", **self._trace_fields())
        if self._is_startup_cancelled():
            trace_mark("startup.cancel.skipped", reason="already_cancelled")
            return
        self._mark_startup_cancelled()
        log_info(_LOGGER, "Startup loading canceled from splash window")
        run_fail_closed_startup_cleanup(
            reason="startup_cancel",
            ports=self._cleanup_ports(cancel_gui_queue=True),
            close_failure_message="Failed to close splash after startup cancel",
            cleanup_failure_message="Failed to clean up Comfy after startup cancel",
        )

    def handle_gui_startup_failure(self, task_name: str) -> None:
        """Fail closed when a queued GUI startup task cannot complete."""

        trace_mark(
            "startup.gui_task.failure",
            task_name=task_name,
            **self._trace_fields(),
        )
        if self._is_startup_cancelled():
            return
        self._mark_startup_cancelled()
        log_error(
            _LOGGER,
            "GUI startup failed; terminating managed startup",
            task_name=task_name,
        )
        run_fail_closed_startup_cleanup(
            reason="gui_startup_failure",
            ports=self._cleanup_ports(cancel_gui_queue=False),
            close_failure_message="Failed to close splash after startup failure",
            cleanup_failure_message="Failed to clean up Comfy after startup failure",
        )

    def handle_managed_startup_failure(self, incident: object) -> None:
        """Close splash and show the blocking startup failure report."""

        trace_mark(
            "startup.managed.failure",
            incident_kind=getattr(incident, "kind", ""),
            incident_severity=getattr(incident, "severity", ""),
            **self._trace_fields(),
        )
        if self._is_startup_cancelled():
            return
        self._mark_startup_cancelled()
        run_fail_closed_startup_cleanup(
            reason="managed_startup_failure",
            ports=self._cleanup_ports(
                cancel_gui_queue=True,
                quit_app=lambda: None,
            ),
            close_failure_message=(
                "Failed to close splash after managed startup failure"
            ),
            cleanup_failure_message=(
                "Failed to clean up Comfy after managed startup failure"
            ),
        )
        report = self._managed_failure_report_factory(
            cast(ComfyStartupIncident, incident)
        )
        self._present_startup_failure_report(report)
        self._quit_app()


def run_fail_closed_startup_cleanup(
    *,
    reason: str,
    ports: StartupFailClosedCleanupPorts,
    close_failure_message: str,
    cleanup_failure_message: str,
) -> None:
    """Stop startup work, clean up managed Comfy, and quit the app."""

    trace_mark(
        "startup.failure.cleanup.start",
        reason=reason,
        timer_count=len(ports.readiness_timers),
        runtime_compatibility_probe_count=len(ports.runtime_compatibility_probes),
        gui_queue_cancelled=ports.cancel_gui_queue is not None,
    )
    if ports.cancel_gui_queue is not None:
        ports.cancel_gui_queue()
    for timer in ports.readiness_timers:
        timer.stop()
    for runtime_probe in ports.runtime_compatibility_probes:
        runtime_probe.cancel_current()
    ports.stop_managed_comfy()
    try:
        ports.close_splash()
    except Exception:
        log_exception(_LOGGER, close_failure_message)
    try:
        ports.cleanup()
    except Exception:
        log_exception(_LOGGER, cleanup_failure_message)
    ports.quit_app()
    trace_mark("startup.failure.cleanup.end", reason=reason)


__all__ = [
    "RuntimeCompatibilityProbeProtocol",
    "SplashCloseProtocol",
    "StartupCleanupPortsFactory",
    "StartupFailClosedCleanupPortFactory",
    "StartupFailClosedCleanupPorts",
    "StartupFailureController",
    "StartupManagedFailureReportAdapter",
    "StartupTimerProtocol",
    "create_startup_fail_closed_cleanup_ports",
    "create_startup_managed_failure_report_adapter",
    "run_fail_closed_startup_cleanup",
]
