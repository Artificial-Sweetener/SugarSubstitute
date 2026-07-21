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

"""Tests for startup readiness timer orchestration."""

from __future__ import annotations

import ast
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

import pytest

from substitute.app.bootstrap.startup_probe_tasks import (
    ReadinessProbeResult,
    RuntimeCompatibilityProbeResult,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    ReadinessTimerProtocol,
    StartupReadinessController,
    StartupReadinessControllerState,
    StartupReadinessFailureAdapter,
    StartupReadinessStarter,
    TimerSignalProtocol,
    create_bound_startup_readiness_controller,
    create_startup_readiness_controller,
    create_startup_readiness_failure_adapter,
)
from substitute.app.bootstrap.startup_readiness_policy import (
    STARTUP_READINESS_MAX_ATTEMPTS,
)
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_readiness_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)


class _Signal:
    """Store one no-argument callback for fake timers."""

    def __init__(self) -> None:
        self.callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Connect one timeout callback."""

        self.callback = callback


class _Timer:
    """Record timer operations and expose a manually fired timeout."""

    def __init__(self) -> None:
        self._timeout_signal = _Signal()
        self.timeout: TimerSignalProtocol = self._timeout_signal
        self.interval_ms: int | None = None
        self.started = 0
        self.stopped = 0

    def setInterval(self, interval_ms: int) -> None:
        """Record the configured timer interval."""

        self.interval_ms = interval_ms

    def start(self) -> None:
        """Record timer starts and restarts."""

        self.started += 1

    def stop(self) -> None:
        """Record timer stops."""

        self.stopped += 1

    def fire(self) -> None:
        """Invoke the connected timeout callback."""

        assert self._timeout_signal.callback is not None
        self._timeout_signal.callback()


class _ReadinessProbe:
    """Fake one single-flight readiness probe task."""

    def __init__(self, probe: Callable[[str, int], bool]) -> None:
        self._probe = probe
        self._callback: Callable[[ReadinessProbeResult], None] | None = None
        self.requests: list[tuple[str, int]] = []
        self.cancel_calls = 0
        self._request_id = 0
        self._in_flight_request_id: int | None = None

    def connect_finished(
        self, callback: Callable[[ReadinessProbeResult], None]
    ) -> None:
        """Store the readiness completion callback."""

        self._callback = callback

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Record one probe request and return a request id."""

        if self._in_flight_request_id is not None:
            return None
        self.requests.append((host, port))
        self._request_id += 1
        self._in_flight_request_id = self._request_id
        return self._request_id

    def accept_result(self, result: ReadinessProbeResult) -> bool:
        """Accept a current fake result."""

        if self._in_flight_request_id != result.request_id:
            return False
        self._in_flight_request_id = None
        return True

    def cancel_current(self) -> None:
        """Record current-probe cancellation."""

        self.cancel_calls += 1
        self._in_flight_request_id = None

    def emit_result(self, *, ready: bool) -> None:
        """Emit a result for the current request."""

        assert self._callback is not None
        request_id = self._in_flight_request_id
        assert request_id is not None
        host, port = self.requests[-1]
        self._callback(
            ReadinessProbeResult(
                request_id=request_id,
                host=host,
                port=port,
                ready=ready,
            )
        )


class _RuntimeCompatibilityProbe:
    """Fake one single-flight runtime compatibility task."""

    def __init__(
        self,
        assess: Callable[[], BackendCompatibilityResult | None],
    ) -> None:
        self._assess = assess
        self._callback: Callable[[RuntimeCompatibilityProbeResult], None] | None = None
        self.request_count = 0
        self.cancel_calls = 0
        self._in_flight_request_id: int | None = None

    def connect_finished(
        self,
        callback: Callable[[RuntimeCompatibilityProbeResult], None],
    ) -> None:
        """Store the compatibility completion callback."""

        self._callback = callback

    def request_assessment(self) -> int | None:
        """Record one compatibility assessment request."""

        if self._in_flight_request_id is not None:
            return None
        self.request_count += 1
        self._in_flight_request_id = self.request_count
        return self.request_count

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Accept a current fake result."""

        if self._in_flight_request_id != result.request_id:
            return False
        self._in_flight_request_id = None
        return True

    def cancel_current(self) -> None:
        """Record compatibility cancellation."""

        self.cancel_calls += 1
        self._in_flight_request_id = None

    def emit_result(
        self,
        compatibility: BackendCompatibilityResult | None,
    ) -> None:
        """Emit a compatibility result for the current request."""

        assert self._callback is not None
        request_id = self._in_flight_request_id
        assert request_id is not None
        self._callback(
            RuntimeCompatibilityProbeResult(
                request_id=request_id,
                compatibility=compatibility,
            )
        )


class _Phase:
    """Record backend-ready phase entry and exit."""

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def __enter__(self) -> object:
        """Record phase entry."""

        self._events.append("phase_enter")
        return self

    def __exit__(self, *_exc: object) -> None:
        """Record phase exit."""

        self._events.append("phase_exit")


@dataclass
class _ComfyHttpReadyState:
    """Expose the Comfy HTTP readiness state field."""

    comfy_http_ready: bool = False


class _Startable:
    """Record readiness start calls."""

    def __init__(self) -> None:
        """Initialize empty start records."""

        self.start_calls = 0

    def start(self) -> None:
        """Record one start request."""

        self.start_calls += 1


def test_startup_readiness_controller_starts_timer_and_requests_probe() -> None:
    """Starting readiness creates probe tasks, starts a timer, and probes the target."""

    harness = _Harness()

    harness.controller.start()
    harness.timer.fire()

    assert harness.timer.interval_ms == 250
    assert harness.timer.started == 1
    assert harness.timer.stopped == 1
    assert harness.readiness_probe.requests == [("127.0.0.1", 8188)]
    assert harness.state.readiness_attempts == 1


def test_startup_readiness_controller_pauses_timer_while_probe_runs() -> None:
    """Readiness polling should not keep firing while one probe is in flight."""

    harness = _Harness()

    harness.controller.start()
    harness.timer.fire()

    assert harness.timer.stopped == 1
    assert harness.timer.started == 1

    harness.readiness_probe.emit_result(ready=False)

    assert harness.timer.started == 2
    assert harness.timer.stopped == 1


def test_startup_readiness_starter_requires_bound_controller() -> None:
    """Readiness starter should fail loudly before the controller is bound."""

    starter = StartupReadinessStarter()

    with pytest.raises(RuntimeError, match="controller is not bound"):
        starter.start()


def test_startup_readiness_starter_forwards_to_bound_controller() -> None:
    """Readiness starter should forward start requests after binding."""

    starter = StartupReadinessStarter()
    controller = _Startable()

    starter.bind(controller)
    starter.start()
    starter.start()

    assert controller.start_calls == 2


def test_startup_readiness_failure_adapter_uses_live_transcript() -> None:
    """Readiness failure adapter should own incident builder port assembly."""

    context = object()
    timeout_incident = _incident(ComfyStartupIncidentKind.READINESS_TIMEOUT)
    compatibility_incident = _incident(
        ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED
    )
    failures: list[ComfyStartupIncident] = []
    timeout_calls: list[dict[str, object]] = []
    compatibility_calls: list[dict[str, object]] = []
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    def build_timeout(**kwargs: object) -> ComfyStartupIncident:
        """Record readiness-timeout builder inputs."""

        timeout_calls.append(kwargs)
        return timeout_incident

    def build_compatibility(**kwargs: object) -> ComfyStartupIncident:
        """Record runtime-compatibility builder inputs."""

        compatibility_calls.append(kwargs)
        return compatibility_incident

    adapter = StartupReadinessFailureAdapter(
        installation_context=context,
        transcript=lambda: ("line",),
        handle_managed_startup_failure=failures.append,
        build_readiness_timeout_incident=build_timeout,
        build_runtime_compatibility_incident=build_compatibility,
    )

    built_timeout = adapter.build_readiness_timeout_incident()
    adapter.handle_runtime_compatibility_failure(
        compatibility,
        recovery_attempted=True,
    )

    assert built_timeout is timeout_incident
    assert timeout_calls == [{"installation_context": context, "transcript": ("line",)}]
    assert compatibility_calls == [
        {
            "installation_context": context,
            "compatibility": compatibility,
            "transcript": ("line",),
            "recovery_attempted": True,
        }
    ]
    assert failures == [compatibility_incident]


def test_create_startup_readiness_failure_adapter_returns_adapter() -> None:
    """Readiness failure adapter construction should live in its owner."""

    adapter = create_startup_readiness_failure_adapter(
        installation_context=object(),
        transcript=lambda: (),
        handle_managed_startup_failure=lambda _incident: None,
        build_readiness_timeout_incident=lambda **_kwargs: _incident(
            ComfyStartupIncidentKind.READINESS_TIMEOUT
        ),
        build_runtime_compatibility_incident=lambda **_kwargs: _incident(
            ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED
        ),
    )

    assert isinstance(adapter, StartupReadinessFailureAdapter)


def test_create_startup_readiness_controller_returns_controller() -> None:
    """Readiness controller construction should live in its owner."""

    controller = create_startup_readiness_controller(
        state=StartupReadinessControllerState(),
        comfy_http_ready_state=_ComfyHttpReadyState(),
        target=_target(),
        timer_factory=_Timer,
        readiness_probe_factory=lambda probe: _ReadinessProbe(probe),
        runtime_compatibility_probe_factory=lambda assess: _RuntimeCompatibilityProbe(
            assess
        ),
        register_timer=lambda _timer: None,
        register_readiness_probe=lambda _probe: None,
        register_runtime_compatibility_probe=lambda _probe: None,
        is_startup_cancelled=lambda: False,
        readiness_probe=lambda _host, _port: False,
        assess_runtime_compatibility=lambda: None,
        fatal_incident=lambda: None,
        handle_managed_startup_failure=lambda _incident: None,
        build_readiness_timeout_incident=lambda: _incident(
            ComfyStartupIncidentKind.READINESS_TIMEOUT
        ),
        handle_runtime_compatibility_failure=lambda _compatibility, _recovery_attempted: (
            None
        ),
        recovery_attempted=lambda: False,
        recovery_running=lambda: False,
        start_managed_compatibility_recovery=lambda _compatibility: None,
        set_backend_state=lambda _state: None,
        release_nonessential_startup_warmups=lambda: None,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )

    assert isinstance(controller, StartupReadinessController)


def test_create_bound_startup_readiness_controller_binds_starter() -> None:
    """Bound readiness factory should connect the late-start port."""

    starter = StartupReadinessStarter()
    timer = _Timer()
    controller = create_bound_startup_readiness_controller(
        starter=starter,
        state=StartupReadinessControllerState(),
        comfy_http_ready_state=_ComfyHttpReadyState(),
        target=_target(),
        timer_factory=lambda: timer,
        readiness_probe_factory=lambda probe: _ReadinessProbe(probe),
        runtime_compatibility_probe_factory=lambda assess: _RuntimeCompatibilityProbe(
            assess
        ),
        register_timer=lambda _timer: None,
        register_readiness_probe=lambda _probe: None,
        register_runtime_compatibility_probe=lambda _probe: None,
        is_startup_cancelled=lambda: False,
        readiness_probe=lambda _host, _port: False,
        assess_runtime_compatibility=lambda: None,
        fatal_incident=lambda: None,
        handle_managed_startup_failure=lambda _incident: None,
        build_readiness_timeout_incident=lambda: _incident(
            ComfyStartupIncidentKind.READINESS_TIMEOUT
        ),
        handle_runtime_compatibility_failure=lambda _compatibility, _recovery_attempted: (
            None
        ),
        recovery_attempted=lambda: False,
        recovery_running=lambda: False,
        start_managed_compatibility_recovery=lambda _compatibility: None,
        set_backend_state=lambda _state: None,
        release_nonessential_startup_warmups=lambda: None,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )

    starter.start()

    assert isinstance(controller, StartupReadinessController)
    assert timer.started == 1


def test_remote_startup_readiness_times_out_after_max_attempts() -> None:
    """Remote readiness should retain its bounded connection failure policy."""

    harness = _Harness()
    harness.state.readiness_attempts = STARTUP_READINESS_MAX_ATTEMPTS - 1

    harness.controller.start()
    harness.timer.fire()
    harness.readiness_probe.emit_result(ready=False)

    assert harness.timer.stopped == 1
    assert harness.readiness_probe.cancel_calls == 1
    assert harness.failures == [harness.timeout_incident]


def test_managed_startup_readiness_keeps_polling_after_max_attempts() -> None:
    """The outer probe must not time out a live process owned by the managed monitor."""

    harness = _Harness(target=_target(mode=ComfyTargetMode.MANAGED_LOCAL))
    harness.state.readiness_attempts = STARTUP_READINESS_MAX_ATTEMPTS - 1

    harness.controller.start()
    harness.timer.fire()
    harness.readiness_probe.emit_result(ready=False)

    assert harness.timer.started == 2
    assert harness.readiness_probe.cancel_calls == 0
    assert harness.failures == []


def test_startup_readiness_controller_marks_backend_ready_and_releases_warmups() -> (
    None
):
    """Compatible runtime results should complete the backend-ready transition."""

    harness = _Harness()
    harness.state.nonessential_startup_warmups_pending_backend = True

    harness.controller.start()
    harness.timer.fire()
    harness.readiness_probe.emit_result(ready=True)
    harness.compatibility_probe.emit_result(None)

    assert harness.timer.stopped == 1
    assert harness.compatibility_probe.request_count == 1
    assert harness.events == [
        "phase_enter",
        "timer_mark:comfy_http_ready",
        "backend:ready",
        "phase_exit",
        "release_warmups",
        "try_show",
    ]
    assert harness.comfy_http_ready_state.comfy_http_ready is True
    assert harness.state.nonessential_startup_warmups_pending_backend is False


def test_startup_readiness_controller_routes_managed_recovery() -> None:
    """Managed incompatible runtime results should start targeted recovery once."""

    harness = _Harness(target=_target(mode=ComfyTargetMode.MANAGED_LOCAL))
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    harness.controller.start()
    harness.timer.fire()
    harness.readiness_probe.emit_result(ready=True)
    harness.compatibility_probe.emit_result(compatibility)

    assert harness.recoveries == [compatibility]
    assert harness.failures == []


def test_startup_readiness_controller_retries_transient_compatibility() -> None:
    """Transient compatibility failures should restart the readiness timer."""

    harness = _Harness()
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_UNREACHABLE)

    harness.controller.start()
    harness.timer.fire()
    harness.readiness_probe.emit_result(ready=True)
    harness.compatibility_probe.emit_result(compatibility)

    assert harness.timer.started == 2
    assert harness.recoveries == []
    assert harness.failures == []


def test_startup_readiness_controller_keeps_boundaries() -> None:
    """Keep readiness orchestration out of presentation and infrastructure layers."""

    imports = _imported_modules(CONTROLLER_SOURCE.read_text(encoding="utf-8"))

    assert "subprocess" not in imports
    assert "qfluentwidgets" not in imports
    assert "qframelesswindow" not in imports
    assert all(not module.startswith("substitute.presentation") for module in imports)
    assert all(not module.startswith("substitute.infrastructure") for module in imports)


def test_startup_facade_no_longer_owns_readiness_timer_handlers() -> None:
    """Keep readiness timer orchestration out of the startup facade."""

    startup_source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def check_ready" not in startup_source
    assert "def handle_readiness_probe_result" not in startup_source
    assert "def handle_runtime_compatibility_probe_result" not in startup_source
    assert "STARTUP_READINESS_MAX_ATTEMPTS" not in startup_source
    assert "should_retry_startup_compatibility" not in startup_source
    assert "should_attempt_managed_core_refresh" not in startup_source
    assert "mark_comfy_http_ready=lambda: setattr(" not in startup_source
    assert "def start_readiness_timer_task" not in startup_source
    assert (
        "readiness_starter = managed_ready_state.readiness_starter"
        not in startup_source
    )
    assert "managed_ready_launch.schedule_startup_tasks(" in launch_source
    assert "start_readiness_timer=readiness_starter.start" not in startup_source
    assert "StartupReadinessStarter(" not in startup_source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert (
        "managed_ready_runtime.bind_startup_readiness_controller(" not in startup_source
    )
    assert "create_bound_startup_readiness_controller(" not in startup_source
    assert "create_startup_readiness_controller(" not in startup_source
    assert "readiness_starter.bind(" not in startup_source
    assert "StartupReadinessController(" not in startup_source
    assert (
        "managed_ready_runtime.create_readiness_failure_adapter(" not in startup_source
    )
    assert "create_startup_readiness_failure_adapter(" not in startup_source
    assert "StartupReadinessFailureAdapter(" not in startup_source
    assert "build_readiness_timeout_incident=lambda" not in startup_source
    assert "handle_runtime_compatibility_failure=lambda" not in startup_source


class _Harness:
    """Assemble one readiness controller with observable fake ports."""

    def __init__(
        self,
        *,
        target: ComfyTargetConfiguration | None = None,
    ) -> None:
        self.state = StartupReadinessControllerState()
        self.comfy_http_ready_state = _ComfyHttpReadyState()
        self.target = target or _target()
        self.timer = _Timer()
        self.readiness_probe: _ReadinessProbe
        self.compatibility_probe: _RuntimeCompatibilityProbe
        self.events: list[str] = []
        self.failures: list[ComfyStartupIncident] = []
        self.recoveries: list[BackendCompatibilityResult] = []
        self.timeout_incident = _incident(ComfyStartupIncidentKind.READINESS_TIMEOUT)
        self.controller = StartupReadinessController(
            state=self.state,
            comfy_http_ready_state=self.comfy_http_ready_state,
            target=self.target,
            timer_factory=self._timer,
            readiness_probe_factory=self._build_readiness_probe,
            runtime_compatibility_probe_factory=self._build_compatibility_probe,
            register_timer=lambda _timer: None,
            register_readiness_probe=lambda _probe: None,
            register_runtime_compatibility_probe=lambda _probe: None,
            is_startup_cancelled=lambda: False,
            readiness_probe=lambda _host, _port: True,
            assess_runtime_compatibility=lambda: None,
            fatal_incident=lambda: None,
            handle_managed_startup_failure=self.failures.append,
            build_readiness_timeout_incident=lambda: self.timeout_incident,
            handle_runtime_compatibility_failure=(
                lambda compatibility, _recovery_attempted: self.failures.append(
                    _incident(
                        ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED,
                        values={"status": compatibility.status.value},
                    )
                )
            ),
            recovery_attempted=lambda: False,
            recovery_running=lambda: False,
            start_managed_compatibility_recovery=self.recoveries.append,
            set_backend_state=lambda state: self.events.append(f"backend:{state}"),
            backend_ready_phase=self._backend_ready_phase,
            mark_startup_timer=lambda name: self.events.append(f"timer_mark:{name}"),
            release_nonessential_startup_warmups=lambda: self.events.append(
                "release_warmups"
            ),
            try_show_main_window=lambda: self.events.append("try_show"),
            trace_fields=lambda: {
                "readiness_attempts": self.state.readiness_attempts,
                "nonessential_startup_warmups_pending_backend": (
                    self.state.nonessential_startup_warmups_pending_backend
                ),
            },
        )

    def _build_readiness_probe(
        self,
        probe: Callable[[str, int], bool],
    ) -> _ReadinessProbe:
        """Create and remember one fake readiness probe."""

        self.readiness_probe = _ReadinessProbe(probe)
        return self.readiness_probe

    def _build_compatibility_probe(
        self,
        assess: Callable[[], BackendCompatibilityResult | None],
    ) -> _RuntimeCompatibilityProbe:
        """Create and remember one fake compatibility probe."""

        self.compatibility_probe = _RuntimeCompatibilityProbe(assess)
        return self.compatibility_probe

    def _timer(self) -> ReadinessTimerProtocol:
        """Return the fake timer through the controller protocol."""

        return self.timer

    def _backend_ready_phase(self) -> AbstractContextManager[object]:
        """Return one phase context manager."""

        return _Phase(self.events)


def _target(
    *,
    mode: ComfyTargetMode = ComfyTargetMode.REMOTE,
) -> ComfyTargetConfiguration:
    """Build one target configuration for readiness controller tests."""

    return ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=Path("ComfyUI")
        if mode is ComfyTargetMode.MANAGED_LOCAL
        else None,
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
    )


def _compatibility(status: RuntimeCompatibilityStatus) -> BackendCompatibilityResult:
    """Build one runtime compatibility result."""

    return BackendCompatibilityResult(
        status=status,
        summary=f"{status.value}.",
        installed_backend_version="1.0.0",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="0.10.0",
        required_sugarcubes_version=">=0.10.0,<2.0.0",
        repairable=True,
    )


def _incident(
    kind: ComfyStartupIncidentKind,
    *,
    values: dict[str, object] | None = None,
) -> ComfyStartupIncident:
    """Build one startup incident for controller tests."""

    return ComfyStartupIncident(
        kind=kind,
        severity=ComfyStartupIncidentSeverity.ERROR,
        title=kind.value,
        message=kind.value,
        values=values or {},
    )


def _imported_modules(source: str) -> set[str]:
    """Return top-level imported module names from one Python source string."""

    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
