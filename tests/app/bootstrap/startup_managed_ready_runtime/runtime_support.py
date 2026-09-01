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

"""Provide deterministic managed-ready runtime composition support."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import cast

import pytest
from sugarsubstitute_shared.launch_splash import SplashActivity

from substitute.app.bootstrap import startup_managed_ready_runtime
from substitute.app.bootstrap.startup_readiness_resources import (
    TimerSignalProtocol,
)
from substitute.app.bootstrap.startup_probe_tasks import (
    RuntimeCompatibilityProbeResult,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedCompatibilityRecoveryBridgeProtocol,
    create_startup_managed_ready_runtime_resources,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationContext,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident

from dataclasses import dataclass

from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedReadyRuntimeResources,
)


class _Context:
    """Expose the installation-context target needed by runtime composition."""

    def __init__(self, target: ComfyTargetConfiguration) -> None:
        """Store the managed Comfy target."""

        self.comfy_target = target


def _target(tmp_path: Path) -> ComfyTargetConfiguration:
    """Build one managed target for runtime compatibility tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=True,
        launch_owned=True,
    )


def _relaunch_phase() -> AbstractContextManager[object]:
    """Return a no-op relaunch timing context."""

    return nullcontext()


class _Checker:
    """Record runtime compatibility target assessments."""

    def __init__(self, result: BackendCompatibilityResult) -> None:
        """Store the compatibility result to return."""

        self._result = result
        self.targets: list[ComfyTargetConfiguration] = []

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Record one target assessment."""

        self.targets.append(target)
        return self._result


class _Clock:
    """Return deterministic timestamps for startup timing."""

    def __init__(self) -> None:
        """Initialize the deterministic clock."""

        self._now = 0.0

    def __call__(self) -> float:
        """Return the next timestamp."""

        self._now += 0.1
        return self._now


class _ControllerTimer:
    """Record timer operations needed by controller compatibility handling."""

    def __init__(self) -> None:
        """Initialize recorded timer operations."""

        self.timeout: TimerSignalProtocol = _UnusedTimerSignal()
        self.started = 0
        self.stopped = 0

    def setInterval(self, _interval_ms: int) -> None:
        """Accept interval configuration."""

    def start(self) -> None:
        """Record a timer start."""

        self.started += 1

    def stop(self) -> None:
        """Record a timer stop."""

        self.stopped += 1


class _ControllerReadinessProbe:
    """Record readiness-probe cancellation from controller failure paths."""

    def __init__(self) -> None:
        """Initialize cancellation records."""

        self.cancel_calls = 0

    def connect_finished(self, _callback: Callable[..., object]) -> None:
        """Accept a readiness completion callback."""

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Return a fake readiness request identifier."""

        return 1 if host and port else None

    def accept_result(self, _result: object) -> bool:
        """Accept fake readiness results."""

        return True

    def cancel_current(self) -> None:
        """Record cancellation of the fake readiness probe."""

        self.cancel_calls += 1


class _UnusedTimerSignal:
    """Accept timer signal connections that are unused by this test."""

    def connect(self, _callback: Callable[[], None]) -> None:
        """Accept one timeout callback."""


class _ControllerRuntimeCompatibilityProbe:
    """Accept a current compatibility result for controller routing tests."""

    def connect_finished(self, _callback: Callable[..., object]) -> None:
        """Accept a runtime compatibility completion callback."""

    def request_assessment(self) -> int | None:
        """Return a fake compatibility request identifier."""

        return 1

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Accept the one fake compatibility result used by this test."""

        return result.request_id == 1

    def cancel_current(self) -> None:
        """Accept cancellation of the fake compatibility request."""


class _Signal:
    """Record a Qt-compatible signal surface."""

    def __init__(self) -> None:
        """Initialize callback and emission records."""

        self.callbacks: list[Callable[..., object]] = []
        self.emissions: list[tuple[object, ...]] = []

    def connect(self, callback: Callable[..., object]) -> object:
        """Return one connection token."""

        self.callbacks.append(callback)
        return object()

    def emit(self, *_args: object) -> None:
        """Record the emission and notify connected callbacks."""

        self.emissions.append(_args)
        for callback in self.callbacks:
            callback(*_args)


class _MetadataBridge:
    """Expose a connectable metadata-updated signal."""

    def __init__(self) -> None:
        """Initialize the fake metadata signal."""

        self.model_updated = _Signal()

    def emit_model_updated(self, _event: object) -> None:
        """Accept metadata update forwarding."""


class _MetadataSurfaceRefreshController:
    """Record metadata refresh callbacks connected during bridge wiring."""

    def __init__(self) -> None:
        """Initialize received metadata events."""

        self.events: list[object] = []

    def handle_model_metadata_updated(self, event: object) -> None:
        """Record one metadata update event."""

        self.events.append(event)


class _MetadataMainWindow:
    """Expose the metadata surface controller expected by bridge wiring."""

    def __init__(self, controller: _MetadataSurfaceRefreshController) -> None:
        """Store the fake metadata controller."""

        self.model_metadata_surface_refresh_controller = controller


class _StartupTaskQueue:
    """Record scheduled ready-shell startup task names."""

    def __init__(self) -> None:
        """Initialize queued task records."""

        self.names: list[str] = []
        self.started = False

    def add(self, name: str, _callback: Callable[[], None]) -> None:
        """Record one queued task name."""

        self.names.append(name)

    def start(self) -> None:
        """Record queue startup."""

        self.started = True


class _RecoveryBridge:
    """Expose the recovery completion signal used by startup."""

    def __init__(self) -> None:
        """Create the fake finished signal."""

        self.finished = _Signal()


class _ReadyState:
    """Expose ready-shell gate fields used by recovery and tracing."""

    def __init__(self) -> None:
        """Initialize ready-shell gate fields."""

        self.minimum_shell_ready = False
        self.comfy_http_ready = False
        self.comfy_activation_started = False
        self.main_window_shown = False
        self.prehydration_attempted = False
        self.prehydration_succeeded = False
        self.hydration_started = False


class _ReadinessState:
    """Expose readiness fields required by recovery controllers and tracing."""

    def __init__(self) -> None:
        """Initialize readiness fields."""

        self.readiness_attempts = 0
        self.nonessential_startup_warmups_pending_backend = False


class _ProjectionState:
    """Expose pre-show projection fields used by tracing."""

    def __init__(self) -> None:
        """Initialize projection state fields."""

        self.pending = False


class _Splash:
    """Record launch-splash lines emitted through recovery adapters."""

    def __init__(self) -> None:
        """Initialize the recorded line list."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one launch-splash line."""

        self.lines.append(line)

    def start_activity(self, _activity: SplashActivity) -> None:
        """Accept activity calls from recovery adapters."""

    def clear_activity(self) -> None:
        """Accept activity cleanup from recovery adapters."""

    def close(self) -> None:
        """Close the fake splash."""


class _OutputStream:
    """Record Comfy output lines emitted through recovery adapters."""

    def __init__(self) -> None:
        """Initialize the recorded line list."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one output line."""

        self.lines.append(line)


@dataclass
class RuntimeHarness:
    """Hold deterministic runtime composition collaborators."""

    resources: StartupManagedReadyRuntimeResources
    context: InstallationContext
    collector: ComfyStartupDiagnosticsCollector
    compatibility: BackendCompatibilityResult
    compatibility_checker: _Checker
    recovery_bridge: _RecoveryBridge
    metadata_bridge: _MetadataBridge
    failure_incident: ComfyStartupIncident
    fatal_incident: ComfyStartupIncident
    presented_reports: list[object]
    report_kwargs: list[dict[str, object]]
    warmed_windows: list[object]


def create_runtime_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> RuntimeHarness:
    """Build the real runtime resource graph with deterministic boundaries."""

    target = _target(tmp_path)
    context = cast(InstallationContext, _Context(target))
    collector = ComfyStartupDiagnosticsCollector()
    ignore_repository = cast(StartupDiagnosticsIgnoreRepository, object())
    compatibility = BackendCompatibilityResult(
        status=RuntimeCompatibilityStatus.BACKEND_TOO_NEW,
        summary="Runtime is newer than supported.",
    )
    compatibility_checker = _Checker(compatibility)
    fake_recovery_bridge = _RecoveryBridge()
    recovery_bridge = cast(
        StartupManagedCompatibilityRecoveryBridgeProtocol,
        fake_recovery_bridge,
    )
    metadata_bridge = _MetadataBridge()
    activation_result = object()
    failure_incident = cast(ComfyStartupIncident, object())
    fatal_incident = cast(ComfyStartupIncident, object())
    presented_reports: list[object] = []
    report_kwargs: list[dict[str, object]] = []
    warmed_windows: list[object] = []

    monkeypatch.setattr(
        startup_managed_ready_runtime,
        "warm_prompt_editor_gui_from_window",
        warmed_windows.append,
    )

    def build_failure_report(**kwargs: object) -> object:
        """Record managed failure report inputs."""

        report_kwargs.append(kwargs)
        return object()

    resources = create_startup_managed_ready_runtime_resources(
        context=context,
        comfy_state=lambda: object(),
        managed_ready_ports=StartupManagedReadyFactoryPorts(
            create_startup_diagnostics_collector=lambda: collector,
            create_startup_diagnostics_ignore_repository=lambda _context: (
                ignore_repository
            ),
            create_runtime_compatibility_checker=lambda: compatibility_checker,
            create_managed_compatibility_recovery_bridge=lambda: recovery_bridge,
            create_model_metadata_update_bridge=lambda _parent: cast(
                ModelMetadataUpdateSignalBridgeProtocol,
                metadata_bridge,
            ),
            request_startup_diagnostics_titlebar_update=lambda **_kwargs: True,
            activate_target=lambda **_kwargs: activation_result,
            managed_startup_fatal_incident=lambda _state: fatal_incident,
            present_startup_failure_report=presented_reports.append,
            build_startup_failure_report=build_failure_report,
            build_startup_readiness_timeout_incident=lambda **_kwargs: failure_incident,
            build_startup_runtime_compatibility_incident=lambda **_kwargs: (
                failure_incident
            ),
        ),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    return RuntimeHarness(
        resources=resources,
        context=context,
        collector=collector,
        compatibility=compatibility,
        compatibility_checker=compatibility_checker,
        recovery_bridge=fake_recovery_bridge,
        metadata_bridge=metadata_bridge,
        failure_incident=failure_incident,
        fatal_incident=fatal_incident,
        presented_reports=presented_reports,
        report_kwargs=report_kwargs,
        warmed_windows=warmed_windows,
    )
