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

"""Run startup readiness and compatibility probes off the Qt GUI thread."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskSubmitter,
)
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.startup_probe_tasks")


@dataclass(frozen=True)
class ReadinessProbeResult:
    """Carry one Comfy readiness probe result back to the startup thread."""

    request_id: int
    host: str
    port: int
    ready: bool
    error: str = ""


@dataclass(frozen=True)
class RuntimeCompatibilityProbeResult:
    """Carry one runtime compatibility assessment back to the startup thread."""

    request_id: int
    compatibility: BackendCompatibilityResult | None
    error: BaseException | None = None


class StartupReadinessProbe:
    """Run blocking Comfy readiness probes away from the Qt GUI thread."""

    def __init__(
        self,
        *,
        probe: Callable[[str, int], bool],
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Initialize a single-flight readiness probe task owner."""

        self._probe = probe
        self._submitter = submitter
        self._close_submitter = close_submitter or (lambda: None)
        self._callbacks: list[Callable[[ReadinessProbeResult], None]] = []
        self._next_request_id = 0
        self._in_flight_request_id: int | None = None
        self._handle: TaskHandle[ReadinessProbeResult] | None = None
        self._cancellation: CancellationSource | None = None
        self._cancelled = False

    @property
    def in_flight(self) -> bool:
        """Return whether one probe is currently waiting for completion."""

        return self._in_flight_request_id is not None

    def connect_finished(
        self, callback: Callable[[ReadinessProbeResult], None]
    ) -> None:
        """Connect a GUI-thread result callback to the completion bridge."""

        self._callbacks.append(callback)

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Start one readiness probe unless another probe is already active."""

        if self._cancelled or self._in_flight_request_id is not None:
            return None
        self._next_request_id += 1
        request_id = self._next_request_id
        self._in_flight_request_id = request_id
        trace_mark(
            "readiness_probe.task.submit",
            request_id=request_id,
            host=host,
            port=port,
        )
        cancellation = CancellationSource(generation=request_id)
        self._cancellation = cancellation
        request: TaskRequest[ReadinessProbeResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="startup_readiness_probe",
                parts=(("host", host), ("port", port)),
                cancellation_generation=cancellation.generation,
            ),
            context=ExecutionContext(
                operation="startup_readiness_probe",
                reason="managed_startup_readiness",
                lane="startup",
                safe_fields=(
                    ("request_id", request_id),
                    ("host", host),
                    ("port", port),
                ),
            ),
            work=lambda _token: self._run_probe(request_id, host, port),
        )
        handle = self._submitter.submit(request, cancellation=cancellation)
        self._handle = handle
        handle.add_done_callback(
            self._publish_result,
            reason="startup_readiness_probe_completed",
        )
        return request_id

    def accept_result(self, result: ReadinessProbeResult) -> bool:
        """Clear one matching in-flight result and report whether it is current."""

        if self._cancelled:
            trace_mark(
                "readiness_probe.result_ignored",
                request_id=result.request_id,
                reason="cancelled",
            )
            return False
        if self._in_flight_request_id != result.request_id:
            trace_mark(
                "readiness_probe.result_ignored",
                request_id=result.request_id,
                reason="stale",
                current_request_id=self._in_flight_request_id,
            )
            return False
        self._in_flight_request_id = None
        self._future = None
        return True

    def cancel_current(self) -> None:
        """Prevent any active probe result from mutating startup state."""

        if self._in_flight_request_id is not None:
            trace_mark(
                "readiness_probe.current_cancelled",
                request_id=self._in_flight_request_id,
            )
        handle = self._handle
        cancellation = self._cancellation
        self._in_flight_request_id = None
        self._handle = None
        self._cancellation = None
        if cancellation is not None:
            cancellation.cancel(reason="startup_readiness_probe_cancelled")
        if handle is not None:
            handle.cancel(reason="startup_readiness_probe_cancelled")

    def shutdown(self) -> None:
        """Cancel pending work and release the probe executor."""

        self._cancelled = True
        self.cancel_current()
        self._close_submitter()

    def _run_probe(self, request_id: int, host: str, port: int) -> ReadinessProbeResult:
        """Execute one blocking readiness probe through the startup lane."""

        trace_mark(
            "readiness_probe.task.start",
            request_id=request_id,
            host=host,
            port=port,
        )
        error = ""
        ready = False
        try:
            ready = self._probe(host, port)
        except Exception as probe_error:
            error = repr(probe_error)
            log_exception(
                _LOGGER,
                "Comfy HTTP readiness probe failed unexpectedly",
                host=host,
                port=port,
                request_id=request_id,
            )
        finally:
            trace_mark(
                "readiness_probe.task.end",
                request_id=request_id,
                host=host,
                port=port,
                ready=ready,
                error=error,
            )
        return ReadinessProbeResult(
            request_id=request_id,
            host=host,
            port=port,
            ready=ready,
            error=error,
        )

    def _publish_result(self, outcome: TaskOutcome[ReadinessProbeResult]) -> None:
        """Publish a completed readiness result through the Qt bridge."""

        if outcome.status == "cancelled":
            trace_mark("readiness_probe.result_ignored", reason="task_cancelled")
            return
        if outcome.status == "failed":
            result = ReadinessProbeResult(
                request_id=self._in_flight_request_id or -1,
                host="",
                port=0,
                ready=False,
                error=repr(outcome.error),
            )
        elif outcome.result is None:
            result = ReadinessProbeResult(
                request_id=self._in_flight_request_id or -1,
                host="",
                port=0,
                ready=False,
                error="missing readiness probe result",
            )
        else:
            result = outcome.result
        for callback in tuple(self._callbacks):
            callback(result)


class StartupRuntimeCompatibilityProbe:
    """Run managed runtime compatibility assessment away from the Qt GUI thread."""

    def __init__(
        self,
        *,
        assess: Callable[[], BackendCompatibilityResult | None],
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Initialize a single-flight runtime compatibility task owner."""

        self._assess = assess
        self._submitter = submitter
        self._close_submitter = close_submitter or (lambda: None)
        self._callbacks: list[Callable[[RuntimeCompatibilityProbeResult], None]] = []
        self._next_request_id = 0
        self._in_flight_request_id: int | None = None
        self._handle: TaskHandle[RuntimeCompatibilityProbeResult] | None = None
        self._cancellation: CancellationSource | None = None
        self._cancelled = False

    def connect_finished(
        self,
        callback: Callable[[RuntimeCompatibilityProbeResult], None],
    ) -> None:
        """Connect a GUI-thread result callback to the completion bridge."""

        self._callbacks.append(callback)

    def request_assessment(self) -> int | None:
        """Start one compatibility assessment unless another is already active."""

        if self._cancelled or self._in_flight_request_id is not None:
            return None
        self._next_request_id += 1
        request_id = self._next_request_id
        self._in_flight_request_id = request_id
        trace_mark("runtime_compatibility_probe.task.submit", request_id=request_id)
        cancellation = CancellationSource(generation=request_id)
        self._cancellation = cancellation
        request: TaskRequest[RuntimeCompatibilityProbeResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="startup_runtime_compatibility_probe",
                cancellation_generation=cancellation.generation,
            ),
            context=ExecutionContext(
                operation="startup_runtime_compatibility_probe",
                reason="managed_startup_compatibility",
                lane="startup",
                safe_fields=(("request_id", request_id),),
            ),
            work=lambda _token: self._run_assessment(request_id),
        )
        handle = self._submitter.submit(request, cancellation=cancellation)
        self._handle = handle
        handle.add_done_callback(
            self._publish_result,
            reason="startup_runtime_compatibility_probe_completed",
        )
        return request_id

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Clear one matching in-flight result and report whether it is current."""

        if self._cancelled:
            trace_mark(
                "runtime_compatibility_probe.result_ignored",
                request_id=result.request_id,
                reason="cancelled",
            )
            return False
        if self._in_flight_request_id != result.request_id:
            trace_mark(
                "runtime_compatibility_probe.result_ignored",
                request_id=result.request_id,
                reason="stale",
                current_request_id=self._in_flight_request_id,
            )
            return False
        self._in_flight_request_id = None
        self._future = None
        return True

    def cancel_current(self) -> None:
        """Prevent any active compatibility result from mutating startup state."""

        if self._in_flight_request_id is not None:
            trace_mark(
                "runtime_compatibility_probe.current_cancelled",
                request_id=self._in_flight_request_id,
            )
        handle = self._handle
        cancellation = self._cancellation
        self._in_flight_request_id = None
        self._handle = None
        self._cancellation = None
        if cancellation is not None:
            cancellation.cancel(reason="runtime_compatibility_probe_cancelled")
        if handle is not None:
            handle.cancel(reason="runtime_compatibility_probe_cancelled")

    def shutdown(self) -> None:
        """Cancel pending work and release the compatibility executor."""

        self._cancelled = True
        self.cancel_current()
        self._close_submitter()

    def _run_assessment(
        self,
        request_id: int,
    ) -> RuntimeCompatibilityProbeResult:
        """Execute one blocking compatibility assessment through the startup lane."""

        trace_mark("runtime_compatibility_probe.task.start", request_id=request_id)
        compatibility: BackendCompatibilityResult | None = None
        error: BaseException | None = None
        try:
            with trace_span("startup.runtime_compatibility.assess"):
                compatibility = self._assess()
        except BaseException as assessment_error:
            error = assessment_error
        finally:
            trace_mark(
                "runtime_compatibility_probe.task.end",
                request_id=request_id,
                compatibility_status=""
                if compatibility is None
                else compatibility.status.value,
                error="" if error is None else repr(error),
            )
        return RuntimeCompatibilityProbeResult(
            request_id=request_id,
            compatibility=compatibility,
            error=error,
        )

    def _publish_result(
        self,
        outcome: TaskOutcome[RuntimeCompatibilityProbeResult],
    ) -> None:
        """Publish a completed compatibility result through the Qt bridge."""

        if outcome.status == "cancelled":
            trace_mark(
                "runtime_compatibility_probe.result_ignored",
                reason="task_cancelled",
            )
            return
        if outcome.status == "failed":
            result = RuntimeCompatibilityProbeResult(
                request_id=self._in_flight_request_id or -1,
                compatibility=None,
                error=outcome.error,
            )
        elif outcome.result is None:
            result = RuntimeCompatibilityProbeResult(
                request_id=self._in_flight_request_id or -1,
                compatibility=None,
                error=RuntimeError("missing runtime compatibility result"),
            )
        else:
            result = outcome.result
        for callback in tuple(self._callbacks):
            callback(result)


__all__ = [
    "ReadinessProbeResult",
    "RuntimeCompatibilityProbeResult",
    "StartupReadinessProbe",
    "StartupRuntimeCompatibilityProbe",
]
