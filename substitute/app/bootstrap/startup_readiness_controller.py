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

"""Coordinate startup HTTP readiness and runtime compatibility probes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Protocol

from substitute.app.bootstrap.managed_compatibility_recovery import (
    should_attempt_owned_nodepack_recovery,
)
from substitute.app.bootstrap.startup_probe_tasks import (
    ReadinessProbeResult,
    RuntimeCompatibilityProbeResult,
)
from substitute.app.bootstrap.startup_readiness_policy import (
    STARTUP_READINESS_MAX_ATTEMPTS,
    should_retry_startup_compatibility,
)
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import ComfyTargetConfiguration
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("app.bootstrap.startup_readiness_controller")
_READINESS_TIMER_INTERVAL_MS = 250


class TimerSignalProtocol(Protocol):
    """Describe the timer signal interface used by readiness orchestration."""

    def connect(self, callback: Callable[[], None]) -> None:
        """Connect one no-argument timeout callback."""


class ReadinessTimerProtocol(Protocol):
    """Describe the timer operations required by readiness orchestration."""

    timeout: TimerSignalProtocol

    def setInterval(self, interval_ms: int) -> None:
        """Set the timer interval in milliseconds."""

    def start(self) -> None:
        """Start or restart the timer."""

    def stop(self) -> None:
        """Stop the timer."""


class StartupReadinessProbeProtocol(Protocol):
    """Describe the readiness probe task surface used by the controller."""

    def connect_finished(
        self, callback: Callable[[ReadinessProbeResult], None]
    ) -> None:
        """Connect one readiness completion callback."""

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Request one asynchronous readiness probe."""

    def accept_result(self, result: ReadinessProbeResult) -> bool:
        """Return whether a result is current and accepted."""

    def cancel_current(self) -> None:
        """Cancel the current probe result."""


class StartupRuntimeCompatibilityProbeProtocol(Protocol):
    """Describe the runtime compatibility probe surface used by the controller."""

    def connect_finished(
        self,
        callback: Callable[[RuntimeCompatibilityProbeResult], None],
    ) -> None:
        """Connect one compatibility completion callback."""

    def request_assessment(self) -> int | None:
        """Request one asynchronous compatibility assessment."""

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Return whether a result is current and accepted."""

    def cancel_current(self) -> None:
        """Cancel the current compatibility result."""


class StartupReadinessStartProtocol(Protocol):
    """Start readiness polling."""

    def start(self) -> None:
        """Start readiness polling."""


class StartupReadinessStarter:
    """Late-bind readiness start/restart callbacks across startup controllers."""

    def __init__(self) -> None:
        """Initialize without a bound readiness controller."""

        self._controller: StartupReadinessStartProtocol | None = None

    def bind(self, controller: StartupReadinessStartProtocol) -> None:
        """Bind the readiness controller that owns timer startup."""

        self._controller = controller

    def start(self) -> None:
        """Start readiness through the bound controller."""

        if self._controller is None:
            raise RuntimeError("Startup readiness controller is not bound.")
        self._controller.start()


@dataclass
class StartupReadinessControllerState:
    """Track mutable readiness orchestration state shared with startup traces."""

    readiness_attempts: int = 0
    nonessential_startup_warmups_pending_backend: bool = False


class ComfyHttpReadyStateProtocol(Protocol):
    """Record whether Comfy HTTP readiness has completed."""

    comfy_http_ready: bool


class StartupReadinessFailureAdapter:
    """Adapt live startup diagnostics into readiness failure incident ports."""

    def __init__(
        self,
        *,
        installation_context: object,
        transcript: Callable[[], tuple[str, ...]],
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        build_readiness_timeout_incident: Callable[..., ComfyStartupIncident],
        build_runtime_compatibility_incident: Callable[..., ComfyStartupIncident],
    ) -> None:
        """Store collaborators used to build and publish readiness failures."""

        self._installation_context = installation_context
        self._transcript = transcript
        self._handle_managed_startup_failure = handle_managed_startup_failure
        self._build_readiness_timeout_incident = build_readiness_timeout_incident
        self._build_runtime_compatibility_incident = (
            build_runtime_compatibility_incident
        )

    def build_readiness_timeout_incident(self) -> ComfyStartupIncident:
        """Build a readiness-timeout incident using current transcript lines."""

        return self._build_readiness_timeout_incident(
            installation_context=self._installation_context,
            transcript=self._transcript(),
        )

    def handle_runtime_compatibility_failure(
        self,
        compatibility: BackendCompatibilityResult,
        recovery_attempted: bool,
    ) -> None:
        """Build and publish one runtime compatibility startup incident."""

        self._handle_managed_startup_failure(
            self._build_runtime_compatibility_incident(
                installation_context=self._installation_context,
                compatibility=compatibility,
                transcript=self._transcript(),
                recovery_attempted=recovery_attempted,
            )
        )


def create_startup_readiness_failure_adapter(
    *,
    installation_context: object,
    transcript: Callable[[], tuple[str, ...]],
    handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    build_readiness_timeout_incident: Callable[..., ComfyStartupIncident],
    build_runtime_compatibility_incident: Callable[..., ComfyStartupIncident],
) -> StartupReadinessFailureAdapter:
    """Create the readiness failure adapter from live startup ports."""

    return StartupReadinessFailureAdapter(
        installation_context=installation_context,
        transcript=transcript,
        handle_managed_startup_failure=handle_managed_startup_failure,
        build_readiness_timeout_incident=build_readiness_timeout_incident,
        build_runtime_compatibility_incident=build_runtime_compatibility_incident,
    )


class StartupReadinessController:
    """Own startup readiness timers, probe sequencing, and backend-ready release."""

    def __init__(
        self,
        *,
        state: StartupReadinessControllerState,
        comfy_http_ready_state: ComfyHttpReadyStateProtocol,
        target: ComfyTargetConfiguration,
        timer_factory: Callable[[], ReadinessTimerProtocol],
        readiness_probe_factory: Callable[
            [Callable[[str, int], bool]], StartupReadinessProbeProtocol
        ],
        runtime_compatibility_probe_factory: Callable[
            [Callable[[], BackendCompatibilityResult | None]],
            StartupRuntimeCompatibilityProbeProtocol,
        ],
        register_timer: Callable[[ReadinessTimerProtocol], None],
        register_readiness_probe: Callable[[StartupReadinessProbeProtocol], None],
        register_runtime_compatibility_probe: Callable[
            [StartupRuntimeCompatibilityProbeProtocol], None
        ],
        is_startup_cancelled: Callable[[], bool],
        readiness_probe: Callable[[str, int], bool],
        assess_runtime_compatibility: Callable[[], BackendCompatibilityResult | None],
        fatal_incident: Callable[[], ComfyStartupIncident | None],
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        build_readiness_timeout_incident: Callable[[], ComfyStartupIncident],
        handle_runtime_compatibility_failure: Callable[
            [BackendCompatibilityResult, bool], None
        ],
        recovery_attempted: Callable[[], bool],
        recovery_running: Callable[[], bool],
        start_managed_compatibility_recovery: Callable[
            [BackendCompatibilityResult], None
        ],
        set_backend_state: Callable[[str], None],
        backend_ready_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
        mark_startup_timer: Callable[[str], None] | None = None,
        release_nonessential_startup_warmups: Callable[[], None],
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        timer_interval_ms: int = _READINESS_TIMER_INTERVAL_MS,
    ) -> None:
        """Store explicit ports needed for readiness orchestration."""

        self._state = state
        self._comfy_http_ready_state = comfy_http_ready_state
        self._target = target
        self._timer_factory = timer_factory
        self._readiness_probe_factory = readiness_probe_factory
        self._runtime_compatibility_probe_factory = runtime_compatibility_probe_factory
        self._register_timer = register_timer
        self._register_readiness_probe = register_readiness_probe
        self._register_runtime_compatibility_probe = (
            register_runtime_compatibility_probe
        )
        self._is_startup_cancelled = is_startup_cancelled
        self._readiness_probe = readiness_probe
        self._assess_runtime_compatibility = assess_runtime_compatibility
        self._fatal_incident = fatal_incident
        self._handle_managed_startup_failure = handle_managed_startup_failure
        self._build_readiness_timeout_incident = build_readiness_timeout_incident
        self._handle_runtime_compatibility_failure = (
            handle_runtime_compatibility_failure
        )
        self._recovery_attempted = recovery_attempted
        self._recovery_running = recovery_running
        self._start_managed_compatibility_recovery = (
            start_managed_compatibility_recovery
        )
        self._set_backend_state = set_backend_state
        self._backend_ready_phase = backend_ready_phase
        self._mark_startup_timer = mark_startup_timer
        self._release_nonessential_startup_warmups = (
            release_nonessential_startup_warmups
        )
        self._try_show_main_window = try_show_main_window
        self._trace_fields = trace_fields
        self._timer_interval_ms = timer_interval_ms

    def start(self) -> None:
        """Start polling Comfy HTTP readiness independently of shell hydration."""

        trace_mark("readiness_timer.start_task", **self._current_trace_fields())
        if self._is_startup_cancelled():
            trace_mark("readiness_timer.start_skipped", reason="startup_cancelled")
            return
        readiness_probe = self._readiness_probe_factory(self._readiness_probe)
        compatibility_probe = self._runtime_compatibility_probe_factory(
            self._assess_runtime_compatibility
        )
        self._register_readiness_probe(readiness_probe)
        self._register_runtime_compatibility_probe(compatibility_probe)
        timer = self._timer_factory()
        self._register_timer(timer)
        readiness_probe.connect_finished(
            lambda result: self.handle_readiness_probe_result(
                timer,
                readiness_probe,
                compatibility_probe,
                result,
            )
        )
        compatibility_probe.connect_finished(
            lambda result: self.handle_runtime_compatibility_probe_result(
                timer,
                readiness_probe,
                compatibility_probe,
                result,
            )
        )
        timer.setInterval(self._timer_interval_ms)
        timer.timeout.connect(lambda: self.check_ready(timer, readiness_probe))
        timer.start()
        trace_mark("readiness_timer.started", interval_ms=self._timer_interval_ms)
        log_info(
            _LOGGER,
            "Startup readiness timer started",
            target_mode=self._target.mode.value,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            interval_ms=self._timer_interval_ms,
        )

    def check_ready(
        self,
        timer: ReadinessTimerProtocol,
        readiness_probe: StartupReadinessProbeProtocol,
    ) -> None:
        """Schedule one Comfy readiness probe from a startup timer tick."""

        if self._is_startup_cancelled():
            timer.stop()
            readiness_probe.cancel_current()
            trace_mark("readiness_timer.cancelled", **self._current_trace_fields())
            return
        fatal_incident = self._fatal_incident()
        if fatal_incident is not None:
            timer.stop()
            readiness_probe.cancel_current()
            trace_mark(
                "readiness_timer.fatal_incident",
                incident_kind=fatal_incident.kind,
                incident_severity=fatal_incident.severity,
                **self._current_trace_fields(),
            )
            self._handle_managed_startup_failure(fatal_incident)
            return
        request_id = readiness_probe.request_probe(
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
        )
        if request_id is None:
            trace_mark("readiness_probe.in_flight_skip", **self._current_trace_fields())
            return
        timer.stop()
        self._state.readiness_attempts += 1
        trace_mark(
            "readiness_timer.tick",
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            request_id=request_id,
            **self._current_trace_fields(),
        )

    def handle_readiness_probe_result(
        self,
        timer: ReadinessTimerProtocol,
        readiness_probe: StartupReadinessProbeProtocol,
        compatibility_probe: StartupRuntimeCompatibilityProbeProtocol,
        result: ReadinessProbeResult,
    ) -> None:
        """Update startup readiness gates from one completed HTTP probe."""

        if not readiness_probe.accept_result(result):
            return
        if self._is_startup_cancelled():
            trace_mark(
                "readiness_probe.result_ignored",
                request_id=result.request_id,
                reason="startup_cancelled",
            )
            return
        if not result.ready:
            trace_mark("readiness_timer.http_not_ready", **self._current_trace_fields())
            if self._state.readiness_attempts >= STARTUP_READINESS_MAX_ATTEMPTS:
                readiness_probe.cancel_current()
                trace_mark("readiness_timer.timeout", **self._current_trace_fields())
                self._handle_managed_startup_failure(
                    self._build_readiness_timeout_incident()
                )
                log_warning(
                    _LOGGER,
                    "Comfy HTTP readiness timed out during startup",
                    target_mode=self._target.mode.value,
                    host=result.host,
                    port=result.port,
                    readiness_attempts=self._state.readiness_attempts,
                )
            else:
                timer.start()
            return
        readiness_probe.cancel_current()
        request_id = compatibility_probe.request_assessment()
        if request_id is None:
            trace_mark(
                "runtime_compatibility_probe.request_skipped",
                **self._current_trace_fields(),
            )
            return
        trace_mark(
            "runtime_compatibility_probe.requested",
            request_id=request_id,
            **self._current_trace_fields(),
        )

    def handle_runtime_compatibility_probe_result(
        self,
        timer: ReadinessTimerProtocol,
        readiness_probe: StartupReadinessProbeProtocol,
        compatibility_probe: StartupRuntimeCompatibilityProbeProtocol,
        result: RuntimeCompatibilityProbeResult,
    ) -> None:
        """Update startup readiness gates from one compatibility result."""

        if not compatibility_probe.accept_result(result):
            return
        if self._is_startup_cancelled():
            trace_mark(
                "runtime_compatibility_probe.result_ignored",
                request_id=result.request_id,
                reason="startup_cancelled",
            )
            return
        if result.error is not None:
            raise result.error
        compatibility = result.compatibility
        if compatibility is not None and not compatibility.compatible:
            self._handle_incompatible_runtime(timer, compatibility)
            return
        self._finish_backend_ready(readiness_probe)

    def _handle_incompatible_runtime(
        self,
        timer: ReadinessTimerProtocol,
        compatibility: BackendCompatibilityResult,
    ) -> None:
        """Route one incompatible runtime result to retry, recovery, or failure."""

        trace_mark(
            "readiness_timer.runtime_incompatible",
            compatibility_status=compatibility.status.value,
            compatibility_summary=compatibility.summary,
            **self._current_trace_fields(),
        )
        if should_retry_startup_compatibility(
            compatibility=compatibility,
            readiness_attempts=self._state.readiness_attempts,
        ):
            trace_mark(
                "readiness_timer.runtime_compatibility_retry",
                compatibility_status=compatibility.status.value,
                **self._current_trace_fields(),
            )
            timer.start()
            return
        recovery_attempted = self._recovery_attempted()
        recovery_running = self._recovery_running()
        if should_attempt_owned_nodepack_recovery(
            target=self._target,
            compatibility=compatibility,
            recovery_attempted=recovery_attempted,
            recovery_running=recovery_running,
        ):
            self._start_managed_compatibility_recovery(compatibility)
            return
        log_warning(
            _LOGGER,
            "Startup runtime compatibility failed",
            target_mode=self._target.mode.value,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            compatibility_status=compatibility.status.value,
            recovery_attempted=recovery_attempted,
            recovery_running=recovery_running,
        )
        self._handle_runtime_compatibility_failure(compatibility, recovery_attempted)

    def _finish_backend_ready(
        self,
        readiness_probe: StartupReadinessProbeProtocol,
    ) -> None:
        """Mark Comfy ready, release backend-gated work, and try shell reveal."""

        readiness_probe.cancel_current()
        with self._backend_ready_phase():
            self._comfy_http_ready_state.comfy_http_ready = True
            if self._mark_startup_timer is not None:
                self._mark_startup_timer("comfy_http_ready")
            trace_mark("readiness_timer.http_ready", **self._current_trace_fields())
            self._set_backend_state("ready")
        log_info(
            _LOGGER,
            "Comfy HTTP readiness completed during startup",
            target_mode=self._target.mode.value,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            readiness_attempts=self._state.readiness_attempts,
        )
        if self._state.nonessential_startup_warmups_pending_backend:
            self._state.nonessential_startup_warmups_pending_backend = False
            trace_mark(
                "post_comfy.nonessential_warmups.backend_ready_release",
                **self._current_trace_fields(),
            )
            self._release_nonessential_startup_warmups()
        self._try_show_main_window()

    def _current_trace_fields(self) -> dict[str, object]:
        """Return the current startup trace fields as a mutable mapping."""

        return dict(self._trace_fields())


def create_startup_readiness_controller(
    *,
    state: StartupReadinessControllerState,
    comfy_http_ready_state: ComfyHttpReadyStateProtocol,
    target: ComfyTargetConfiguration,
    timer_factory: Callable[[], ReadinessTimerProtocol],
    readiness_probe_factory: Callable[
        [Callable[[str, int], bool]], StartupReadinessProbeProtocol
    ],
    runtime_compatibility_probe_factory: Callable[
        [Callable[[], BackendCompatibilityResult | None]],
        StartupRuntimeCompatibilityProbeProtocol,
    ],
    register_timer: Callable[[ReadinessTimerProtocol], None],
    register_readiness_probe: Callable[[StartupReadinessProbeProtocol], None],
    register_runtime_compatibility_probe: Callable[
        [StartupRuntimeCompatibilityProbeProtocol], None
    ],
    is_startup_cancelled: Callable[[], bool],
    readiness_probe: Callable[[str, int], bool],
    assess_runtime_compatibility: Callable[[], BackendCompatibilityResult | None],
    fatal_incident: Callable[[], ComfyStartupIncident | None],
    handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    build_readiness_timeout_incident: Callable[[], ComfyStartupIncident],
    handle_runtime_compatibility_failure: Callable[
        [BackendCompatibilityResult, bool], None
    ],
    recovery_attempted: Callable[[], bool],
    recovery_running: Callable[[], bool],
    start_managed_compatibility_recovery: Callable[[BackendCompatibilityResult], None],
    set_backend_state: Callable[[str], None],
    backend_ready_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
    mark_startup_timer: Callable[[str], None] | None = None,
    release_nonessential_startup_warmups: Callable[[], None],
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> StartupReadinessController:
    """Create the live startup readiness controller."""

    return StartupReadinessController(
        state=state,
        comfy_http_ready_state=comfy_http_ready_state,
        target=target,
        timer_factory=timer_factory,
        readiness_probe_factory=readiness_probe_factory,
        runtime_compatibility_probe_factory=runtime_compatibility_probe_factory,
        register_timer=register_timer,
        register_readiness_probe=register_readiness_probe,
        register_runtime_compatibility_probe=register_runtime_compatibility_probe,
        is_startup_cancelled=is_startup_cancelled,
        readiness_probe=readiness_probe,
        assess_runtime_compatibility=assess_runtime_compatibility,
        fatal_incident=fatal_incident,
        handle_managed_startup_failure=handle_managed_startup_failure,
        build_readiness_timeout_incident=build_readiness_timeout_incident,
        handle_runtime_compatibility_failure=handle_runtime_compatibility_failure,
        recovery_attempted=recovery_attempted,
        recovery_running=recovery_running,
        start_managed_compatibility_recovery=start_managed_compatibility_recovery,
        set_backend_state=set_backend_state,
        backend_ready_phase=backend_ready_phase,
        mark_startup_timer=mark_startup_timer,
        release_nonessential_startup_warmups=release_nonessential_startup_warmups,
        try_show_main_window=try_show_main_window,
        trace_fields=trace_fields,
    )


def create_bound_startup_readiness_controller(
    *,
    starter: StartupReadinessStarter,
    state: StartupReadinessControllerState,
    comfy_http_ready_state: ComfyHttpReadyStateProtocol,
    target: ComfyTargetConfiguration,
    timer_factory: Callable[[], ReadinessTimerProtocol],
    readiness_probe_factory: Callable[
        [Callable[[str, int], bool]], StartupReadinessProbeProtocol
    ],
    runtime_compatibility_probe_factory: Callable[
        [Callable[[], BackendCompatibilityResult | None]],
        StartupRuntimeCompatibilityProbeProtocol,
    ],
    register_timer: Callable[[ReadinessTimerProtocol], None],
    register_readiness_probe: Callable[[StartupReadinessProbeProtocol], None],
    register_runtime_compatibility_probe: Callable[
        [StartupRuntimeCompatibilityProbeProtocol], None
    ],
    is_startup_cancelled: Callable[[], bool],
    readiness_probe: Callable[[str, int], bool],
    assess_runtime_compatibility: Callable[[], BackendCompatibilityResult | None],
    fatal_incident: Callable[[], ComfyStartupIncident | None],
    handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    build_readiness_timeout_incident: Callable[[], ComfyStartupIncident],
    handle_runtime_compatibility_failure: Callable[
        [BackendCompatibilityResult, bool], None
    ],
    recovery_attempted: Callable[[], bool],
    recovery_running: Callable[[], bool],
    start_managed_compatibility_recovery: Callable[[BackendCompatibilityResult], None],
    set_backend_state: Callable[[str], None],
    backend_ready_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
    mark_startup_timer: Callable[[str], None] | None = None,
    release_nonessential_startup_warmups: Callable[[], None],
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> StartupReadinessController:
    """Create the readiness controller and bind the late-start port."""

    controller = create_startup_readiness_controller(
        state=state,
        comfy_http_ready_state=comfy_http_ready_state,
        target=target,
        timer_factory=timer_factory,
        readiness_probe_factory=readiness_probe_factory,
        runtime_compatibility_probe_factory=runtime_compatibility_probe_factory,
        register_timer=register_timer,
        register_readiness_probe=register_readiness_probe,
        register_runtime_compatibility_probe=register_runtime_compatibility_probe,
        is_startup_cancelled=is_startup_cancelled,
        readiness_probe=readiness_probe,
        assess_runtime_compatibility=assess_runtime_compatibility,
        fatal_incident=fatal_incident,
        handle_managed_startup_failure=handle_managed_startup_failure,
        build_readiness_timeout_incident=build_readiness_timeout_incident,
        handle_runtime_compatibility_failure=handle_runtime_compatibility_failure,
        recovery_attempted=recovery_attempted,
        recovery_running=recovery_running,
        start_managed_compatibility_recovery=start_managed_compatibility_recovery,
        set_backend_state=set_backend_state,
        backend_ready_phase=backend_ready_phase,
        mark_startup_timer=mark_startup_timer,
        release_nonessential_startup_warmups=release_nonessential_startup_warmups,
        try_show_main_window=try_show_main_window,
        trace_fields=trace_fields,
    )
    starter.bind(controller)
    return controller


__all__ = [
    "ComfyHttpReadyStateProtocol",
    "ReadinessTimerProtocol",
    "StartupReadinessController",
    "StartupReadinessControllerState",
    "StartupReadinessFailureAdapter",
    "StartupReadinessProbeProtocol",
    "StartupReadinessStarter",
    "StartupReadinessStartProtocol",
    "StartupRuntimeCompatibilityProbeProtocol",
    "create_bound_startup_readiness_controller",
    "create_startup_readiness_controller",
    "create_startup_readiness_failure_adapter",
]
